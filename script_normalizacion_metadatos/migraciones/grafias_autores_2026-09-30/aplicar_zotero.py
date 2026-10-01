"""aplicar_zotero.py — paso 2 de la campaña de grafías de autores (2026-09-30): escribe en Zotero.

Con Zotero CERRADO (lo comprueba main.sh):
    python3 aplicar_zotero.py <zotero.sqlite> <metadata.db> <salida>

Lee lo que dejó el paso 1 en <salida>:
  - hechos.tsv: cada `attachments:<ruta vieja>` pasa a `attachments:<ruta nueva>` (Calibre movió carpeta y
    archivo). Sin esto, el PDF enlazado en Zotero queda huérfano.
  - autores.tsv: los creadores del ítem enlazado (`#zotero_key`) se rehacen con la grafía nueva, pero solo
    si eran el espejo de la vieja (mismas palabras); si Zotero tenía otra cosa, se reporta y no se toca.
    Persona «Nombre, Apellidos» → firstName/lastName; sin coma → campo único (fieldMode 1).
Escribe <salida>/zotero.tsv con lo hecho (y lo que el UNDO necesita).
Reutiliza `z_set_creators` del sincronizador (marca synced=0 y la fecha, como toda escritura del ecosistema).
"""
import importlib.util
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path

DOCS = Path(__file__).resolve().parents[4]


def _sincronizador(zot, cal):
    for k, v in {"CALIBRE_DB": cal, "ZOTERO_DB": zot, "REPORT_TSV": os.devnull,
                 "REPORT_MD": os.devnull, "STATE_JSON": os.devnull}.items():
        os.environ.setdefault(k, v)
    ruta = DOCS / "scripts_for_calibre/script_sincronizar_zotero/lib/sincronizador.py"
    spec = importlib.util.spec_from_file_location("sincronizador", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _palabras(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {t for t in "".join(ch if ch.isalnum() else " " for ch in s).split() if len(t) > 1}


def _persona(nombre):
    a = nombre.replace("|", ",").strip()
    if "," in a:
        fn, ln = [x.strip() for x in a.split(",", 1)]
        return (fn, ln, 0)
    return ("", a, 1)


def main(zot, cal, salida):
    salida = Path(salida)
    sinc = _sincronizador(zot, cal)
    z = sqlite3.connect(zot)
    c = sqlite3.connect(f"file:{cal}?mode=ro", uri=True)
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    clave = dict(c.execute(f"select book, value from custom_column_{col}"))
    out = open(salida / "zotero.tsv", "w", encoding="utf-8")
    rutas = creadores = omitidos = 0
    cur = z.cursor()
    for linea in open(salida / "hechos.tsv", encoding="utf-8"):
        libro, viejo, nuevo = linea.rstrip("\n").split("\t")
        n = cur.execute("update itemAttachments set path = ? where path = ?",
                        (f"attachments:{nuevo}", f"attachments:{viejo}")).rowcount
        if n:
            rutas += n
            out.write(f"ruta\t{libro}\t{viejo}\t{nuevo}\t{n}\n")
    for linea in open(salida / "autores.tsv", encoding="utf-8"):
        libro, viejos, nuevos = linea.rstrip("\n").split("\t")
        key = clave.get(int(libro))
        if not key:
            continue
        r = cur.execute("select itemID from items where key = ?", (key,)).fetchone()
        if not r:
            continue
        item = r[0]
        actuales = cur.execute(
            "select c.firstName, c.lastName, ic.creatorTypeID from itemCreators ic join creators c"
            " on c.creatorID = ic.creatorID where ic.itemID = ? order by ic.orderIndex", (item,)).fetchall()
        if not actuales:
            continue
        tipo = actuales[0][2]
        primarios = [a for a in actuales if a[2] == tipo]
        espejo = set().union(*(_palabras(f"{fn} {ln}") for fn, ln, _ in primarios))
        if espejo != _palabras(viejos.replace("&", " ")):
            omitidos += 1
            out.write(f"omitido\t{libro}\t{key}\tZotero no era espejo de Calibre\n")
            continue
        antes = " ; ".join(f"{ln}, {fn}" for fn, ln, _ in primarios)
        sinc.z_set_creators(cur, item, [_persona(a) for a in nuevos.split(" & ")], tipo)
        creadores += 1
        out.write(f"creadores\t{libro}\t{key}\t{antes}\t{nuevos}\n")
    z.commit()
    integridad = z.execute("pragma integrity_check").fetchone()[0]
    z.close()
    out.close()
    print(f"  {rutas} rutas de adjunto reescritas · {creadores} ítems con creadores rehechos · "
          f"{omitidos} omitidos · integridad {integridad}")
    return 0 if integridad == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
