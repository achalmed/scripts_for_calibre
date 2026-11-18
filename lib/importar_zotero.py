#!/usr/bin/env python3
"""lib/importar_zotero.py — fusionar e importar a Zotero: uno o varios RIS, BibTeX o CSL-JSON, sin duplicar (decisiones §2.15).

Objetivo: que lo que Zotero recibía importando a mano los RIS de `ingesta/salida_ris/` (Archivo › Importar) entre por la
  puerta, como el ingreso del flujo de conocimiento (`lib/ingresar.py`, §9.10): sin duplicar lo que ya está, con el adjunto
  enlazado al archivo de Calibre desde el principio (§2.14), en una colección por lote y con el puente `#zotero_key`.
Método: lee los archivos (RIS por `TY  -`, BibTeX por `@tipo{`, CSL-JSON por su lista de objetos), los FUSIONA (un mismo
  registro en dos archivos es una sola obra: por DOI, ISBN, id de Calibre o título normalizado + año + primer apellido) y
  coteja cada obra, en SOLO LECTURA, con Calibre (`ID - calibre:N`, la carpeta «(N)/» del archivo, DOI, ISBN, título y
  año) y con Zotero (la `#zotero_key` del libro, un adjunto que enlaza su carpeta, DOI, ISBN, clave de cita, título y año).
  Cada obra queda NUEVA (falta en Zotero), YA ESTABA (y no se toca: Zotero manda en metadatos) o DUDOSA (un parecido que
  no basta: el mismo título con otro año o autor, un ítem en la papelera, un id de Calibre que es de otra obra, un tipo
  que Calibre ya cambió); las dudosas no se crean salvo `--incluir-dudosos`. Simula por defecto y deja el informe (JSON) y
  el RIS fusionado de lo que falta. Con `--aplicar`, con Zotero cerrado (y Calibre, si hay puentes que escribir), abre la
  puerta de Zotero (candado y respaldo verificado), crea cada ítem con las primitivas `z_*` y el mapeo de campos de
  `lib/ingresar.py` (los campos válidos de su tipo; DOI e ISBN a Extra si el tipo no los lleva), su clave de cita, sus
  etiquetas, la colección del lote y el adjunto enlazado (`linkMode=2`, `attachments:<ruta en Calibre>`); después, la puerta
  de Calibre escribe `#zotero_key` en cada libro (`set_custom`).
Fundamento: normativa 9.6 (primero en la biblioteca, después la cita); docs/citar.md y decisiones §1.6 y §1.7 (Zotero manda
  en citas y metadatos: lo que ya existe no se reescribe); §2.5 (una sola puerta); §2.14 (el linkMode nace bien).
Límite: no crea registros en Calibre (eso es catalogar: `ingesta`, `lib/ingresar.py`); una obra sin libro en Calibre entra
  en Zotero sin archivo. El lector BibTeX entiende lo común (llaves, comillas, `and`, acentos de LaTeX), no macros @string.
  Con Zotero o Calibre abiertos, o un candado ocupado, sale 75 sin escribir.

    python3 lib/importar_zotero.py ARCHIVO… [--coleccion NOMBRE] [--etiqueta X] [--ids 1,2] [--excluir-ids 3,4]
                                   [--incluir-dudosos] [--salida DIR] [--json] [--aplicar]
Salida: 0 · 1 fallo · 2 uso · 75 aplicación abierta o candado ocupado.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_PUERTA = 75
SUITE = "importar_zotero"


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


def _ro(db) -> sqlite3.Connection:
    return _ing()._ro(Path(db))


def _normal(t) -> str:
    return _ing()._normal(str(t or ""))


def _corto(t) -> str:
    """El título sin subtítulo, normalizado. Corta en «:», «?» o un punto seguido de espacio: «Decreto Legislativo N.° 1621.
    Decreto…» da «decreto legislativo n 1621» (cortar en cualquier punto daba «decreto legislativo n» a todas las normas)."""
    return _normal(re.split(r"[:?]|\.\s", str(t or ""), maxsplit=1)[0])


def _anio(v) -> str:
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", str(v or ""))
    return m.group(1) if m else ""


def _apellido(autores: list[dict]) -> str:
    a = (autores or [{}])[0]
    t = _normal(a.get("corporativo") or a.get("apellido") or "")
    return t.split(" ")[-1] if t else ""


# ================================================================== lectores
# Un registro: {origen, tipo, titulo, autores [{apellido, nombre} | {corporativo}], editores, fecha, revista, libro,
# editorial, lugar, doi, isbn, issn, url, idioma, volumen, numero (fascículo), numero_doc (número de la ley o del informe),
# paginas, num_paginas, edicion, serie, serie_numero, titulo_corto, resumen, etiquetas, calibre_id, clave, archivos, catalogo}

TY_ZOTERO = {"JOUR": "journalArticle", "EJOUR": "journalArticle", "JFULL": "journalArticle", "BOOK": "book", "EBOOK": "book",
             "EDBOOK": "book", "CHAP": "bookSection", "ECHAP": "bookSection", "RPRT": "report", "GEN": "document",
             "STAT": "statute", "THES": "thesis", "MANSCPT": "manuscript", "UNPB": "manuscript", "SLIDE": "presentation",
             "MGZN": "magazineArticle", "ELEC": "webpage", "WEB": "webpage", "CPAPER": "conferencePaper", "CONF": "conferencePaper",
             "NEWS": "newspaperArticle", "MAP": "map", "DATA": "dataset", "MPCT": "film", "PAT": "patent", "ICOMM": "interview",
             "PCOMM": "letter", "CASE": "case", "BILL": "bill", "ENCYC": "encyclopediaArticle", "DICT": "dictionaryEntry",
             "BLOG": "blogPost", "SOUND": "audioRecording", "COMP": "computerProgram", "VIDEO": "videoRecording", "ART": "artwork"}
BIB_ZOTERO = {"article": "journalArticle", "book": "book", "booklet": "book", "manual": "book", "inbook": "bookSection",
              "incollection": "bookSection", "inproceedings": "conferencePaper", "conference": "conferencePaper",
              "techreport": "report", "report": "report", "phdthesis": "thesis", "mastersthesis": "thesis", "thesis": "thesis",
              "misc": "document", "online": "webpage", "electronic": "webpage", "www": "webpage", "unpublished": "manuscript",
              "legislation": "statute", "law": "statute", "legal": "statute", "dataset": "dataset", "software": "computerProgram"}
CSL_ZOTERO = {"article-journal": "journalArticle", "article-magazine": "magazineArticle", "article-newspaper": "newspaperArticle",
              "book": "book", "chapter": "bookSection", "paper-conference": "conferencePaper", "report": "report",
              "thesis": "thesis", "legislation": "statute", "bill": "bill", "legal_case": "case", "webpage": "webpage",
              "post-weblog": "blogPost", "manuscript": "manuscript", "dataset": "dataset", "software": "computerProgram",
              "document": "document", "article": "document", "entry-encyclopedia": "encyclopediaArticle",
              "entry-dictionary": "dictionaryEntry", "map": "map", "motion_picture": "film", "patent": "patent"}
PAGINAS_DEL_LIBRO = {"book", "thesis", "manuscript"}


def _persona(texto: str) -> dict:
    """«Apellido, Nombre» → persona; sin coma → una institución (como el AU que escribe `biblioteca.autor_ris`)."""
    t = (texto or "").strip()
    if "," in t:
        ap, nom = [x.strip() for x in t.split(",", 1)]
        return {"apellido": ap, "nombre": nom} if ap else {"corporativo": nom}
    return {"corporativo": t}


def _identificadores(valores) -> tuple[str, str]:
    """(ISBN-13, ISSN) de una lista de SN / isbn / issn."""
    vi = _vi()
    isbn = issn = ""
    for v in valores:
        for parte in re.split(r"[\s,;]+", str(v or "")):
            if not parte:
                continue
            n, ok = vi.normalizar_isbn(parte)
            if ok and not isbn:
                isbn = n
            elif re.fullmatch(r"\d{4}-?\d{3}[\dXx]", parte) and not issn:
                issn = parte[:4] + "-" + parte[-4:].upper()
    return isbn, issn


def _id_de_ruta(ruta: str) -> int | None:
    m = re.search(r"\((\d+)\)/[^/]*$", ruta or "")
    return int(m.group(1)) if m else None


def _fecha(v: str) -> str:
    """«2024/01/01» → «2024-01-01»; «2024///» → «2024»; «2024/05» → «2024-05»."""
    partes = [p for p in re.split(r"[/-]", str(v or "").strip()) if p.strip()]
    if partes and re.fullmatch(r"\d{4}", partes[0]):
        return "-".join(p.zfill(2) if i else p for i, p in enumerate(partes[:3]) if p.isdigit())
    return str(v or "").strip()


