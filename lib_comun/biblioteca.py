#!/usr/bin/env python3
"""biblioteca.py — resolutor único de la biblioteca Calibre (SOLO LECTURA sobre metadata.db).

Es la única pieza del ecosistema que sabe dónde está físicamente un libro y cómo se compara una
referencia con lo que ya existe. Los proyectos no guardan PDF ni enlaces simbólicos: referencian por
`calibre_id` (y `zotero_key`, `clave_bibtex`) y, cuando una herramienta necesita la ruta, se la pide aquí
(Método Documental, regla 1; `prompts/00 metodo/METODO_DOCUMENTAL.md`). Creado en FD2 (2026-09-07)
absorbiendo las copias locales de `ingesta_cursos/lib/biblioteca.py`, `ingesta/lib/catalogar.py` y el
`06_lecturas_biblioteca.py` de datafw.

Uso como módulo:
    import sys; sys.path.insert(0, "~/Documents/scripts_for_calibre/lib_comun"); import biblioteca as bib
    bib.datos(10064)            → dict con título, autores, serie, identificadores, columnas #…, carpeta, formatos, anexos
    bib.ruta(10064)             → Path del formato principal (PDF antes que EPUB)
    bib.anexos(10064)           → archivos de la carpeta data/ del libro
    bib.texto(10064)            → lista de páginas de texto (pdftotext -layout; caché en ~/.cache/biblioteca_texto)
    bib.existe(titulo=…, autor=…, isbn=…, doi=…, norma=…, archivo=…, paginas=…) → veredicto y candidatos
    bib.referencia(texto)       → identificadores que se reconocen en un texto libre (isbn, doi, norma)

Uso como CLI (misma semántica, salida legible o --json):
    biblioteca.py datos <id> [--json] · ruta <id> [--formato PDF] · anexos <id> · abrir <id> · texto <id> [--pagina N]
    biblioteca.py existe [--isbn X] [--doi X] [--norma X] [--titulo X] [--autor X] [--archivo RUTA] [--paginas N] [--ref "texto"] [--json]
    biblioteca.py duplicado TITULO PAGINAS [TOL] · autor "AUTOR" · titulo "archivo.pdf"   (compatibilidad con ingesta_cursos)

Variables: BIBLIOTECA (o QIR_BIBLIOTECA) cambia la biblioteca; XDG_CACHE_HOME la caché de texto.
Nunca escribe en metadata.db: escribir es de calibredb (con Calibre cerrado y el lock de lib_comun/lock.sh).
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path

BIB = Path(os.environ.get("BIBLIOTECA") or os.environ.get("QIR_BIBLIOTECA") or (Path.home() / "Documents" / "biblioteca"))
DB = BIB / "metadata.db"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "biblioteca_texto"
FORMATOS_PREF = ["PDF", "EPUB", "DJVU", "DOCX", "MOBI", "AZW3", "TXT", "HTML"]
COLUMNAS = ["zotero_key", "clasificador", "item_type", "pages", "genres", "estudio", "sub_tipo", "edition"]
TIPOS_NORMA = ["ley", "decreto supremo", "decreto legislativo", "decreto de urgencia", "decreto ley",
               "resolucion ministerial", "resolucion suprema", "resolucion directoral", "resolucion legislativa",
               "resolucion de superintendencia", "ordenanza regional", "ordenanza municipal", "directiva", "acuerdo"]
RE_NORMA = re.compile(r"\b(" + "|".join(t.replace(" ", r"\s+") for t in TIPOS_NORMA) + r")\s*(?:n[.º°o]*\s*)?"
                      r"([0-9]{2,5}(?:-[0-9]{4})?(?:-[a-z]{2,12})?)\b")
RE_ISBN = re.compile(r"\b(?:97[89][- ]?)?(?:[0-9][- ]?){9}[0-9xX]\b")
RE_DOI = re.compile(r"\b10\.[0-9]{4,9}/[^\s\"'<>)]+", re.I)


# ---------------------------------------------------------------- normalización
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(s):
    return {t for t in norm(s).split() if len(t) > 1}


def limpiar_titulo(s):
    s = re.sub(r"\.(pdf|epub|djvu|docx?)$", "", s, flags=re.I)
    s = re.sub(r"^(lectura|slide|sesion|clase|unidad|tema|capitulo|cap)?\s*[0-9]+([ ._-][0-9]+)*[ ._-]*", "", s, flags=re.I)
    s = s.replace("_", " ").strip()
    return (s[:1].upper() + s[1:]) if s else ""


def norma_id(texto):
    """«Decreto Supremo N.° 040-2014-PCM» → «decreto_supremo_040-2014-pcm» (grafía de la ingesta)."""
    m = RE_NORMA.search(norm_ligera(texto))
    if not m:
        return ""
    return re.sub(r"\s+", "_", m.group(1).strip()) + "_" + m.group(2)


def norm_ligera(s):
    """minúsculas sin tildes, conservando puntuación (para regex de identificadores)."""
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def referencia(texto):
    """Identificadores reconocibles en un texto libre: {'isbn': …, 'doi': …, 'norma': …}."""
    out = {}
    m = RE_DOI.search(texto or "")
    if m:
        out["doi"] = m.group(0).rstrip(".,;").lower()
    m = RE_ISBN.search(texto or "")
    if m:
        isbn = re.sub(r"[- ]", "", m.group(0))
        if len(isbn) in (10, 13):
            out["isbn"] = isbn
    n = norma_id(texto)
    if n:
        out["norma"] = n
    return out


# ---------------------------------------------------------------- acceso a la base
def conn():
    if not DB.exists():
        raise FileNotFoundError(f"no existe {DB}; fija BIBLIOTECA")
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def _columnas(c):
    """label → (id, datatype, normalizada) de las columnas personalizadas que interesan."""
    out = {}
    for cid, label, dt in c.execute("select id, label, datatype from custom_columns"):
        if label not in COLUMNAS:
            continue
        cols = [r[1] for r in c.execute(f"pragma table_info(custom_column_{cid})")]
        out[label] = (cid, dt, "book" not in cols)
    return out


def _valor(c, col, bid):
    cid, dt, normalizada = col
    if normalizada:
        rows = c.execute(f"select v.value from custom_column_{cid} v join books_custom_column_{cid}_link l on l.value=v.id "
                         f"where l.book=?", (bid,)).fetchall()
        vals = [r[0] for r in rows]
        return vals if len(vals) > 1 else (vals[0] if vals else None)
    r = c.execute(f"select value from custom_column_{cid} where book=?", (bid,)).fetchone()
    return r[0] if r else None


def _formatos(c, bid, carpeta):
    fm = [(f, n, sz) for f, n, sz in c.execute("select format, name, uncompressed_size from data where book=?", (bid,))]
    fm.sort(key=lambda x: FORMATOS_PREF.index(x[0]) if x[0] in FORMATOS_PREF else 99)
    return [{"formato": f, "ruta": str(carpeta / f"{n}.{f.lower()}"), "bytes": sz} for f, n, sz in fm]


def datos(bid):
    """Todo lo que un proyecto necesita saber de un libro; None si el id no existe."""
    bid = int(bid)
    with conn() as c:
        r = c.execute("select id, title, path, pubdate, timestamp, series_index, has_cover from books where id=?", (bid,)).fetchone()
        if not r:
            return None
        carpeta = BIB / r[2]
        autores = [a for (a,) in c.execute("select a.name from authors a join books_authors_link l on l.author=a.id "
                                            "where l.book=? order by l.id", (bid,))]
        serie = c.execute("select s.name from series s join books_series_link l on l.series=s.id where l.book=?", (bid,)).fetchone()
        editorial = c.execute("select p.name from publishers p join books_publishers_link l on l.publisher=p.id where l.book=?", (bid,)).fetchone()
        idiomas = [x for (x,) in c.execute("select lc.lang_code from languages lc join books_languages_link l on l.lang_code=lc.id where l.book=?", (bid,))]
        tags = [t for (t,) in c.execute("select t.name from tags t join books_tags_link l on l.tag=t.id where l.book=? order by t.name", (bid,))]
        ids = {t: v for t, v in c.execute("select type, val from identifiers where book=?", (bid,))}
        cols = _columnas(c)
        extra = {f"#{k}": _valor(c, cols[k], bid) for k in COLUMNAS if k in cols}
        formatos = _formatos(c, bid, carpeta)
    return {"calibre_id": bid, "titulo": r[1], "autores": [a.replace("|", ",") for a in autores], "autores_calibre": autores,
            "serie": serie[0] if serie else "", "serie_index": r[5] if serie else None, "editorial": editorial[0] if editorial else "",
            "pubdate": (r[3] or "")[:10], "anadido": (r[4] or "")[:10], "idiomas": idiomas, "tags": tags, "identificadores": ids,
            "zotero_key": extra.get("#zotero_key") or "", **extra, "carpeta": str(carpeta), "formatos": formatos,
            "ruta": formatos[0]["ruta"] if formatos else "", "anexos": [str(p) for p in _anexos(carpeta)]}


def _anexos(carpeta):
    d = Path(carpeta) / "data"
    return sorted(p for p in d.rglob("*") if p.is_file()) if d.is_dir() else []


def ruta(bid, formato=None):
    """Path del formato principal (o del pedido); None si no hay archivo."""
    d = datos(bid)
    if not d:
        return None
    for f in d["formatos"]:
        if not formato or f["formato"].upper() == formato.upper():
            p = Path(f["ruta"])
            if p.exists():
                return p
    return None


def anexos(bid):
    d = datos(bid)
    return [Path(a) for a in d["anexos"]] if d else []


def abrir(bid):
    p = ruta(bid)
    if not p:
        return False
    subprocess.Popen(["xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


# ---------------------------------------------------------------- texto por páginas
def texto(bid, cache=True, layout=True):
    """Páginas de texto del formato principal (índice 0 = página 1 del PDF, no la impresa). [] si no hay texto.
    layout=True conserva la disposición (tablas, cabeceras); layout=False da el orden de lectura, necesario en los
    documentos a dos columnas (normas de El Peruano y del Congreso), donde -layout entrelaza las columnas."""
    p = ruta(bid)
    if not p:
        return []
    st = p.stat()
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / f"{int(bid)}_{int(st.st_mtime)}_{st.st_size}{'' if layout else '_lectura'}.txt"
    if not (cache and cf.exists()):
        if p.suffix.lower() == ".pdf":
            subprocess.run(["pdftotext", *(["-layout"] if layout else []), "-enc", "UTF-8", str(p), str(cf)], capture_output=True)
        else:
            subprocess.run(["ebook-convert", str(p), str(cf)], capture_output=True)
        if not cf.exists():
            return []
    return cf.read_text(encoding="utf-8", errors="replace").split("\f")


# ---------------------------------------------------------------- existencia
def _sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _lite(c, bid, cols):
    d = datos(bid)
    return {k: d[k] for k in ("calibre_id", "titulo", "autores", "pubdate", "serie", "identificadores", "zotero_key", "ruta")} | {"paginas": d.get("#pages")}


def existe(titulo=None, autor=None, isbn=None, doi=None, norma=None, archivo=None, paginas=None, ref=None, tol=2):
    """Veredicto: existe | otra-edicion | no-existe, con candidatos y las búsquedas ejecutadas (prompt_00)."""
    if ref:
        r = referencia(ref)
        isbn, doi, norma = isbn or r.get("isbn"), doi or r.get("doi"), norma or r.get("norma")
        if not titulo and not any((isbn, doi, norma)):
            titulo = ref
    if norma and ":" not in norma and not RE_NORMA.match(norma.replace("_", " ")):
        norma = norma_id(norma) or norma
    busquedas, exactos, parecidos = [], [], []
    with conn() as c:
        cols = _columnas(c)
        for tipo, val in (("isbn", (isbn or "").replace("-", "")), ("doi", (doi or "").lower()), ("norma", (norma or "").replace("norma:", ""))):
            if not val:
                continue
            hits = [b for (b,) in c.execute("select book from identifiers where type=? and lower(val)=?", (tipo, val.lower()))]
            busquedas.append({"metodo": f"identificador {tipo}:{val}", "resultados": len(hits)})
            exactos += hits
        if archivo and Path(archivo).exists():
            sz = Path(archivo).stat().st_size
            cand = c.execute("select book, format, name from data where uncompressed_size=?", (sz,)).fetchall()
            sha = _sha256(archivo)
            hits = []
            for b, f, n in cand:
                p = BIB / c.execute("select path from books where id=?", (b,)).fetchone()[0] / f"{n}.{f.lower()}"
                if p.exists() and _sha256(p) == sha:
                    hits.append(b)
            busquedas.append({"metodo": f"huella sha256 {sha[:16]}… (mismo tamaño: {len(cand)} candidatos)", "resultados": len(hits)})
            exactos += hits
        if titulo:
            key = norm(limpiar_titulo(titulo)); kt = tokens(key); at = tokens(autor or "")
            pcol = cols.get("pages")
            for b, t in c.execute("select id, title from books"):
                nt = norm(t)
                if not nt:
                    continue
                tt = tokens(nt)
                mismo = nt == key or (kt and tt == kt)
                jac = len(kt & tt) / len(kt | tt) if (kt | tt) else 0
                if not mismo and jac < 0.6 and not (kt and kt <= tt and len(kt) >= 3):
                    continue
                if at:
                    aut = " ".join(a for (a,) in c.execute("select a.name from authors a join books_authors_link l on l.author=a.id where l.book=?", (b,)))
                    if not (at & tokens(aut)):
                        if not mismo:
                            continue
                pg = _valor(c, pcol, b) if pcol else None
                if mismo and (not paginas or not pg or abs(int(pg) - int(paginas)) <= tol):
                    exactos.append(b)
                else:
                    parecidos.append(b)
            busquedas.append({"metodo": f"título por tokens «{key}»" + (f" y autor «{norm(autor)}»" if autor else ""),
                              "resultados": len(set(exactos)) + len(set(parecidos))})
        exactos = sorted(set(exactos)); parecidos = sorted(set(parecidos) - set(exactos))
        res = "existe" if exactos else ("otra-edicion" if parecidos else "no-existe")
        return {"resultado": res, "busquedas": busquedas,
                "candidatos": [_lite(c, b, cols) for b in exactos[:10]], "parecidos": [_lite(c, b, cols) for b in parecidos[:10]]}


# ---------------------------------------------------------------- compatibilidad con ingesta_cursos
def duplicado(titulo, paginas, tol=0):
    r = existe(titulo=titulo, paginas=paginas, tol=tol)
    ids = [str(x["calibre_id"]) for x in r["candidatos"]]
    return ",".join(ids)


def autor_canonico(autor_pdf):
    tk = tokens(autor_pdf)
    if not tk:
        return ""
    with conn() as c:
        nombres = [n for (n,) in c.execute("select name from authors")]
    hits = sorted({n for n in nombres if tk <= tokens(n)}, key=len)
    if len(hits) == 1 or (hits and all(tokens(h) == tokens(hits[0]) for h in hits)):
        return hits[0].replace("|", ",")
    return ""


# ---------------------------------------------------------------- CLI
def _imprimir_datos(d):
    print(f"[{d['calibre_id']}] {d['titulo']}")
    print(f"  autores: {'; '.join(d['autores'])}   año: {d['pubdate'][:4]}   serie: {d['serie']} {d['serie_index'] or ''}")
    print(f"  identificadores: {d['identificadores']}   zotero_key: {d['zotero_key'] or '(vacía)'}   #clasificador: {d.get('#clasificador')}   #item_type: {d.get('#item_type')}   #pages: {d.get('#pages')}")
    print(f"  ruta: {d['ruta'] or '(sin archivo)'}")
    for f in d["formatos"][1:]:
        print(f"        {f['ruta']}")
    if d["anexos"]:
        print(f"  anexos ({len(d['anexos'])}):")
        for a in d["anexos"]:
            print(f"        {a}")


def imprimir_existe(r):
    print(f"RESULTADO: {r['resultado'].replace('-', ' ')}")
    print("Búsquedas ejecutadas:")
    for b in r["busquedas"]:
        print(f"  - {b['metodo']} → {b['resultados']} resultado(s)")
    for rot, lst in (("Ítem existente", r["candidatos"]), ("Parecidos (otra edición o versión)", r["parecidos"])):
        if lst:
            print(f"{rot}:")
            for x in lst:
                print(f"  calibre_id: {x['calibre_id']}   zotero_key: {x['zotero_key'] or '(vacía)'}   título: {x['titulo']}   autores: {'; '.join(x['autores'])}   año: {x['pubdate'][:4]}   páginas: {x['paginas'] or '?'}")
    print("Siguiente paso: " + {"existe": "prompt_03 si falta zotero_key; prompt_09 para vincular al proyecto",
                                "otra-edicion": "decidir si la edición importa; si no, usar el ítem parecido",
                                "no-existe": "prompt_01 (localizar y descargar)"}[r["resultado"]])


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="resolutor de la biblioteca Calibre (solo lectura)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("datos", "ruta", "anexos", "abrir", "texto"):
        p = sub.add_parser(n); p.add_argument("id", type=int)
        if n == "datos": p.add_argument("--json", action="store_true")
        if n == "ruta": p.add_argument("--formato")
        if n == "texto": p.add_argument("--pagina", type=int)
    p = sub.add_parser("existe")
    for o in ("--isbn", "--doi", "--norma", "--titulo", "--autor", "--archivo", "--ref"):
        p.add_argument(o)
    p.add_argument("--paginas", type=int); p.add_argument("--json", action="store_true")
    p = sub.add_parser("duplicado"); p.add_argument("titulo"); p.add_argument("paginas", type=int, nargs="?", default=0); p.add_argument("tol", type=int, nargs="?", default=0)
    p = sub.add_parser("autor"); p.add_argument("autor")
    p = sub.add_parser("titulo"); p.add_argument("nombre")
    a = ap.parse_args(argv)
    if a.cmd == "datos":
        d = datos(a.id)
        if not d:
            print(f"[ERROR] no existe el id {a.id}", file=sys.stderr); return 1
        print(json.dumps(d, ensure_ascii=False, indent=2)) if a.json else _imprimir_datos(d); return 0
    if a.cmd == "ruta":
        p = ruta(a.id, a.formato); print(p or ""); return 0 if p else 1
    if a.cmd == "anexos":
        for x in anexos(a.id): print(x)
        return 0
    if a.cmd == "abrir":
        return 0 if abrir(a.id) else 1
    if a.cmd == "texto":
        pags = texto(a.id)
        if a.pagina:
            print(pags[a.pagina - 1] if 0 < a.pagina <= len(pags) else "")
        else:
            print("\f".join(pags))
        return 0 if pags else 1
    if a.cmd == "existe":
        if not any((a.isbn, a.doi, a.norma, a.titulo, a.archivo, a.ref)):
            ap.error("indica al menos --ref, --titulo, --isbn, --doi, --norma o --archivo")
        r = existe(a.titulo, a.autor, a.isbn, a.doi, a.norma, a.archivo, a.paginas, a.ref)
        print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else imprimir_existe(r)
        return {"existe": 0, "otra-edicion": 2, "no-existe": 1}[r["resultado"]]
    if a.cmd == "duplicado":
        print(duplicado(a.titulo, a.paginas, a.tol)); return 0
    if a.cmd == "autor":
        print(autor_canonico(a.autor)); return 0
    if a.cmd == "titulo":
        print(limpiar_titulo(a.nombre)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
