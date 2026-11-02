#!/usr/bin/env python3
"""lib/indice.py — el índice de libros para Biblioteca Studio y los complementos de Calibre, KOReader y Zotero.

Objetivo: que cada pieza sepa de un libro (su `calibre_id`, su clave de Zotero, su clave para citar, sus apuntes y sus
fichas) sin abrir las bases por su cuenta: KOReader no lee `metadata.db`, Zotero no lee la de Calibre.
Método: SOLO LEE (`mode=ro`) `metadata.db` y `zotero.sqlite` y las fichas de `catalogacion/fichas/`; no es una puerta
de escritura. El JSON queda fuera del repo y de las bases: `$XDG_STATE_HOME/biblioteca/indice.json`.
Entra: CALIBRE_DB, ZOTERO_DB y BIBLIOTECA_DIR de core/env. Sale: el JSON (con `--aplicar`); sin él, simula.
`editorial(db)` (aditiva, 2026-11-02) lee en solo lectura lo editorial de cada libro (año, serie, etiquetas, editorial,
idiomas, identificadores, descripción, formatos, tipo, páginas, lectura de KOReader) para el catálogo de Biblioteca
Studio; no va al JSON (los complementos no lo necesitan y KOReader lo leería entero).
Uso:
    python3 lib/indice.py              # simula: cuántos libros, cuántos con clave, sin escribir
    python3 lib/indice.py --aplicar    # escribe el índice (lo corre el timer de KOReader cada 30 min y «Actualizar el índice» del Studio)
    python3 lib/indice.py --ruta       # dónde vive el índice
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESQUEMA = 1
_ID_EN_RUTA = re.compile(r"\((\d+)\)/[^/]*$")


def _env():
    d = RAIZ
    while d != d.parent and not (d / "core" / "env.py").is_file():
        d = d.parent
    import importlib.util
    s = importlib.util.spec_from_file_location("core_env", d / "core" / "env.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def ruta_indice() -> Path:
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return estado / "biblioteca" / "indice.json"


def _leer(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)


def _columna(c, etiqueta: str) -> dict[int, str]:
    """{libro: valor} de una columna personalizada de Calibre, por su etiqueta (nunca por número)."""
    fila = c.execute("select id from custom_columns where label=?", (etiqueta,)).fetchone()
    if not fila:
        return {}
    cid = fila[0]
    cols = [r[1] for r in c.execute(f"pragma table_info(custom_column_{cid})")]
    if "book" in cols:
        return {b: v for b, v in c.execute(f"select book, value from custom_column_{cid}") if v not in (None, "")}
    return {b: v for b, v in c.execute(f"select l.book, v.value from custom_column_{cid} v "
                                       f"join books_custom_column_{cid}_link l on l.value=v.id")}


def calibre(db: Path) -> dict[int, dict]:
    with _leer(db) as c:
        autores: dict[int, list[str]] = {}
        for b, nombre in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id=l.author "
                                   "order by l.id"):
            autores.setdefault(b, []).append(nombre.replace("|", ","))
        formatos: dict[int, list[str]] = {}
        for b, fmt, nombre in c.execute("select book, format, name from data"):
            formatos.setdefault(b, []).append(f"{nombre}.{fmt.lower()}")
        zkey = _columna(c, "zotero_key")
        apuntes = _columna(c, "apuntes")
        libros = {}
        for b, titulo, carpeta in c.execute("select id, title, path from books"):
            libros[b] = {"titulo": titulo, "autores": autores.get(b, []), "carpeta": carpeta,
                         "formatos": [f"{carpeta}/{f}" for f in formatos.get(b, [])],
                         "zotero_key": str(zkey.get(b, "") or ""), "clave": "",
                         "apuntes": _enlace(apuntes.get(b, "")), "fichas": []}
    return libros


def _enlace(valor: str) -> str:
    """La ruta de los apuntes: `#apuntes` guarda un enlace `file://` dentro de un HTML corto."""
    m = re.search(r"file://([^\"'<> ]+)", valor or "")
    from urllib.parse import unquote
    return unquote(m.group(1)) if m else ""


def zotero(db: Path) -> tuple[dict[str, str], dict[int, str]]:
    """({clave de Zotero: clave para citar}, {calibre_id: clave de Zotero}) leídos de zotero.sqlite en solo lectura.

    Como `lib/leer.sh`: `mode=ro` también con Zotero abierto (lee su WAL); si Zotero la tiene bloqueada, `immutable`
    (lee lo último confirmado en el archivo, sin el WAL). Nunca se escribe ni se copia la base."""
    if not Path(db).is_file():
        return {}, {}
    uri = Path(db).resolve().as_uri()
    try:
        c = sqlite3.connect(uri + "?mode=ro", uri=True)
        c.execute("select 1 from items limit 1")
    except sqlite3.OperationalError:
        c = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True)
    try:
        claves = {k: v for k, v in c.execute(
            "select i.key, v.value from items i join itemData d on d.itemID=i.itemID "
            "join fields f on f.fieldID=d.fieldID join itemDataValues v on v.valueID=d.valueID "
            "where f.fieldName='citationKey'")}
        por_id = {}
        for ruta, padre in c.execute("select a.path, p.key from itemAttachments a join items p on p.itemID=a.parentItemID "
                                     "where a.path like 'attachments:%'"):
            m = _ID_EN_RUTA.search(ruta or "")
            if m:
                por_id.setdefault(int(m.group(1)), padre)
    finally:
        c.close()
    return claves, por_id


def fichas(carpeta: Path) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for f in sorted(carpeta.glob("*.md")):
        m = re.search(r"^calibre_id:\s*(\d+)", f.read_text(encoding="utf-8", errors="replace")[:600], re.M)
        if m:
            out.setdefault(int(m.group(1)), []).append(str(f.relative_to(RAIZ)))
    return out


def _filas(c, sql: str, args=()) -> list:
    """Una consulta que tolera las tablas que la base no tenga (una biblioteca mínima, una versión antigua)."""
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []


def _columna_tolerante(c, etiqueta: str) -> dict:
    try:
        return _columna(c, etiqueta)
    except sqlite3.OperationalError:
        return {}


def editorial(db: Path) -> dict:
    """{libros: {id: {…}}, inmutable}: lo editorial de cada libro de `metadata.db`, en SOLO LECTURA (`mode=ro`; si la
    base está bloqueada porque una suite escribe, `immutable`: lo último confirmado en el archivo). Las columnas
    personalizadas, por etiqueta. Nunca escribe ni copia la base."""
    uri = Path(db).resolve().as_uri()
    c, inmutable = sqlite3.connect(uri + "?mode=ro", uri=True), False
    try:
        c.execute("select 1 from books limit 1")
    except sqlite3.OperationalError as e:
        c.close()
        if "no such table" in str(e):
            raise
        c, inmutable = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True), True
    try:
        cols = {r[1] for r in _filas(c, "pragma table_info(books)")}
        extra = ", ".join(x if x in cols else f"null as {x}" for x in ("pubdate", "series_index", "author_sort", "sort", "timestamp", "has_cover"))
        libros = {}
        for b, titulo, carpeta, pubdate, serie_indice, autor_orden, titulo_orden, añadido, portada in _filas(c, f"select id, title, path, {extra} from books"):
            libros[b] = {"titulo": titulo or "", "carpeta": carpeta or "", "pubdate": pubdate, "serie_indice": serie_indice,
                         "orden_autor": autor_orden or "", "orden_titulo": titulo_orden or "", "añadido": añadido, "has_cover": portada,
                         "autores": [], "serie": "", "etiquetas": [], "editorial": "", "idiomas": [], "identificadores": {}, "descripcion": "",
                         "formatos": []}
        def poner(sql, f):
            for fila in _filas(c, sql):
                if fila[0] in libros:
                    f(libros[fila[0]], *fila[1:])
        poner("select l.book, a.name from books_authors_link l join authors a on a.id=l.author order by l.id", lambda d, n: d["autores"].append(str(n).replace("|", ",")))
        poner("select l.book, s.name from books_series_link l join series s on s.id=l.series", lambda d, n: d.__setitem__("serie", n))
        poner("select l.book, t.name from books_tags_link l join tags t on t.id=l.tag order by t.name", lambda d, n: d["etiquetas"].append(n))
        poner("select l.book, p.name from books_publishers_link l join publishers p on p.id=l.publisher", lambda d, n: d.__setitem__("editorial", n))
        poner("select l.book, g.lang_code from books_languages_link l join languages g on g.id=l.lang_code order by l.item_order", lambda d, n: d["idiomas"].append(n))
        poner("select book, type, val from identifiers", lambda d, t, v: d["identificadores"].__setitem__(t, v))
        poner("select book, text from comments", lambda d, t: d.__setitem__("descripcion", t or ""))
        datos = _filas(c, "select book, format, name, uncompressed_size from data") or [(b, f, n, 0) for b, f, n in _filas(c, "select book, format, name from data")]
        for b, fmt, nombre, tam in datos:
            if b in libros:
                libros[b]["formatos"].append({"formato": str(fmt).upper(), "nombre": f"{nombre}.{str(fmt).lower()}", "bytes": int(tam or 0)})
        for clave, etiqueta in (("item_type", "item_type"), ("clasificador", "clasificador"), ("pages", "pages"), ("ko_progfloat", "ko_progfloat"),
                                ("ko_status", "ko_status"), ("ko_tiempo", "ko_tiempo"), ("ko_lastmod", "ko_lastmod")):
            for b, v in _columna_tolerante(c, etiqueta).items():
                if b in libros:
                    libros[b][clave] = v
    finally:
        c.close()
    return {"libros": libros, "inmutable": inmutable}


def construir(env=None) -> dict:
    env = env or _env()
    libros = calibre(Path(env.CALIBRE_DB))
    claves, por_id = zotero(Path(env.ZOTERO_DB))
    for b, f in fichas(RAIZ / "catalogacion" / "fichas").items():
        if b in libros:
            libros[b]["fichas"] = f
    notas = Path(env.DOCS_ROOT) / "notas"
    for b, d in libros.items():
        if not d["zotero_key"] and b in por_id:
            d["zotero_key"] = por_id[b]
        d["clave"] = claves.get(d["zotero_key"], "")
        # la nota de lectura del libro: la de #apuntes si la hay; si no, la que crea Zotero Integration en Obsidian
        # (`notas/{{citekey | lower}}.md`), para que un libro tenga una sola nota venga de donde venga
        d["nota"] = d["apuntes"] or str(notas / f"{(d['clave'] or f'calibre-{b}').lower()}.md")
    return {"esquema": ESQUEMA, "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "biblioteca": str(env.BIBLIOTECA_DIR),
            "repo": str(RAIZ), "notas": str(notas), "libros": {str(b): d for b, d in sorted(libros.items())}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="El índice de libros de Biblioteca Studio y los complementos (solo lee).")
    ap.add_argument("--aplicar", action="store_true", help="escribe el índice (sin esto, simula)")
    ap.add_argument("--ruta", action="store_true", help="imprime dónde vive el índice y sale")
    a = ap.parse_args(argv)
    destino = ruta_indice()
    if a.ruta:
        print(destino)
        return 0
    indice = construir()
    libros = indice["libros"].values()
    resumen = (f"{len(indice['libros'])} libros · {sum(bool(d['zotero_key']) for d in libros)} con clave de Zotero · "
               f"{sum(bool(d['clave']) for d in libros)} con clave para citar · {sum(bool(d['fichas']) for d in libros)} "
               f"con ficha · {sum(bool(d['apuntes']) for d in libros)} con apuntes")
    if not a.aplicar:
        print(f"[simulación] {resumen} → {destino} (--aplicar escribe)")
        return 0
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(indice, ensure_ascii=False), encoding="utf-8")
    tmp.replace(destino)                     # atómico: los complementos nunca leen un índice a medias
    print(f"✓ {resumen} → {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
