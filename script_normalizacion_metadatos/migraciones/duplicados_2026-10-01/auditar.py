"""auditar.py — duplicados en Calibre y en Zotero (2026-10-01; SOLO LECTURA de metadata.db y zotero.sqlite).

    python3 auditar.py            (escribe los TSV de esta carpeta e imprime el resumen)

Calibre
  C1 mismo título normalizado y mismo primer autor (por tokens)       → calibre_titulo_autor.tsv
  C2 mismo ISBN                                                       → calibre_isbn.tsv
  C3 archivo idéntico (mismo tamaño y mismo MD5)                      → calibre_archivo.tsv
Zotero (ítems regulares fuera de la papelera)
  Z1 mismo título normalizado, primer creador y año                   → zotero_titulo.tsv
  Z2 un ítem con adjuntos de varios libros de Calibre                 → zotero_varios_libros.tsv
  Z3 varios libros de Calibre con la misma #zotero_key                → zotero_clave_compartida.tsv
  Z4 ítems sin libro de Calibre (huérfanos), por colección            → zotero_huerfanos.tsv
Un grupo es un CANDIDATO: se decide mirando el contenido (páginas, primera página), nunca por la sola
coincidencia de título; dos ediciones o un artículo y su libro no son duplicados.
"""
import hashlib
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[3] / "core"))
import env  # noqa: E402

BIB = Path(env.BIBLIOTECA_DIR)


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", s))


def tokens_autor(a):
    return frozenset(t for t in norm((a or "").replace("|", " ")).split() if len(t) > 2)


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def escribir(nombre, cab, filas):
    with open(AQUI / nombre, "w", encoding="utf-8") as f:
        f.write("# " + "\t".join(cab) + "\n")
        for r in filas:
            f.write("\t".join(str(x) for x in r) + "\n")


