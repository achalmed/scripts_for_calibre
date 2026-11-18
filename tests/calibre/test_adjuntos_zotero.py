"""tests/test_adjuntos_zotero.py — el único escritor de rutas de adjuntos en Zotero (ola 2a, K4; RQ-BIB-03).

Objetivo: sobre una copia de zotero.sqlite, `lib/adjuntos_zotero.py rutas` reescribe `attachments:` de las
  carpetas «movidas», deja 0 rutas nuevas rotas, respalda verificado antes, simula por defecto, sale 1 si
  una ruta nueva no resuelve y 75 con el candado de Zotero ocupado.
Método: la corrida aislada de la caracterización (biblioteca espejo); se «mueven» tres libros creando en el
  espejo su carpeta nueva con el mismo archivo, como hace Calibre al cambiar autor o título.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path

import calibre_apoyo as ap

HERRAMIENTA = ap.REPO / "lib" / "adjuntos_zotero.py"


def _mover_tres(c):
    """Crea en el espejo la carpeta nueva de tres adjuntos existentes; devuelve las filas de hechos.tsv."""
    z = sqlite3.connect(f"file:{c.zotero}?mode=ro", uri=True)
    filas = []
    for (ruta,) in z.execute("select path from itemAttachments where linkMode = 2 and path like 'attachments:%' "
                             "order by itemID"):
        viejo = ruta[len("attachments:"):]
        origen = c.biblioteca / viejo
        if not origen.is_symlink() or "/" not in viejo:
            continue
        nuevo = f"Prueba K4 ({len(filas)})/{Path(viejo).name}"
        (c.biblioteca / nuevo).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(os.readlink(origen), c.biblioteca / nuevo)
        filas.append(("1", viejo, nuevo))
        if len(filas) == 3:
            break
    z.close()
    assert len(filas) == 3
    return filas


def _correr(c, *args):
    return subprocess.run([str(ap.core_env.CORE_PYTHON), str(HERRAMIENTA), *args, "--zotero", str(c.zotero),
                           "--biblioteca", str(c.biblioteca)], env=c.env, capture_output=True, text=True)


def _rutas(db):
    z = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    r = {p for (p,) in z.execute("select path from itemAttachments")}
    z.close()
    return r


def test_rutas_simula_aplica_y_deja_cero_rotas(corrida, tmp_path):
    c = corrida("k4")
    filas = _mover_tres(c)
    hechos = tmp_path / "hechos.tsv"
    hechos.write_text("".join("\t".join(f) + "\n" for f in filas))
    antes = _rutas(c.zotero)
    rotos_antes = len(_correr(c, "verificar").stdout.splitlines())

    r = _correr(c, "rutas", str(hechos))                        # simulación
    assert r.returncode == 0 and "SIMULACIÓN" in r.stdout, r.stderr
    assert _rutas(c.zotero) == antes

    r = _correr(c, "rutas", str(hechos), "--aplicar")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 rutas nuevas rotas" in r.stdout and "integridad ok" in r.stdout
    despues = _rutas(c.zotero)
    for _, viejo, nuevo in filas:
        assert f"attachments:{nuevo}" in despues and f"attachments:{viejo}" not in despues
    assert _correr(c, "verificar", "--rutas", str(hechos)).returncode == 0
    assert len(_correr(c, "verificar").stdout.splitlines()) == rotos_antes   # ni uno roto más
    respaldos = list(Path(c.env["XDG_STATE_HOME"]).glob("biblioteca/respaldos/adjuntos_zotero/zotero/zotero_*"))
    assert len(respaldos) == 1
    assert (tmp_path / "zotero.tsv").read_text().count("ruta\t") == 3


def test_ruta_nueva_que_no_resuelve_sale_1(corrida, tmp_path):
    c = corrida("k4roto")
    filas = _mover_tres(c)
    hechos = tmp_path / "hechos.tsv"
    hechos.write_text("1\t" + filas[0][1] + "\tNo existe (0)/nada.pdf\n")
    r = _correr(c, "rutas", str(hechos), "--aplicar")
    assert r.returncode == 1 and "no resuelven" in r.stderr


def test_candado_de_zotero_ocupado_sale_75(corrida, tmp_path):
    c = corrida("k4candado")
    filas = _mover_tres(c)
    hechos = tmp_path / "hechos.tsv"
    hechos.write_text("".join("\t".join(f) + "\n" for f in filas))
    antes = _rutas(c.zotero)
    lock = Path(c.env["LOCK_ZOTERO"])
    lock.parent.mkdir(parents=True, exist_ok=True)
    ocupante = subprocess.Popen(["flock", str(lock), "sleep", "10"])
    try:
        time.sleep(0.3)
        r = _correr(c, "rutas", str(hechos), "--aplicar")
    finally:
        ocupante.kill()
    assert r.returncode == 75, r.stdout + r.stderr
    assert _rutas(c.zotero) == antes


def test_linkmode_rehace_con_clave_nueva_y_borra_en_el_servidor(corrida, tmp_path):
    """«Cannot change attachment linkMode» (decisiones §2.14): un adjunto que el servidor conoce guardado y aquí está
    enlazado renace con clave nueva, la misma ruta y su anotación; la clave vieja va a syncDeleteLog."""
    c = corrida("k4linkmode")
    z = sqlite3.connect(c.zotero)
    adj, clave, ruta = z.execute("select i.itemID, i.key, ia.path from itemAttachments ia join items i using(itemID) "
                                 "where ia.linkMode = 2 and ia.path like 'attachments:%' order by itemID limit 1").fetchone()
    z.execute("update items set synced = 1 where synced = 0")    # la copia trae los conflictos reales: fuera
    z.execute("update items set synced = 0, version = 7 where itemID = ?", (adj,))
    tipo = z.execute("select syncObjectTypeID from syncObjectTypes where name = 'item'").fetchone()[0]
    z.execute("delete from syncCache where key = ?", (clave,))
    z.execute("insert into syncCache(libraryID, key, syncObjectTypeID, version, data) values (1, ?, ?, 7, ?)",
              (clave, tipo, '{"data": {"linkMode": "imported_file"}}'))
    z.commit()
    z.close()

    r = _correr(c, "linkmode", "--salida", str(tmp_path))       # simulación
    assert r.returncode == 0 and "1 conflictos · 0 rehechos" in r.stdout, r.stdout + r.stderr
    r = _correr(c, "linkmode", "--salida", str(tmp_path), "--aplicar")
    assert r.returncode == 0 and "1 rehechos" in r.stdout and "integridad ok" in r.stdout, r.stdout + r.stderr

    z = sqlite3.connect(f"file:{c.zotero}?mode=ro", uri=True)
    assert not z.execute("select 1 from items where key = ?", (clave,)).fetchone()
    assert z.execute("select 1 from syncDeleteLog where key = ?", (clave,)).fetchone()
    nueva = z.execute("select i.key, i.synced, i.version from itemAttachments ia join items i using(itemID) "
                      "where ia.path = ? and ia.linkMode = 2", (ruta,)).fetchone()
    assert nueva and nueva[0] != clave and nueva[1:] == (0, 0)
    assert not z.execute("pragma foreign_key_check").fetchall()
    z.close()
    assert _correr(c, "linkmode", "--salida", str(tmp_path)).stdout.count("0 conflictos") == 1