def leer_ris(texto: str, origen: str) -> list[dict]:
    regs, actual = [], None
    for linea in texto.lstrip("\ufeff").splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  -(?: ?(.*))?$", linea.rstrip("\r"))
        if not m:
            continue
        tag, val = m.group(1), (m.group(2) or "").strip()
        if tag == "TY":
            actual = {"TY": [val]}
        elif tag == "ER":
            if actual:
                regs.append(_de_ris(actual, origen))
            actual = None
        elif actual is not None and val:
            actual.setdefault(tag, []).append(val)
    return [r for r in regs if r["titulo"]]


def _de_ris(c: dict, origen: str) -> dict:
    uno = lambda *tags: next((v for t in tags for v in c.get(t, []) if v), "")
    tipo = TY_ZOTERO.get(uno("TY").upper(), "document")
    de_calibre = "Calibre" in c.get("DB", [])         # el RIS de `ingesta/main.sh zotero` (biblioteca.ris)
    isbn, issn = _identificadores(c.get("SN", []))
    r = {"origen": origen, "tipo": tipo, "titulo": uno("TI", "T1", "CT"),
         "autores": [_persona(a) for a in c.get("AU", []) + c.get("A1", [])],
         "editores": [_persona(a) for a in c.get("ED", []) + (c.get("A2", []) if tipo == "bookSection" else [])],
         "fecha": _fecha(uno("DA", "PY", "Y1")), "editorial": uno("PB"), "lugar": uno("CY", "PP"), "doi": uno("DO"),
         "isbn": isbn, "issn": issn, "url": uno("UR"), "idioma": uno("LA"), "volumen": uno("VL"), "numero": uno("IS"),
         "edicion": uno("ET"), "titulo_corto": uno("ST"), "resumen": " ".join(c.get("AB", []) + c.get("N2", [])),
         "etiquetas": [k for v in c.get("KW", []) for k in [v.strip()] if k], "archivos": c.get("L1", []),
         "catalogo": uno("DB"), "clave": "", "calibre_id": None}
    sp, ep = uno("SP"), uno("EP")
    if tipo in PAGINAS_DEL_LIBRO and not ep:
        r["num_paginas"] = sp
    elif sp:
        r["paginas"] = f"{sp}-{ep}" if ep else sp
    if de_calibre:
        # Calibre guarda solo el año como «AAAA-01-01»: el 1 de enero de ese RIS no es una fecha, es un año
        r["fecha"] = re.sub(r"^(\d{4})-01-01$", r"\1", r["fecha"])
        # y la revista de un artículo, en la editorial (como la escribe lib/ingresar.py)
        if tipo in ("journalArticle", "magazineArticle", "newspaperArticle") and not uno("JO", "JF"):
            r["revista"], r["editorial"] = r["editorial"], ""
    t2, m1 = uno("T2", "JO", "JF", "BT"), uno("M1")
    if tipo == "statute":
        r["numero_doc"] = m1
    elif de_calibre:                                   # en ese RIS, T2 y M1 son la serie de Calibre y su índice
        r["serie"], r["serie_numero"] = t2, m1
    elif tipo in ("journalArticle", "magazineArticle", "newspaperArticle", "conferencePaper"):
        r["revista"] = uno("JO", "JF", "T2") or r.get("revista", "")
    elif tipo == "bookSection":
        r["libro"] = uno("T2", "BT")
    else:
        r["serie"] = uno("T3", "T2")
        r["numero_doc"] = m1
    for v in c.get("ID", []):
        m = re.fullmatch(r"calibre:(\d+)", v.strip())
        if m:
            r["calibre_id"] = int(m.group(1))
    if r["calibre_id"] is None:
        r["calibre_id"] = next((i for i in map(_id_de_ruta, r["archivos"]) if i), None)
    return r


# ------------------------------------------------------------------ BibTeX
ACENTOS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "c": "\u0327", "=": "\u0304", "v": "\u030c"}


