#!/usr/bin/env python3
"""Aplica refinar_prop.tsv: reclasifica Item type y, si el destino es Book por
OpenLibrary, rellena editorial/ISBN donde esten vacios (bonus, aditivo).
Uso: aplicar_refino.py [--apply]"""
import os
import sqlite3, sys, re
from collections import Counter
DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal
PROP = os.path.join(os.environ.get("MIGRACION_TRABAJO") or os.getcwd(), "refinar_prop.tsv")  # carpeta de trabajo con los TSV: MIGRACION_TRABAJO o la actual (era el scratchpad de la sesión que la corrió; normativa 5.5)
apply="--apply" in sys.argv
con=sqlite3.connect(DB); cur=con.cursor()
enum={v:i for i,v in cur.execute("SELECT id,value FROM custom_column_39")}
cur_type={}
for b,v in cur.execute("SELECT l.book,c.value FROM books_custom_column_39_link l JOIN custom_column_39 c ON c.id=l.value"): cur_type[b]=v
reclass=0; pub_fill=0; isbn_fill=0; rech=0
for l in open(PROP,encoding="utf-8"):
    p=l.rstrip("\n").split("\t")
    if len(p)<3: continue
    bid=int(p[0]); old=p[1]; new=p[2]; src=p[3] if len(p)>3 else ""; extra=p[5] if len(p)>5 else ""
    if cur_type.get(bid)!=old or new not in enum:  # el libro debe seguir con el tipo viejo
        rech+=1; continue
    if apply:
        cur.execute("UPDATE books_custom_column_39_link SET value=? WHERE book=? AND value=?",(enum[new],bid,enum[old]))
    reclass+=1
    # bonus: rellenar editorial/isbn si OL y estan vacios
    if src=="OL" and new=="Book":
        m=re.match(r"^(.*?)\|isbn:(.*?)\|pg:",extra)
        if m:
            pub=m.group(1).strip(); isbn=m.group(2).strip()
            if pub and not cur.execute("SELECT 1 FROM books_publishers_link WHERE book=?",(bid,)).fetchone():
                pub_fill+=1
                if apply:
                    r=cur.execute("SELECT id FROM publishers WHERE name=?",(pub,)).fetchone()
                    if r:
                        pid=r[0]
                    else:
                        cur.execute("INSERT INTO publishers(name) VALUES(?)",(pub,)); pid=cur.lastrowid
                    cur.execute("INSERT OR IGNORE INTO books_publishers_link(book,publisher) VALUES(?,?)",(bid,pid))
            if isbn and re.fullmatch(r"[0-9Xx-]{10,17}",isbn) and not cur.execute("SELECT 1 FROM identifiers WHERE book=? AND type='isbn'",(bid,)).fetchone():
                isbn_fill+=1
                if apply: cur.execute("INSERT OR IGNORE INTO identifiers(book,type,val) VALUES(?,?,?)",(bid,'isbn',isbn))
print(f"reclasificaciones: {reclass} | rechazadas: {rech}")
tot=[l.rstrip("\n").split("\t") for l in open(PROP,encoding="utf-8") if l.strip()]
print("  destino:",dict(Counter(r[2] for r in tot)))
print(f"  bonus (aditivo): editorial rellenada {pub_fill}, ISBN {isbn_fill}")
if apply:
    con.commit(); print("APLICADO | integridad:",cur.execute("PRAGMA integrity_check").fetchone()[0])
else:
    print("SIMULACION (usar --apply)")
con.close()
