"""Caracterización de `ingesta/main.sh` (ola 2, F1): lo que hace hoy, en seco y contra la copia de la base.

Fija el recorrido entrada → identificar → catalogar (simulado y aplicado en la copia) y las salidas de los
comandos que no escriben. Ninguna prueba toca la biblioteca real: la caja de arena (conftest.py) lo garantiza.
"""
import csv
import sqlite3

from conftest import pdf_minimo, saltar_si_calibre


def _filas(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_ayuda_y_comando_desconocido(caja):
    r = caja.ingesta("estado", "-h")
    assert r.returncode == 0
    assert "catalogar" in r.stdout
    r = caja.ingesta("no-existe")
    assert r.returncode == 1
    assert "comando desconocido" in r.stdout + r.stderr


def test_estado_cuenta_el_ledger(caja):
    total = len(_filas(caja.repo / "ingesta" / "ingesta.tsv"))
    r = caja.ingesta("estado")
    assert r.returncode == 0, r.stderr
    assert f"ledger: {total} documento(s)" in r.stdout + r.stderr
    assert "en zona de entrada sin catalogar: 0" in r.stdout + r.stderr


def _documento_en_entrada(caja, nombre="informe_prueba_ingesta.pdf", texto="Informe de prueba de la ingesta"):
    destino = caja.repo / "entrada" / "programa-prueba" / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(pdf_minimo(texto))
    return destino


def test_identificar_escribe_pendientes_y_ficha_provisional(caja):
    doc = _documento_en_entrada(caja)
    r = caja.ingesta("recibir")
    assert r.returncode == 0
    assert "1 documento(s) en la zona de entrada sin catalogar" in r.stdout + r.stderr
    r = caja.ingesta("identificar")
    assert r.returncode == 0, r.stderr
    filas = [f for f in _filas(caja.repo / "ingesta" / "pendientes.tsv") if doc.name in f["origen"]]
    assert len(filas) == 1
    assert filas[0]["sha256"]
    assert (caja.repo / "ingesta" / "fichas" / filas[0]["ficha"]).is_file()


def test_catalogar_simula_sin_escribir(caja):
    _documento_en_entrada(caja)
    assert caja.ingesta("identificar").returncode == 0
    antes_db, antes_led = caja.huella_db(), (caja.repo / "ingesta" / "ingesta.tsv").read_bytes()
    r = caja.ingesta("catalogar", "--solo", "informe_prueba_ingesta")
    assert r.returncode == 0, r.stderr
    assert "SIM  add" in r.stdout
    assert "[catalogar] 1 procesado(s) · 0 omitido(s) por confianza · simulación" in r.stdout
    assert caja.huella_db() == antes_db
    assert (caja.repo / "ingesta" / "ingesta.tsv").read_bytes() == antes_led


def test_catalogar_aplicado_en_la_copia(caja, sin_calibre_abierto):
    _documento_en_entrada(caja)
    assert caja.ingesta("identificar").returncode == 0
    pend = [f for f in _filas(caja.repo / "ingesta" / "pendientes.tsv") if "informe_prueba_ingesta" in f["origen"]][0]
    n_led = len(_filas(caja.repo / "ingesta" / "ingesta.tsv"))
    ultimo = caja.max_id()
    r = caja.ingesta("catalogar", "--aplicar", "--solo", "informe_prueba_ingesta")
    saltar_si_calibre(r)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "APLICADO" in r.stdout
    # la copia tiene el libro nuevo; el ledger y el registro canónico lo anotan con su id
    assert caja.max_id() == ultimo + 1
    filas = _filas(caja.repo / "ingesta" / "ingesta.tsv")
    assert len(filas) == n_led + 1
    assert filas[-1]["sha256"] == pend["sha256"] and filas[-1]["calibre_id"] == str(ultimo + 1)
    cat = caja.docs / "scripts_for_calibre" / "catalogacion"
    assert _filas(cat / "resumen_catalogacion.tsv")[-1]["id"] == str(ultimo + 1)
    # la ficha provisional pasa a la canónica con su id
    assert not (caja.repo / "ingesta" / "fichas" / pend["ficha"]).exists()
    assert list((cat / "fichas").glob(f"{ultimo + 1}_*.md"))
    c = sqlite3.connect(f"file:{caja.db}?mode=ro", uri=True)
    assert c.execute("select count(*) from books where id=?", (ultimo + 1,)).fetchone()[0] == 1
    c.close()


def test_ocr_y_paquetes_simulan(caja):
    r = caja.ingesta("ocr")
    assert r.returncode == 0, r.stderr
    assert "[ocr] 0 formato(s) · 0 sin libro · simulación" in r.stdout
    r = caja.ingesta("paquetes")
    assert r.returncode == 0, r.stderr
