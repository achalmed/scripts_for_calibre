"""aplicar_calibre.py — paso de Calibre de las tildes en lote (2026-10-01): título y sort en un solo proceso.

Con el Python de Calibre, Calibre CERRADO y el lock tomado (lo hace main.sh):
    calibre-debug aplicar_calibre.py -- <biblioteca> <propuesta.tsv>

Un `calibredb set_metadata` por libro abre la biblioteca entera cada vez (~1300 libros); aquí se abre una vez.
`set_field("title")` mueve carpeta y archivo como calibredb (de eso se ocupan foto.py y aplicar_zotero.py);
`sort` se fija aparte porque en esta biblioteca es el título literal. Solo toca un libro si su título sigue
siendo el viejo de la propuesta.
"""
import sys

from calibre.library import db as abrir_db


def main(bib, propuesta):
    filas = [l.rstrip("\n").split("\t") for l in open(propuesta, encoding="utf-8")
             if l.strip() and not l.startswith("#")]
    api = abrir_db(bib).new_api
    nuevos, omitidos = {}, 0
    for libro, viejo, nuevo, _ in filas:
        libro = int(libro)
        if api.field_for("title", libro) != viejo:
            omitidos += 1
            print(f"  · {libro}: el título ya no es el de la propuesta; se omite")
            continue
        nuevos[libro] = nuevo
    api.set_field("title", nuevos)
    api.set_field("sort", nuevos)
    api.close()
    print(f"  {len(nuevos)} títulos escritos · {omitidos} omitidos")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[-2:]))
