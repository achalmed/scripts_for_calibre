#!/usr/bin/env python3
"""papelera_duplicado.py — manda a la papelera de Zotero la segunda importación del RIS del 2026-09-30.

El RIS de `--enlazar --ris` (488 libros) se importó dos veces: una en la colección «Calibre» (la principal)
y otra en la colección que Zotero crea con el nombre del archivo, «enlazar_20260930_224021». Se conserva la
de «Calibre». La otra va a la PAPELERA, no se borra: deletedItems para cada padre (los adjuntos lo siguen,
como hace Zotero) y deletedCollections para la colección. synced=0 y fecha, como toda escritura del ecosistema.

    python3 papelera_duplicado.py            # simula
    python3 papelera_duplicado.py --aplicar  # Zotero cerrado; respaldo previo en ../../backups/
Deshacer: restaurar el respaldo, o en Zotero, Papelera → Restaurar.
"""
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "core"))
import env  # noqa: E402

COLECCION = "enlazar_20260930_224021"
aplicar = "--aplicar" in sys.argv
zot = Path(env.ZOTERO_DB)
if aplicar and subprocess.run(["pgrep", "-x", "zotero|zotero-bin"], capture_output=True).returncode == 0:
    sys.exit("Zotero está abierto: ciérralo.")
z = sqlite3.connect(zot if aplicar else f"file:{zot}?mode=ro", uri=not aplicar)
cid = z.execute("select collectionID from collections where collectionName = ?", (COLECCION,)).fetchone()
if not cid:
    sys.exit(f"no existe la colección {COLECCION}")
cid = cid[0]
padres = [i for (i,) in z.execute(
    "select ci.itemID from collectionItems ci where ci.collectionID = ? "
    "and ci.itemID not in (select itemID from deletedItems)", (cid,))]
# garantía: ninguno de estos ítems está en otra colección (sería un ítem que alguien quiso conservar)
otra = z.execute(
    f"select count(*) from collectionItems where collectionID != ? and itemID in ({','.join('?' * len(padres))})",
    (cid, *padres)).fetchone()[0] if padres else 0
print(f"{len(padres)} ítems de «{COLECCION}» a la papelera (en otra colección: {otra})")
if otra:
    sys.exit("hay ítems compartidos con otra colección: no se toca nada")
if not aplicar:
    print("simulación: --aplicar escribe")
    sys.exit(0)
z.close()
resp = Path(__file__).resolve().parents[2] / "backups" / "zotero_alta_2026-09-30"
resp.mkdir(parents=True, exist_ok=True)
destino = resp / f"zotero_{datetime.now():%Y%m%d_%H%M%S}.sqlite"
src = sqlite3.connect(zot)
src.backup(sqlite3.connect(destino))
src.close()
ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
z = sqlite3.connect(zot)
z.executemany("insert or ignore into deletedItems(itemID, dateDeleted) values (?, ?)", [(i, ahora) for i in padres])
z.executemany("update items set synced = 0, dateModified = ?, clientDateModified = ? where itemID = ?",
              [(ahora, ahora, i) for i in padres])
z.execute("insert or ignore into deletedCollections(collectionID, dateDeleted) values (?, ?)", (cid, ahora))
z.execute("update collections set synced = 0, clientDateModified = ? where collectionID = ?", (ahora, cid))
z.commit()
print(f"hecho · respaldo {destino} · integridad {z.execute('pragma integrity_check').fetchone()[0]}")
