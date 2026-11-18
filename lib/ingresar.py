#!/usr/bin/env python3
"""lib/ingresar.py — ingresar obras por su DOI o su ISBN: los pasos 00 a 03 del Método Documental para una lista de obras
identificadas (decisiones §9.10; la primera, las del FLUJO_DE_CONOCIMIENTO del 2026-11-18).

Objetivo: que una obra que funda una norma, un prompt o una revisión entre a la biblioteca entera, con o sin archivo:
  su registro en Calibre con sus metadatos e identificadores (y el PDF si es de acceso abierto desde la sede oficial),
  su ítem en Zotero con su clave de Better BibTeX, su etiqueta y su colección, y el puente entre los dos (`#zotero_key` y el
  adjunto enlazado al archivo de Calibre), sin duplicar lo que ya existe.
Método: la lista es un JSON de obras ya cotejadas (autores, año, título, revista o editorial, DOI, ISBN, URL del PDF libre;
  la forma de `obras-flujo.json`). `plan` SOLO LEE: compara cada obra con Calibre y con Zotero por DOI, ISBN y título
  (`mode=ro`), arma su registro de Calibre (autor «Nombre, Apellido», `#item_type`, `#clasificador` de su enumeración) y su
  ítem de Zotero (los campos válidos de su tipo; lo que el tipo no admite va a Extra) y su clave con la fórmula del
  ecosistema (`auth.lower + shorttitle(3, 3) + year`, docs/citar.md §2; única frente a todas las de Zotero). `aplicar`:
  baja los PDF (solo `%PDF` y de la URL dada) a `entrada/<lote>/`, abre la puerta de Calibre (`escribir.puerta`: Calibre
  cerrado, candado, respaldo verificado) y añade cada registro con la orden `add` de calibredb (`--empty` sin archivo) y
  `set_metadata`; abre la de Zotero (cerrado, candado, respaldo) y crea los ítems con las primitivas `z_*`; vuelve a la de
  Calibre para escribir `#zotero_key`; deja la ficha de catalogación de cada obra, sus filas en `resumen_catalogacion.tsv`
  (y en `ingesta.tsv` las que tienen archivo) y el resultado en JSON. Lo que ya existía solo recibe la etiqueta y la
  colección.
Fundamento: normativa 9.6 (primero en la biblioteca, después la cita); docs/citar.md (Zotero manda en la clave);
  METODO_DOCUMENTAL.md pasos 00–03; las descargas solo de la sede oficial y de acceso abierto (regla 9 de la noche).
Límite: no busca obras ni descarga de otra parte que la URL dada; no inventa metadatos (los trae la lista). Con Calibre o
  Zotero abiertos sale 75 sin escribir.

    python3 lib/ingresar.py plan <obras.json> [--etiqueta flujo-de-conocimiento] [--coleccion «Flujo de conocimiento»] [--json]
    python3 lib/ingresar.py aplicar <obras.json> --lote <nombre> [--etiqueta …] [--coleccion …] [--salida resultado.json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_PUERTA = 75
MAX_PDF = 80 * 1024 * 1024
AGENTE = "biblioteca-studio/3 (ingresar)"

# el tipo de Zotero → (#item_type, #clasificador) de la enumeración de Calibre
TIPOS = {"journalArticle": ("Journal Article", "Artículo de revista"), "book": ("Book", "Libro"),
         "bookSection": ("Book Section", "Capítulo de libro"), "report": ("Report", "Informe técnico"),
         "document": ("Document", "Guía"), "webpage": ("Webpage", "Guía"), "statute": ("Statute", "Normativa"),
         "manuscript": ("Manuscript", "Documento de trabajo"), "preprint": ("Preprint", "Documento de trabajo"),
         "conferencePaper": ("Conference Paper", "Artículo de revista"), "computerProgram": ("Computer Program", "Guía")}
IDIOMAS = {"en": "eng", "es": "spa", "fr": "fra", "pt": "por", "de": "deu", "it": "ita"}

# ------------------------------------------------------------------ la clave de Better BibTeX (docs/citar.md §2)
# `auth.lower + shorttitle(3, 3) + year`: el apellido del primer autor (o el nombre entero de la institución) en minúsculas
# y sin tildes; las tres primeras palabras con contenido del título, cada una con mayúscula inicial; el año. Contrastada con
# las 4 687 claves de Zotero el 2026-11-18: coincide en el 85 %; el resto son claves fijadas con un título o un año de antes.
SALTAR = set("""a ab aboard about above across after against al along amid among an and anti around as at before behind below
beneath beside besides between beyond but by d da das de del dell dello dei degli della delle dem den der des despite die do
down du during ein eine einem einen einer eines el en et except excepting excluding following for from i il in inside into is
l la las le les like lo los minus near nor of off on onto opposite or outside over past per plus regarding round save since so
some than the through to toward towards under underneath unlike until up upon versus via von whilst with within without yet zu
zum y e un una unos unas u o""".split())
TRANS = {"æ": "ae", "Æ": "AE", "ø": "o", "Ø": "O", "ß": "ss", "œ": "oe", "Œ": "OE", "ł": "l", "Ł": "L", "đ": "d"}


def _ascii(t: str) -> str:
    t = "".join(TRANS.get(c, c) for c in str(t or "")).replace("°", "deg")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def clave_bbt(autores: list[dict], titulo: str, anio) -> str:
    a = autores[0] if autores else {}
    auth = re.sub(r"[^a-z0-9.\-+]", "", _ascii(a.get("corporativo") or a.get("apellido") or "").lower())
    palabras = [re.sub(r"[^A-Za-z0-9+]", "", w) for w in re.split(r"[\s/:;,!?¿¡()\[\]\"“”«»–—]+", _ascii(titulo)) if w]
    palabras = [w for w in palabras if len(w) > 1 and w.lower() not in SALTAR][:3]
    m = re.search(r"\d{4}", str(anio or ""))
    return auth + "".join(w[:1].upper() + w[1:] for w in palabras) + (m.group() if m else "")


def unica(clave: str, usadas: set[str]) -> str:
    """La clave, o con «a», «b»… si ya existe (como Better BibTeX)."""
    if clave not in usadas:
        return clave
    for letra in "abcdefghijklmnopqrstuvwxyz":
        if clave + letra not in usadas:
            return clave + letra
    raise ValueError(f"demasiadas obras con la clave {clave}")


# ------------------------------------------------------------------ utilidades
def _cargar(nombre: str, ruta: Path):
    if nombre in sys.modules:
        return sys.modules[nombre]
    s = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(s)
    sys.modules[nombre] = m
    s.loader.exec_module(m)
    return m


def _env():
    return _cargar("biblioteca_indice", RAIZ / "lib" / "indice.py")._env()


def _vi():
    return _cargar("biblioteca_verificar_ids", RAIZ / "lib" / "verificar_ids.py")


def _ro(db: Path) -> sqlite3.Connection:
    uri = Path(db).resolve().as_uri()
    c = sqlite3.connect(uri + "?mode=ro", uri=True)
    try:
        c.execute("select 1 from sqlite_master limit 1")
    except sqlite3.OperationalError:
        c.close()
        c = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True)
    return c


def _normal(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _ascii(t).lower()).strip()


def _titulo_corto(t: str) -> str:
    """El título sin subtítulo, normalizado (para cotejar «Complex surveys» con «Complex surveys: a guide…»)."""
    return _normal(re.split(r"[:.?]", t or "", maxsplit=1)[0])


def _autores_calibre(autores: list[dict]) -> str:
    """«Matthew J., Page & Joanne E., McKenzie»: la grafía de la biblioteca (nombre, apellido); una institución, tal cual."""
    # la coma separa el nombre del apellido en Calibre: un «Henry L., III» pasa a «Henry L. III»
    return " & ".join(a["corporativo"] if a.get("corporativo") else (f"{a['nombre'].replace(',', '')}, {a['apellido']}" if a.get("nombre") else a["apellido"])
                      for a in autores) or "Unknown"


def _slug(t: str, n: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _ascii(t).lower()).strip("-")
    return s[:n].rsplit("-", 1)[0] if len(s) > n else s


# ------------------------------------------------------------------ lo que ya existe
def existentes(env) -> dict:
    """Los DOI, ISBN y títulos de Calibre y de Zotero, y las claves de cita, para no duplicar (solo lectura)."""
    vi = _vi()
    cal = vi.de_calibre(Path(env.CALIBRE_DB))
    zot = vi.de_zotero(Path(env.ZOTERO_DB))
    autores: dict[int, str] = {}
    c = _ro(Path(env.CALIBRE_DB))
    try:
        for b, n in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id=l.author order by l.id"):
            autores.setdefault(b, n)
        rutas = {b: p for b, p in c.execute("select id, path from books")}
    finally:
        c.close()
    return {"cal": cal, "zot": zot, "autor_cal": autores, "rutas": rutas, "claves": set(zot)}


def _apellido(a: dict) -> str:
    return _normal(a.get("corporativo") or a.get("apellido") or "").split(" ")[-1] if (a.get("corporativo") or a.get("apellido")) else ""


def cotejar(obra: dict, ex: dict) -> dict:
    """{calibre: [ids], zotero: [{key, clave}]} de lo que ya es esta obra: el mismo DOI o ISBN, o el mismo título (sin
    subtítulo) con el mismo primer apellido."""
    vi = _vi()
    doi = vi.normalizar_doi(obra.get("doi"))
    isbn = vi.normalizar_isbn(obra.get("isbn"))[0] if obra.get("isbn") else ""
    corto = _titulo_corto(obra.get("titulo", ""))
    ap = _apellido((obra.get("autores") or [{}])[0])
    cal = []
    for b, d in ex["cal"].items():
        if (doi and d["doi"] == doi) or (isbn and d["isbn"] == isbn) or (
                corto and _titulo_corto(d["titulo"]) == corto and ap and ap in _normal(ex["autor_cal"].get(b, ""))):
            cal.append(b)
    zot = []
    for k, d in ex["zot"].items():
        if (doi and d["doi"] == doi) or (isbn and d["isbn"] == isbn) or (corto and _titulo_corto(d["titulo"]) == corto and ap and k.startswith(ap.replace(" ", "")[:4])):
            zot.append({"key": d["zotero_key"], "clave": k})
    return {"calibre": sorted(set(cal)), "zotero": zot}


# ------------------------------------------------------------------ el plan
def _esquema_zotero(db: Path) -> dict:
    c = _ro(db)
    try:
        validos: dict[str, set[str]] = {}
        for t, f in c.execute("select t.typeName, f.fieldName from itemTypeFields itf join itemTypes t on t.itemTypeID=itf.itemTypeID "
                              "join fields f on f.fieldID=itf.fieldID"):
            validos.setdefault(t, set()).add(f)
        base: dict[tuple[str, str], str] = {}
        for t, b, f in c.execute("select t.typeName, fb.fieldName, f.fieldName from baseFieldMappings m join itemTypes t on t.itemTypeID=m.itemTypeID "
                                 "join fields fb on fb.fieldID=m.baseFieldID join fields f on f.fieldID=m.fieldID"):
            base[(t, b)] = f
        roles = {t: {r for (r,) in c.execute("select ct.creatorType from itemTypeCreatorTypes x join itemTypes it on it.itemTypeID=x.itemTypeID "
                                             "join creatorTypes ct on ct.creatorTypeID=x.creatorTypeID where it.typeName=?", (t,))} for t in validos}
    finally:
        c.close()
    return {"validos": validos, "base": base, "roles": roles}


def fecha_zotero(v) -> str:
    """La fecha como la guarda Zotero en su base («2023-00-00 2023», «2024-03-05 2024-03-05»): la parte SQL y el texto
    original. Así queda desde el principio lo que Zotero reescribía al sincronizar (los 111 del 2026-11-18)."""
    t = str(v or "").strip().replace("/", "-").strip("-")
    if not t:
        return ""
    m = re.fullmatch(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", t)
    if m:
        a, mes, dia = m.group(1), int(m.group(2) or 0), int(m.group(3) or 0)
        return f"{a}-{mes:02d}-{dia:02d} {t}"
    m = re.search(r"\b(\d{4})\b", t)
    return f"{m.group(1) if m else '0000'}-00-00 {t}"


def campos_zotero(obra: dict, tipo: str, esquema: dict, clave: str, hoy: str) -> dict:
    """Los campos del ítem: los genéricos se traducen al campo de su tipo (publisher → institution en un informe, number →
    publicLawNumber en una norma…); lo que el tipo no admite va a Extra («DOI: …», «ISBN: …»), como hace Zotero. Además de
    los de `obras-flujo.json`, entiende los de un registro de `lib/importar_zotero.py` (fecha completa, título corto, serie,
    número del documento, páginas del libro, resumen, ISSN, el libro de un capítulo y el catálogo de origen)."""
    validos = esquema["validos"].get(tipo, set())
    genericos = {"title": obra.get("titulo"), "date": fecha_zotero(obra.get("fecha") or obra.get("anio")), "url": obra.get("url"),
                 "language": obra.get("idioma"), "DOI": obra.get("doi"), "ISBN": obra.get("isbn"),
                 "publicationTitle": obra.get("revista"), "publisher": obra.get("editorial"), "volume": obra.get("volumen"),
                 "issue": obra.get("numero"), "pages": obra.get("paginas"), "edition": obra.get("edicion"), "place": obra.get("lugar"),
                 "shortTitle": obra.get("titulo_corto"), "series": obra.get("serie"), "seriesNumber": obra.get("serie_numero"),
                 "number": obra.get("numero_doc"), "numPages": obra.get("num_paginas"), "abstractNote": obra.get("resumen"),
                 "ISSN": obra.get("issn"), "bookTitle": obra.get("libro"),
                 "citationKey": clave, "accessDate": f"{hoy} 00:00:00" if obra.get("url") else "",
                 "libraryCatalog": obra.get("catalogo") or ("Crossref" if obra.get("doi_cotejado") else ("Open Library" if obra.get("isbn") else ""))}
    campos, extra = {}, []
    for g, v in genericos.items():
        if v in (None, ""):
            continue
        f = g if g in validos else esquema["base"].get((tipo, g))
        if f and f in validos:
            campos[f] = v
        elif g in ("DOI", "ISBN"):
            extra.append(f"{g}: {v}")
        elif g == "publicationTitle" and "websiteTitle" in validos:
            campos["websiteTitle"] = v
        elif g == "series" and "seriesTitle" in validos:
            campos["seriesTitle"] = v
    if extra:
        campos["extra"] = "\n".join(extra)
    return campos


def plan(obras: list[dict], ex: dict, esquema: dict, etiqueta: str, coleccion: str, hoy: str | None = None) -> list[dict]:
    hoy = hoy or date.today().isoformat()
    usadas = set(ex["claves"])
    salida = []
    for o in obras:
        if not o.get("incluir", True):
            salida.append({"ref": o.get("ref", ""), "accion": "omitir", "motivo": o.get("motivo") or "no se incluye"})
            continue
        tipo = o.get("tipo_zotero") or "document"
        if tipo not in esquema["validos"]:
            tipo = "document"
        ya = cotejar(o, ex)
        clave_previa = ya["zotero"][0]["clave"] if ya["zotero"] else ""
        clave = clave_previa or unica(clave_bbt(o.get("autores") or [], o.get("titulo", ""), o.get("anio")), usadas)
        usadas.add(clave)
        item_type, clasificador = TIPOS.get(tipo, ("Document", "Guía"))
        vi = _vi()
        ids = [f"doi:{vi.normalizar_doi(o['doi'])}" if vi.normalizar_doi(o.get("doi")) else "",
               f"isbn:{vi.normalizar_isbn(o['isbn'])[0]}" if o.get("isbn") and vi.normalizar_isbn(o["isbn"])[1] else "",
               f"url:{o['url']}" if o.get("url") else ""]
        rol = "author" if "author" in esquema["roles"].get(tipo, {"author"}) else sorted(esquema["roles"].get(tipo) or ["author"])[0]
        creadores = [{"apellido": a["corporativo"], "nombre": "", "modo": 1, "rol": a.get("rol") or rol} if a.get("corporativo")
                     else {"apellido": a["apellido"], "nombre": a.get("nombre") or "", "modo": 0, "rol": a.get("rol") or rol}
                     for a in o.get("autores") or []]
        materias = [m for m in (o.get("materias") or []) if m]
        p = {"ref": o.get("ref", ""), "titulo": o.get("titulo", ""), "clave": clave, "tipo_zotero": tipo,
             "calibre_existente": ya["calibre"][0] if ya["calibre"] else None, "zotero_existente": ya["zotero"][0]["key"] if ya["zotero"] else "",
             "duplicados": ya, "pdf": (o.get("pdf_oa") or {}).get("url") or "",
             "calibre": {"title": o.get("titulo", ""), "authors": _autores_calibre(o.get("autores") or []),
                         "publisher": o.get("revista") or o.get("editorial") or "", "pubdate": str(o.get("anio") or ""),
                         "identifiers": ",".join(x for x in ids if x), "tags": ", ".join(materias + [etiqueta]),
                         "languages": IDIOMAS.get(str(o.get("idioma") or "en")[:2], "eng"), "#item_type": item_type,
                         "#clasificador": clasificador},
             "zotero": {"tipo": tipo, "campos": campos_zotero(o, tipo, esquema, clave, hoy), "creadores": creadores,
                        "etiquetas": [etiqueta], "coleccion": coleccion}}
        p["accion"] = ("enlazar" if ya["calibre"] and ya["zotero"] else "zotero" if ya["calibre"] else "calibre" if ya["zotero"] else "nueva")
        salida.append(p)
    return salida


def resumen(planes: list[dict]) -> dict:
    cuenta: dict[str, int] = {}
    for p in planes:
        cuenta[p["accion"]] = cuenta.get(p["accion"], 0) + 1
    cuenta["con_pdf"] = sum(1 for p in planes if p.get("pdf") and p["accion"] in ("nueva", "calibre"))
    return cuenta


# ------------------------------------------------------------------ aplicar
def _app_abierta(patron: str) -> bool:
    return _cargar("biblioteca_escribir", RAIZ / "lib" / "escribir.py")._app_abierta(patron)


def bajar(url: str, destino: Path) -> dict:
    """El PDF de la URL dada a `destino`: solo si responde un PDF (`%PDF`) de menos de 80 MB. {sha256, bytes} o {error}."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/pdf,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            datos = r.read(MAX_PDF + 1)
    except Exception as e:  # noqa: BLE001 — una descarga fallida se dice y la obra entra sin archivo
        return {"error": f"{type(e).__name__}: {e}"}
    if len(datos) > MAX_PDF:
        return {"error": "más de 80 MB"}
    if not datos.startswith(b"%PDF"):
        return {"error": "no es un PDF (la sede respondió otra cosa)"}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return {"sha256": hashlib.sha256(datos).hexdigest(), "bytes": len(datos)}


