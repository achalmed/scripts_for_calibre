"""tests/fuentes/test_zotero_normas.py — el plan de ZOTERO-NORMAS (2026-11-15): número, código y título corto de las normas.

Objetivo: que la campaña ponga el número de la ley (no el índice de la serie), quite el código solo si es la serie de
  Calibre y ponga el título corto sin pisar uno que ya exista; y que una norma sin número quede para revisar a mano.
Método: normas y libros armados a mano (no abre Zotero ni Calibre).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "migraciones"))
import zotero_normas as zn  # noqa: E402


def _norma(key="AAA", titulo="Ley N.° 32069. Contrataciones públicas", numero="1", codigo="Marco legal 05 - Contrataciones", corto=""):
    return {"itemID": 1, "key": key, "titulo": titulo, "publicLawNumber": numero, "code": codigo, "shortTitle": corto, "dateEnacted": ""}


LIBRO = {"calibre_id": 10050, "serie": "Marco legal 05 - Contrataciones", "identificadores": {"norma": "ley_32069"}}


def test_pone_el_numero_quita_la_serie_y_pone_el_titulo_corto():
    p = zn.plan([_norma()], {"AAA": LIBRO})
    assert p["cambios"][0]["campos"] == {"publicLawNumber": ["1", "32069"], "code": ["Marco legal 05 - Contrataciones", ""],
                                         "shortTitle": ["", "Ley N.° 32069"]}


def test_un_codigo_de_verdad_y_un_titulo_corto_existente_no_se_tocan():
    p = zn.plan([_norma(codigo="Código Civil", corto="LGCP")], {"AAA": LIBRO})
    assert p["cambios"][0]["campos"] == {"publicLawNumber": ["1", "32069"]}


def test_sin_libro_toma_el_numero_del_titulo_con_su_sufijo():
    p = zn.plan([_norma(titulo="Decreto Supremo N.° 005-2002-EF. Reglamento de la Ley de Canon", codigo="")], {})
    assert p["cambios"][0]["campos"]["publicLawNumber"] == ["1", "005-2002-EF"]


def test_una_norma_sin_numero_queda_para_revisar_a_mano():
    p = zn.plan([_norma(titulo="Constitución Política del Perú (texto actualizado)")], {})
    assert p["cambios"] == [] and p["revisar"][0]["motivo"] == "sin número de norma"


def test_lo_que_ya_esta_bien_no_cambia():
    p = zn.plan([_norma(numero="32069", codigo="", corto="Ley N.° 32069")], {"AAA": LIBRO})
    assert p["cambios"] == [] and p["sin_cambio"] == 1


def test_la_fecha_entra_solo_si_esta_verificada():
    norma = {**_norma(numero="32069", codigo="", corto="Ley N.° 32069"), "dateEnacted": "2025-00-00 2025"}
    p = zn.plan([norma], {"AAA": LIBRO}, {"ley_32069": "2024-06-24"})
    assert p["cambios"][0]["campos"] == {"dateEnacted": ["2025-00-00 2025", "2024-06-24 2024-06-24"]}
    assert zn.plan([norma], {"AAA": LIBRO}, {})["cambios"] == []
