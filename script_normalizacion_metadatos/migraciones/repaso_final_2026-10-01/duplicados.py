"""duplicados.py — repaso final de duplicados (2026-10-01, aprobado por el usuario): 6 libros más, hallados por huellas
de página (conjuntos de palabras por página, Jaccard > 0,85), que la comparación por fragmentos no vio.

    python3 aplicar.py              simula: dice qué haría en Zotero y en Calibre
    python3 duplicados.py --aplicar escribe (Calibre y Zotero CERRADOS; lo comprueba main.sh)

Nada se borra para siempre: en Zotero los ítems van a la papelera (`deletedItems`, se recuperan desde la app) y en
Calibre `calibredb remove` usa su papelera. Respaldo de metadata.db y zotero.sqlite en backups/<esta carpeta>/.
  A  ítems huérfanos de la importación RIS repetida cuyo adjunto es el mismo PDF que el de un ítem enlazado
  B  tesis 10288: 9646 (duplicado) a la papelera; #zotero_key de 10288 = clave de 9645
  C  quitar el adjunto del 399 del ítem del 461 (a la papelera) y vaciar la clave rota del 399
  D  13 duplicados de Calibre: notas de Zotero al ítem del ejemplar que se queda, ítem a la papelera, libro a la
     papelera de Calibre
Escribe duplicados_hechos.tsv (acción · id · detalle) para deshacer.sh.
"""
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[3] / "core"))
import env  # noqa: E402

CAL = Path(env.BIBLIOTECA_DIR) / "metadata.db"
ZOT = Path(env.ZOTERO_DB)
# libro que sale → libro que se queda (DUPLICADOS_BIBLIOTECA_2026-10, «Calibre: duplicados reales»)
SALE = {352: 9888, 3154: 3159, 3156: 3160, 3157: 3161, 3158: 3162, 3580: 3578}
# el que se queda pasa a número de tema entero en su serie
INDICE = {3159: 1, 3162: 2, 3161: 3, 3160: 4}
TESIS, TESIS_BUENO, TESIS_DUP = 10288, "4RCE726X", "VIF485HW"
CORTO, LARGO_ITEM = 399, "GNGTL477"


def sincronizador():
    for k, v in {"CALIBRE_DB": str(CAL), "ZOTERO_DB": str(ZOT), "REPORT_TSV": os.devnull,
                 "REPORT_MD": os.devnull, "STATE_JSON": os.devnull}.items():
        os.environ.setdefault(k, v)
    ruta = AQUI.parents[2] / "script_sincronizar_zotero/lib/sincronizador.py"
    spec = importlib.util.spec_from_file_location("sincronizador", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    aplicar = "--aplicar" in argv
    c = sqlite3.connect(f"file:{CAL}?mode=ro", uri=True)
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    clave = dict(c.execute(f"select book, value from custom_column_{col}"))
    ruta = dict(c.execute("select id, path from books"))
    c.close()
    if aplicar:
        resp = AQUI.parents[1] / "backups" / AQUI.name
        resp.mkdir(parents=True, exist_ok=True)
        marca = time.strftime("%Y%m%d_%H%M%S")
        for src, nombre in ((CAL, "metadata"), (ZOT, "zotero")):
            b = sqlite3.connect(str(resp / f"{nombre}_{marca}.db"))
            sqlite3.connect(str(src)).backup(b)
            b.close()
    sinc = sincronizador()
    z = sqlite3.connect(str(ZOT)) if aplicar else sqlite3.connect(f"file:{ZOT}?mode=ro", uri=True)
    cur = z.cursor()
    item = {k: i for i, k in cur.execute("select itemID, key from items")}
    papelera = {i for (i,) in cur.execute("select itemID from deletedItems")}
    hechos = []

    def a_papelera(i, motivo):
        hijos = [h for (h,) in cur.execute("select itemID from itemAttachments where parentItemID = ? union "
                                           "select itemID from itemNotes where parentItemID = ?", (i, i))]
        for x in [i, *hijos]:
            if x not in papelera:
                if aplicar:
                    cur.execute("insert into deletedItems (itemID) values (?)", (x,))
                    sinc.z_touch(cur, x)
                papelera.add(x)
        hechos.append(("papelera_zotero", i, motivo))

    # D
    for sale, queda in SALE.items():
        ks, kq = clave.get(sale), clave.get(queda)
        if ks in item and kq in item and ks != kq:
            for (n,) in cur.execute("select itemID from itemNotes where parentItemID = ?", (item[ks],)).fetchall():
                if aplicar:
                    cur.execute("update itemNotes set parentItemID = ? where itemID = ?", (item[kq], n))
                    sinc.z_touch(cur, n)
                hechos.append(("nota_movida", n, f"{ks}→{kq}"))
            a_papelera(item[ks], f"D ítem del libro {sale} (se queda {queda})")
        hechos.append(("calibre_remove", sale, f"{ruta[sale]} · se queda {queda}"))
    if aplicar:
        z.commit()
        print("integridad Zotero:", z.execute("pragma integrity_check").fetchone()[0])
    z.close()

    if aplicar:
        cdb = ["calibredb", "--with-library", str(CAL.parent)]
        for libro, n in INDICE.items():
            subprocess.run([*cdb, "set_metadata", str(libro), "--field", f"series_index:{n}"], check=True, capture_output=True)
        subprocess.run([*cdb, "remove", ",".join(map(str, SALE))], check=True)
        subprocess.run([*cdb, "backup_metadata"], check=True, capture_output=True)
        with open(AQUI / "duplicados_hechos.tsv", "w", encoding="utf-8") as f:
            for h in hechos:
                f.write("\t".join(map(str, h)) + "\n")
    cuenta = {}
    for a, *_ in hechos:
        cuenta[a] = cuenta.get(a, 0) + 1
    print(("hecho: " if aplicar else "simulación: ") + str(cuenta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