def es_la_obra(pdf: Path, titulo: str, anio="") -> str:
    """«» si las primeras hojas del PDF traen el título de la obra (y su año, si se da); si no, por qué no: la sede pudo
    servir otra obra u otra versión (Unpaywall daba PDF de otras obras para dos libros de Mayer, 2026-11-18)."""
    import subprocess
    r = subprocess.run(["pdftotext", "-l", "4", "-q", str(pdf), "-"], capture_output=True, text=True, errors="replace", timeout=120)
    texto = r.stdout or ""
    if not texto.strip():
        return "el PDF no tiene texto para comprobar que sea la obra"
    if _vi().mismo_titulo(re.split(r"[:?]", titulo, maxsplit=1)[0], texto[:20000]) is not True:
        palabras = _vi()._palabras(re.split(r"[:?]", titulo, maxsplit=1)[0])
        if not palabras or sum(w in _normal(texto) for w in palabras) / len(palabras) < 0.8:
            return "el PDF no trae el título de la obra en sus primeras hojas"
    # otra versión: la portada lleva otro año (una preimpresión de arXiv, una traducción anterior) y el citado no aparece;
    # un documento sin año en la portada (DCAS v1.0) no se descarta por eso
    a = str(anio or "")[:4]
    if a.isdigit() and a not in texto[:40000]:
        otros = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", texto[:1500])) - {a})
        if otros:
            return f"el PDF es de otra versión: su portada dice {', '.join(otros)} y la obra citada es de {a}"
    return ""


