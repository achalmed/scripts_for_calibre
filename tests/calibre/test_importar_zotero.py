"""tests/calibre/test_importar_zotero.py — `lib/importar_zotero.py --aplicar` sobre COPIAS de las bases (decisiones §2.15).

Objetivo: que lo que falta entre en Zotero por la puerta (respaldo, ítem sin sincronizar, adjunto enlazado `linkMode=2` al
  archivo de Calibre, colección del lote, `#zotero_key` en Calibre), que lo que ya estaba no se toque, que una segunda
  pasada no cree nada y que con el candado de Zotero ocupado salga 75 sin escribir.
Método: la corrida aislada de la caracterización (copias de metadata.db y zotero.sqlite, biblioteca espejo, `ps` falso y
  `unshare -rn`); el lote son dos libros reales de la copia sin ítem en Zotero (uno repetido en un BibTeX) y uno que ya
  está, más una obra de CSL-JSON que no está en Calibre.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import calibre_apoyo as ap

HERRAMIENTA = ap.REPO / "lib" / "importar_zotero.py"


def _ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def _correr(c, *args):
    return subprocess.run([*ap._aislar(), str(ap.core_env.CORE_PYTHON), str(HERRAMIENTA), *args], env=c.env,
                          capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)


def _sin_zotero(c, n=2) -> list[tuple[int, str]]:
    """Libros de la copia con PDF, sin #zotero_key y cuya carpeta no enlaza ningún adjunto de Zotero."""
    z = _ro(c.zotero)
    carpetas = {p[len("attachments:"):].rsplit("/", 1)[0] for (p,) in z.execute("select path from itemAttachments where path like 'attachments:%'")}
    z.close()
    k = _ro(c.calibre)
    col = k.execute("select id from custom_columns where label='zotero_key'").fetchone()[0]
    filas = k.execute(f"select b.id, b.title, b.path from books b join data d on d.book=b.id and d.format='PDF' "
                      f"where b.id not in (select book from custom_column_{col}) order by b.id desc").fetchall()
    k.close()
    return [(b, t) for b, t, p in filas if p not in carpetas][:n]


def _con_zotero(c) -> tuple[int, str, str]:
    k = _ro(c.calibre)
    col = k.execute("select id from custom_columns where label='zotero_key'").fetchone()[0]
    z = _ro(c.zotero)
    vivos = {key for (key,) in z.execute("select key from items where itemID not in (select itemID from deletedItems)")}
    z.close()
    for b, t, key in k.execute(f"select b.id, b.title, z.value from books b join custom_column_{col} z on z.book=b.id order by b.id"):
        if key in vivos:
            k.close()
            return b, t, key
    raise AssertionError("la copia no tiene ningún libro enlazado con Zotero")


def _ris(libros) -> str:
    return "\n".join(f"TY  - BOOK\nT1  - {t}\nAU  - Prueba, Autora\nDA  - 2001\nKW  - prueba_importar\n"
                     f"ID  - calibre:{b}\nER  - \n" for b, t in libros)