def _latex(t: str) -> str:
    """Lo común de LaTeX a texto: los acentos (\\'e, {\\'\\i}, \\~n, \\c{c}), \\&, \\%, -- y las llaves."""
    t = re.sub(r"\\([`'^\"~=]|[cv](?=[{\s]))\s*\{?\\?([A-Za-z])\}?",
               lambda m: unicodedata.normalize("NFC", ("i" if m.group(2) == "i" else m.group(2)) + ACENTOS[m.group(1)]), t)
    t = t.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("\\$", "$").replace("---", "—").replace("--", "–")
    t = re.sub(r"\\(?:emph|textit|textbf|textsc)\s*", "", t)
    return re.sub(r"\s+", " ", t.replace("{", "").replace("}", "")).strip()


def _bloque(texto: str, i: int, abre: str, cierra: str) -> int:
    """El índice tras el `cierra` que equilibra el `abre` en texto[i] (llaves anidadas)."""
    nivel = 0
    for j in range(i, len(texto)):
        if texto[j] == abre:
            nivel += 1
        elif texto[j] == cierra:
            nivel -= 1
            if nivel == 0:
                return j + 1
    return len(texto)


def _campos_bib(cuerpo: str) -> dict:
    campos, i = {}, 0
    while i < len(cuerpo):
        m = re.compile(r"\s*,?\s*([A-Za-z][\w:-]*)\s*=\s*").match(cuerpo, i)
        if not m:
            break
        nombre, i, partes = m.group(1).lower(), m.end(), []
        while i < len(cuerpo):
            if cuerpo[i] == "{":
                fin = _bloque(cuerpo, i, "{", "}")
                partes.append(cuerpo[i + 1:fin - 1])
            elif cuerpo[i] == '"':
                fin = i + 1
                nivel = 0
                while fin < len(cuerpo) and not (cuerpo[fin] == '"' and nivel == 0):
                    nivel += {"{": 1, "}": -1}.get(cuerpo[fin], 0)
                    fin += 1
                partes.append(cuerpo[i + 1:fin])
                fin += 1
            else:
                mm = re.compile(r"[^,#\s]+").match(cuerpo, i)
                fin = mm.end() if mm else i + 1
                partes.append(mm.group() if mm else "")
            i = fin
            mm = re.compile(r"\s*#\s*").match(cuerpo, i)
            if not mm:
                break
            i = mm.end()
        campos[nombre] = "".join(partes)
    return campos


def _nombres_bib(v: str) -> list[dict]:
    salida, nivel, actual, i = [], 0, "", 0
    while i < len(v):                                   # « and » solo fuera de llaves
        if v[i] in "{}":
            nivel += 1 if v[i] == "{" else -1
        if nivel == 0 and re.compile(r"\s+and\s+", re.I).match(v, i):
            salida.append(actual)
            actual = ""
            i = re.compile(r"\s+and\s+", re.I).match(v, i).end()
            continue
        actual += v[i]
        i += 1
    salida.append(actual)
    personas = []
    for n in (s.strip() for s in salida if s.strip()):
        if n.startswith("{") and n.endswith("}") and _bloque(n, 0, "{", "}") == len(n):
            personas.append({"corporativo": _latex(n)})
        elif "," in n:
            partes = [p.strip() for p in n.split(",")]
            personas.append({"apellido": _latex(partes[0]), "nombre": _latex(partes[-1] if len(partes) > 1 else "")})
        else:
            palabras = _latex(n).split()
            personas.append({"apellido": palabras[-1], "nombre": " ".join(palabras[:-1])} if len(palabras) > 1
                            else {"corporativo": " ".join(palabras)})
    return personas


def leer_bib(texto: str, origen: str) -> list[dict]:
    regs = []
    for m in re.finditer(r"@(\w+)\s*\{", texto):
        tipo_bib = m.group(1).lower()
        if tipo_bib in ("comment", "string", "preamble"):
            continue
        fin = _bloque(texto, m.end() - 1, "{", "}")
        cuerpo = texto[m.end():fin - 1]
        clave, _, resto = cuerpo.partition(",")
        f = {k: _latex(v) if k not in ("author", "editor") else v for k, v in _campos_bib(resto).items()}
        tipo = BIB_ZOTERO.get(tipo_bib, "document")
        isbn, issn = _identificadores([f.get("isbn", ""), f.get("issn", "")])
        r = {"origen": origen, "tipo": tipo, "titulo": f.get("title", ""), "autores": _nombres_bib(f.get("author", "")),
             "editores": _nombres_bib(f.get("editor", "")), "fecha": _fecha(f.get("date") or f.get("year") or ""),
             "editorial": f.get("publisher") or f.get("institution") or f.get("organization") or f.get("school") or "",
             "lugar": f.get("address") or f.get("location") or "", "doi": f.get("doi", ""), "isbn": isbn, "issn": issn,
             "url": f.get("url", ""), "idioma": f.get("langid") or f.get("language") or "", "volumen": f.get("volume", ""),
             "edicion": f.get("edition", ""), "serie": f.get("series", ""), "titulo_corto": f.get("shorttitle", ""),
             "resumen": f.get("abstract", ""), "revista": f.get("journaltitle") or f.get("journal") or "",
             "libro": f.get("booktitle", ""), "etiquetas": [k.strip() for k in re.split(r"[,;]", f.get("keywords", "")) if k.strip()],
             "archivos": [], "catalogo": "", "clave": clave.strip(), "calibre_id": None}
        numero = f.get("number") or f.get("issue") or ""
        r["numero_doc" if tipo in ("report", "statute", "manuscript") else "numero"] = numero
        if tipo in PAGINAS_DEL_LIBRO and f.get("pagetotal"):
            r["num_paginas"] = f["pagetotal"]
        elif f.get("pages"):
            r["paginas"] = f["pages"].replace("–", "-")
        if r["titulo"]:
            regs.append(r)
    return regs


# ------------------------------------------------------------------ CSL-JSON
def _nombres_csl(lista) -> list[dict]:
    return [{"corporativo": p["literal"]} if p.get("literal") else {"apellido": p.get("family", ""), "nombre": p.get("given", "")}
            for p in (lista or []) if isinstance(p, dict) and (p.get("literal") or p.get("family"))]


