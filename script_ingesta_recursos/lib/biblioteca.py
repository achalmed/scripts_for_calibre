#!/usr/bin/env python3
"""lib/biblioteca.py — consultas de SOLO LECTURA a metadata.db para la ingesta.

  biblioteca.py duplicado  TITULO PAGINAS [TOLERANCIA]   → id existente (o vacío)
  biblioteca.py autor      "AUTOR DEL PDF"               → nombre canónico de la biblioteca (o vacío)
  biblioteca.py titulo     "nombre de archivo o Title"   → título limpio en la grafía de la biblioteca

Reglas (meta/MODELO_METADATOS.md): comparación SEMÁNTICA por tokens, nunca por cadena;
autores en la grafía «Nombre, Apellidos» ya existente; títulos en frase (sin numeración inicial).
"""
import os, re, sqlite3, sys, unicodedata
DB = os.path.join(os.environ.get("QIR_BIBLIOTECA", os.path.expanduser("~/Documents/biblioteca")), "metadata.db")
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
def tokens(s): return {t for t in norm(s).split() if len(t) > 1}
def conn(): return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
def limpiar_titulo(s):
    s = re.sub(r"\.pdf$", "", s, flags=re.I)
    s = re.sub(r"^(lectura|slide|sesion|clase|unidad|tema|capitulo|cap)?\s*[0-9]+([ ._-][0-9]+)*[ ._-]*", "", s, flags=re.I)
    s = s.replace("_", " ").strip()
    return (s[:1].upper() + s[1:]) if s else ""
def duplicado(titulo, paginas, tol=0):
    key = norm(limpiar_titulo(titulo)); key_t = tokens(key)
    if not key: return ""
    with conn() as c:
        pages_col = c.execute("select id from custom_columns where label='pages'").fetchone()
        sql = "select b.id, b.title, coalesce(p.value, 0) from books b left join custom_column_%s p on p.book=b.id" % pages_col[0] if pages_col else "select id, title, 0 from books"
        cand = []
        for bid, t, pg in c.execute(sql):
            nt = norm(t)
            if nt == key or (key_t and tokens(nt) == key_t):
                if not paginas or not pg or abs(int(pg) - int(paginas)) <= tol: cand.append(bid)
    return str(cand[0]) if len(cand) == 1 else (",".join(map(str, cand)) if cand else "")
def autor_canonico(autor_pdf):
    tk = tokens(autor_pdf)
    if not tk: return ""
    with conn() as c:
        rows = [(n, len(tokens(n))) for (n,) in c.execute("select name from authors")]
    # el nombre del PDF debe estar contenido en el nombre canónico (TONY HINOJOSA ⊂ Tony| Hinojosa Vivanco)
    hits = sorted({n for n, _ in rows if tk <= tokens(n)}, key=len)
    if len(hits) == 1 or (hits and all(tokens(h) == tokens(hits[0]) for h in hits)):
        return hits[0].replace("|", ",")
    return ""
if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    if op == "duplicado": print(duplicado(sys.argv[2], int(sys.argv[3] or 0), int(sys.argv[4]) if len(sys.argv) > 4 else 0))
    elif op == "autor": print(autor_canonico(sys.argv[2]))
    elif op == "titulo": print(limpiar_titulo(sys.argv[2]))
    else: print(__doc__); sys.exit(2)