def test_importa_lo_que_falta_por_la_puerta_y_no_toca_lo_demas(corrida, tmp_path):
    c = corrida("importar")
    (b1, t1), (b2, t2) = _sin_zotero(c)
    b3, t3, k3 = _con_zotero(c)
    (tmp_path / "lote.ris").write_text(_ris([(b1, t1), (b2, t2), (b3, t3)]), encoding="utf-8")
    (tmp_path / "otro.bib").write_text(f"@book{{clavePrueba2001,\n  title = {{{t1}}},\n  author = {{Prueba, Autora}},\n"
                                       f"  year = {{2001}}, publisher = {{Editorial de Prueba}}\n}}\n", encoding="utf-8")
    (tmp_path / "fuera.json").write_text(json.dumps([{"type": "report", "title": "Un informe que no está en Calibre zqx",
                                                      "author": [{"literal": "Institución de Prueba"}],
                                                      "issued": {"date-parts": [[2020]]}}]), encoding="utf-8")
    archivos = [str(tmp_path / n) for n in ("lote.ris", "otro.bib", "fuera.json")]
    salida = tmp_path / "salida"
    antes = _ro(c.zotero).execute("select count(*) from items").fetchone()[0]

    r = _correr(c, *archivos, "--coleccion", "Prueba de importar", "--salida", str(salida))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "4 registros → 4 obras" not in r.stdout and "(1 repetidos entre archivos, fundidos)" in r.stdout, r.stdout
    assert "Nuevas 3 · Ya estaban 1 · Dudosas 0" in r.stdout, r.stdout
    assert _ro(c.zotero).execute("select count(*) from items").fetchone()[0] == antes, "la simulación no escribe"
    informe = json.loads((salida / "ultimo.json").read_text())
    assert informe["cuentas"]["con_adjunto"] == 2 and informe["cuentas"]["sin_calibre"] == 1
    assert Path(informe["ris"]).read_text().count("TY  - ") == 3

    r = _correr(c, *archivos, "--coleccion", "Prueba de importar", "--salida", str(salida), "--aplicar")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "── Backup:" in r.stdout and "integridad ok" in r.stdout and "2 #zotero_key escritas" in r.stdout, r.stdout

    z = _ro(c.zotero)
    k = _ro(c.calibre)
    col = k.execute("select id from custom_columns where label='zotero_key'").fetchone()[0]
    for b in (b1, b2):
        key = k.execute(f"select value from custom_column_{col} where book=?", (b,)).fetchone()[0]
        item, synced, version = z.execute("select itemID, synced, version from items where key=?", (key,)).fetchone()
        assert (synced, version) == (0, 0)
        modo, ruta, sync_adj = z.execute("select ia.linkMode, ia.path, i.synced from itemAttachments ia join items i using(itemID) "
                                         "where ia.parentItemID=?", (item,)).fetchone()
        assert modo == 2 and ruta.startswith("attachments:") and f"({b})/" in ruta and sync_adj == 0
        assert (c.biblioteca / ruta[len("attachments:"):]).exists()
        assert z.execute("select 1 from collectionItems ci join collections co using(collectionID) where ci.itemID=? "
                         "and co.collectionName='Prueba de importar'", (item,)).fetchone()
        assert z.execute("select 1 from itemTags it join tags t using(tagID) where it.itemID=? and t.name='prueba_importar'",
                         (item,)).fetchone()
    clave = z.execute("select v.value from itemData d join fields f using(fieldID) join itemDataValues v using(valueID) "
                      "join items i using(itemID) where f.fieldName='citationKey' and i.key=?",
                      (k.execute(f"select value from custom_column_{col} where book=?", (b1,)).fetchone()[0],)).fetchone()[0]
    assert clave == "clavePrueba2001", "la clave del BibTeX fundido se respeta"
    assert k.execute(f"select value from custom_column_{col} where book=?", (b3,)).fetchone()[0] == k3, "lo que ya estaba no se toca"
    assert z.execute("select count(*) from items").fetchone()[0] == antes + 5, "3 ítems y 2 adjuntos"
    assert z.execute("pragma integrity_check").fetchone()[0] == "ok" and not z.execute("pragma foreign_key_check").fetchall()
    z.close()
    k.close()
    respaldos = [r for d in (c.env["RESPALDOS_DIR"], c.env["XDG_STATE_HOME"])
                 for r in Path(d).glob("biblioteca/**/importar_zotero/zotero/zotero_*")]
    assert respaldos, "la puerta respaldó zotero.sqlite antes de escribir"

    r = _correr(c, *archivos, "--coleccion", "Prueba de importar", "--salida", str(salida))
    assert "Nuevas 0 · Ya estaban 4 · Dudosas 0" in r.stdout, r.stdout


def test_candado_de_zotero_ocupado_sale_75_y_no_escribe(corrida, tmp_path):
    c = corrida("importar-candado")
    (tmp_path / "lote.ris").write_text(_ris(_sin_zotero(c, 1)), encoding="utf-8")
    lock = Path(c.env["LOCK_ZOTERO"])
    lock.parent.mkdir(parents=True, exist_ok=True)
    antes = _ro(c.zotero).execute("select count(*) from items").fetchone()[0]
    ocupante = subprocess.Popen(["flock", str(lock), "sleep", "20"])
    try:
        import time
        time.sleep(0.5)
        r = _correr(c, str(tmp_path / "lote.ris"), "--salida", str(tmp_path / "s"), "--aplicar")
    finally:
        ocupante.kill()
        ocupante.wait()
    assert r.returncode == 75, r.stdout + r.stderr
    assert _ro(c.zotero).execute("select count(*) from items").fetchone()[0] == antes
