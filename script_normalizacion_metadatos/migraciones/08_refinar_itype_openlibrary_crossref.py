#!/usr/bin/env python3
"""Refina Item type de los libros 'inciertos' (Manuscript / Journal Article
SIN serie ni editorial): los verifica en OpenLibrary y Crossref.
  - hallado como LIBRO publicado (editorial real) -> Book
  - hallado en Crossref como articulo -> Journal Article
  - no hallado -> se deja igual
Escribe una propuesta TSV: id  tipo_actual  tipo_propuesto  fuente  ratio  extra
Solo LECTURA de las bases. Uso: refinar_itype.py
"""
import os
import sqlite3, json, time, re, unicodedata, urllib.parse, urllib.request
from difflib import SequenceMatcher
DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal
OUT = os.path.join(os.environ.get("MIGRACION_TRABAJO") or os.getcwd(), "refinar_prop.tsv")  # carpeta de trabajo con los TSV: MIGRACION_TRABAJO o la actual (era el scratchpad de la sesión que la corrió; normativa 5.5)
UA={"User-Agent":"biblioteca-personal/1.0 (refine item type)"}
JUNK=re.compile(r"createspace|independent publishing|lulu\.com|\bpublishing platform\b|scribd|z-library|academia\.edu", re.I)

def norm(s):
    if not s: return ""
    s=unicodedata.normalize("NFKD",str(s)); s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())
def ratio(a,b): return SequenceMatcher(None,norm(a),norm(b)).ratio()
def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20) as r:
            return json.load(r)
    except Exception: return None

def ol(title,author):
    q={"title":title,"limit":"1","fields":"title,publisher,isbn,number_of_pages_median"}
    if author: q["author"]=author
    d=get("https://openlibrary.org/search.json?"+urllib.parse.urlencode(q))
    if not d or not d.get("docs"): return None
    doc=d["docs"][0]
    pub=(doc.get("publisher") or [""])[0]
    return {"title":doc.get("title",""),"publisher":pub,
            "isbn":(doc.get("isbn") or [""])[0],
            "pages":doc.get("number_of_pages_median"),
            "r":ratio(title,doc.get("title",""))}

def cr(title,author):
    p={"query.bibliographic":title,"rows":"1"}
    if author: p["query.author"]=author
    d=get("https://api.crossref.org/works?"+urllib.parse.urlencode(p))
    it=(d or {}).get("message",{}).get("items") or None
    if not it: return None
    it=it[0]; st=(it.get("title") or [""])[0]
    return {"title":st,"type":it.get("type",""),"doi":it.get("DOI",""),
            "journal":(it.get("container-title") or [""])[0],"r":ratio(title,st)}

con=sqlite3.connect(f"file:{DB}?mode=ro",uri=True); cur=con.cursor()
rows=cur.execute("""
 SELECT b.id, b.title,
   (SELECT a.name FROM books_authors_link al JOIN authors a ON a.id=al.author WHERE al.book=b.id LIMIT 1),
   it.value
 FROM books b
 JOIN books_custom_column_39_link l ON l.book=b.id JOIN custom_column_39 it ON it.id=l.value
 WHERE it.value IN ('Manuscript','Journal Article')
   AND NOT EXISTS(SELECT 1 FROM books_series_link s WHERE s.book=b.id)
   AND NOT EXISTS(SELECT 1 FROM books_publishers_link p WHERE p.book=b.id)
   AND EXISTS(SELECT 1 FROM books_authors_link al JOIN authors a ON a.id=al.author WHERE al.book=b.id AND a.name NOT IN ('Unknown','Desconocido'))
 ORDER BY b.id""").fetchall()
TH=0.92
out=[]
for n,(bid,title,author,cur_t) in enumerate(rows,1):
    author=(author or "").replace("|"," ")
    prop=None
    o=ol(title,author); time.sleep(0.6)
    if o and o["r"]>=TH and o["publisher"] and not JUNK.search(o["publisher"]):
        prop=(bid,cur_t,"Book","OL",f"{o['r']:.2f}",f"{o['publisher']}|isbn:{o['isbn']}|pg:{o['pages']}")
    if prop is None:
        c=cr(title,author); time.sleep(0.6)
        if c and c["r"]>=TH:
            t=c["type"]
            if "book" in t or "monograph" in t:
                prop=(bid,cur_t,"Book","CR",f"{c['r']:.2f}",f"doi:{c['doi']}")
            elif cur_t!="Journal Article" and t in ("journal-article","proceedings-article","report","posted-content"):
                prop=(bid,cur_t,"Journal Article","CR",f"{c['r']:.2f}",f"{c['journal']}|doi:{c['doi']}")
    if prop and prop[1]!=prop[2]:
        out.append(prop)
    if n%100==0:
        print(f"[{n}/{len(rows)}] propuestas hasta ahora: {len(out)}", flush=True)
with open(OUT,"w",encoding="utf-8") as f:
    for r in out: f.write("\t".join(str(x) for x in r)+"\n")
from collections import Counter
print("TOTAL candidatos:",len(rows))
print("reclasificaciones propuestas:",len(out))
print("  por destino:",dict(Counter(r[2] for r in out)))
print("  por origen->destino:",dict(Counter(f"{r[1]}->{r[2]}" for r in out)))
print("fichero:",OUT)
con.close()
