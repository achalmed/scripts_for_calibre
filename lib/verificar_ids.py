#!/usr/bin/env python3
"""lib/verificar_ids.py — «referencia que no existe» (FLUJO_DE_CONOCIMIENTO C12.5; decisiones §9.10): el DOI de cada obra se
resuelve en Crossref y su ISBN en Open Library, con caché, y el índice compartido publica `doi_verificado`.

Objetivo: que ningún escrito cite una obra inventada (la referencia que un LLM fabrica tiene un DOI que no existe, o uno
  real de otra obra): el control «Antes de entregar» de escritura lee del índice si el DOI o el ISBN de cada clave citada
  existe y es de esa obra.
Método: SOLO LEE `metadata.db` (los identificadores `doi` e `isbn` de Calibre) y `zotero.sqlite` (los campos DOI e ISBN, o
  «DOI:» en Extra, y la clave de cita), en `mode=ro`, como `lib/indice.py`. Cada identificador se consulta una vez:
  · DOI → `api.crossref.org/works/<doi>`; si Crossref no lo tiene (404), `doi.org/api/handles/<doi>`, porque un DOI de
    DataCite (Zenodo, OSF) existe aunque Crossref no lo conozca;
  · ISBN → se valida su dígito de control y se busca en `openlibrary.org/isbn/<isbn>.json`; que Open Library no lo tenga
    no prueba que no exista (muchas ediciones peruanas no están): queda «no hallado», que avisa sin fallar.
  El título que devuelve la agencia se compara con el de la biblioteca: un DOI que existe pero es de otra obra «discrepa».
  La caché vive en `$XDG_STATE_HOME/biblioteca/identificadores.json` (junto al índice, fuera del repo y de las bases): lo
  que existe se vuelve a mirar a los 180 días, lo que no existe a los 30, y un error de red no se guarda.
Salida en el índice (`lib/indice.py` la funde; campos nuevos, los de antes no cambian): en cada libro `doi`, `isbn`,
  `doi_verificado` y `isbn_verificado` (true · false · null = sin consultar o sin identificador) y `verificacion_ids`
  (estados y fecha: `no_existe` y `mal_formado` son un fallo; `discrepa`, el identificador existe pero con otro título, una
  traducción o una referencia cambiada, es para revisar); arriba, `referencias`: {clave para citar: lo mismo, más `zotero_key` y `calibre_id`} de todo ítem de
  Zotero con clave, esté o no en Calibre.
Fundamento: ICMJE (2025), el autor responde por la exactitud de sus referencias; Jergas y Baethge (2015), los errores de
  cita son frecuentes y se previenen cotejando.
Límite: no escribe en ninguna base (no es una puerta); sin `--aplicar` dice qué consultaría y no consulta. Sin red, nada se
  marca como inexistente.

    python3 lib/verificar_ids.py estado                         # cuántos identificadores hay y qué dice la caché (no consulta)
    python3 lib/verificar_ids.py verificar [--limite N] [--ids 1,2] [--claves k1,k2] [--forzar] [--aplicar] [--json]
    python3 lib/verificar_ids.py escrito <carpeta del escrito> [--aplicar] [--json]   # las claves de su .bib
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VIGENCIA = {"existe": 180, "discrepa": 180, "no_existe": 30, "no_hallado": 30, "mal_formado": 3650}
PAUSA = 0.2                                   # segundos entre consultas (Crossref pide no apurar su API pública)
AGENTE = "biblioteca-studio/3 (verificar_ids)"
POR_QUE = ("Una referencia inventada tiene un DOI que no existe o que es de otra obra: se resuelve antes de entregar.",
           "ICMJE (2025); Jergas y Baethge (2015)")
VACIAS = {"the", "and", "for", "with", "from", "una", "del", "las", "los", "por", "para", "con", "como", "sobre", "entre"}


# ------------------------------------------------------------------ identificadores
def normalizar_doi(v) -> str:
    """«https://doi.org/10.1037/ABC » → «10.1037/abc» (los DOI no distinguen mayúsculas); «» si no lo es."""
    t = str(v or "").strip()
    t = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", t, flags=re.I).strip().rstrip(".")
    return t.lower() if re.match(r"^10\.\d{4,9}/\S+$", t) else ""


def _isbn10_a_13(d: str) -> str:
    base = "978" + d[:9]
    suma = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))
    return base + str((10 - suma % 10) % 10)


