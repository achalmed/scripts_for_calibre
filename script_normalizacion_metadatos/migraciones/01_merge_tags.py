#!/usr/bin/env python3
"""Consolida etiquetas duplicadas en la biblioteca Calibre.

Uso: merge_tags.py [--apply]
Sin --apply solo simula (dry-run), segun la convencion del repo.
"""
import os
import sqlite3
import sys

DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal

# (etiqueta_origen, etiqueta_destino)
MERGES = [
    # --- typos, mayusculas y acentos ---
    ("ecuacione s_lineales", "algebra_lineal"),
    ("Ciencias sociales", "ciencias_sociales"),
    ("Divulgación", "divulgacion_cientifica"),
    ("divulgacion", "divulgacion_cientifica"),
    ("precálculo", "precalculo"),
    ("economía_desarrollo", "economia_desarrollo"),
    ("economía_computacional", "economia_computacional"),
    ("economía_ambiental", "economia_ambiental"),
    ("economía_financiera", "economia_financiera"),
    ("economia_asíatica", "economia_asiatica"),
    ("teoría_macroeconomica", "teoria_macroeconomica"),
    # --- duplicados es/en (cede el minoritario) ---
    ("matematica", "matematicas"),
    ("mathematics", "matematicas"),
    ("econometria", "econometrics"),
    ("finanzas", "finance"),
    ("etica", "ethics"),
    ("historia_economica", "economic_history"),
    ("probabilidad", "probability"),
    ("r_programming", "programming_r"),
    ("politica", "political_science"),
    ("ciencia_politica", "political_science"),
    # --- sinonimos evidentes ---
    ("economia", "economia_general"),
    ("recurso_educativo", "recursos_educativos"),
    ("logica", "logica_matematica"),
    ("ensayo", "ensayos"),
    ("regulacion", "teoria_regulacion"),
]

apply = "--apply" in sys.argv
con = sqlite3.connect(DB)
cur = con.cursor()


def tag_id(name):
    r = cur.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
    return r[0] if r else None


def n_books(tid):
    return cur.execute(
        "SELECT COUNT(*) FROM books_tags_link WHERE tag=?", (tid,)
    ).fetchone()[0]


total = 0
for old, new in MERGES:
    oid = tag_id(old)
    if oid is None:
        print(f"  omitido  {old!r}: no existe")
        continue
    nid = tag_id(new)
    n = n_books(oid)
    total += n
    if nid is None:
        print(f"  RENOMBRA {old!r} -> {new!r}  ({n} libros)")
        if apply:
            cur.execute("UPDATE tags SET name=? WHERE id=?", (new, oid))
    else:
        print(f"  FUSIONA  {old!r} -> {new!r}  ({n} libros)")
        if apply:
            cur.execute(
                "INSERT OR IGNORE INTO books_tags_link(book, tag) "
                "SELECT book, ? FROM books_tags_link WHERE tag=?",
                (nid, oid),
            )
            cur.execute("DELETE FROM books_tags_link WHERE tag=?", (oid,))
            cur.execute("DELETE FROM tags WHERE id=?", (oid,))

print(f"\n{len(MERGES)} reglas | {total} asignaciones de etiqueta afectadas")
if apply:
    con.commit()
    print("APLICADO")
else:
    print("SIMULACION (usar --apply para escribir)")
print("Etiquetas restantes:", cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0])
con.close()