def leer_csl(texto: str, origen: str) -> list[dict]:
    datos = json.loads(texto)
    if isinstance(datos, dict):
        datos = datos.get("items") or [datos]
    regs = []
    for o in datos:
        if not isinstance(o, dict) or not o.get("title"):
            continue
        tipo = CSL_ZOTERO.get(o.get("type", ""), "document")
        partes = ((o.get("issued") or {}).get("date-parts") or [[]])[0]
        fecha = "-".join(str(p).zfill(2) if i else str(p) for i, p in enumerate(partes[:3])) if partes else str((o.get("issued") or {}).get("raw", ""))
        isbn, issn = _identificadores([o.get("ISBN", ""), o.get("ISSN", "")])
        r = {"origen": origen, "tipo": tipo, "titulo": o["title"], "autores": _nombres_csl(o.get("author")),
             "editores": _nombres_csl(o.get("editor")), "fecha": fecha, "editorial": o.get("publisher", ""),
             "lugar": o.get("publisher-place", ""), "doi": o.get("DOI", ""), "isbn": isbn, "issn": issn, "url": o.get("URL", ""),
             "idioma": o.get("language", ""), "volumen": str(o.get("volume", "") or ""), "edicion": str(o.get("edition", "") or ""),
             "serie": o.get("collection-title", ""), "serie_numero": str(o.get("collection-number", "") or ""),
             "titulo_corto": o.get("title-short", ""), "resumen": o.get("abstract", ""),
             "etiquetas": [k.strip() for k in re.split(r"[,;]", o.get("keyword", "") or "") if k.strip()], "archivos": [],
             "catalogo": "", "clave": o.get("citation-key") or (o.get("id") if isinstance(o.get("id"), str) else "") or "",
             "calibre_id": None}
        if tipo == "bookSection":
            r["libro"] = o.get("container-title", "")
        else:
            r["revista"] = o.get("container-title", "")
        r["numero"] = str(o.get("issue", "") or "")
        r["numero_doc"] = str(o.get("number", "") or "")
        r["paginas"] = str(o.get("page", "") or "")
        r["num_paginas"] = str(o.get("number-of-pages", "") or "")
        regs.append(r)
    return regs


def leer(ruta: Path) -> list[dict]:
    """Los registros de un archivo RIS, BibTeX o CSL-JSON (por la extensión o, si no dice, por el contenido)."""
    texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    ext, origen = Path(ruta).suffix.lower(), Path(ruta).name
    if ext == ".ris" or (ext not in (".bib", ".json") and re.search(r"^TY  - ", texto, re.M)):
        return leer_ris(texto, origen)
    if ext == ".bib" or (ext != ".json" and re.search(r"^\s*@\w+\s*\{", texto, re.M)):
        return leer_bib(texto, origen)
    return leer_csl(texto, origen)


# ================================================================== fusionar
def _llaves(r: dict) -> set[str]:
    vi, ks = _vi(), set()
    if vi.normalizar_doi(r.get("doi")):
        ks.add("doi:" + vi.normalizar_doi(r["doi"]))
    if r.get("isbn"):
        ks.add("isbn:" + r["isbn"])
    if r.get("calibre_id"):
        ks.add(f"calibre:{r['calibre_id']}")
    t, a = _normal(r.get("titulo")), _anio(r.get("fecha"))
    if t and a:
        ks.add(f"titulo:{t}|{a}|{_apellido(r.get('autores') or [])}")
    return ks


def fusionar(registros: list[dict]) -> tuple[list[dict], int]:
    """Las obras distintas (un registro repetido en otro archivo se funde: lo vacío se rellena, las etiquetas y los
    archivos se suman, y quedan sus orígenes) y cuántos registros se fundieron."""
    obras: list[dict] = []
    por_llave: dict[str, int] = {}
    fundidos = 0
    for r in registros:
        ks = _llaves(r)
        i = next((por_llave[k] for k in ks if k in por_llave), None)
        if i is None:
            obras.append({**r, "origenes": [r["origen"]], "etiquetas": list(dict.fromkeys(r.get("etiquetas") or [])),
                          "archivos": list(r.get("archivos") or [])})
            i = len(obras) - 1
        else:
            fundidos += 1
            o = obras[i]
            for k, v in r.items():
                if k in ("etiquetas", "archivos", "origen"):
                    continue
                if v not in (None, "", []) and o.get(k) in (None, "", []):
                    o[k] = v
            o["etiquetas"] = list(dict.fromkeys(o["etiquetas"] + (r.get("etiquetas") or [])))
            o["archivos"] = list(dict.fromkeys(o["archivos"] + (r.get("archivos") or [])))
            if r["origen"] not in o["origenes"]:
                o["origenes"].append(r["origen"])
        for k in _llaves(obras[i]) | ks:
            por_llave.setdefault(k, i)
    return obras, fundidos


