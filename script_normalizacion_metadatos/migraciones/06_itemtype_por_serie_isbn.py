#!/usr/bin/env python3
"""Plan (dry-run) para completar Item type de los libros sin catalogar,
estrictamente por señal fuerte:
  1) misma SERIE que hermanos ya catalogados -> tipo dominante de la serie
  2) sin serie pero con ISBN -> Book (el prompt: ISBN = libro publicado)
Todo lo demas queda SIN resolver (para subagentes/manual).
"""
import os
import sqlite3
from collections import Counter, defaultdict
DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal
con=sqlite3.connect(f"file:{DB}?mode=ro",uri=True); cur=con.cursor()

itype={}   # book -> item_type actual
for b,v in cur.execute("SELECT l.book,c.value FROM books_custom_column_39_link l JOIN custom_column_39 c ON c.id=l.value"):
    itype[b]=v
serie={}   # book -> serie
for b,s in cur.execute("SELECT l.book,x.name FROM books_series_link l JOIN series x ON x.id=l.series"):
    serie[b]=s
isbn={b for (b,) in cur.execute("SELECT book FROM identifiers WHERE type='isbn'")}

# tipo dominante por serie (de los ya catalogados)
serie_types=defaultdict(Counter)
for b,t in itype.items():
    if b in serie: serie_types[serie[b]][t]+=1
serie_dom={}
for s,c in serie_types.items():
    top,n=c.most_common(1)[0]
    # dominante fuerte: mayoria absoluta y >=2 hermanos
    if n>=2 and n>=0.6*sum(c.values()): serie_dom[s]=(top,n,sum(c.values()))

sin=[b for (b,) in cur.execute("SELECT id FROM books") if b not in itype]
plan_serie=[]; plan_isbn=[]; sin_resolver=[]
for b in sin:
    s=serie.get(b)
    if s in serie_dom:
        plan_serie.append((b,serie_dom[s][0]))
    elif b in isbn:
        plan_isbn.append((b,"Book"))
    else:
        sin_resolver.append(b)

print(f"SIN item type: {len(sin)}")
print(f"  1) por SERIE (hermanos catalogados): {len(plan_serie)}")
print(f"     ->", dict(Counter(t for _,t in plan_serie)))
print(f"  2) por ISBN sin serie -> Book: {len(plan_isbn)}")
print(f"  SIN RESOLVER (necesitan juicio por metadato): {len(sin_resolver)}")

# de los sin resolver, cuantos tienen editorial / paginas (pistas para subagente)
con_ed=sum(1 for b in sin_resolver if cur.execute("SELECT 1 FROM books_publishers_link WHERE book=?",(b,)).fetchone())
print(f"     de esos, con editorial: {con_ed} | sin editorial: {len(sin_resolver)-con_ed}")
print("\n  muestra de series que se propagan:")
seen=set()
for b,t in plan_serie:
    s=serie[b]
    if s not in seen:
        seen.add(s); print(f"    '{s}' -> {t}  (serie ya {serie_dom[s][2]} catalogados)")
    if len(seen)>=12: break
