#!/usr/bin/env python3
"""Aplica los res_it_*.tsv (id, item_type) al Item type de Calibre.
Valida ANTES de escribir: tipo debe existir en el enum custom_column_39 y el
libro debe estar REALMENTE sin item type. Uso: aplicar_itype.py [--apply]"""
import os
import glob, sqlite3, sys
from collections import Counter
DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal
S="/tmp/claude-1000/-home-achalmaedison-Documents-biblioteca/07e95f6c-2ea4-43cc-a8d4-62fab1b16986/scratchpad"
apply="--apply" in sys.argv
con=sqlite3.connect(DB); cur=con.cursor()
enum={v:i for i,v in cur.execute("SELECT id,value FROM custom_column_39")}
objetivo={b for (b,) in cur.execute(
  "SELECT id FROM books b WHERE NOT EXISTS(SELECT 1 FROM books_custom_column_39_link g WHERE g.book=b.id)")}
filas=[]; revisar=0; rech=[]
for f in sorted(glob.glob(f"{S}/res_it_0*.tsv")):
    for ln,l in enumerate(open(f,encoding="utf-8"),1):
        l=l.rstrip("\n")
        if not l.strip(): continue
        p=l.split("\t")
        if len(p)<2 or not p[0].strip().isdigit(): rech.append((f,ln,"formato",l[:50])); continue
        b=int(p[0]); t=p[1].strip()
        if t.upper()=="REVISAR" or not t: revisar+=1; continue
        if b not in objetivo: rech.append((f,ln,"ya tiene tipo / fuera",str(b))); continue
        if t not in enum: rech.append((f,ln,f"tipo invalido: {t!r}",str(b))); continue
        filas.append((b,t))
print(f"validas: {len(filas)} | REVISAR: {revisar} | rechazadas: {len(rech)}")
if rech:
    for r in rech[:20]: print("  rech:",r)
print("distribucion:", dict(Counter(t for _,t in filas).most_common()))
if apply and filas:
    for b,t in filas:
        cur.execute("INSERT OR IGNORE INTO books_custom_column_39_link(book,value) VALUES(?,?)",(b,enum[t]))
    con.commit(); print("APLICADO")
    print("SIN item type restantes:", cur.execute(
      "SELECT COUNT(*) FROM books b WHERE NOT EXISTS(SELECT 1 FROM books_custom_column_39_link g WHERE g.book=b.id)").fetchone()[0])
    print("integridad:", cur.execute("PRAGMA integrity_check").fetchone()[0])
else:
    print("SIMULACION (usar --apply)")
con.close()
