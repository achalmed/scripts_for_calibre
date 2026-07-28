#!/usr/bin/env python3
"""Aplica los TSV de catalogacion (res_*.tsv) a la biblioteca Calibre.

Valida ANTES de escribir: toda etiqueta debe existir ya en la tabla tags, y
genero/clasificador/item_type deben pertenecer a sus enums. Cualquier fila
invalida se rechaza y se reporta; no se inventan valores nuevos.

Uso: aplicar.py [--apply]
"""
import glob
import sqlite3
import sys
from collections import Counter

DB = "/home/achalmaedison/Documents/biblioteca/metadata.db"
S = "/tmp/claude-1000/-home-achalmaedison-Documents-biblioteca/07e95f6c-2ea4-43cc-a8d4-62fab1b16986/scratchpad"

apply = "--apply" in sys.argv
con = sqlite3.connect(DB)
cur = con.cursor()

vocab = {r[0] for r in cur.execute("SELECT name FROM tags")}
generos = {r[0] for r in cur.execute("SELECT value FROM custom_column_32")}
clasifs = {r[0] for r in cur.execute("SELECT value FROM custom_column_43")}
itypes = {r[0] for r in cur.execute("SELECT value FROM custom_column_39")}
# ids que realmente estaban sin etiquetas (unico conjunto que podemos tocar)
objetivo = {r[0] for r in cur.execute(
    "SELECT b.id FROM books b WHERE NOT EXISTS"
    "(SELECT 1 FROM books_tags_link l WHERE l.book=b.id)")}

filas, revisar, rechazos = [], [], []
for f in sorted(glob.glob(f"{S}/res_0*.tsv")):
    for ln, linea in enumerate(open(f, encoding="utf-8"), 1):
        linea = linea.rstrip("\n")
        if not linea.strip():
            continue
        p = linea.split("\t")
        if len(p) < 2:
            rechazos.append((f, ln, "columnas insuficientes", linea[:60]))
            continue
        p += [""] * (5 - len(p))
        bid, tags, gen, cla, ity = p[0].strip(), p[1].strip(), p[2].strip(), p[3].strip(), p[4].strip()
        if not bid.isdigit():
            rechazos.append((f, ln, "id no numerico", linea[:60]))
            continue
        bid = int(bid)
        if bid not in objetivo:
            rechazos.append((f, ln, "id fuera del conjunto sin-etiquetas", str(bid)))
            continue
        if tags.upper() == "REVISAR" or not tags:
            revisar.append(bid)
            continue
        ts = [t.strip() for t in tags.split(",") if t.strip()]
        malas = [t for t in ts if t not in vocab]
        if malas:
            rechazos.append((f, ln, f"etiqueta inexistente: {malas}", str(bid)))
            continue
        if not 2 <= len(ts) <= 4:
            rechazos.append((f, ln, f"n tags={len(ts)} fuera de 2..4", str(bid)))
            continue
        for val, conj, nom in ((gen, generos, "genero"), (cla, clasifs, "clasificador"),
                               (ity, itypes, "item_type")):
            if val and val not in conj:
                rechazos.append((f, ln, f"{nom} invalido: {val!r}", str(bid)))
                break
        else:
            filas.append((bid, ts, gen, cla, ity))

print(f"validas: {len(filas)} | REVISAR: {len(revisar)} | rechazadas: {len(rechazos)}")
if rechazos:
    print("\n-- rechazos (primeros 25) --")
    for r in rechazos[:25]:
        print("  ", r)
print("\nGeneros:", dict(Counter(x[2] for x in filas).most_common()))
print("Clasificadores:", dict(Counter(x[3] for x in filas).most_common()))
print("Item types:", dict(Counter(x[4] for x in filas).most_common()))
if revisar:
    print("\nIDs marcados REVISAR:", revisar)

if apply and filas:
    tagid = {r[1]: r[0] for r in cur.execute("SELECT id,name FROM tags")}
    gid = {r[1]: r[0] for r in cur.execute("SELECT id,value FROM custom_column_32")}
    cid = {r[1]: r[0] for r in cur.execute("SELECT id,value FROM custom_column_43")}
    iid = {r[1]: r[0] for r in cur.execute("SELECT id,value FROM custom_column_39")}
    for bid, ts, gen, cla, ity in filas:
        for t in ts:
            cur.execute("INSERT OR IGNORE INTO books_tags_link(book,tag) VALUES (?,?)",
                        (bid, tagid[t]))
        for val, mapa, tabla in ((gen, gid, 32), (cla, cid, 43), (ity, iid, 39)):
            if val:
                cur.execute(
                    f"INSERT OR IGNORE INTO books_custom_column_{tabla}_link(book,value) "
                    "SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM "
                    f"books_custom_column_{tabla}_link WHERE book=?)",
                    (bid, mapa[val], bid))
    con.commit()
    print("\nAPLICADO")
elif not apply:
    print("\nSIMULACION (usar --apply para escribir)")
con.close()
