"""foto.py — ruta de cada formato y carpeta de los libros de propuesta.tsv (solo lee metadata.db).

    python3 foto.py <metadata.db> <propuesta.tsv> <foto.tsv>
    python3 foto.py <metadata.db> <propuesta.tsv> --comparar <antes.tsv> <salida>

Sin --comparar escribe <foto.tsv> (`formato|carpeta`, libro, clave, ruta). Con --comparar fotografía de
nuevo y escribe en <salida> hechos.tsv (libro · ruta vieja · ruta nueva de cada formato, como la campaña de
grafías) y carpetas.tsv (libro · carpeta vieja · carpeta nueva); solo lo que cambió.
"""
import sqlite3
import sys
from pathlib import Path


def libros(propuesta):
    return [int(l.split("\t")[0]) for l in open(propuesta, encoding="utf-8")
            if l.strip() and not l.startswith("#")]


def foto(db, ids):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = ",".join("?" * len(ids))
    filas = [("formato", b, f, f"{p}/{n}.{f.lower()}") for b, f, n, p in c.execute(
        f"select d.book, d.format, d.name, b.path from data d join books b on b.id = d.book where d.book in ({q})", ids)]
    filas += [("carpeta", b, "", p) for b, p in c.execute(f"select id, path from books where id in ({q})", ids)]
    c.close()
    return {(k, b, f): r for k, b, f, r in filas}


def main(argv):
    db, propuesta = argv[0], argv[1]
    ahora = foto(db, libros(propuesta))
    if argv[2] != "--comparar":
        with open(argv[2], "w", encoding="utf-8") as f:
            for (k, b, fm), r in sorted(ahora.items()):
                f.write(f"{k}\t{b}\t{fm}\t{r}\n")
        return 0
    antes = {}
    for l in open(argv[3], encoding="utf-8"):
        k, b, fm, r = l.rstrip("\n").split("\t")
        antes[(k, int(b), fm)] = r
    salida = Path(argv[4])
    with open(salida / "hechos.tsv", "w", encoding="utf-8") as h, \
         open(salida / "carpetas.tsv", "w", encoding="utf-8") as c:
        for (k, b, fm), viejo in sorted(antes.items()):
            nuevo = ahora.get((k, b, fm))
            if nuevo and nuevo != viejo:
                (h if k == "formato" else c).write(f"{b}\t{viejo}\t{nuevo}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
