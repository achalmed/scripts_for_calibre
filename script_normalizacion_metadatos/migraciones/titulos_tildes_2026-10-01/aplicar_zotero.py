"""aplicar_zotero.py — paso 2 de las erratas de título (2026-09-30): escribe en Zotero.

Con Zotero CERRADO (lo comprueba main.sh):
    python3 aplicar_zotero.py <zotero.sqlite> <metadata.db> <salida> <propuesta.tsv>

- hechos.tsv: cada `attachments:<ruta vieja>` pasa a `attachments:<ruta nueva>` (Calibre renombró carpeta
  y archivo al cambiar el título). Sin esto, el PDF enlazado en Zotero queda huérfano.
- propuesta.tsv: el título del ítem enlazado (`#zotero_key`) pasa al nuevo solo si era el viejo; es lo que
  haría el sincronizador diario (título: Calibre manda), adelantado para dejar ambos almacenes iguales hoy.
Escribe <salida>/zotero.tsv. Reutiliza `z_set_field` del sincronizador (marca synced=0 y la fecha).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "grafias_autores_2026-09-30"))
from aplicar_zotero import _sincronizador  # noqa: E402


def main(zot, cal, salida, propuesta):
    salida = Path(salida)
    sinc = _sincronizador(zot, cal)
    z = sqlite3.connect(zot)
    c = sqlite3.connect(f"file:{cal}?mode=ro", uri=True)
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    clave = dict(c.execute(f"select book, value from custom_column_{col}"))
    cur = z.cursor()
    rutas = titulos = 0
    with open(salida / "zotero.tsv", "w", encoding="utf-8") as out:
        for linea in open(salida / "hechos.tsv", encoding="utf-8"):
            libro, viejo, nuevo = linea.rstrip("\n").split("\t")
            n = cur.execute("update itemAttachments set path = ? where path = ?",
                            (f"attachments:{nuevo}", f"attachments:{viejo}")).rowcount
            if n:
                rutas += n
                out.write(f"ruta\t{libro}\t{viejo}\t{nuevo}\t{n}\n")
        for linea in open(propuesta, encoding="utf-8"):
            if not linea.strip() or linea.startswith("#"):
                continue
            libro, viejo, nuevo, _ = linea.rstrip("\n").split("\t")
            key = clave.get(int(libro))
            r = key and cur.execute("select itemID from items where key = ?", (key,)).fetchone()
            if not r:
                continue
            actual = sinc.z_get_field(cur, r[0], "title")
            if actual != viejo:
                out.write(f"omitido\t{libro}\t{key}\tZotero tenía «{actual}»\n")
                continue
            sinc.z_set_field(cur, r[0], "title", nuevo)
            titulos += 1
            out.write(f"titulo\t{libro}\t{key}\t{viejo}\t{nuevo}\n")
    z.commit()
    integridad = z.execute("pragma integrity_check").fetchone()[0]
    z.close()
    print(f"  {rutas} rutas de adjunto reescritas · {titulos} títulos en Zotero · integridad {integridad}")
    return 0 if integridad == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