def normalizar_isbn(v) -> tuple[str, bool]:
    """(ISBN-13, dígito de control correcto). Acepta ISBN-10 (lo pasa a 13) y guiones o espacios; («», False) si no lo es."""
    d = re.sub(r"[^0-9Xx]", "", str(v or "")).upper()
    if len(d) == 10:
        ok = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d)) % 11 == 0 if re.match(r"^\d{9}[\dX]$", d) else False
        return (_isbn10_a_13(d) if ok else d), ok
    if len(d) == 13 and d.isdigit():
        return d, sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d)) % 10 == 0
    return "", False


def _palabras(t: str) -> set[str]:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2 and w not in VACIAS}


def mismo_titulo(a: str, b: str) -> bool | None:
    """¿Son el mismo título? Las palabras con contenido del más corto, casi todas en el otro (el subtítulo puede faltar);
    None si alguno está vacío."""
    x, y = _palabras(a), _palabras(b)
    if not x or not y:
        return None
    corto, largo = (x, y) if len(x) <= len(y) else (y, x)
    from difflib import SequenceMatcher

    def esta(w: str) -> bool:     # la misma palabra, o casi (una errata de la agencia: «Genealgía», «Probabllity»)
        return w in largo or (len(w) >= 5 and any(SequenceMatcher(None, w, v).ratio() >= 0.85 for v in largo))
    return sum(esta(w) for w in corto) / len(corto) >= 0.6


# ------------------------------------------------------------------ la caché
def ruta_cache() -> Path:
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return estado / "biblioteca" / "identificadores.json"


def leer_cache(ruta: Path | None = None) -> dict:
    ruta = ruta or ruta_cache()
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        return d.get("identificadores") or {} if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_cache(cache: dict, ruta: Path | None = None) -> Path:
    ruta = ruta or ruta_cache()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"esquema": 1, "generado": datetime.now().isoformat(timespec="seconds"),
                               "identificadores": dict(sorted(cache.items()))}, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(ruta)
    return ruta


def vigente(entrada: dict | None, hoy: date | None = None) -> bool:
    if not entrada or entrada.get("estado") not in VIGENCIA:
        return False
    try:
        cuando = date.fromisoformat(str(entrada.get("fecha"))[:10])
    except ValueError:
        return False
    return (hoy or date.today()) - cuando <= timedelta(days=VIGENCIA[entrada["estado"]])


