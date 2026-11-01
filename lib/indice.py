#!/usr/bin/env python3
"""lib/indice.py — el índice de libros para Biblioteca Studio y los complementos de Calibre, KOReader y Zotero.

Objetivo: que cada pieza sepa de un libro (su `calibre_id`, su clave de Zotero, su clave para citar, sus apuntes y sus
fichas) sin abrir las bases por su cuenta: KOReader no lee `metadata.db`, Zotero no lee la de Calibre.
Método: SOLO LEE (`mode=ro`) `metadata.db` y `zotero.sqlite` y las fichas de `catalogacion/fichas/`; no es una puerta
de escritura. El JSON queda fuera del repo y de las bases: `$XDG_STATE_HOME/biblioteca/indice.json`.
Entra: CALIBRE_DB, ZOTERO_DB y BIBLIOTECA_DIR de core/env. Sale: el JSON (con `--aplicar`); sin él, simula.
Uso:
    python3 lib/indice.py              # simula: cuántos libros, cuántos con clave, sin escribir
    python3 lib/indice.py --aplicar    # escribe el índice (Biblioteca Studio → Sincronizar → «Actualizar el índice»)
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
