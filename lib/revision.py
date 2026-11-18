#!/usr/bin/env python3
"""lib/revision.py — la revisión de literatura de un escrito: el tipo de revisión, la bitácora de búsqueda, el cribado en
dos fases y las cuentas del diagrama PRISMA 2020 (FLUJO_DE_CONOCIMIENTO C2.1, C2.2 y C2.3; decisiones §9.10).

Objetivo: que una revisión se pueda repetir y reportar. Queda escrito *cómo* se halló cada obra (la base, la cadena exacta,
  los filtros, la fecha y cuántos resultados dio), qué se descartó en cada fase y por qué, y de ahí sale el diagrama PRISMA
  2020 que el escrito incluye con `\\includegraphics{fuentes/prisma}`.
Método: una sola fuente de verdad por escrito, `fuentes/revision.yml` (junto a `fuentes.yml` y `fuentes/fichas/`), que
  escribe este módulo con la huella del archivo (si otro la cambió, no se pisa) y que se puede editar a mano con la misma
  forma. Los registros entran a mano o desde la exportación de la base (RIS o BibTeX), y se marcan duplicados por DOI o por
  título y año. El cribado tiene dos fases: título y resumen (fase 1) y texto completo (fase 2, con motivo de exclusión
  obligatorio). Las cuentas PRISMA salen de la bitácora y de los registros, y se dice si cuadran. El diagrama lo dibuja
  `lib/prisma.py` (TikZ, compilado con LuaLaTeX).
Fundamento: Rethlefsen et al. (2021), PRISMA-S: lo que se reporta de cada búsqueda; Page et al. (2021, Calibre 11073 y
  11074), PRISMA 2020: el diagrama y sus cajas; Haddaway et al. (2022): el diagrama se genera de los datos; Grant y Booth
  (2009) y Snyder (2019): cada tipo de revisión con su búsqueda, su evaluación, su síntesis y su análisis.
Límite: escribe solo en `fuentes/revision.yml` (y `lib/prisma.py`, en `fuentes/prisma.*`) del escrito, y solo con
  `aplicar`; nunca toca Calibre ni Zotero. No busca en las bases: registra lo que la persona buscó.

    python3 lib/revision.py ver <escrito> [--json]
    python3 lib/revision.py tipos [--json]
    python3 lib/revision.py declarar <escrito> <tipo> [--pregunta …] [--incluir …]… [--excluir …]… [--aplicar]
    python3 lib/revision.py buscar <escrito> --base … --cadena … [--filtros …] [--fecha AAAA-MM-DD] --resultados N
                                   [--clase base|registro|web|organizacion|citas] [--aplicar]
    python3 lib/revision.py importar <escrito> <búsqueda> <archivo .ris o .bib> [--aplicar]
    python3 lib/revision.py registro <escrito> <búsqueda> --titulo … [--autores …] [--anio …] [--doi …] [--aplicar]
    python3 lib/revision.py cribar <escrito> <registro> --fase 1|2 --decision incluir|excluir|recuperar|no_recuperado
                                   [--motivo …] [--aplicar]
    python3 lib/revision.py prisma <escrito> [--json]           # las cuentas y si cuadran (no escribe)
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import yaml

ARCHIVO = Path("fuentes") / "revision.yml"
CLASES = {"base": "Base de datos", "registro": "Registro", "web": "Sitio web", "organizacion": "Organización",
          "citas": "Búsqueda de citas"}
DE_BASES = ("base", "registro")                    # la columna izquierda del diagrama; las demás son «otros métodos»
DECISIONES = {"incluir": "incluido", "excluir": "excluido"}
CABECERA = ("# fuentes/revision.yml — la revisión de literatura de este escrito: su tipo, la bitácora de búsqueda y el\n"
            "# cribado en dos fases (Biblioteca Studio, lib/revision.py; FLUJO_DE_CONOCIMIENTO C2.1–C2.3). Se puede editar\n"
            "# a mano con la misma forma; el diagrama PRISMA (fuentes/prisma.pdf) sale de aquí con lib/prisma.py.\n")

# Grant y Booth (2009) caracterizan cada tipo por su búsqueda, su evaluación, su síntesis y su análisis (SALSA); Snyder
# (2019), por su método. Los requisitos son lo que el flujo exige antes de dar la revisión por hecha: `obligatorio` o
# `recomendado`.
TIPOS = {
    "narrativa": {"nombre": "Revisión narrativa", "busqueda": "puede ser exhaustiva o no", "evaluacion": "puede evaluar la calidad o no",
                  "sintesis": "narrativa", "analisis": "cronológico, conceptual o temático",
                  "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "recomendado",
                                 "cribado": "recomendado", "prisma": "no"}},
    "alcance": {"nombre": "Revisión de alcance", "busqueda": "tan completa como el tiempo y el alcance permitan",
                "evaluacion": "sin evaluación formal de la calidad", "sintesis": "en tablas, con comentario narrativo",
                "analisis": "cuánta literatura hay y de qué tipo, por diseño y rasgos clave",
                "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "obligatorio",
                               "cribado": "obligatorio", "prisma": "recomendado"}},
    "sistematica": {"nombre": "Revisión sistemática", "busqueda": "exhaustiva y reproducible",
                    "evaluacion": "la calidad decide la inclusión o la exclusión", "sintesis": "narrativa, con tablas",
                    "analisis": "qué se sabe, qué falta saber y con qué incertidumbre",
                    "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "obligatorio",
                                   "cribado": "obligatorio", "prisma": "obligatorio"}},
    "metaanalisis": {"nombre": "Metaanálisis", "busqueda": "exhaustiva y reproducible",
                     "evaluacion": "la calidad decide la inclusión o un análisis de sensibilidad",
                     "sintesis": "gráfica y en tablas, con comentario", "analisis": "numérico, de las medidas del efecto",
                     "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "obligatorio",
                                    "cribado": "obligatorio", "prisma": "obligatorio"}},
    "rapida": {"nombre": "Revisión rápida", "busqueda": "tan completa como el tiempo permita",
               "evaluacion": "formal, limitada por el tiempo", "sintesis": "narrativa y en tablas",
               "analisis": "cuánta literatura hay, su calidad y la dirección del efecto",
               "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "obligatorio",
                              "cribado": "obligatorio", "prisma": "recomendado"}},
    "paraguas": {"nombre": "Revisión paraguas", "busqueda": "de revisiones, no de estudios primarios",
                 "evaluacion": "de las revisiones y de sus estudios", "sintesis": "gráfica y en tablas, con comentario",
                 "analisis": "qué se sabe y qué falta saber",
                 "requisitos": {"pregunta": "obligatorio", "criterios": "obligatorio", "bitacora": "obligatorio",
                                "cribado": "obligatorio", "prisma": "recomendado"}},
}
REQUISITOS = {"pregunta": "La pregunta de la revisión", "criterios": "Criterios de inclusión y de exclusión",
              "bitacora": "Bitácora de búsqueda completa", "cribado": "Cribado en dos fases, con motivos",
              "prisma": "Diagrama PRISMA 2020 que cuadra"}
POR_QUE = {
    "tipo": ("Cada tipo de revisión tiene su búsqueda, su evaluación, su síntesis y su análisis; declararlo fija lo que se exige.",
             "Grant y Booth (2009); Snyder (2019)"),
    "bitacora": ("Una búsqueda se repite y se reporta solo si queda la base, la cadena exacta, los filtros, la fecha y los resultados.",
                 "Rethlefsen et al. (2021); Page et al. (2021, Calibre 11073)"),
    "cribado": ("Primero por título y resumen, después por texto completo, con el motivo de cada exclusión.",
                "Page et al. (2021, Calibre 11073)"),
    "prisma": ("El diagrama de flujo sale de la bitácora: si no cuadra con ella, algo se perdió.",
               "Page et al. (2021); Haddaway et al. (2022)"),
}


class Cambiada(RuntimeError):
    """La bitácora cambió en disco desde que se abrió: no se pisa."""


# ------------------------------------------------------------------ leer y escribir
def ruta(escrito: Path) -> Path:
    return Path(escrito) / ARCHIVO


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def vacia() -> dict:
    return {"tipo": "", "declarada": "", "pregunta": "", "criterios": {"inclusion": [], "exclusion": []},
            "eliminados": {"automatizacion": 0, "otras_razones": 0, "nota": ""}, "busquedas": [], "registros": []}


def leer(escrito: Path) -> tuple[dict, str]:
    """(la revisión, su huella). Sin archivo, una vacía con la huella de «» (crearla no pisa a nadie)."""
    p = ruta(escrito)
    if not p.is_file():
        return vacia(), huella("")
    texto = p.read_text(encoding="utf-8")
    try:
        d = yaml.safe_load(texto) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"fuentes/revision.yml ilegible: {e}") from e
    r = {**vacia(), **{k: v for k, v in d.items() if v is not None}}
    r["criterios"] = {"inclusion": [], "exclusion": [], **(r.get("criterios") or {})}
    r["eliminados"] = {"automatizacion": 0, "otras_razones": 0, "nota": "", **(r.get("eliminados") or {})}
    return r, huella(texto)


def _texto(r: dict) -> str:
    return CABECERA + yaml.safe_dump(r, allow_unicode=True, sort_keys=False, width=110)


def escribir(escrito: Path, r: dict, huella_base: str | None, aplicar: bool) -> dict:
    """Simula o escribe la revisión; con otra huella en disco, `Cambiada`. Devuelve {escrito, diff, huella}."""
    p = ruta(escrito)
    previo = p.read_text(encoding="utf-8") if p.is_file() else ""
    if huella_base is not None and huella(previo) != huella_base:
        raise Cambiada("La bitácora cambió fuera de aquí desde que la abrió: vuelva a abrirla.")
    nuevo = _texto(r)
    diff = "".join(difflib.unified_diff(previo.splitlines(keepends=True), nuevo.splitlines(keepends=True),
                                        fromfile=str(ARCHIVO) if previo else "/dev/null", tofile=str(ARCHIVO)))
    if aplicar:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.guardando")
        tmp.write_text(nuevo, encoding="utf-8")
        os.replace(tmp, p)
    return {"escrito": bool(aplicar), "diff": diff, "huella": huella(nuevo) if aplicar else huella(previo), "ruta": str(p)}


# ------------------------------------------------------------------ declarar el tipo (C2.3)
def declarar(r: dict, tipo: str, pregunta: str | None = None, inclusion: list[str] | None = None,
             exclusion: list[str] | None = None, hoy: str | None = None) -> dict:
    if tipo not in TIPOS:
        raise ValueError("El tipo de revisión es uno de: " + ", ".join(f"{k} ({v['nombre']})" for k, v in TIPOS.items()) + ".")
    r = {**r, "tipo": tipo, "declarada": r.get("declarada") if r.get("tipo") == tipo and r.get("declarada") else (hoy or date.today().isoformat())}
    if pregunta is not None:
        r["pregunta"] = " ".join(pregunta.split())
    crit = dict(r.get("criterios") or {})
    if inclusion is not None:
        crit["inclusion"] = [" ".join(x.split()) for x in inclusion if x.strip()]
    if exclusion is not None:
        crit["exclusion"] = [" ".join(x.split()) for x in exclusion if x.strip()]
    r["criterios"] = {"inclusion": crit.get("inclusion") or [], "exclusion": crit.get("exclusion") or []}
    return r


# ------------------------------------------------------------------ la bitácora (C2.1)
def _siguiente(lista: list[dict], prefijo: str, ancho: int) -> str:
    n = max([int(m.group(1)) for x in lista if (m := re.match(rf"^{prefijo}(\d+)$", str(x.get("id") or "")))] + [0]) + 1
    return f"{prefijo}{n:0{ancho}d}"


def buscar(r: dict, base: str, cadena: str, resultados: int, filtros: str = "", fecha: str | None = None,
           clase: str = "base", nota: str = "") -> tuple[dict, dict]:
    """Añade una búsqueda a la bitácora (PRISMA-S: la base, la cadena exacta tal cual se escribió, los filtros, la fecha y
    cuántos resultados dio). Devuelve (la revisión, la búsqueda)."""
    if clase not in CLASES:
        raise ValueError("La clase de búsqueda es base, registro, web, organizacion o citas.")
    if not base.strip():
        raise ValueError("Diga en qué base o sitio buscó.")
    if not cadena.strip() and clase in DE_BASES:
        raise ValueError("Copie la cadena de búsqueda exacta, tal cual la escribió en la base.")
    try:
        n = int(resultados)
    except (TypeError, ValueError):
        raise ValueError("Escriba cuántos resultados dio la búsqueda (un número).") from None
    if n < 0:
        raise ValueError("Los resultados no pueden ser negativos.")
    fecha = fecha or date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
        raise ValueError("La fecha de la búsqueda va como AAAA-MM-DD.")
    b = {"id": _siguiente(r["busquedas"], "b", 1), "clase": clase, "base": " ".join(base.split()), "cadena": cadena.strip(),
         "filtros": " ".join(filtros.split()), "fecha": fecha, "resultados": n, "nota": " ".join(nota.split())}
    return {**r, "busquedas": [*r["busquedas"], b]}, b


def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _doi(t: str) -> str:
    t = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(t or "").strip(), flags=re.I).rstrip(".")
    return t.lower() if re.match(r"^10\.\d{4,9}/\S+$", t) else ""


def _copia_de(reg: dict, previos: list[dict]) -> str:
    """El id del registro del que `reg` es copia: el mismo DOI, o el mismo título y año."""
    for p in previos:
        if p.get("duplicado_de"):
            continue
        if reg.get("doi") and reg["doi"] == p.get("doi"):
            return p["id"]
        if _normal(reg.get("titulo")) and _normal(reg.get("titulo")) == _normal(p.get("titulo")) and str(reg.get("anio") or "") == str(p.get("anio") or ""):
            return p["id"]
    return ""


def registro(r: dict, busqueda: str, titulo: str, autores: str = "", anio: str = "", doi: str = "", resumen: str = "") -> tuple[dict, dict]:
    if not any(b["id"] == busqueda for b in r["busquedas"]):
        raise LookupError(f"No hay una búsqueda «{busqueda}» en la bitácora.")
    if not " ".join(str(titulo or "").split()):
        raise ValueError("Un registro lleva su título.")
    reg = {"id": _siguiente(r["registros"], "r", 4), "busqueda": busqueda, "titulo": " ".join(str(titulo).split()),
           "autores": " ".join(str(autores or "").split()), "anio": str(anio or "").strip()[:4], "doi": _doi(doi),
           "resumen": " ".join(str(resumen or "").split())[:1500], "duplicado_de": "", "fase1": "", "motivo1": "",
           "recuperado": "", "fase2": "", "motivo2": "", "calibre_id": "", "clave": ""}
    reg["duplicado_de"] = _copia_de(reg, r["registros"])
    return {**r, "registros": [*r["registros"], reg]}, reg


def leer_exportacion(texto: str) -> list[dict]:
    """Los registros de una exportación RIS o BibTeX: título, autores, año, DOI y resumen."""
    salida = []
    if re.search(r"^TY  - ", texto, re.M):
        for bloque in re.split(r"^ER  -.*$", texto, flags=re.M):
            campos: dict[str, list[str]] = {}
            for etiqueta, valor in re.findall(r"^([A-Z][A-Z0-9])  - ?(.*)$", bloque, re.M):
                campos.setdefault(etiqueta, []).append(valor.strip())
            titulo = (campos.get("TI") or campos.get("T1") or [""])[0]
            if titulo:
                anio = re.search(r"\d{4}", " ".join(campos.get("PY") or campos.get("Y1") or campos.get("DA") or []))
                salida.append({"titulo": titulo, "autores": "; ".join(campos.get("AU") or campos.get("A1") or []),
                               "anio": anio.group() if anio else "", "doi": (campos.get("DO") or [""])[0],
                               "resumen": " ".join(campos.get("AB") or campos.get("N2") or [])})
        return salida
    for cuerpo in re.findall(r"@\w+\s*\{[^,]*,(.*?)\n\}", texto, re.S):
        f = {k.lower(): re.sub(r"[{}]", "", v).strip() for k, v in re.findall(r"(\w+)\s*=\s*[{\"](.*?)[}\"]\s*,?\s*$", cuerpo, re.M | re.S)}
        if f.get("title"):
            salida.append({"titulo": f["title"], "autores": f.get("author", "").replace(" and ", "; "),
                           "anio": (re.search(r"\d{4}", f.get("year", "") or f.get("date", "")) or [""])[0] if (f.get("year") or f.get("date")) else "",
                           "doi": f.get("doi", ""), "resumen": f.get("abstract", "")})
    return salida


def importar(r: dict, busqueda: str, texto: str) -> tuple[dict, dict]:
    regs = leer_exportacion(texto)
    if not regs:
        raise ValueError("No se hallaron registros: exporte de la base en RIS o en BibTeX.")
    duplicados = 0
    for x in regs:
        r, reg = registro(r, busqueda, x["titulo"], x["autores"], x["anio"], x["doi"], x["resumen"])
        duplicados += bool(reg["duplicado_de"])
    return r, {"importados": len(regs), "duplicados": duplicados}


# ------------------------------------------------------------------ el cribado en dos fases
def cribar(r: dict, rid: str, fase: int, decision: str, motivo: str = "") -> tuple[dict, dict]:
    """Fase 1 (título y resumen): incluir o excluir. Fase 2 (texto completo): `recuperar` / `no_recuperado` dicen si se
    consiguió el texto; incluir o excluir, este con motivo (PRISMA 2020: las exclusiones del texto completo, con su razón)."""
    regs = [dict(x) for x in r["registros"]]
    reg = next((x for x in regs if x["id"] == rid), None)
    if reg is None:
        raise LookupError(f"No hay un registro «{rid}».")
    if reg.get("duplicado_de"):
        raise ValueError(f"«{rid}» es copia de «{reg['duplicado_de']}»: se criba el original.")
    motivo = " ".join(str(motivo or "").split())
    if int(fase) == 1:
        if decision not in DECISIONES:
            raise ValueError("En la fase 1 se incluye o se excluye.")
        reg.update(fase1=DECISIONES[decision], motivo1=motivo if decision == "excluir" else "")
        if decision == "excluir":
            reg.update(recuperado="", fase2="", motivo2="")
    elif int(fase) == 2:
        if reg.get("fase1") != "incluido":
            raise ValueError("A la fase 2 solo pasa lo que se incluyó por título y resumen.")
        if decision in ("recuperar", "no_recuperado"):
            reg.update(recuperado=decision == "recuperar")
            if decision == "no_recuperado":
                reg.update(fase2="", motivo2="")
        elif decision in DECISIONES:
            if decision == "excluir" and not motivo:
                raise ValueError("Toda exclusión por texto completo lleva su motivo (PRISMA 2020).")
            reg.update(recuperado=True, fase2=DECISIONES[decision], motivo2=motivo if decision == "excluir" else "")
        else:
            raise ValueError("En la fase 2: recuperar, no_recuperado, incluir o excluir.")
    else:
        raise ValueError("La fase es 1 (título y resumen) o 2 (texto completo).")
    return {**r, "registros": regs}, reg


# ------------------------------------------------------------------ las cuentas PRISMA (C2.2) y los requisitos (C2.3)
def cuentas(r: dict) -> dict:
    """Las cajas del diagrama PRISMA 2020 y si cuadran con la bitácora."""
    clase = {b["id"]: b["clase"] for b in r["busquedas"]}
    col = {"bases": {"identificados": {}, "registros": []}, "otros": {"identificados": {}, "registros": []}}
    for b in r["busquedas"]:
        lado = "bases" if b["clase"] in DE_BASES else "otros"
        col[lado]["identificados"][b["clase"]] = col[lado]["identificados"].get(b["clase"], 0) + int(b.get("resultados") or 0)
    for x in r["registros"]:
        col["bases" if clase.get(x["busqueda"]) in DE_BASES else "otros"]["registros"].append(x)
    avisos = []
    for b in r["busquedas"]:
        n = sum(1 for x in r["registros"] if x["busqueda"] == b["id"])
        if n and n != int(b.get("resultados") or 0):
            avisos.append(f"La búsqueda {b['id']} ({b['base']}) dio {b['resultados']} resultados y hay {n} registros: importe el resto o corrija la cifra.")
    salida = {"avisos": avisos}
    for lado, d in col.items():
        regs = d["registros"]
        unicos = [x for x in regs if not x.get("duplicado_de")]
        duplicados = len(regs) - len(unicos)
        identificados = sum(d["identificados"].values())
        excluidos1 = [x for x in unicos if x.get("fase1") == "excluido"]
        pasan = [x for x in unicos if x.get("fase1") == "incluido"]
        no_recuperados = [x for x in pasan if x.get("recuperado") is False]
        evaluados = [x for x in pasan if x.get("recuperado") is True]
        excluidos2 = [x for x in evaluados if x.get("fase2") == "excluido"]
        incluidos = [x for x in evaluados if x.get("fase2") == "incluido"]
        motivos: dict[str, int] = {}
        for x in excluidos2:
            motivos[x.get("motivo2") or "sin motivo"] = motivos.get(x.get("motivo2") or "sin motivo", 0) + 1
        e = r.get("eliminados") or {} if lado == "bases" else {}
        auto, otras = int(e.get("automatizacion") or 0), int(e.get("otras_razones") or 0)
        cribados = len(unicos) if lado == "bases" else 0
        caja = {"identificados": identificados, "por_clase": d["identificados"], "duplicados": duplicados,
                "automatizacion": auto, "otras_razones": otras, "cribados": cribados,
                "excluidos_titulo": len(excluidos1), "buscados": len(pasan), "no_recuperados": len(no_recuperados),
                "evaluados": len(evaluados), "excluidos_texto": len(excluidos2), "motivos": motivos,
                "incluidos": len(incluidos), "estudios": len({x.get("estudio") or x["id"] for x in incluidos}),
                "sin_cribar": sum(1 for x in unicos if not x.get("fase1")),
                "sin_decidir": sum(1 for x in pasan if x.get("recuperado") in ("", None) or (x.get("recuperado") is True and not x.get("fase2")))}
        if lado == "bases" and regs and identificados - duplicados - auto - otras != cribados:
            avisos.append(f"No cuadra: {identificados} identificados − {duplicados} duplicados − {auto + otras} eliminados por otras "
                          f"causas = {identificados - duplicados - auto - otras}, pero se cribaron {cribados}.")
        salida[lado] = caja
    b, o = salida["bases"], salida["otros"]
    salida["incluidos"] = b["incluidos"] + o["incluidos"]
    salida["estudios"] = b["estudios"] + o["estudios"]
    salida["cuadra"] = not avisos
    salida["otros_metodos"] = bool(o["identificados"] or o["buscados"] or any(c not in DE_BASES for c in (x["clase"] for x in r["busquedas"])))
    return salida


def requisitos(r: dict, prisma_al_dia: bool | None = None) -> list[dict]:
    """[{clave, texto, exigencia, cumple, detalle}] según el tipo declarado (Grant y Booth, 2009; Snyder, 2019)."""
    t = TIPOS.get(r.get("tipo") or "")
    if not t:
        return []
    c = cuentas(r)
    completas = [b for b in r["busquedas"] if b.get("base") and (b.get("cadena") or b["clase"] not in DE_BASES)
                 and b.get("fecha") and b.get("resultados") not in (None, "")]
    sin_filtros = [b["id"] for b in r["busquedas"] if not b.get("filtros")]
    unicos = [x for x in r["registros"] if not x.get("duplicado_de")]
    estado = {
        "pregunta": (bool(r.get("pregunta")), "" if r.get("pregunta") else "Escriba la pregunta que la revisión responde."),
        "criterios": (bool(r["criterios"]["inclusion"]) and bool(r["criterios"]["exclusion"]),
                      "Declare los criterios de inclusión y de exclusión." if not (r["criterios"]["inclusion"] and r["criterios"]["exclusion"]) else ""),
        "bitacora": (bool(r["busquedas"]) and len(completas) == len(r["busquedas"]),
                     "Registre al menos una búsqueda." if not r["busquedas"] else
                     ("Complete la base, la cadena, la fecha y los resultados de cada búsqueda." if len(completas) != len(r["busquedas"])
                      else ("Sin filtros declarados en " + ", ".join(sin_filtros) + " (si no hubo, escríbalo)." if sin_filtros else ""))),
        "cribado": (bool(unicos) and c["bases"]["sin_cribar"] + c["otros"]["sin_cribar"] == 0 and c["bases"]["sin_decidir"] + c["otros"]["sin_decidir"] == 0,
                    "No hay registros que cribar." if not unicos else
                    (f"Faltan {c['bases']['sin_cribar'] + c['otros']['sin_cribar']} por cribar por título y resumen y "
                     f"{c['bases']['sin_decidir'] + c['otros']['sin_decidir']} por decidir con el texto completo."
                     if c["bases"]["sin_cribar"] + c["otros"]["sin_cribar"] + c["bases"]["sin_decidir"] + c["otros"]["sin_decidir"] else "")),
        "prisma": (c["cuadra"] and bool(r["busquedas"]) and prisma_al_dia is not False,
                   " ".join(c["avisos"]) or ("Genere el diagrama: el que hay es de otras cifras." if prisma_al_dia is False else "")),
    }
    salida = []
    for clave, exigencia in t["requisitos"].items():
        if exigencia == "no":
            continue
        cumple, detalle = estado[clave]
        salida.append({"clave": clave, "texto": REQUISITOS[clave], "exigencia": exigencia, "cumple": bool(cumple), "detalle": detalle,
                       "porque": POR_QUE.get(clave, POR_QUE["tipo"])[0], "fuente": POR_QUE.get(clave, POR_QUE["tipo"])[1]})
    return salida


def ver(escrito: Path) -> dict:
    """Todo lo que la ventana pinta de la revisión de un escrito."""
    r, h = leer(escrito)
    import importlib.util
    s = importlib.util.spec_from_file_location("biblioteca_prisma", Path(__file__).resolve().parent / "prisma.py")
    prisma = importlib.util.module_from_spec(s)
    s.loader.exec_module(prisma)
    al_dia = prisma.al_dia(escrito, r) if r["busquedas"] else None
    t = TIPOS.get(r.get("tipo") or "")
    return {"escrito": str(escrito), "huella": h, "existe": ruta(escrito).is_file(), "revision": r, "cuentas": cuentas(r),
            "requisitos": requisitos(r, al_dia), "prisma": {"al_dia": al_dia, **prisma.archivos(escrito)},
            "tipo": {"clave": r.get("tipo") or "", **(t or {})}, "porque": {k: {"texto": v[0], "fuente": v[1]} for k, v in POR_QUE.items()}}


# ------------------------------------------------------------------ CLI
def _escrito(texto: str) -> Path:
    p = Path(texto).expanduser().resolve()
    if not (p / "proyecto.yaml").is_file() and not (p / "fuentes").is_dir():
        raise SystemExit(f"[ERROR] {p} no es un escrito (sin proyecto.yaml ni fuentes/)")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    for n in ("ver", "prisma"):
        s = sub.add_parser(n); s.add_argument("escrito"); s.add_argument("--json", action="store_true")
    sub.add_parser("tipos").add_argument("--json", action="store_true")
    d = sub.add_parser("declarar"); d.add_argument("escrito"); d.add_argument("tipo"); d.add_argument("--pregunta")
    d.add_argument("--incluir", action="append"); d.add_argument("--excluir", action="append")
    b = sub.add_parser("buscar"); b.add_argument("escrito"); b.add_argument("--base", required=True); b.add_argument("--cadena", default="")
    b.add_argument("--filtros", default=""); b.add_argument("--fecha"); b.add_argument("--resultados", required=True)
    b.add_argument("--clase", default="base"); b.add_argument("--nota", default="")
    i = sub.add_parser("importar"); i.add_argument("escrito"); i.add_argument("busqueda"); i.add_argument("archivo")
    g = sub.add_parser("registro"); g.add_argument("escrito"); g.add_argument("busqueda"); g.add_argument("--titulo", required=True)
    g.add_argument("--autores", default=""); g.add_argument("--anio", default=""); g.add_argument("--doi", default="")
    c = sub.add_parser("cribar"); c.add_argument("escrito"); c.add_argument("registro"); c.add_argument("--fase", type=int, required=True)
    c.add_argument("--decision", required=True); c.add_argument("--motivo", default="")
    for s in (d, b, i, g, c):
        s.add_argument("--aplicar", action="store_true"); s.add_argument("--huella"); s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.orden == "tipos":
        r = {"tipos": TIPOS, "requisitos": REQUISITOS, "porque": POR_QUE["tipo"]}
        print(json.dumps(r, ensure_ascii=False) if a.json else "\n".join(f"{k:<13} {v['nombre']}: búsqueda {v['busqueda']}; "
                                                                           f"síntesis {v['sintesis']}" for k, v in TIPOS.items()))
        return 0
    escrito = _escrito(a.escrito)
    try:
        if a.orden in ("ver", "prisma"):
            v = ver(escrito)
            r = v if a.orden == "ver" else v["cuentas"]
            if a.json:
                print(json.dumps(r, ensure_ascii=False))
            elif a.orden == "prisma":
                bq = r["bases"]
                print(f"identificados {bq['identificados']} · duplicados {bq['duplicados']} · cribados {bq['cribados']} · excluidos "
                      f"{bq['excluidos_titulo']} · buscados {bq['buscados']} · no recuperados {bq['no_recuperados']} · evaluados "
                      f"{bq['evaluados']} · excluidos {bq['excluidos_texto']} · incluidos {r['incluidos']}")
                print("✓ cuadra" if r["cuadra"] else "✗ " + " ".join(r["avisos"]))
            else:
                print(yaml.safe_dump({k: v[k] for k in ("tipo", "requisitos", "cuentas")}, allow_unicode=True, sort_keys=False))
            return 0
        r, h = leer(escrito)
        base = a.huella if a.huella else h
        extra: dict = {}
        if a.orden == "declarar":
            r = declarar(r, a.tipo, a.pregunta, a.incluir, a.excluir)
        elif a.orden == "buscar":
            r, extra = buscar(r, a.base, a.cadena, a.resultados, a.filtros, a.fecha, a.clase, a.nota)
        elif a.orden == "importar":
            r, extra = importar(r, a.busqueda, Path(a.archivo).read_text(encoding="utf-8", errors="replace"))
        elif a.orden == "registro":
            r, extra = registro(r, a.busqueda, a.titulo, a.autores, a.anio, a.doi)
        elif a.orden == "cribar":
            r, extra = cribar(r, a.registro, a.fase, a.decision, a.motivo)
        salida = {**escribir(escrito, r, base, a.aplicar), "resultado": extra, "cuentas": cuentas(r)}
    except Cambiada as e:
        salida = {"codigo": "revision_cambiada", "error": str(e)}
    except (ValueError, LookupError) as e:
        salida = {"error": str(e)}
    if a.json:
        print(json.dumps(salida, ensure_ascii=False))
    elif salida.get("error"):
        print(f"✗ {salida['error']}", file=sys.stderr)
    else:
        print(salida["diff"] or "(sin cambios)")
        print("✓ escrito" if salida["escrito"] else "[simulación] --aplicar escribe fuentes/revision.yml")
    return 1 if salida.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