# ------------------------------------------------------------------ las agencias
def _pedir(url: str, timeout: int = 20):
    """(código HTTP, JSON o None). Un fallo de red da (0, None): nunca se toma por «no existe»."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


def consultar_doi(doi: str, pedir=_pedir) -> dict:
    hoy = date.today().isoformat()
    correo = os.environ.get("CROSSREF_MAILTO", "").strip()
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/") + (f"?mailto={urllib.parse.quote(correo)}" if correo else "")
    codigo, d = pedir(url)
    if codigo == 200 and isinstance(d, dict):
        m = d.get("message") or {}
        anio = ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        return {"estado": "existe", "fuente": "Crossref", "titulo": " ".join(m.get("title") or [])[:300],
                "anio": anio, "fecha": hoy}
    if codigo == 404:
        c2, h = pedir("https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/"))
        if c2 == 200 and isinstance(h, dict) and h.get("responseCode") == 1:
            return {"estado": "existe", "fuente": "doi.org (otra agencia que Crossref)", "titulo": "", "anio": None, "fecha": hoy}
        if c2 in (404, 200):
            return {"estado": "no_existe", "fuente": "Crossref y doi.org", "titulo": "", "anio": None, "fecha": hoy}
    return {"estado": "error", "fuente": "Crossref", "detalle": f"HTTP {codigo}" if codigo else "sin red", "fecha": hoy}


def consultar_isbn(isbn: str, pedir=_pedir) -> dict:
    hoy = date.today().isoformat()
    codigo, d = pedir(f"https://openlibrary.org/isbn/{isbn}.json")
    if codigo == 200 and isinstance(d, dict):
        anio = re.search(r"\d{4}", str(d.get("publish_date") or ""))
        return {"estado": "existe", "fuente": "Open Library", "titulo": " ".join(x for x in (d.get("title"), d.get("subtitle")) if x)[:300],
                "anio": int(anio.group()) if anio else None, "fecha": hoy}
    if codigo == 404:
        return {"estado": "no_hallado", "fuente": "Open Library", "titulo": "", "anio": None, "fecha": hoy}
    return {"estado": "error", "fuente": "Open Library", "detalle": f"HTTP {codigo}" if codigo else "sin red", "fecha": hoy}


# ------------------------------------------------------------------ lo que tiene la biblioteca (solo lectura)
def _ro(db: Path) -> sqlite3.Connection:
    uri = Path(db).resolve().as_uri()
    c = sqlite3.connect(uri + "?mode=ro", uri=True)
    try:
        c.execute("select 1 from sqlite_master limit 1")
    except sqlite3.OperationalError:
        c.close()
        c = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True)
    return c


def de_calibre(db: Path) -> dict[int, dict]:
    """{libro: {titulo, doi, isbn}} de `metadata.db` (sus identificadores), en solo lectura."""
    if not Path(db).is_file():
        return {}
    c = _ro(db)
    try:
        libros = {b: {"titulo": t or "", "doi": "", "isbn": ""} for b, t in c.execute("select id, title from books")}
        for b, tipo, val in c.execute("select book, type, val from identifiers where type in ('doi','isbn')"):
            if b in libros:
                libros[b][tipo] = normalizar_doi(val) if tipo == "doi" else (normalizar_isbn(val)[0] or str(val))
    finally:
        c.close()
    return libros


def de_zotero(db: Path) -> dict[str, dict]:
    """{clave para citar: {zotero_key, titulo, doi, isbn}} de todo ítem con clave de `zotero.sqlite`, en solo lectura
    (el DOI de los tipos que no lo traen como campo va en Extra, «DOI: …»)."""
    if not Path(db).is_file():
        return {}
    c = _ro(db)
    try:
        campos: dict[int, dict] = {}
        for item, nombre, valor in c.execute(
                "select d.itemID, f.fieldName, v.value from itemData d join fields f on f.fieldID=d.fieldID "
                "join itemDataValues v on v.valueID=d.valueID where f.fieldName in ('citationKey','title','DOI','ISBN','extra')"):
            campos.setdefault(item, {})[nombre] = str(valor or "")
        claves = dict(c.execute("select itemID, key from items"))
    finally:
        c.close()
    salida = {}
    for item, f in campos.items():
        clave = f.get("citationKey", "").strip()
        if not clave:
            continue
        doi = normalizar_doi(f.get("DOI"))
        if not doi:
            m = re.search(r"^DOI:\s*(\S+)", f.get("extra", ""), re.M | re.I)
            doi = normalizar_doi(m.group(1)) if m else ""
        isbns = [normalizar_isbn(x)[0] or x for x in re.split(r"[\s,;]+", f.get("ISBN", "")) if x.strip()]
        salida[clave] = {"zotero_key": claves.get(item, ""), "titulo": f.get("title", ""), "doi": doi, "isbn": isbns[0] if isbns else ""}
    return salida


# ------------------------------------------------------------------ juntar y verificar
def _id(tipo: str, valor: str) -> str:
    return f"{tipo}:{valor}"


def estado_de(tipo: str, valor: str, titulo: str, cache: dict) -> dict:
    """{estado, verificado (true · false · null), fuente, fecha, titulo_agencia} de un identificador según la caché."""
    if not valor:
        return {"estado": "sin_identificador", "verificado": None}
    if tipo == "isbn" and not normalizar_isbn(valor)[1]:
        return {"estado": "mal_formado", "verificado": False, "fuente": "dígito de control", "fecha": date.today().isoformat()}
    e = cache.get(_id(tipo, valor))
    if not e or e.get("estado") == "error":
        return {"estado": "sin_consultar", "verificado": None}
    estado = e["estado"]
    if estado == "existe" and e.get("titulo") and mismo_titulo(e["titulo"], titulo) is False:
        estado = "discrepa"
    verificado = {"existe": True, "discrepa": False, "no_existe": False, "no_hallado": None}.get(estado)
    return {"estado": estado, "verificado": verificado, "fuente": e.get("fuente", ""), "fecha": e.get("fecha", ""),
            "titulo_agencia": e.get("titulo", "")}


def campos(doi: str, isbn: str, titulo: str, cache: dict) -> dict:
    """Los campos que el índice publica para una obra."""
    d, i = estado_de("doi", doi, titulo, cache), estado_de("isbn", isbn, titulo, cache)
    return {"doi": doi, "isbn": isbn, "doi_verificado": d["verificado"], "isbn_verificado": i["verificado"],
            "verificacion_ids": {"doi": d["estado"], "isbn": i["estado"], "fecha": max(d.get("fecha", ""), i.get("fecha", "")),
                                 **({"titulo_agencia": d.get("titulo_agencia") or i.get("titulo_agencia")}
                                    if d["estado"] == "discrepa" or i["estado"] == "discrepa" else {})}}


def pendientes(obras: list[dict], cache: dict, forzar: bool = False) -> list[tuple[str, str]]:
    """[(tipo, valor)] por consultar: los que faltan en la caché o vencieron (todos con `forzar`); ISBN mal formados, no."""
    vistos, salida = set(), []
    for o in obras:
        for tipo in ("doi", "isbn"):
            v = o.get(tipo) or ""
            if not v or (tipo, v) in vistos or (tipo == "isbn" and not normalizar_isbn(v)[1]):
                continue
            vistos.add((tipo, v))
            if forzar or not vigente(cache.get(_id(tipo, v))):
                salida.append((tipo, v))
    return salida


def consultar(lista: list[tuple[str, str]], cache: dict, pausa: float = PAUSA, pedir=_pedir, avisar=None) -> dict:
    """Consulta cada (tipo, valor) y lo guarda en `cache` (salvo los errores de red). Devuelve las cuentas por estado."""
    cuentas: dict[str, int] = {}
    for n, (tipo, v) in enumerate(lista, 1):
        r = consultar_doi(v, pedir) if tipo == "doi" else consultar_isbn(v, pedir)
        cuentas[r["estado"]] = cuentas.get(r["estado"], 0) + 1
        if r["estado"] != "error":
            cache[_id(tipo, v)] = r
        if avisar:
            avisar(n, len(lista), tipo, v, r)
        if pausa and n < len(lista):
            time.sleep(pausa)
    return cuentas


def _env():
    d = RAIZ
    while d != d.parent and not (d / "core" / "env.py").is_file():
        d = d.parent
    import importlib.util
    s = importlib.util.spec_from_file_location("core_env", d / "core" / "env.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def obras(env=None, ids: set[int] | None = None, claves: set[str] | None = None) -> list[dict]:
    """Las obras de Calibre y de Zotero con su DOI o ISBN (Zotero manda en los metadatos: su DOI va primero)."""
    env = env or _env()
    cal = de_calibre(Path(env.CALIBRE_DB))
    zot = de_zotero(Path(env.ZOTERO_DB))
    salida = []
    for b, d in cal.items():
        if (ids is None or b in ids) and claves is None and (d["doi"] or d["isbn"]):
            salida.append({"calibre_id": b, **d})
    for k, d in zot.items():
        if (claves is None or k in claves) and ids is None and (d["doi"] or d["isbn"]):
            salida.append({"clave": k, **d})
    return salida


def resumen(lista: list[dict], cache: dict) -> dict:
    cuentas: dict[str, int] = {}
    for o in lista:
        c = campos(o.get("doi", ""), o.get("isbn", ""), o.get("titulo", ""), cache)["verificacion_ids"]
        for tipo in ("doi", "isbn"):
            if c[tipo] != "sin_identificador":
                k = f"{tipo}_{c[tipo]}"
                cuentas[k] = cuentas.get(k, 0) + 1
    return cuentas


# ------------------------------------------------------------------ un escrito
def claves_del_bib(carpeta: Path) -> list[str]:
    """Las claves de los .bib del escrito (sus `references.bib` y los de `bib/`), sin duplicados y en orden."""
    vistas: list[str] = []
    for bib in [carpeta / "references.bib", *sorted((carpeta / "bib").glob("*.bib"))]:
        if bib.is_file():
            for k in re.findall(r"^@\w+\s*\{\s*([^,\s]+)\s*,", bib.read_text(encoding="utf-8", errors="replace"), re.M):
                if k not in vistas:
                    vistas.append(k)
    return vistas


def revisar_escrito(carpeta: Path, cache: dict, zot: dict) -> list[dict]:
    """[{clave, estado, detalle}] de cada clave del .bib del escrito: «verificada», «sin identificador», «no existe»…"""
    salida = []
    for k in claves_del_bib(carpeta):
        z = zot.get(k)
        if not z:
            salida.append({"clave": k, "estado": "fuera_de_zotero", "detalle": "No está en Zotero: primero en la biblioteca, después la cita."})
            continue
        c = campos(z["doi"], z["isbn"], z["titulo"], cache)
        v = c["verificacion_ids"]
        if c["doi_verificado"] is False or c["isbn_verificado"] is False:
            malo = "doi" if c["doi_verificado"] is False else "isbn"
            if v[malo] == "discrepa":      # existe, pero con otro título: una traducción, otra edición o una referencia cambiada
                salida.append({"clave": k, "estado": "revisar", "detalle": f"Su {malo.upper()} {c[malo]} existe, pero es de "
                               f"«{v.get('titulo_agencia', '')[:80]}»: compruebe que es esta obra."})
                continue
            texto = {"no_existe": "no existe", "mal_formado": "está mal formado"}.get(v[malo], v[malo])
            salida.append({"clave": k, "estado": "falla", "detalle": f"Su {malo.upper()} {c[malo]} {texto}."})
        elif c["doi_verificado"] or c["isbn_verificado"]:
            salida.append({"clave": k, "estado": "verificada", "detalle": f"{'DOI' if c['doi_verificado'] else 'ISBN'} resuelto."})
        elif not c["doi"] and not c["isbn"]:
            salida.append({"clave": k, "estado": "sin_identificador", "detalle": "Sin DOI ni ISBN en Zotero."})
        else:
            salida.append({"clave": k, "estado": "sin_verificar", "detalle": "Aún no se consultó su identificador." if "sin_consultar" in v.values()
                           else "Open Library no tiene ese ISBN: no prueba que no exista."})
    return salida


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("estado").add_argument("--json", action="store_true")
    v = sub.add_parser("verificar")
    v.add_argument("--limite", type=int, default=0)
    v.add_argument("--ids", default="")
    v.add_argument("--claves", default="")
    v.add_argument("--forzar", action="store_true")
    v.add_argument("--aplicar", action="store_true", help="consulta y guarda la caché (sin esto, dice qué consultaría)")
    v.add_argument("--json", action="store_true")
    e = sub.add_parser("escrito")
    e.add_argument("carpeta")
    e.add_argument("--aplicar", action="store_true", help="consulta lo que falte de sus claves (sin esto, solo la caché)")
    e.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cache = leer_cache()
    if a.orden == "estado":
        lista = obras()
        r = {"obras": len(lista), "cuentas": resumen(lista, cache), "cache": str(ruta_cache()), "porque": POR_QUE[0], "fuente": POR_QUE[1]}
        print(json.dumps(r, ensure_ascii=False) if a.json else
              f"{r['obras']} obras con DOI o ISBN · " + " · ".join(f"{k} {n}" for k, n in sorted(r["cuentas"].items())) + f" → {r['cache']}")
        return 0
    if a.orden == "verificar":
        ids = {int(x) for x in a.ids.split(",") if x.strip().isdigit()} or None
        claves = {x.strip() for x in a.claves.split(",") if x.strip()} or None
        lista = obras(ids=ids, claves=claves)
        por = pendientes(lista, cache, a.forzar)
        if a.limite:
            por = por[: a.limite]
        if not a.aplicar:
            r = {"simulacion": True, "por_consultar": len(por), "doi": sum(t == "doi" for t, _ in por), "isbn": sum(t == "isbn" for t, _ in por),
                 "en_cache": len(cache)}
            print(json.dumps(r, ensure_ascii=False) if a.json else
                  f"[simulación] consultaría {r['por_consultar']} identificadores ({r['doi']} DOI en Crossref, {r['isbn']} ISBN en "
                  f"Open Library); {r['en_cache']} ya en la caché (--aplicar consulta)")
            return 0
        avisar = None if a.json else (lambda n, t, tipo, val, r: print(f"  [{n}/{t}] {tipo} {val}: {r['estado']}"))
        cuentas = consultar(por, cache, avisar=avisar)
        guardar_cache(cache)
        r = {"consultados": len(por), "cuentas": cuentas, "cache": str(ruta_cache()), "resumen": resumen(lista, cache)}
        print(json.dumps(r, ensure_ascii=False) if a.json else
              f"✓ {len(por)} consultados · " + " · ".join(f"{k} {n}" for k, n in sorted(cuentas.items())) + f" → {r['cache']}"
              "\n  el índice los publica en su próxima corrida (python3 lib/indice.py --aplicar)")
        return 0
    carpeta = Path(a.carpeta).expanduser().resolve()
    env = _env()
    zot = de_zotero(Path(env.ZOTERO_DB))
    if a.aplicar:
        lista = [{"clave": k, **zot[k]} for k in claves_del_bib(carpeta) if k in zot]
        consultar(pendientes(lista, cache), cache)
        guardar_cache(cache)
    filas = revisar_escrito(carpeta, cache, zot)
    if a.json:
        print(json.dumps({"escrito": str(carpeta), "claves": filas, "porque": POR_QUE[0], "fuente": POR_QUE[1]}, ensure_ascii=False))
    else:
        for f in filas:
            print(f"  {f['estado']:<17} {f['clave']}: {f['detalle']}")
        print(f"{len(filas)} claves · {sum(f['estado'] == 'falla' for f in filas)} fallan")
    return 1 if any(f["estado"] == "falla" for f in filas) else 0


if __name__ == "__main__":
    sys.exit(main())