def _fecha_calibre(anio: str) -> str:
    m = re.search(r"\d{4}", anio or "")
    return f"{m.group()}-01-01 05:00:00+00:00" if m else ""


def _id_anadido(salida: str) -> str:
    m = re.search(r"(?:Added book ids?|ID de libros? a[ñn]adidos?|ids?)\s*:\s*([0-9]+)", salida, re.I)
    return m.group(1) if m else ""


def calibre_anadir(E, biblioteca: Path, p: dict, archivo: Path | None) -> str:
    """Añade el registro (con su archivo o vacío) y le pone sus metadatos en una llamada; devuelve su id."""
    c = p["calibre"]
    args = ["add", "--title", c["title"], "--authors", c["authors"], "--tags", c["tags"], "--languages", c["languages"]]
    args += ["--automerge", "ignore", str(archivo)] if archivo else ["--empty"]
    r = E.calibredb(biblioteca, *args)
    bid = _id_anadido(r.stdout + r.stderr)
    if not bid:
        raise RuntimeError(f"la orden add de Calibre no devolvió id: {(r.stdout + r.stderr).strip()[:200]}")
    campos = ["--field", f"#item_type:{c['#item_type']}", "--field", f"#clasificador:{c['#clasificador']}"]
    if c["publisher"]:
        campos += ["--field", f"publisher:{c['publisher']}"]
    if _fecha_calibre(c["pubdate"]):
        campos += ["--field", f"pubdate:{_fecha_calibre(c['pubdate'])}"]
    if c["identifiers"]:
        campos += ["--field", f"identifiers:{c['identifiers']}"]
    sm = E.calibredb(biblioteca, "set_metadata", bid, *campos)
    if sm.returncode:
        print(f"  [WARN] set_metadata {bid}: {(sm.stdout + sm.stderr).strip()[:200]}", file=sys.stderr)
    return bid


