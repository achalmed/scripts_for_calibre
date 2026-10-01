"""aplicar_calibre.py — paso 1 de la campaña de grafías de autores (2026-09-30): escribe en Calibre.

Autorizado por el usuario el 2026-09-30. Se ejecuta con el Python de Calibre, con Calibre CERRADO y el
lock de escritura tomado (lo hace main.sh):
    calibre-debug aplicar_calibre.py -- <biblioteca> <propuesta.tsv> <salida>

Aplica `propuesta.tsv`: `autor` → `rename_items` (lo que hace «Gestionar autores»: renombra en todos los
libros, fusiona si la grafía nueva ya existe y mueve la carpeta de cada libro); `libro` → la lista de
autores del libro en ese orden. Calibre renombra la carpeta y los archivos («Título - Autor.pdf»), así que
antes y después se fotografía la ruta de cada formato y se escribe en <salida>:
    hechos.tsv        libro · ruta vieja · ruta nueva (relativas a la biblioteca), un formato por línea
    autores.tsv       libro · autores viejos · autores nuevos (para Zotero y para el UNDO)
    carpetas.tsv      libro · carpeta vieja · carpeta nueva (el UNDO devuelve la carpeta entera)
"""
import sqlite3
import sys
from pathlib import Path

from calibre.library import db as abrir_db


def foto(bib):
    c = sqlite3.connect(f"file:{bib / 'metadata.db'}?mode=ro", uri=True)
    formatos = {(b, f): f"{p}/{n}.{f.lower()}" for b, f, n, p in c.execute(
        "select d.book, d.format, d.name, b.path from data d join books b on b.id = d.book")}
    carpetas = dict(c.execute("select id, path from books"))
    autores = {}
    for b, n in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id = l.author order by l.id"):
        autores.setdefault(b, []).append(n)
    c.close()
    return formatos, carpetas, autores


def main(bib, propuesta, salida):
    bib, salida = Path(bib), Path(salida)
    filas = [l.rstrip("\n").split("\t") for l in open(propuesta, encoding="utf-8")
             if l.strip() and not l.startswith(("#", "clase\t"))]
    f0, c0, a0 = foto(bib)
    api = abrir_db(str(bib)).new_api
    n_autor = n_libro = 0
    for clase, ident, nuevo, *_ in filas:
        ident = int(ident)
        if clase == "autor":
            if ident not in api.all_field_ids("authors"):
                print(f"  · autor {ident} ya no existe (fusionado antes): se omite")
                continue
            api.rename_items("authors", {ident: nuevo})
            n_autor += 1
        elif clase == "libro":
            api.set_field("authors", {ident: [a.strip() for a in nuevo.split(" & ")]})
            n_libro += 1
    api.close()
    f1, c1, a1 = foto(bib)
    with open(salida / "hechos.tsv", "w", encoding="utf-8") as f:
        for k, viejo in sorted(f0.items()):
            if f1.get(k) and f1[k] != viejo:
                f.write(f"{k[0]}\t{viejo}\t{f1[k]}\n")
    with open(salida / "autores.tsv", "w", encoding="utf-8") as f:
        for b in sorted(a1):
            if a0.get(b) != a1[b]:
                f.write(f"{b}\t{' & '.join(a0.get(b, []))}\t{' & '.join(a1[b])}\n")
    with open(salida / "carpetas.tsv", "w", encoding="utf-8") as f:
        for b in sorted(c0):
            if c1.get(b) and c1[b] != c0[b]:
                f.write(f"{b}\t{c0[b]}\t{c1[b]}\n")
    movidas = sum(1 for b in c0 if c1.get(b) != c0[b])
    print(f"  {n_autor} autores renombrados · {n_libro} libros con autores fijados · {movidas} carpetas movidas")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[-3:]))
