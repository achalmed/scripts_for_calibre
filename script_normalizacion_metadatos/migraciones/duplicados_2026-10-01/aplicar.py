"""aplicar.py — acciones A–D de DUPLICADOS_BIBLIOTECA_2026-10 (aprobadas por el usuario el 2026-10-01).

    python3 aplicar.py              simula: dice qué haría en Zotero y en Calibre
    python3 aplicar.py --aplicar    escribe (Calibre y Zotero CERRADOS; lo comprueba main.sh)

Nada se borra para siempre: en Zotero los ítems van a la papelera (`deletedItems`, se recuperan desde la app) y en
Calibre `calibredb remove` usa su papelera. Respaldo de metadata.db y zotero.sqlite en backups/<esta carpeta>/.
  A  ítems huérfanos de la importación RIS repetida cuyo adjunto es el mismo PDF que el de un ítem enlazado
  B  tesis 10288: 9646 (duplicado) a la papelera; #zotero_key de 10288 = clave de 9645
  C  quitar el adjunto del 399 del ítem del 461 (a la papelera) y vaciar la clave rota del 399
  D  13 duplicados de Calibre: notas de Zotero al ítem del ejemplar que se queda, ítem a la papelera, libro a la
     papelera de Calibre
Escribe hechos.tsv (acción · id · detalle) para deshacer.sh.
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
SALE = {1546: 131, 208: 204, 353: 9881, 560: 455, 618: 525, 619: 525, 3462: 529, 742: 9880,
        1180: 3372, 1957: 9812, 3916: 3915, 8529: 4265, 10180: 10192}
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

    # A
    enlazados = {item[k] for k in clave.values() if k in item}
    ruta_enlazada = {p for pid, p in cur.execute("select parentItemID, path from itemAttachments where linkMode = 2")
                     if pid in enlazados}
    n_a = 0
    for i, k, d in cur.execute("select itemID, key, dateAdded from items where dateAdded like '2026-10-01%'").fetchall():
        if i in enlazados or i in papelera:
            continue
        adj = [p for (p,) in cur.execute("select path from itemAttachments where parentItemID = ?", (i,))]
        if adj and all(p in ruta_enlazada for p in adj):
            a_papelera(i, f"A duplicado RIS {k}")
            n_a += 1
    # B
    a_papelera(item[TESIS_DUP], f"B duplicado de la tesis {TESIS_DUP}")
    hechos.append(("clave_calibre", TESIS, f"{clave.get(TESIS, '')}→{TESIS_BUENO}"))
    # C
    for adj, p in cur.execute("select itemID, path from itemAttachments where parentItemID = ?", (item[LARGO_ITEM],)).fetchall():
        if f"({CORTO})/" in p:
            a_papelera(adj, f"C adjunto del {CORTO} colgado del ítem del 461")
    hechos.append(("clave_calibre", CORTO, f"{clave.get(CORTO, '')}→"))
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
        subprocess.run([*cdb, "set_custom", "zotero_key", str(TESIS), TESIS_BUENO], check=True)
        subprocess.run([*cdb, "set_custom", "zotero_key", str(CORTO), ""], check=True)
        subprocess.run([*cdb, "remove", ",".join(map(str, SALE))], check=True)
        subprocess.run([*cdb, "backup_metadata"], check=True, capture_output=True)
        with open(AQUI / "hechos.tsv", "w", encoding="utf-8") as f:
            for h in hechos:
                f.write("\t".join(map(str, h)) + "\n")
    cuenta = {}
    for a, *_ in hechos:
        cuenta[a] = cuenta.get(a, 0) + 1
    print(("hecho: " if aplicar else "simulación: ") + str(cuenta) + f" · A = {n_a} ítems RIS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