def _pdf_de(env, bid: int) -> str:
    """`attachments:<carpeta>/<archivo>.pdf` del PDF del libro en Calibre (lo que guarda Zotero), o «»."""
    c = _ro(Path(env.CALIBRE_DB))
    try:
        fila = c.execute("select b.path, d.name from books b join data d on d.book=b.id where b.id=? and d.format='PDF'", (bid,)).fetchone()
    finally:
        c.close()
    return f"attachments:{fila[0]}/{fila[1]}.pdf" if fila else ""


def _ficha_catalogacion(bid: str, p: dict, origen: str, sha: str, zkey: str, hoy: str, lote: str) -> tuple[str, str]:
    c = p["calibre"]
    a0 = (c["authors"].split(" & ")[0].split(", ")[-1] if c["authors"] else "anonimo")
    nombre = f"{bid}_flujo-{_slug(a0, 24)}_{c['pubdate'][:4] or 'sf'}_{_slug(p['titulo'], 48)}.md"
    texto = f"""---
tipo: ficha_catalogacion
calibre_id: {bid}
zotero_key: {zkey}
clave_bibtex: {p['clave']}
proyecto: prompts
verificacion:
  estado: pendiente
  metodo:
  fecha:
---

> Ficha de catalogación de «{p['titulo']}». Obra del flujo de producción de conocimiento (prompts/00 metodo/FLUJO_DE_CONOCIMIENTO.md, {hoy}), ingresada por `lib/ingresar.py` (lote `{lote}`): metadatos cotejados en {'Crossref' if 'doi:' in c['identifiers'] else 'Open Library' if 'isbn:' in c['identifiers'] else 'su sede oficial'}. Confianza: **alta**.

## Origen

{f"`{origen}` · SHA-256 `{sha[:16]}…` · {p['pdf']}" if origen else "Sin archivo: la obra no tiene un PDF de acceso abierto en su sede oficial; queda el registro con sus metadatos e identificadores."}

## Zotero
| Campo | Valor |
|---|---|
| Item Type | {p['tipo_zotero']} |
| Citation Key | {p['clave']} |
| Collection | {p['zotero']['coleccion']} |
| Tags | {', '.join(p['zotero']['etiquetas'])} |

## Calibre
| Campo | Valor |
|---|---|
| Title | {c['title']} |
| Authors | {c['authors']} |
| Publisher | {c['publisher']} |
| Pubdate | {c['pubdate']} |
| Identifiers | {c['identifiers']} |
| Tags | {c['tags']} |
| #clasificador | {c['#clasificador']} |
| #item_type | {c['#item_type']} |

## Notas
- Referencia del fundamento: {p['ref'][:300]}
"""
    return nombre, texto