# ================================================================== lo que ya existe (solo lectura)
FORMATOS = ("PDF", "EPUB", "DJVU", "AZW3", "MOBI", "DOCX", "DOC", "ODT", "RTF", "TXT", "HTML", "ZIP")
CONTENIDO = {"pdf": "application/pdf", "epub": "application/epub+zip", "djvu": "image/vnd.djvu", "html": "text/html",
             "txt": "text/plain", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _tipo_de_calibre(item_type: str) -> str:
    """«Journal Article» → «journalArticle» (la enumeración `#item_type` de Calibre son los tipos de Zotero en inglés)."""
    p = (item_type or "").split()
    return (p[0].lower() + "".join(x[:1].upper() + x[1:] for x in p[1:])) if p else ""


def de_calibre(db: Path) -> dict[int, dict]:
    """{libro: {titulo, anio, autor, doi, isbn, ruta, zotero_key, tipo, formatos [(formato, nombre)]}}."""
    vi = _vi()
    c = _ro(db)
    try:
        libros = {b: {"titulo": t or "", "anio": _anio(p), "ruta": r or "", "autor": "", "doi": "", "isbn": "",
                      "zotero_key": "", "tipo": "", "formatos": []}
                  for b, t, p, r in c.execute("select id, title, pubdate, path from books")}
        for b, n in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id=l.author order by l.id"):
            if b in libros and not libros[b]["autor"]:
                libros[b]["autor"] = n
        for b, tipo, val in c.execute("select book, type, val from identifiers where type in ('doi','isbn')"):
            if b in libros:
                libros[b][tipo] = vi.normalizar_doi(val) if tipo == "doi" else (vi.normalizar_isbn(val)[0] or str(val))
        cols = dict(c.execute("select label, id from custom_columns"))
        if "zotero_key" in cols:
            for b, v in c.execute(f"select book, value from custom_column_{cols['zotero_key']}"):
                if b in libros:
                    libros[b]["zotero_key"] = (v or "").strip()
        if "item_type" in cols:
            n = cols["item_type"]
            for b, v in c.execute(f"select l.book, v.value from books_custom_column_{n}_link l join custom_column_{n} v on v.id=l.value"):
                if b in libros:
                    libros[b]["tipo"] = _tipo_de_calibre(v)
        for b, f, nombre in c.execute("select book, format, name from data"):
            if b in libros:
                libros[b]["formatos"].append((f.upper(), nombre))
    finally:
        c.close()
    for d in libros.values():
        d["formatos"].sort(key=lambda x: FORMATOS.index(x[0]) if x[0] in FORMATOS else 99)
    return libros


def de_zotero(db: Path) -> dict:
    """Los ítems de Zotero (no adjuntos, notas ni anotaciones) con su título, año, DOI, ISBN, clave de cita, primer apellido
    y si están en la papelera; y qué ítem enlaza cada carpeta de la biblioteca (`attachments:<carpeta>/…`)."""
    vi = _vi()
    c = _ro(db)
    try:
        base = {f: b for b, f in c.execute("select fb.fieldName, f.fieldName from baseFieldMappings m join fields fb on "
                                           "fb.fieldID=m.baseFieldID join fields f on f.fieldID=m.fieldID")}
        papelera = {i for (i,) in c.execute("select itemID from deletedItems")}
        items = {i: {"key": k, "tipo": t, "papelera": i in papelera, "titulo": "", "anio": "", "doi": "", "isbn": "",
                     "clave": "", "autor": ""}
                 for i, k, t in c.execute("select i.itemID, i.key, t.typeName from items i join itemTypes t using(itemTypeID) "
                                          "where t.typeName not in ('attachment','note','annotation')")}
        for i, f, v in c.execute("select d.itemID, f.fieldName, v.value from itemData d join fields f using(fieldID) "
                                 "join itemDataValues v using(valueID)"):
            if i not in items:
                continue
            g, v = base.get(f, f), str(v or "")
            d = items[i]
            if g == "title":
                d["titulo"] = v
            elif g == "date":
                d["anio"] = _anio(v.split(" ", 1)[-1]) or _anio(v)
            elif f == "DOI":
                d["doi"] = vi.normalizar_doi(v) or d["doi"]
            elif f == "ISBN":
                d["isbn"] = _identificadores([v])[0]
            elif f == "citationKey":
                d["clave"] = v.strip()
            elif f == "extra" and not d["doi"]:
                m = re.search(r"^DOI:\s*(\S+)", v, re.M | re.I)
                d["doi"] = vi.normalizar_doi(m.group(1)) if m else ""
        for i, apellido in c.execute("select itemID, lastName from itemCreators join creators using(creatorID) where orderIndex=0"):
            if i in items:
                items[i]["autor"] = apellido or ""
        carpetas: dict[str, set[str]] = {}
        for padre, ruta in c.execute("select parentItemID, path from itemAttachments where parentItemID is not null "
                                     "and path like 'attachments:%'"):
            if padre in items and "/" in ruta:
                carpetas.setdefault(ruta[len("attachments:"):].rsplit("/", 1)[0], set()).add(items[padre]["key"])
        claves = {k for (k,) in c.execute("select v.value from itemData d join fields f using(fieldID) join itemDataValues v "
                                          "using(valueID) where f.fieldName='citationKey'")}
    finally:
        c.close()
    por_key = {d["key"]: d for d in items.values()}
    indice: dict[str, list[str]] = {}
    for d in items.values():
        for k in (f"doi:{d['doi']}" if d["doi"] else "", f"isbn:{d['isbn']}" if d["isbn"] else "",
                  f"clave:{d['clave']}" if d["clave"] else "", f"titulo:{_normal(d['titulo'])}" if d["titulo"] else "",
                  f"corto:{_corto(d['titulo'])}" if d["titulo"] else ""):
            if k:
                indice.setdefault(k, []).append(d["key"])
    return {"items": por_key, "indice": indice, "carpetas": carpetas, "claves": claves}


# ================================================================== cotejar
def cotejar_calibre(o: dict, cal: dict, idx: dict) -> tuple[int | None, str]:
    """(libro de Calibre, «» o el porqué de la duda)."""
    vi = _vi()
    b = o.get("calibre_id")
    if b:
        if b not in cal:
            return None, f"el archivo cita el libro {b} de Calibre, que no existe"
        if vi.mismo_titulo(o["titulo"], cal[b]["titulo"]) is False:
            return None, f"el libro {b} de Calibre es «{cal[b]['titulo'][:60]}», otra obra"
        return b, ""
    for k in (f"doi:{vi.normalizar_doi(o.get('doi'))}" if vi.normalizar_doi(o.get("doi")) else "",
              f"isbn:{o['isbn']}" if o.get("isbn") else ""):
        if k and len(idx.get(k, [])) == 1:
            return idx[k][0], ""
    t, a, ap = _normal(o["titulo"]), _anio(o.get("fecha")), _apellido(o.get("autores") or [])
    cand = [b for b in idx.get(f"titulo:{t}", []) if cal[b]["anio"] == a and (not ap or ap in _normal(cal[b]["autor"]))]
    return (cand[0], "") if len(cand) == 1 else (None, "")


def _indice_calibre(cal: dict) -> dict:
    idx: dict[str, list[int]] = {}
    for b, d in cal.items():
        for k in (f"doi:{d['doi']}" if d["doi"] else "", f"isbn:{d['isbn']}" if d["isbn"] else "", f"titulo:{_normal(d['titulo'])}"):
            if k:
                idx.setdefault(k, []).append(b)
    return idx


def cotejar_zotero(o: dict, libro: dict | None, zot: dict) -> tuple[str, str, str]:
    """(«ya» · «dudoso» · «nuevo», clave del ítem de Zotero, porqué)."""
    vi, items, idx = _vi(), zot["items"], zot["indice"]

    def vivo(k):
        return k in items and not items[k]["papelera"]

    def describir(k):
        d = items[k]
        return f"«{d['titulo'][:70]}» ({d['anio'] or 's. f.'}), {k}"

    if libro:
        if libro["zotero_key"] and vivo(libro["zotero_key"]):
            return "ya", libro["zotero_key"], "su #zotero_key en Calibre"
        enlazan = sorted(k for k in zot["carpetas"].get(libro["ruta"], set()) if vivo(k))
        if enlazan:
            return "ya", enlazan[0], "un adjunto enlaza su archivo de Calibre"
    doi = vi.normalizar_doi(o.get("doi"))
    for k, por in ((f"doi:{doi}" if doi else "", "el mismo DOI"), (f"isbn:{o['isbn']}" if o.get("isbn") else "", "el mismo ISBN")):
        vivos = [x for x in idx.get(k, []) if vivo(x)] if k else []
        if vivos:
            return "ya", vivos[0], por
    if o.get("clave"):
        for x in idx.get(f"clave:{o['clave']}", []):
            if vivo(x) and vi.mismo_titulo(o["titulo"], items[x]["titulo"]) is not False:
                return "ya", x, "la misma clave de cita"
    a, ap = _anio(o.get("fecha")), _apellido(o.get("autores") or [])
    exactos = idx.get(f"titulo:{_normal(o['titulo'])}", [])
    for x in exactos:
        d = items[x]
        if vivo(x) and d["anio"] == a and (not ap or not d["autor"] or ap in _normal(d["autor"])):
            return "ya", x, "el mismo título, año y autor"
    corto = _corto(o["titulo"])
    parecidos = list(dict.fromkeys(exactos + (idx.get(f"corto:{corto}", []) if len(corto.split()) >= 3 else [])))
    # dos sentencias o dos decretos con otro número son otra obra aunque compartan el título corto
    numeros = lambda s: set(re.findall(r"\d+", _normal(s)))
    parecidos = [x for x in parecidos if not (numeros(o["titulo"]) and numeros(items[x]["titulo"])
                                              and numeros(o["titulo"]) != numeros(items[x]["titulo"]))]
    for x in parecidos:                                # el subtítulo puede faltar en uno de los dos
        d = items[x]
        if not d["papelera"] and a and d["anio"] == a and ap and d["autor"] and ap in _normal(d["autor"]):
            return "ya", x, "el mismo título (sin subtítulo), año y autor"
    for x in parecidos:
        d = items[x]
        if d["papelera"]:
            return "dudoso", x, f"en la papelera de Zotero: {describir(x)}"
        if d["anio"] != a:
            return "dudoso", x, f"el mismo título con otro año en Zotero: {describir(x)}"
        return "dudoso", x, f"el mismo título con otro autor en Zotero: {describir(x)}"
    return "nuevo", "", ""


def _filtro(ids: str) -> set[int]:
    return {int(x) for x in re.split(r"[,\s]+", ids or "") if x.strip().isdigit()}


def plan(archivos: list[Path], env, coleccion: str, etiqueta: str = "", incluir_dudosos: bool = False,
         ids: str = "", excluir_ids: str = "", hoy: str | None = None) -> dict:
    """El plan entero (solo lee): las obras fusionadas, cada una con su estado, su porqué, su libro de Calibre, su adjunto
    y, si es nueva, su ítem de Zotero."""
    hoy = hoy or date.today().isoformat()
    ing = _ing()
    registros, por_archivo = [], {}
    for a in archivos:
        rs = leer(a)
        registros += rs
        por_archivo[Path(a).name] = {"archivo": Path(a).name, "registros": len(rs), "nuevo": 0, "ya": 0, "dudoso": 0, "omitido": 0}
    obras, fundidos = fusionar(registros)
    solo, fuera = _filtro(ids), _filtro(excluir_ids)
    cal = de_calibre(Path(env.CALIBRE_DB))
    idx_cal = _indice_calibre(cal)
    zot = de_zotero(Path(env.ZOTERO_DB))
    esquema = ing._esquema_zotero(Path(env.ZOTERO_DB))
    usadas = set(zot["claves"])
    biblioteca = Path(env.BIBLIOTECA_DIR)
    salida = []
    for o in obras:
        libro_id, duda_cal = cotejar_calibre(o, cal, idx_cal)
        p = {"titulo": o["titulo"], "anio": _anio(o.get("fecha")), "tipo": o["tipo"], "origenes": o["origenes"],
             "autores": "; ".join(a.get("corporativo") or ", ".join(x for x in (a.get("apellido"), a.get("nombre")) if x)
                                  for a in o.get("autores") or []),
             "calibre_id": libro_id, "zotero_key": "", "motivo": "", "adjunto": "", "clave": ""}
        cid = libro_id or o.get("calibre_id")
        if (solo and cid not in solo) or (cid and cid in fuera):
            p.update(estado="omitido", motivo="fuera de --ids" if solo and cid not in solo else "en --excluir-ids")
            salida.append(p)
            continue
        libro = cal.get(libro_id) if libro_id else None
        estado, key, motivo = cotejar_zotero(o, libro, zot)
        if estado == "nuevo" and duda_cal:
            estado, motivo = "dudoso", duda_cal
        elif estado == "nuevo" and libro and libro["tipo"] and o.get("catalogo") == "Calibre" and libro["tipo"] != o["tipo"]:
            # el RIS de Calibre da GEN a lo que RIS no tiene (Standard…): el tipo de Calibre manda si es el mismo en RIS
            if libro["tipo"] in esquema["validos"] and RIS_DE.get(libro["tipo"], "GEN") == RIS_DE.get(o["tipo"], "GEN"):
                o = {**o, "tipo": libro["tipo"]}
                p["tipo"] = libro["tipo"]
            else:
                estado, motivo = "dudoso", (f"el archivo la da como {o['tipo']} y Calibre hoy como {libro['tipo']}: "
                                            "regenere el RIS (ingesta/main.sh zotero)")
        if estado == "nuevo" and libro and libro["zotero_key"]:
            motivo = f"la #zotero_key de Calibre ({libro['zotero_key']}) no existe en Zotero: se reemplaza"
        p.update(estado=estado, zotero_key=key, motivo=motivo)
        if estado == "nuevo" or (estado == "dudoso" and incluir_dudosos):
            tipo = o["tipo"] if o["tipo"] in esquema["validos"] else "document"
            clave = o["clave"] if o.get("clave") and o["clave"] not in usadas else ing.unica(
                ing.clave_bbt(o.get("autores") or [], o["titulo"], _anio(o.get("fecha"))), usadas)
            usadas.add(clave)
            roles = esquema["roles"].get(tipo) or {"author"}
            rol = "author" if "author" in roles else sorted(roles)[0]
            creadores = [({"apellido": a["corporativo"], "nombre": "", "modo": 1} if a.get("corporativo")
                          else {"apellido": a["apellido"], "nombre": a.get("nombre") or "", "modo": 0}) | {"rol": r}
                         for lista, r in ((o.get("autores") or [], rol), (o.get("editores") or [], "editor"))
                         if r in roles for a in lista if a.get("corporativo") or a.get("apellido")]
            if libro and libro["formatos"]:
                f, nombre = libro["formatos"][0]
                rel = f"{libro['ruta']}/{nombre}.{f.lower()}"
                if (biblioteca / rel).exists():
                    p["adjunto"] = "attachments:" + rel
                    p["adjunto_formato"] = f
            etiquetas = list(dict.fromkeys((o.get("etiquetas") or []) + ([etiqueta] if etiqueta else [])))
            p.update(crear=True, clave=clave, tipo=tipo, etiquetas=etiquetas,
                     zotero={"tipo": tipo, "campos": ing.campos_zotero(o, tipo, esquema, clave, hoy), "creadores": creadores},
                     registro=o)
        salida.append(p)
        for a in o["origenes"]:
            por_archivo[a][p["estado"]] += 1
    for p in salida:
        if p["estado"] == "omitido":
            for a in p["origenes"]:
                por_archivo[a]["omitido"] += 1
    cuentas = {"registros": len(registros), "obras": len(obras), "repetidos": fundidos,
               **{e: sum(1 for p in salida if p["estado"] == e) for e in ("nuevo", "ya", "dudoso", "omitido")},
               "crear": sum(1 for p in salida if p.get("crear")),
               "con_adjunto": sum(1 for p in salida if p.get("crear") and p["adjunto"]),
               "sin_calibre": sum(1 for p in salida if p.get("crear") and not p["calibre_id"])}
    return {"fecha": datetime.now().isoformat(timespec="seconds"), "coleccion": coleccion, "etiqueta": etiqueta,
            "archivos": list(por_archivo.values()), "cuentas": cuentas, "obras": salida, "aplicado": False}


# ================================================================== RIS de lo que falta
RIS_DE = {v: k for k, v in reversed(list(TY_ZOTERO.items()))}


def ris_de(p: dict, biblioteca: Path) -> str:
    o = p["registro"]
    lineas = [f"TY  - {RIS_DE.get(p['tipo'], 'GEN')}", f"T1  - {o['titulo']}"]
    lineas += [f"AU  - {a['corporativo'] if a.get('corporativo') else ', '.join(x for x in (a['apellido'], a.get('nombre')) if x)}"
               for a in o.get("autores") or [] if a.get("corporativo") or a.get("apellido")]
    for etq, campo in (("DA", "fecha"), ("PB", "editorial"), ("SN", "isbn"), ("DO", "doi"), ("UR", "url"), ("ST", "titulo_corto"),
                       ("T2", "revista"), ("VL", "volumen"), ("IS", "numero"), ("M1", "numero_doc"), ("ET", "edicion"),
                       ("LA", "idioma")):
        if o.get(campo):
            lineas.append(f"{etq}  - {str(o[campo]).replace('-', '/') if campo == 'fecha' else o[campo]}")
    lineas += [f"KW  - {t}" for t in p.get("etiquetas") or []]
    if p["adjunto"]:
        lineas.append(f"L1  - {biblioteca / p['adjunto'][len('attachments:'):]}")
    if p["calibre_id"]:
        lineas += ["DB  - Calibre", f"ID  - calibre:{p['calibre_id']}"]
    return "\n".join(lineas + ["ER  - ", ""])


# ================================================================== aplicar
def _app_abierta(patron: str) -> bool:
    return _cargar("biblioteca_escribir", RAIZ / "lib" / "escribir.py")._app_abierta(patron)


def aplicar(pl: dict, env) -> list[dict]:
    """Crea en Zotero lo que falta (por la puerta) y escribe `#zotero_key` en Calibre. Devuelve lo hecho por obra."""
    E = _cargar("biblioteca_escribir", RAIZ / "lib" / "escribir.py")
    sys.path.insert(0, str(RAIZ / "lib"))
    Z = _cargar("escribir_zotero", RAIZ / "lib" / "escribir_zotero.py")
    crear = [p for p in pl["obras"] if p.get("crear")]
    if not crear:
        return []
    puentes = [p for p in crear if p["calibre_id"]]
    if _app_abierta(r"^zotero") or (puentes and _app_abierta(r"^calibre")):
        raise SystemExit(SALIDA_PUERTA)
    zdb, biblioteca = Path(env.ZOTERO_DB), Path(env.BIBLIOTECA_DIR)
    hechos = []
    with E.puerta(SUITE, zotero=zdb):
        con = Z.conexion_zotero(zdb)
        try:
            cur = con.cursor()
            libreria = cur.execute("SELECT libraryID FROM libraries WHERE type='user'").fetchone()[0]
            col = Z.z_coleccion(cur, libreria, pl["coleccion"])
            for p in crear:
                item, key = Z.z_nuevo_item(cur, libreria, p["zotero"]["tipo"], p["zotero"]["campos"], p["zotero"]["creadores"])
                if p["adjunto"]:
                    f = p.get("adjunto_formato", "PDF")
                    Z.z_adjunto_enlazado(cur, libreria, item, p["adjunto"], f, CONTENIDO.get(f.lower(), "application/octet-stream"))
                if p["etiquetas"]:
                    Z.z_etiquetar(cur, item, p["etiquetas"])
                Z.z_en_coleccion(cur, col, item)
                p["zotero_key"] = key
                hechos.append({"titulo": p["titulo"], "zotero_key": key, "calibre_id": p["calibre_id"], "adjunto": bool(p["adjunto"]),
                               "origenes": p["origenes"], "puente": False})
                print(f"  Zotero {key}: {p['titulo'][:70]}" + (f" · adjunto de Calibre {p['calibre_id']}" if p["adjunto"] else ""))
            con.commit()
            bien = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not con.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            con.close()
        if not bien:
            raise RuntimeError("zotero.sqlite no pasó integrity_check o foreign_key_check: restaure el respaldo de la puerta")
        print(f"── Zotero: {len(hechos)} ítems nuevos en «{pl['coleccion']}» · integridad ok")
    if puentes:
        with E.puerta(SUITE, calibre=biblioteca):
            for p, h in zip(crear, hechos):
                if p["calibre_id"]:
                    r = E.calibredb(biblioteca, "set_custom", "zotero_key", str(p["calibre_id"]), p["zotero_key"])
                    h["puente"] = r.returncode == 0
                    if r.returncode:
                        print(f"  [WARN] #zotero_key {p['calibre_id']}: {(r.stdout + r.stderr).strip()[:200]}", file=sys.stderr)
            E.calibredb(biblioteca, "backup_metadata")
        print(f"── Calibre: {sum(h['puente'] for h in hechos)} #zotero_key escritas")
    return hechos


# ================================================================== informe y CLI
def carpeta_salida() -> Path:
    if os.environ.get("IMPORTAR_ZOTERO_SALIDA"):
        return Path(os.environ["IMPORTAR_ZOTERO_SALIDA"])
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "biblioteca" / "importar-zotero"


def coleccion_por_defecto(archivos: list[Path], hoy: str) -> str:
    """«ingesta_20261116_canon-de-las-miradas.ris» → «Canon de las miradas»; varios o sin nombre → «Importado <fecha>»."""
    if len(archivos) == 1:
        t = re.sub(r"^ingesta_\d{8}(?:_\d{6})?_?", "", Path(archivos[0]).stem)
        t = re.sub(r"[-_]+", " ", t).strip()
        if t and not t.isdigit():
            return t[:1].upper() + t[1:]
    return f"Importado {hoy}"


def _publico(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in ("registro", "zotero", "crear")} | (
        {"campos": p["zotero"]["campos"]} if p.get("zotero") else {})


def guardar(pl: dict, carpeta: Path, biblioteca: Path) -> tuple[Path, Path]:
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    ris = carpeta / f"{sello}_faltan.ris"
    ris.write_text("\n".join(ris_de(p, biblioteca) for p in pl["obras"] if p.get("crear")), encoding="utf-8")
    informe = {**pl, "obras": [_publico(p) for p in pl["obras"]], "ris": str(ris)}
    texto = json.dumps(informe, ensure_ascii=False, indent=1)
    (carpeta / f"{sello}_informe.json").write_text(texto, encoding="utf-8")
    (carpeta / "ultimo.json").write_text(texto, encoding="utf-8")
    return carpeta / f"{sello}_informe.json", ris


def texto_plan(pl: dict, aplicar_: bool, limite: int = 40) -> str:
    c = pl["cuentas"]
    l = [f"[{'aplicar' if aplicar_ else 'simulación'}] {len(pl['archivos'])} archivo(s) · {c['registros']} registros → "
         f"{c['obras']} obras" + (f" ({c['repetidos']} repetidos entre archivos, fundidos)" if c["repetidos"] else ""),
         f"  Nuevas {c['nuevo']} · Ya estaban {c['ya']} · Dudosas {c['dudoso']}" + (f" · Omitidas {c['omitido']}" if c["omitido"] else ""),
         f"  Se crearían {c['crear']} en «{pl['coleccion']}»: {c['con_adjunto']} con su archivo de Calibre, {c['sin_calibre']} sin libro en Calibre"]
    l.append("  por archivo:")
    for a in pl["archivos"]:
        l.append(f"    {a['archivo']}: {a['registros']} registros · nuevas {a['nuevo']} · ya {a['ya']} · dudosas {a['dudoso']}"
                 + (f" · omitidas {a['omitido']}" if a["omitido"] else ""))
    for estado, titulo in (("dudoso", "Dudosas (no se crean salvo --incluir-dudosos)"), ("nuevo", "Nuevas"), ("ya", "Ya estaban (no se tocan)")):
        grupo = [p for p in pl["obras"] if p["estado"] == estado]
        if not grupo:
            continue
        l.append(f"\n{titulo}: {len(grupo)}")
        for p in grupo[:limite]:
            fuente = ", ".join(p["origenes"])
            detalle = {"ya": f"{p['zotero_key']} · {p['motivo']}", "dudoso": p["motivo"],
                       "nuevo": (f"Calibre {p['calibre_id']}" + (" · con adjunto" if p["adjunto"] else " · sin archivo")
                                 if p["calibre_id"] else "sin libro en Calibre") + (f" · {p['motivo']}" if p["motivo"] else "")}[estado]
            l.append(f"  - «{p['titulo'][:90]}» ({p['anio'] or 's. f.'})")
            l.append(f"      {detalle} · {fuente}")
        if len(grupo) > limite:
            l.append(f"  … y {len(grupo) - limite} más (en el informe)")
    return "\n".join(l)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archivos", nargs="+", type=Path, help="RIS, BibTeX o CSL-JSON")
    ap.add_argument("--coleccion", default="", help="la colección del lote (por omisión, del nombre del archivo)")
    ap.add_argument("--etiqueta", default="", help="una etiqueta más para lo nuevo")
    ap.add_argument("--ids", default="", help="solo los libros de Calibre de esta lista")
    ap.add_argument("--excluir-ids", default="", help="sin los libros de Calibre de esta lista")
    ap.add_argument("--incluir-dudosos", action="store_true", help="crea también las dudosas")
    ap.add_argument("--salida", type=Path, default=None, help="dónde dejar el informe y el RIS (por omisión, el estado)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    faltan = [str(x) for x in a.archivos if not x.is_file()]
    if faltan:
        print(f"✗ no existe: {', '.join(faltan)}", file=sys.stderr)
        return 2
    env = _ing()._env()
    hoy = date.today().isoformat()
    pl = plan(a.archivos, env, a.coleccion or coleccion_por_defecto(a.archivos, hoy), a.etiqueta, a.incluir_dudosos,
              a.ids, a.excluir_ids, hoy)
    pl["zotero_abierto"], pl["calibre_abierto"] = _app_abierta(r"^zotero"), _app_abierta(r"^calibre")
    if a.aplicar:
        try:
            pl["hechos"] = aplicar(pl, env)
            pl["aplicado"] = True
        except SystemExit as e:
            if e.code == SALIDA_PUERTA:
                print("[puerta] Zotero o Calibre abiertos: no se escribió nada; reintente con los dos cerrados (75)", file=sys.stderr)
                return SALIDA_PUERTA
            raise
        except Exception as e:  # noqa: BLE001 — la puerta cerrada o el candado ocupado son «reintentar luego»
            if type(e).__name__ in ("PuertaCerrada", "Ocupado"):
                print(f"[puerta] {e}: no se escribió nada; reintente luego (75)", file=sys.stderr)
                return SALIDA_PUERTA
            raise
    informe, ris = guardar(pl, a.salida or carpeta_salida(), Path(env.BIBLIOTECA_DIR))
    if a.json:
        print(json.dumps({"cuentas": pl["cuentas"], "archivos": pl["archivos"], "informe": str(informe), "ris": str(ris)}, ensure_ascii=False))
    else:
        print(texto_plan(pl, a.aplicar))
        print(f"\nInforme: {informe}\nRIS de lo que falta: {ris}")
        if not a.aplicar:
            if pl["zotero_abierto"] or pl["calibre_abierto"]:
                print("  Zotero o Calibre abiertos: aplicar saldría 75")
            print(f"· Simulación: --aplicar crearía {pl['cuentas']['crear']} ítems en Zotero por la puerta.")
        else:
            print(f"✓ {len(pl.get('hechos') or [])} ítems creados en Zotero")
    return 0


if __name__ == "__main__":
    sys.exit(main())
