"""pendientes.py — cierre de DUPLICADOS_BIBLIOTECA_2026-10 (2026-10-01): lo que se dejó para hacer en Zotero.

    python3 pendientes.py              simula
    python3 pendientes.py --aplicar    escribe (Calibre y Zotero CERRADOS; lo comprueba pendientes.sh)

Escribe en zotero.sqlite las mismas filas que crea Zotero al «Adjuntar enlace a archivo» o al importar un RIS
con «enlazar a los archivos»: `items` (versión 0, synced 0: Zotero las sube en su próxima sincronización),
`itemAttachments` (linkMode 2, ruta relativa `attachments:`) y el título del adjunto.
  T  tesis 10288: adjunto enlazado al PDF del libro, colgado del ítem 9645 (`4RCE726X`)
  P  libro 399: ítem nuevo clonado del ítem del 461 (mismo trabajo: tipo, creadores, fecha, idioma, colección;
     sin citationKey, que la pone Better BibTeX), con su número de páginas, su ruta y su adjunto;
     #zotero_key del 399 = la clave nueva
  V  ítems 138 y 161 (duplicados de marzo de 174 y 175): sus notas, si no están ya en el gemelo, pasan al gemelo;
     después, a la papelera
Respaldo de ambas bases en backups/<esta carpeta>/ y crea pendientes_hechos.tsv.
"""
import importlib.util
import os
import random
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
ALFABETO = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"   # el de las claves de Zotero
VIEJOS = {138: 175, 161: 174}                     # duplicado → gemelo enlazado


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
    def pdf(b):
        p, n = c.execute("select b.path, d.name from books b join data d on d.book = b.id"
                         " where b.id = ? and d.format = 'PDF'", (b,)).fetchone()
        return p, n
    pcol = c.execute("select id from custom_columns where label = 'pages'").fetchone()[0]
    pags399 = c.execute(f"select value from custom_column_{pcol} where book = 399").fetchone()
    rutas = {b: pdf(b) for b in (10288, 399)}
    c.close()
    pdf = rutas.__getitem__
    if aplicar:
        resp = AQUI.parents[1] / "backups" / AQUI.name
        marca = time.strftime("%Y%m%d_%H%M%S")
        for src, nombre in ((CAL, "metadata_pendientes"), (ZOT, "zotero_pendientes")):
            b = sqlite3.connect(str(resp / f"{nombre}_{marca}.db"))
            sqlite3.connect(str(src)).backup(b)
            b.close()
    sinc = sincronizador()
    z = sqlite3.connect(str(ZOT)) if aplicar else sqlite3.connect(f"file:{ZOT}?mode=ro", uri=True)
    cur = z.cursor()
    item = {k: i for i, k in cur.execute("select itemID, key from items")}
    tipo_adj = cur.execute("select itemTypeID from itemTypes where typeName = 'attachment'").fetchone()[0]
    ahora = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    hechos = []

    def clave_nueva():
        while True:
            k = "".join(random.choice(ALFABETO) for _ in range(8))
            if k not in item:
                item[k] = None
                return k

    def nuevo_item(tipo):
        k = clave_nueva()
        if not aplicar:
            return None, k
        cur.execute("insert into items (itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key,"
                    " version, synced) values (?, ?, ?, ?, 1, ?, 0, 0)", (tipo, ahora, ahora, ahora, k))
        return cur.lastrowid, k

    def adjuntar(padre, carpeta, nombre):
        i, k = nuevo_item(tipo_adj)
        if aplicar:
            cur.execute("insert into itemAttachments (itemID, parentItemID, linkMode, contentType, path)"
                        " values (?, ?, 2, 'application/pdf', ?)", (i, padre, f"attachments:{carpeta}/{nombre}.pdf"))
            sinc.z_set_field(cur, i, "title", nombre)
        return k

    # T
    p, n = pdf(10288)
    hechos.append(("adjunto_tesis", adjuntar(item["4RCE726X"], p, n), f"{p}/{n}.pdf"))
    # P
    viejo = item["GNGTL477"]
    tipo = cur.execute("select itemTypeID from items where itemID = ?", (viejo,)).fetchone()[0]
    nid, nkey = nuevo_item(tipo)
    p, n = pdf(399)
    if aplicar:
        for f, v in cur.execute("select f.fieldName, v.value from itemData d join fields f on f.fieldID = d.fieldID"
                                " join itemDataValues v on v.valueID = d.valueID where d.itemID = ?", (viejo,)).fetchall():
            if f == "citationKey":
                continue
            if f == "numPages" and pags399:
                v = str(pags399[0])
            if f == "extra":
                v = str(CAL.parent / p / f"{n}.pdf")
            sinc.z_set_field(cur, nid, f, v)
        cur.execute("insert into itemCreators (itemID, creatorID, creatorTypeID, orderIndex)"
                    " select ?, creatorID, creatorTypeID, orderIndex from itemCreators where itemID = ?", (nid, viejo))
        cur.execute("insert into collectionItems (collectionID, itemID, orderIndex)"
                    " select collectionID, ?, 0 from collectionItems where itemID = ?", (nid, viejo))
        adjuntar(nid, p, n)
    hechos.append(("item_399", nkey, f"clonado de GNGTL477 · {p}/{n}.pdf"))
    # V
    papelera = {i for (i,) in cur.execute("select itemID from deletedItems")}
    for dup, gem in VIEJOS.items():
        notas_gem = {t for (t,) in cur.execute("select note from itemNotes where parentItemID = ?", (gem,))}
        for nid_, txt in cur.execute("select itemID, note from itemNotes where parentItemID = ?", (dup,)).fetchall():
            if txt in notas_gem:
                hechos.append(("nota_repetida", nid_, f"ya está en {gem}"))
            else:
                if aplicar:
                    cur.execute("update itemNotes set parentItemID = ? where itemID = ?", (gem, nid_))
                    sinc.z_touch(cur, nid_)
                hechos.append(("nota_movida", nid_, f"{dup}→{gem}"))
        hijos = [h for (h,) in cur.execute("select itemID from itemAttachments where parentItemID = ? union"
                                           " select itemID from itemNotes where parentItemID = ?", (dup, dup))]
        for x in [dup, *hijos]:
            if x not in papelera and aplicar:
                cur.execute("insert into deletedItems (itemID) values (?)", (x,))
                sinc.z_touch(cur, x)
        hechos.append(("papelera_zotero", dup, f"duplicado de {gem}"))
    if aplicar:
        z.commit()
        print("integridad Zotero:", z.execute("pragma integrity_check").fetchone()[0])
        subprocess.run(["calibredb", "--with-library", str(CAL.parent), "set_custom", "zotero_key", "399", nkey], check=True)
        with open(AQUI / "pendientes_hechos.tsv", "w", encoding="utf-8") as f:
            for h in hechos:
                f.write("\t".join(map(str, h)) + "\n")
    z.close()
    for h in hechos:
        print(("hecho: " if aplicar else "simulación: "), *h, sep=" ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
