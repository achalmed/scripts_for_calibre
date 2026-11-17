"""tests/lectura_base/juguete_lectura.py — un mundo de juguete para la base de lectura (decisiones §9.6).

Nada real: en una carpeta temporal (en el disco, `$XDG_CACHE_HOME/pytest/`, nunca /tmp) se crean una biblioteca Calibre
mínima (`metadata.db` con `books`, `authors`, `data` y la columna `#ko_md5`) con dos PDF con texto, una carpeta de
KOReader (un sidecar central por hash y su `statistics.sqlite3`), una `zotero.sqlite` con el esquema de anotaciones
de Zotero 7, una carpeta docdata de Okular y la base de lectura vacía. El entorno (`CALIBRE_DB`, `ZOTERO_DB`,
`KOREADER_DIR`, `OKULAR_DOCDATA`, `LECTURA_DB`, `PUERTA_RESPALDOS`, los candados) apunta ahí.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
BASETEMP = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pytest" / "biblioteca-studio-lectura" / "basetemp"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ------------------------------------------------------------------------------------------------- un PDF con texto
LINEAS = [  # (hoja, y desde arriba en puntos, texto)
    (1, 100, "La productividad es casi todo en el largo plazo."),
    (1, 200, "El crecimiento depende de la acumulacion de capital."),
    (2, 150, "Las instituciones reducen la incertidumbre economica."),
]
ANCHO, ALTO = 600, 800


def pdf_con_texto(lineas=LINEAS, hojas: int = 2) -> bytes:
    objetos = ["<</Type/Catalog/Pages 2 0 R>>", None, "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    kids = []
    for h in range(1, hojas + 1):
        flujo = "".join(f"BT /F1 12 Tf 72 {ALTO - y} Td ({t}) Tj ET\n" for hh, y, t in lineas if hh == h).encode()
        objetos.append(f"<</Length {len(flujo)}>>stream\n".encode() + flujo + b"endstream")
        n_flujo = len(objetos)
        objetos.append(f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 {ANCHO} {ALTO}]/Resources<</Font<</F1 3 0 R>>>>/Contents {n_flujo} 0 R>>")
        kids.append(f"{len(objetos)} 0 R")
    objetos[1] = f"<</Type/Pages/Kids[{' '.join(kids)}]/Count {hojas}>>"
    salida, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objetos, 1):
        offsets.append(len(salida))
        cuerpo = o if isinstance(o, bytes) else o.encode()
        salida += f"{i} 0 obj".encode() + cuerpo + b"endobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += f"trailer<</Size {len(objetos) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(salida)


def rect_de_linea(hoja: int, y: float, ancho_pts: float = 300) -> list:
    """El rectángulo (fracciones) que cubre una línea de LINEAS: 72 pt a la izquierda, 12 pt de alto sobre la base."""
    return [hoja, 72 / ANCHO, (y - 11) / ALTO, ancho_pts / ANCHO, 14 / ALTO]


# ---------------------------------------------------------------------------------------------------------- el mundo
@dataclass
class Mundo:
    raiz: Path
    biblioteca: Path
    calibre_db: Path
    zotero_db: Path
    koreader: Path
    docdata: Path
    lectura_db: Path
    pdf1: Path
    pdf2: Path
    md5_1: str


def _calibre(db: Path, libros: list[tuple[int, str, str, str]], md5s: dict[int, str]) -> None:
    c = sqlite3.connect(db)
    c.executescript("""
        create table books(id integer primary key, title text, path text);
        create table authors(id integer primary key, name text);
        create table books_authors_link(id integer primary key, book int, author int);
        create table data(book int, format text, name text);
        create table custom_columns(id integer primary key, label text);
        insert into custom_columns values (7, 'ko_md5');
        create table custom_column_7(id integer primary key, book int, value text);
    """)
    for i, titulo, autor, carpeta in libros:
        c.execute("insert into books values (?,?,?)", (i, titulo, carpeta))
        c.execute("insert into authors values (?,?)", (i, autor))
        c.execute("insert into books_authors_link(book, author) values (?,?)", (i, i))
        c.execute("insert into data values (?, 'PDF', ?)", (i, titulo))
        if i in md5s:
            c.execute("insert into custom_column_7(book, value) values (?,?)", (i, md5s[i]))
    c.commit()
    c.close()


ZOTERO_ESQUEMA = """
CREATE TABLE libraries (libraryID INTEGER PRIMARY KEY, type TEXT);
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INT NOT NULL, dateAdded TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dateModified TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, clientDateModified TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    libraryID INT NOT NULL, key TEXT NOT NULL, version INT NOT NULL DEFAULT 0, synced INT NOT NULL DEFAULT 0,
    clientVersion INT NOT NULL DEFAULT 0, UNIQUE (libraryID, key), FOREIGN KEY (libraryID) REFERENCES libraries(libraryID));
CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INT, linkMode INT, contentType TEXT, path TEXT);
CREATE TABLE itemAnnotations (itemID INTEGER PRIMARY KEY, parentItemID INT NOT NULL, type INTEGER NOT NULL, authorName TEXT,
    text TEXT, comment TEXT, color TEXT, pageLabel TEXT, sortIndex TEXT NOT NULL, position TEXT NOT NULL, isExternal INT NOT NULL,
    textNormalized TEXT, commentNormalized TEXT,
    FOREIGN KEY (itemID) REFERENCES items(itemID) ON DELETE CASCADE, FOREIGN KEY (parentItemID) REFERENCES itemAttachments(itemID));
CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INT, note TEXT, title TEXT);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY, dateDeleted DEFAULT CURRENT_TIMESTAMP NOT NULL);
CREATE TABLE syncedSettings (setting TEXT NOT NULL, libraryID INT NOT NULL, value NOT NULL, version INT NOT NULL DEFAULT 0,
    synced INT NOT NULL DEFAULT 0, PRIMARY KEY (setting, libraryID));
INSERT INTO libraries VALUES (1, 'user');
INSERT INTO itemTypes VALUES (1, 'annotation'), (2, 'book'), (3, 'attachment'), (4, 'note');
"""


def _zotero(db: Path, adjuntos: list[tuple[int, str]]) -> dict[int, int]:
    """Un ítem de libro y su adjunto PDF por cada (calibre_id, ruta relativa); {calibre_id: itemID del adjunto}."""
    c = sqlite3.connect(db)
    c.executescript(ZOTERO_ESQUEMA)
    salida = {}
    for n, (calibre_id, rel) in enumerate(adjuntos):
        libro, adj = 10 + 2 * n, 11 + 2 * n
        c.execute("insert into items(itemID, itemTypeID, libraryID, key) values (?, 2, 1, ?)", (libro, f"LIBRO{n:03d}"))
        c.execute("insert into items(itemID, itemTypeID, libraryID, key) values (?, 3, 1, ?)", (adj, f"ADJUN{n:03d}"))
        c.execute("insert into itemAttachments values (?, ?, 2, 'application/pdf', ?)", (adj, libro, f"attachments:{rel}"))
        salida[calibre_id] = adj
    c.commit()
    c.close()
    return salida


def zotero_anotacion(db: Path, adjunto: int, clave: str, texto: str, hoja: int, y: float, comentario: str = "",
                     color: str = "#ffd400", tipo: int = 1, modificada: str = "2026-03-02 20:00:00") -> None:
    """Una anotación de Zotero en la línea de LINEAS que empieza en `y` (desde arriba): rects en puntos, origen abajo."""
    import json
    c = sqlite3.connect(db)
    item = c.execute("select coalesce(max(itemID), 100) + 1 from items").fetchone()[0]
    c.execute("insert into items(itemID, itemTypeID, libraryID, key, dateAdded, dateModified) values (?, 1, 1, ?, ?, ?)",
              (item, clave, modificada, modificada))
    pos = {"pageIndex": hoja - 1, "rects": [[72, ALTO - y - 3, 372, ALTO - y + 11]]}
    c.execute("insert into itemAnnotations values (?,?,?,NULL,?,?,?,?,?,?,0,NULL,NULL)",
              (item, adjunto, tipo, texto, comentario, color, str(hoja), f"{hoja - 1:05d}|000000|{int(y):05d}", json.dumps(pos)))
    c.commit()
    c.close()


def sidecar_koreader(carpeta: Path, md5: str, doc_path: Path, anotaciones: list[dict], extra: dict | None = None) -> Path:
    from lectura_base.lib import lua
    sdr = carpeta / "hashdocsettings" / md5[:2] / f"{md5}.sdr"
    sdr.mkdir(parents=True, exist_ok=True)
    datos = {"doc_path": str(doc_path), "partial_md5_checksum": md5, "percent_finished": 0.42, "doc_pages": 2,
             "summary": {"status": "reading", "modified": "2026-11-10"}, "stats": {"highlights": len(anotaciones), "notes": 0},
             "annotations": {i: a for i, a in enumerate(anotaciones, 1)}}
    datos.update(extra or {})
    p = sdr / "metadata.pdf.lua"
    p.write_bytes(lua.escribir(datos, str(doc_path)))
    return p


def ko_resaltado(hoja: int, y: float, texto: str, cuando: str, nota: str = "", color: str = "yellow") -> dict:
    a = {"chapter": "Capítulo 1", "color": color, "datetime": cuando, "drawer": "lighten", "page": hoja, "pageno": hoja,
         "pboxes": {1: {"x": 72.0, "y": y - 11, "w": 300.0, "h": 14.0}}, "text": texto,
         "pos0": {"page": hoja, "x": 72.0, "y": y}, "pos1": {"page": hoja, "x": 372.0, "y": y}}
    if nota:
        a["note"] = nota
    return a


def estadisticas_koreader(ruta: Path, md5: str, filas: list[tuple[int, int, int]], total: int) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(ruta)
    c.executescript("""
        create table book(id integer primary key autoincrement, title text, authors text, notes integer, last_open integer,
            highlights integer, pages integer, series text, language text, md5 text, total_read_time integer, total_read_pages integer);
        create table page_stat_data(id_book integer, page integer not null default 0, start_time integer not null default 0,
            duration integer not null default 0, total_pages integer not null default 0, unique (id_book, page, start_time));
    """)
    c.execute("insert into book(id, title, md5, pages, total_read_time) values (1, 'Economía de juguete', ?, 2, ?)", (md5, total))
    for pagina, inicio, dur in filas:
        c.execute("insert into page_stat_data values (1, ?, ?, ?, 2)", (pagina, inicio, dur))
    c.commit()
    c.close()