def aplicar(planes: list[dict], env, lote: str, hoy: str | None = None) -> list[dict]:
    """Escribe por la puerta: los PDF, Calibre, Zotero y el `#zotero_key`. Devuelve una fila por obra."""
    hoy = hoy or date.today().isoformat()
    E = _cargar("biblioteca_escribir", RAIZ / "lib" / "escribir.py")
    if _app_abierta(r"^calibre") or _app_abierta(r"^zotero"):
        raise SystemExit(SALIDA_PUERTA)
    sys.path.insert(0, str(RAIZ / "lib"))
    Z = _cargar("escribir_zotero", RAIZ / "lib" / "escribir_zotero.py")
    biblioteca = Path(env.BIBLIOTECA_DIR)
    # INGRESAR_DATOS: dónde van la entrada, las fichas y los registros (el repo; un temporal en el ensayo sobre copias)
    datos = Path(os.environ.get("INGRESAR_DATOS") or RAIZ)
    entrada = datos / "entrada" / lote
    hechos = []
    # 1. los PDF de acceso abierto
    archivos: dict[str, dict] = {}
    for p in planes:
        if p["accion"] in ("nueva", "calibre") and p.get("pdf"):
            destino = entrada / f"{p['clave']}.pdf"
            r = bajar(p["pdf"], destino)
            if not r.get("error"):
                motivo = es_la_obra(destino, p["titulo"], p["calibre"]["pubdate"])
                if motivo:
                    destino.unlink(missing_ok=True)
                    r = {"error": motivo}
            archivos[p["clave"]] = {**r, "ruta": destino} if not r.get("error") else r
            print(f"  PDF {p['clave']}: {'✓ ' + str(r['bytes']) + ' bytes' if not r.get('error') else '✗ ' + r['error']}")
    # 2. Calibre: los registros que faltan
    ids: dict[str, str] = {}
    with E.puerta("ingresar", calibre=biblioteca):
        for p in planes:
            if p["accion"] not in ("nueva", "calibre"):
                continue
            a = archivos.get(p["clave"]) or {}
            ids[p["clave"]] = calibre_anadir(E, biblioteca, p, a.get("ruta") if not a.get("error") else None)
            print(f"  Calibre {ids[p['clave']]}: {p['titulo'][:70]}")
        # lo que ya estaba: solo la etiqueta (sumada a las suyas)
        c = _ro(Path(env.CALIBRE_DB))
        try:
            for p in planes:
                if p["accion"] in ("zotero", "enlazar") and p.get("calibre_existente"):
                    actuales = [t for (t,) in c.execute("select t.name from books_tags_link l join tags t on t.id=l.tag where l.book=?",
                                                        (p["calibre_existente"],))]
                    etiqueta = p["zotero"]["etiquetas"][0]
                    if etiqueta not in actuales:
                        E.calibredb(biblioteca, "set_metadata", str(p["calibre_existente"]), "--field", "tags:" + ", ".join(actuales + [etiqueta]))
                    ids[p["clave"]] = str(p["calibre_existente"])
        finally:
            c.close()
        E.calibredb(biblioteca, "backup_metadata")
    # 3. Zotero: los ítems que faltan, la etiqueta y la colección
    zkeys: dict[str, str] = {}
    zdb = Path(env.ZOTERO_DB)
    with E.puerta("ingresar", zotero=zdb):
        con = Z.conexion_zotero(zdb)
        try:
            cur = con.cursor()
            libreria = cur.execute("SELECT libraryID FROM libraries WHERE type='user'").fetchone()[0]
            col = Z.z_coleccion(cur, libreria, planes[0]["zotero"]["coleccion"] if planes else "Flujo de conocimiento")
            for p in planes:
                if p["accion"] == "omitir":
                    continue
                if p["accion"] in ("nueva", "zotero"):
                    item, key = Z.z_nuevo_item(cur, libreria, p["zotero"]["tipo"], p["zotero"]["campos"], p["zotero"]["creadores"])
                    pdf = _pdf_de(env, int(ids[p["clave"]])) if p["clave"] in ids else ""
                    if pdf:
                        Z.z_adjunto_enlazado(cur, libreria, item, pdf, "PDF")
                else:
                    key = p["zotero_existente"]
                    item = cur.execute("SELECT itemID FROM items WHERE key=? AND libraryID=?", (key, libreria)).fetchone()[0]
                Z.z_etiquetar(cur, item, p["zotero"]["etiquetas"])
                Z.z_en_coleccion(cur, col, item)
                zkeys[p["clave"]] = key
            con.commit()
            bien = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not con.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            con.close()
        if not bien:
            raise RuntimeError("zotero.sqlite no pasó integrity_check o foreign_key_check: restaure el respaldo de la puerta")
    # 4. Calibre: el puente (#zotero_key)
    with E.puerta("ingresar", calibre=biblioteca):
        for p in planes:
            if p.get("clave") in ids and p.get("clave") in zkeys:
                # `#zotero_key` es una columna de texto largo: `set_metadata --field` no la admite, `set_custom` sí
                r = E.calibredb(biblioteca, "set_custom", "zotero_key", ids[p["clave"]], zkeys[p["clave"]])
                if r.returncode:
                    print(f"  [WARN] #zotero_key {ids[p['clave']]}: {(r.stdout + r.stderr).strip()[:200]}", file=sys.stderr)
        E.calibredb(biblioteca, "backup_metadata")
    # 5. las fichas y los registros
    fichas = datos / "catalogacion" / "fichas"
    fichas.mkdir(parents=True, exist_ok=True)
    filas_cat, filas_led = [], []
    for p in planes:
        if p["accion"] == "omitir":
            hechos.append({"ref": p["ref"], "accion": "omitir"})
            continue
        bid = ids.get(p["clave"], "")
        a = archivos.get(p["clave"]) or {}
        origen = (str(Path(a["ruta"]).relative_to(datos.parent)) if Path(a["ruta"]).is_relative_to(datos.parent) else str(a["ruta"])) if a.get("ruta") else ""
        if p["accion"] in ("nueva", "calibre") and bid:
            nombre, texto = _ficha_catalogacion(bid, p, origen, a.get("sha256", ""), zkeys.get(p["clave"], ""), hoy, lote)
            (fichas / nombre).write_text(texto, encoding="utf-8")
            c = p["calibre"]
            filas_cat.append([bid, c["authors"], c["title"], p["tipo_zotero"], c["#clasificador"], c["publisher"], c["pubdate"], c["identifiers"],
                              {"eng": "English", "spa": "Spanish"}.get(c["languages"], c["languages"]), c["tags"], "alta",
                              f"ingresar {hoy} ({lote}); flujo de conocimiento; " + ("PDF de acceso abierto de " + p["pdf"] if origen else "sin archivo: registro con sus identificadores")])
            if origen:
                filas_led.append([hoy, a["sha256"], origen, c["title"], c["authors"], p["tipo_zotero"], c["#clasificador"], c["pubdate"],
                                  c["publisher"], c["tags"], bid, "", zkeys.get(p["clave"], ""), "catalogado"])
        hechos.append({"ref": p["ref"], "titulo": p["titulo"], "accion": p["accion"], "calibre_id": int(bid) if bid else None,
                       "zotero_key": zkeys.get(p["clave"], ""), "clave": p["clave"], "pdf": bool(origen),
                       "pdf_error": a.get("error", "") if p.get("pdf") else ""})
    if filas_cat:
        with open(datos / "catalogacion" / "resumen_catalogacion.tsv", "a", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(filas_cat)
    if filas_led:
        (datos / "ingesta").mkdir(parents=True, exist_ok=True)
        with open(datos / "ingesta" / "ingesta.tsv", "a", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(filas_led)
    return hechos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    for n in ("plan", "aplicar"):
        s = sub.add_parser(n)
        s.add_argument("obras")
        s.add_argument("--etiqueta", default="flujo-de-conocimiento")
        s.add_argument("--coleccion", default="Flujo de conocimiento")
        s.add_argument("--json", action="store_true")
        s.add_argument("--salida", default="")
        if n == "aplicar":
            s.add_argument("--lote", required=True)
    a = ap.parse_args(argv)
    obras = json.loads(Path(a.obras).read_text(encoding="utf-8"))
    env = _env()
    ex = existentes(env)
    planes = plan(obras, ex, _esquema_zotero(Path(env.ZOTERO_DB)), a.etiqueta, a.coleccion)
    if a.orden == "plan":
        r = {"resumen": resumen(planes), "obras": planes, "calibre_abierto": _app_abierta(r"^calibre"),
             "zotero_abierto": _app_abierta(r"^zotero")}
        if a.salida:
            Path(a.salida).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(r, ensure_ascii=False) if a.json else
              f"[simulación] {len(planes)} obras · " + " · ".join(f"{k} {n}" for k, n in r["resumen"].items())
              + ("\n  Calibre abierto: aplicar saldría 75" if r["calibre_abierto"] else "") + ("\n  Zotero abierto: aplicar saldría 75" if r["zotero_abierto"] else ""))
        return 0
    try:
        hechos = aplicar(planes, env, a.lote)
    except SystemExit as e:
        if e.code == SALIDA_PUERTA:
            print("[puerta] Calibre o Zotero abiertos: no se escribió nada; reintente con los dos cerrados (75)", file=sys.stderr)
            return SALIDA_PUERTA
        raise
    if a.salida:
        Path(a.salida).write_text(json.dumps(hechos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(hechos, ensure_ascii=False) if a.json else f"✓ {len(hechos)} obras · " + " · ".join(
        f"{k} {sum(1 for h in hechos if h['accion'] == k)}" for k in ("nueva", "calibre", "zotero", "enlazar", "omitir")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
