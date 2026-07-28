#!/usr/bin/env python3
"""Rellena Item type (col 39) a partir del Clasificador (col 43).

Solo actua sobre libros con Item type VACIO y cuyo Clasificador tiene un
mapeo dominante e inequivoco observado en los datos ya catalogados.
Uso: itemtype.py [--apply]
"""
import sqlite3
import sys
from collections import Counter

DB = "/home/achalmaedison/Documents/biblioteca/metadata.db"

# Clasificador -> Item type Zotero (solo mapeos de alta confianza)
MAP = {
    # presentaciones / diapositivas de clase
    "Sesión": "Presentation",
    "Clase": "Presentation",
    "Diapositiva": "Presentation",
    "Slide": "Presentation",
    "Semana": "Presentation",
    "Unidad": "Presentation",
    "Tutorial": "Presentation",
    "Tema": "Presentation",
    "Presentación": "Presentation",
    # libros
    "Libro": "Book",
    # secciones de libro
    "Apuntes de estudio": "Book Section",
    "Capítulo de libro": "Book Section",
    # manuscritos / apuntes
    "Apuntes de clase": "Manuscript",
    # publicaciones periodicas
    "Número": "Journal Article",
    "Estudios economicos": "Journal Article",
    "Artículo de revista": "Magazine Article",
    # informes
    "Informe": "Report",
    "Informe técnico": "Report",
    "Documento oficial": "Report",
    "Normativa": "Report",
    "Guía": "Report",
    "Guía de estudio": "Report",
}

apply = "--apply" in sys.argv
con = sqlite3.connect(DB)
cur = con.cursor()

rows = cur.execute("""
    SELECT b.id, cl.value
    FROM books b
    JOIN books_custom_column_43_link l ON l.book = b.id
    JOIN custom_column_43 cl ON cl.id = l.value
    WHERE NOT EXISTS (SELECT 1 FROM books_custom_column_39_link g WHERE g.book = b.id)
""").fetchall()

plan = [(bid, MAP[cl]) for bid, cl in rows if cl in MAP]
print("Item type a asignar (por Clasificador):")
for it, n in Counter(x[1] for x in plan).most_common():
    print(f"  {n:5d}  {it}")
print(f"\n  {len(plan)} libros | {len(rows)-len(plan)} con Clasificador pero sin mapeo confiable")

if apply:
    def iid(v):
        r = cur.execute("SELECT id FROM custom_column_39 WHERE value=?", (v,)).fetchone()
        if r:
            return r[0]
        cur.execute("INSERT INTO custom_column_39(value) VALUES (?)", (v,))
        return cur.lastrowid

    cache = {}
    for bid, it in plan:
        if it not in cache:
            cache[it] = iid(it)
        cur.execute(
            "INSERT OR IGNORE INTO books_custom_column_39_link(book, value) VALUES (?, ?)",
            (bid, cache[it]),
        )
    con.commit()
    print("APLICADO")
else:
    print("SIMULACION (usar --apply para escribir)")
con.close()
