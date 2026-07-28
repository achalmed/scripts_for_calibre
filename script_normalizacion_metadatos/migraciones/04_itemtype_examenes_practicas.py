#!/usr/bin/env python3
"""Completa Item type del residuo, decidido por familia de Clasificador.
Solo actua sobre libros con Item type VACIO. Uso: itemtype2.py [--apply]"""
import sqlite3, sys
from collections import Counter
DB = "/home/achalmaedison/Documents/biblioteca/metadata.db"

MAP = {
    # material de aula inedito (examenes, practicas, ejercicios, apuntes) -> Manuscript
    "Ejercicio": "Manuscript", "Ejercicios resueltos": "Manuscript",
    "Problemas": "Manuscript", "Problemas resueltos": "Manuscript",
    "Solucionario": "Manuscript", "Laboratorio": "Manuscript",
    "Taller": "Manuscript", "Práctica": "Manuscript",
    "Evaluación": "Manuscript", "Práctica calificada": "Manuscript",
    "Práctica dirigida": "Manuscript", "Parcial": "Manuscript",
    "Caso práctico": "Manuscript", "Handout": "Manuscript",
    "Material complementario": "Manuscript", "Monografía": "Manuscript",
    "Lectura": "Manuscript", "Notas de sesion": "Manuscript",
    "Apuntes de historia": "Manuscript", "Compendio": "Manuscript",
    # parte de un libro -> Book Section
    "Capítulo": "Book Section", "Parte": "Book Section",
    # documento institucional -> Report
    "Documento de trabajo": "Report", "Lineamientos": "Report",
    "Folleto": "Report", "Programa": "Report", "Sílabus": "Report",
    # DELIBERADAMENTE fuera (ambiguos): "Módulo", "Serie"
}

apply = "--apply" in sys.argv
con = sqlite3.connect(DB); cur = con.cursor()
rows = cur.execute("""
    SELECT b.id, cl.value FROM books b
    JOIN books_custom_column_43_link l ON l.book=b.id
    JOIN custom_column_43 cl ON cl.id=l.value
    WHERE NOT EXISTS(SELECT 1 FROM books_custom_column_39_link g WHERE g.book=b.id)
""").fetchall()
plan = [(b, MAP[c]) for b, c in rows if c in MAP]
sin = Counter(c for b, c in rows if c not in MAP)
print("A asignar:", dict(Counter(x[1] for x in plan)))
print(f"total {len(plan)} | quedan sin mapear (ambiguos):", dict(sin))
if apply:
    def iid(v):
        r = cur.execute("SELECT id FROM custom_column_39 WHERE value=?", (v,)).fetchone()
        return r[0]
    cache = {}
    for b, it in plan:
        cache.setdefault(it, iid(it))
        cur.execute("INSERT OR IGNORE INTO books_custom_column_39_link(book,value) VALUES(?,?)",
                    (b, cache[it]))
    con.commit(); print("APLICADO")
else:
    print("SIMULACION")
con.close()
