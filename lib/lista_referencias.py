#!/usr/bin/env python3
"""lib/lista_referencias.py — una lista de referencias pegada (la de un chat de IA, el informe de Deep Research de un
cuaderno de Gemini Notebook o la bibliografía de un artículo): qué ya está en la biblioteca, qué falta y si lo que falta
existe, antes de ingresarlo.

Objetivo (2026-11-22, Edison: «sigue con las propuestas»; P3 del análisis de NotebookLM): que una fuente que descubrió
  una IA entre por el Método Documental y no por la cita. Se pega la lista tal como vino; sale, por cada referencia, si
  ya está en Calibre o en Zotero, si falta, y (al aplicar) si su DOI o su ISBN existen: una IA puede inventar una
  referencia con un DOI que no existe, o uno real de otra obra.
Método: SOLO LEE. Del texto saca los DOI (también dentro de una URL de doi.org), los ISBN con su dígito de control, las
  demás URL y las líneas que parecen una referencia (un año y cinco palabras o más, o un ítem numerado o con viñeta).
  Cada una se coteja con Calibre y Zotero en solo lectura con `ingresar.existentes` y `ingresar.cotejar` (DOI, ISBN o
  título); una línea sin identificador, por los títulos de Calibre de tres palabras o más que contiene. El informe va al
  estado (`$XDG_STATE_HOME/biblioteca/lista-referencias/ultimo.json`). Con `--aplicar` consulta además cada DOI e ISBN
  que falta en Crossref, doi.org y Open Library (`verificar_ids.consultar`, con su caché) y deja en
  `entrada/<lote>/candidatos.json` la lista de lo que falta con lo que dijo la agencia: el comienzo de la lista que
  `lib/ingresar.py plan` recibe, después de completar los autores y cotejar cada obra (ingresar no inventa metadatos).
Fundamento: normativa 9.6 (primero en la biblioteca, después la cita); FLUJO_DE_CONOCIMIENTO C12.5 (referencia que no
  existe; ICMJE, 2025; Jergas y Baethge, 2015); METODO_DOCUMENTAL.md pasos 00–01.
Límite: no escribe en ninguna base, no descarga ni crea ítems; `--aplicar` solo consulta las agencias y escribe en la
  zona de entrada. Sin red, nada se marca como inexistente. Lo que la lista no identifica (una URL suelta, una línea sin
  título reconocible) queda «por identificar» para la persona.

    python3 lib/lista_referencias.py <lista.txt> [--json]                   # simula: qué está y qué falta (no consulta)
    python3 lib/lista_referencias.py <lista.txt> --aplicar [--lote <nombre>] # además, Crossref y Open Library, y candidatos.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "entrada"             # la zona de entrada (docs/arquitectura.md §2): tránsito hacia Calibre, fuera de git
MIN_PALABRAS = 5
MAX_CANDIDATOS = 500

RE_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>»\]\)]+", re.I)
RE_ISBN = re.compile(r"\bISBN(?:-1[03])?\s*:?\s*([0-9Xx][0-9Xx\- ]{8,16}[0-9Xx])\b")
RE_URL = re.compile(r"https?://[^\s<>\"»\]\)]+", re.I)
RE_ANIO = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
RE_ITEM = re.compile(r"^\s*(?:\[\d{1,3}\]|\d{1,3}[.)]|[-*•])\s+")


def _cargar(nombre: str, ruta: Path):
    if nombre in sys.modules:
        return sys.modules[nombre]
    s = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(s)
    sys.modules[nombre] = m
    s.loader.exec_module(m)
    return m


def _ing():
    return _cargar("biblioteca_ingresar", RAIZ / "lib" / "ingresar.py")


def _vi():
    return _cargar("biblioteca_verificar_ids", RAIZ / "lib" / "verificar_ids.py")


# ------------------------------------------------------------------------------------------------------- extraer
def _limpio(t: str) -> str:
    return " ".join(RE_ITEM.sub("", t or "").replace("**", "").split()).strip()


def entradas(texto: str) -> list[str]:
    """Las entradas de la lista: un ítem numerado o con viñeta (o un párrafo) con sus líneas de continuación juntas, porque
    una referencia larga se parte en dos o tres líneas al pegarla. Los títulos («## Fuentes») van solos."""
    salida: list[str] = []
    actual: list[str] = []

    def cerrar():
        if actual:
            salida.append(" ".join(x.strip() for x in actual))
            actual.clear()

    for linea in (texto or "").replace("\r\n", "\n").split("\n"):
        if not linea.strip():
            cerrar()
        elif linea.lstrip().startswith("#") or RE_ITEM.match(linea):
            cerrar()
            actual.append(linea)
            if linea.lstrip().startswith("#"):
                cerrar()
        else:
            actual.append(linea)
    cerrar()
    return salida


def extraer(texto: str) -> list[dict]:
    """Las referencias de una lista pegada: [{tipo (doi, isbn, url, referencia), valor, linea}], sin repetir. Una línea con
    DOI o ISBN da ese identificador (y no además su URL ni la línea como referencia)."""
    vi = _vi()
    salida, vistos = [], set()

    def sumar(tipo, valor, linea):
        if (tipo, valor) in vistos or len(salida) >= MAX_CANDIDATOS:
            return
        vistos.add((tipo, valor))
        salida.append({"tipo": tipo, "valor": valor, "linea": _limpio(linea)[:600]})

    for linea in entradas(texto):
        con_id = False
        for m in RE_DOI.finditer(linea):
            doi = vi.normalizar_doi(m.group(0).rstrip(".,;:"))
            if doi:
                sumar("doi", doi, linea)
                con_id = True
        for m in RE_ISBN.finditer(linea):
            isbn, ok = vi.normalizar_isbn(m.group(1))
            if isbn and ok:
                sumar("isbn", isbn, linea)
                con_id = True
        if con_id:
            continue
        urls = [u.rstrip(".,;:") for u in RE_URL.findall(linea)]
        resto = _limpio(RE_URL.sub(" ", linea))
        palabras = re.findall(r"\w+", resto)
        if len(palabras) >= MIN_PALABRAS and (RE_ANIO.search(resto) or RE_ITEM.match(linea)):
            sumar("referencia", resto, linea)
        elif urls:
            for u in urls:
                sumar("url", u, linea)
    return salida


# ------------------------------------------------------------------------------------------------------ cotejar
def _titulos_calibre(ex: dict) -> list[tuple[int, str]]:
    ing = _ing()
    salida = []
    for b, d in ex["cal"].items():
        t = ing._normal(ing._titulo_corto(d.get("titulo") or ""))
        if len(t.split()) >= 3:
            salida.append((b, t))
    return salida


def cotejar_lista(candidatos: list[dict], ex: dict) -> list[dict]:
    """Cada candidato con {estado (en_biblioteca, falta, por_identificar), calibre, zotero}: lo que ya es esa obra."""
    ing = _ing()
    titulos = None
    salida = []
    for c in candidatos:
        r = dict(c, calibre=[], zotero=[])
        if c["tipo"] in ("doi", "isbn"):
            ya = ing.cotejar({c["tipo"]: c["valor"]}, ex)
            r.update(calibre=ya["calibre"], zotero=[z["clave"] for z in ya["zotero"]])
            r["estado"] = "en_biblioteca" if (ya["calibre"] or ya["zotero"]) else "falta"
        elif c["tipo"] == "referencia":
            if titulos is None:
                titulos = _titulos_calibre(ex)
            linea = " " + ing._normal(c["valor"]) + " "
            r["calibre"] = sorted({b for b, t in titulos if f" {t} " in linea})[:10]
            r["estado"] = "en_biblioteca" if r["calibre"] else "por_identificar"
        else:
            r["estado"] = "por_identificar"
        salida.append(r)
    return salida


def cuentas(lista: list[dict]) -> dict:
    c = {"total": len(lista), "en_biblioteca": 0, "falta": 0, "por_identificar": 0, "no_existe": 0, "discrepa": 0}
    for r in lista:
        c[r["estado"]] = c.get(r["estado"], 0) + 1
        v = (r.get("agencia") or {}).get("estado")
        if v in ("no_existe", "discrepa"):
            c[v] += 1
    return c


# -------------------------------------------------------------------------------------------------- verificar
def verificar(lista: list[dict], cache: dict, pedir=None, pausa: float | None = None) -> dict:
    """Consulta en las agencias cada DOI o ISBN que falta (los de la caché vigente, no) y anota en cada uno lo que dijeron
    (`agencia`: estado, fuente, título, año). Devuelve las cuentas de la consulta."""
    vi = _vi()
    faltan = [r for r in lista if r["estado"] == "falta"]
    por_consultar = [(r["tipo"], r["valor"]) for r in faltan if not vi.vigente(cache.get(vi._id(r["tipo"], r["valor"])))]
    kw = {} if pedir is None else {"pedir": pedir}
    if pausa is not None:
        kw["pausa"] = pausa
    hechas = vi.consultar(por_consultar, cache, **kw) if por_consultar else {}
    for r in faltan:
        e = cache.get(vi._id(r["tipo"], r["valor"])) or {}
        estado = e.get("estado") or "sin_consultar"
        sin_ids = RE_URL.sub(" ", RE_DOI.sub(" ", r.get("linea") or ""))
        if (estado == "existe" and e.get("titulo") and len(re.findall(r"[^\W\d_]{3,}", sin_ids)) >= MIN_PALABRAS
                and vi.mismo_titulo(e["titulo"], sin_ids) is False):
            estado = "discrepa"          # existe, pero el título de la agencia no está en la referencia que dio la IA
        r["agencia"] = {"estado": estado, "fuente": e.get("fuente", ""), "titulo": e.get("titulo", ""), "anio": e.get("anio")}
    return hechas


def candidatos(lista: list[dict]) -> list[dict]:
    """Lo que falta, en la forma de la lista de `lib/ingresar.py` (doi, isbn, titulo, anio), con lo que falta por completar
    antes de ingresarlo. Lo que la agencia dio por inexistente no entra."""
    salida = []
    for r in lista:
        if r["estado"] != "falta" or (r.get("agencia") or {}).get("estado") == "no_existe":
            continue
        a = r.get("agencia") or {}
        obra = {r["tipo"]: r["valor"], "titulo": a.get("titulo", ""), "anio": a.get("anio") or "", "autores": [],
                "referencia": r["linea"], "verificacion": a.get("estado", "sin_consultar"),
                "por_completar": ["autores", "tipo"] + ([] if a.get("titulo") else ["titulo"])}
        salida.append(obra)
    return salida


# ---------------------------------------------------------------------------------------------------- informe
def carpeta_estado() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "biblioteca" / "lista-referencias"


def texto_informe(lista: list[dict], aplicado: bool) -> str:
    c = cuentas(lista)
    lineas = [f"{c['total']} referencias: {c['en_biblioteca']} ya en la biblioteca · {c['falta']} faltan · "
              f"{c['por_identificar']} por identificar" + (f" · {c['no_existe']} no existen · {c['discrepa']} de otra obra" if aplicado else "")]
    nombres = {"en_biblioteca": "ya está", "falta": "falta", "por_identificar": "por identificar"}
    for r in lista:
        donde = ""
        if r["calibre"]:
            donde = " → Calibre " + ", ".join(map(str, r["calibre"]))
        if r["zotero"]:
            donde += " → Zotero " + ", ".join(r["zotero"])
        agencia = (r.get("agencia") or {}).get("estado", "")
        extra = {"no_existe": " · ✗ NO EXISTE (¿inventada?)", "discrepa": " · ⚠ el identificador es de otra obra",
                 "existe": " · existe", "no_hallado": " · Open Library no lo tiene"}.get(agencia, "")
        lineas.append(f"- [{nombres.get(r['estado'], r['estado'])}] {r['tipo']} {r['valor'][:120]}{donde}{extra}")
    if not aplicado and c["falta"]:
        lineas.append("\nSimulado: con --aplicar se consultan Crossref y Open Library y se deja candidatos.json en la entrada.")
    return "\n".join(lineas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lista", type=Path, help="el texto pegado (.txt o .md)")
    ap.add_argument("--lote", default="", help="la carpeta de entrada/ donde dejar candidatos.json (por omisión, referencias-<fecha>)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--aplicar", action="store_true", help="consulta las agencias y escribe candidatos.json en la entrada")
    a = ap.parse_args(argv)
    if not a.lista.is_file():
        print(f"✗ no existe: {a.lista}", file=sys.stderr)
        return 2
    lista = extraer(a.lista.read_text(encoding="utf-8", errors="replace"))
    if not lista:
        print("No se reconoció ninguna referencia (DOI, ISBN, URL o una línea con año y título).")
        return 3
    env = _ing()._env()
    lista = cotejar_lista(lista, _ing().existentes(env))
    hoy = date.today().isoformat()
    destino = None
    if a.aplicar:
        vi = _vi()
        cache = vi.leer_cache()
        verificar(lista, cache)
        vi.guardar_cache(cache)
        lote = re.sub(r"[^\w.-]+", "-", a.lote or f"referencias-{hoy}").strip("-") or f"referencias-{hoy}"
        carpeta = ENTRADA / lote
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / "candidatos.json"
        destino.write_text(json.dumps({"fecha": hoy, "origen": str(a.lista.name), "obras": candidatos(lista)}, ensure_ascii=False,
                                      indent=2) + "\n", encoding="utf-8")
    est = carpeta_estado()
    est.mkdir(parents=True, exist_ok=True)
    informe = {"fecha": hoy, "aplicado": a.aplicar, "cuentas": cuentas(lista), "referencias": lista,
               "candidatos": str(destino) if destino else ""}
    (est / "ultimo.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(informe, ensure_ascii=False))
    else:
        print(texto_informe(lista, a.aplicar))
        if destino:
            print(f"\nCandidatos para ingresar: entrada/{destino.parent.name}/{destino.name} (complete los autores y coteje cada obra antes de "
                  "`lib/ingresar.py plan`).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