def main():
    c = sqlite3.connect(f"file:{BIB / 'metadata.db'}?mode=ro", uri=True)
    z = sqlite3.connect(f"file:{env.ZOTERO_DB}?mode=ro", uri=True)
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    pcol = c.execute("select id from custom_columns where label = 'pages'").fetchone()
    libros = {}
    for b, t, p in c.execute("select id, title, path from books"):
        libros[b] = {"titulo": t, "ruta": p}
    for b, a in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id = l.author order by l.id"):
        libros[b].setdefault("autor", a)
    for b, k in c.execute(f"select book, value from custom_column_{col}"):
        libros[b]["clave"] = k
    if pcol:
        for b, n in c.execute(f"select book, value from custom_column_{pcol[0]}"):
            libros[b]["pags"] = n
    res = {}

    # C1
    g = defaultdict(list)
    for b, d in libros.items():
        g[(norm(d["titulo"]), tokens_autor(d.get("autor")))].append(b)
    filas = [(i, b, libros[b]["titulo"], libros[b].get("autor"), libros[b].get("pags", ""), libros[b].get("clave", ""))
             for i, (k, bs) in enumerate(x for x in g.items() if len(x[1]) > 1) for b in bs]
    escribir("calibre_titulo_autor.tsv", ["grupo", "libro", "título", "autor", "páginas", "zotero_key"], filas)
    res["C1 título+autor"] = sum(1 for x in g.values() if len(x) > 1)

    # C2
    g = defaultdict(list)
    for b, v in c.execute("select book, val from identifiers where type = 'isbn'"):
        v = re.sub(r"[^0-9Xx]", "", v)
        if len(v) in (10, 13):
            g[v].append(b)
    filas = [(isbn, b, libros[b]["titulo"], libros[b].get("pags", "")) for isbn, bs in g.items() if len(bs) > 1 for b in bs]
    escribir("calibre_isbn.tsv", ["isbn", "libro", "título", "páginas"], filas)
    res["C2 ISBN"] = sum(1 for x in g.values() if len(x) > 1)

    # C3
    por_tam = defaultdict(list)
    for b, f, n, s in c.execute("select book, format, name, uncompressed_size from data"):
        p = BIB / libros[b]["ruta"] / f"{n}.{f.lower()}"
        if p.exists():
            por_tam[(f, p.stat().st_size)].append((b, p))
    g = defaultdict(list)
    for (f, _), xs in por_tam.items():
        if len({b for b, _ in xs}) > 1:
            for b, p in xs:
                g[(f, md5(p))].append(b)
    filas = [(h[:12], f, b, libros[b]["titulo"], libros[b].get("clave", "")) for (f, h), bs in g.items() if len(set(bs)) > 1 for b in bs]
    escribir("calibre_archivo.tsv", ["md5", "formato", "libro", "título", "zotero_key"], filas)
    res["C3 archivo idéntico"] = sum(1 for x in g.values() if len(set(x)) > 1)

    # Zotero
    borrados = {i for (i,) in z.execute("select itemID from deletedItems")}
    tipos_fuera = {r[0] for r in z.execute("select itemTypeID from itemTypes where typeName in ('attachment','note','annotation')")}
    items = {}
    for i, k, t in z.execute("select itemID, key, itemTypeID from items"):
        if i not in borrados and t not in tipos_fuera:
            items[i] = {"key": k}
    for i, f, v in z.execute("select d.itemID, f.fieldName, v.value from itemData d join fields f on f.fieldID = d.fieldID"
                             " join itemDataValues v on v.valueID = d.valueID where f.fieldName in ('title','date')"):
        if i in items:
            items[i][f] = v
    for i, ln in z.execute("select ic.itemID, c.lastName from itemCreators ic join creators c on c.creatorID = ic.creatorID"
                           " where ic.orderIndex = 0"):
        if i in items:
            items[i]["autor"] = ln
    colec = defaultdict(list)
    for i, n in z.execute("select ci.itemID, c.collectionName from collectionItems ci join collections c on c.collectionID = ci.collectionID"):
        colec[i].append(n)
    # Z1
    g = defaultdict(list)
    for i, d in items.items():
        if d.get("title"):
            g[(norm(d["title"]), norm(d.get("autor", "")), (d.get("date") or "")[:4])].append(i)
    filas = [(n, i, items[i]["key"], items[i]["title"], items[i].get("autor", ""), (items[i].get("date") or "")[:4], ",".join(colec[i]))
             for n, (k, ii) in enumerate(x for x in g.items() if len(x[1]) > 1) for i in ii]
    escribir("zotero_titulo.tsv", ["grupo", "itemID", "key", "título", "autor", "año", "colecciones"], filas)
    res["Z1 título+autor+año"] = sum(1 for x in g.values() if len(x) > 1)
    # Z2
    libro_de_ruta = {}
    for b, d in libros.items():
        libro_de_ruta[d["ruta"]] = b
    g = defaultdict(set)
    for aid, pid, path in z.execute("select itemID, parentItemID, path from itemAttachments where linkMode = 2 and path like 'attachments:%'"):
        if pid in items and aid not in borrados:
            carpeta = path[len("attachments:"):].rsplit("/", 1)[0]
            if carpeta in libro_de_ruta:
                g[pid].add(libro_de_ruta[carpeta])
    filas = [(i, items[i]["key"], items[i].get("title", ""), b, libros[b]["titulo"], libros[b].get("pags", ""), libros[b].get("clave", ""))
             for i, bs in g.items() if len(bs) > 1 for b in sorted(bs)]
    escribir("zotero_varios_libros.tsv", ["itemID", "key", "título zotero", "libro", "título calibre", "páginas", "zotero_key del libro"], filas)
    res["Z2 ítem con varios libros"] = sum(1 for x in g.values() if len(x) > 1)
    # Z3
    g = defaultdict(list)
    for b, d in libros.items():
        if d.get("clave"):
            g[d["clave"]].append(b)
    filas = [(k, b, libros[b]["titulo"]) for k, bs in g.items() if len(bs) > 1 for b in bs]
    escribir("zotero_clave_compartida.tsv", ["zotero_key", "libro", "título"], filas)
    res["Z3 clave compartida"] = sum(1 for x in g.values() if len(x) > 1)
    # Z4
    claves = {d.get("clave") for d in libros.values()}
    huer = [(i, d["key"], d.get("title", ""), ",".join(colec[i])) for i, d in items.items() if d["key"] not in claves]
    escribir("zotero_huerfanos.tsv", ["itemID", "key", "título", "colecciones"], huer)
    res["Z4 huérfanos (sin libro)"] = len(huer)
    por_col = defaultdict(int)
    for *_, cs in huer:
        por_col[cs or "(sin colección)"] += 1
    res["   papelera de Zotero (ítems)"] = len(borrados)
    for k, v in res.items():
        print(f"{k:32} {v}")
    print("huérfanos por colección:", dict(sorted(por_col.items(), key=lambda x: -x[1])[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
