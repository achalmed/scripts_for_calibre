"""tests/fuentes/test_zotero_creadores.py — el plan de ZOTERO-CREADORES (2026-11-23): instituciones partidas en Zotero.

Objetivo: que la campaña una solo el creador de dos campos que es, palabra por palabra, un autor corporativo de Calibre
  del mismo libro, conserve el orden y el rol de los demás y no toque personas ni ítems no pedidos.
Método: ítems y libros armados a mano (no abre Zotero ni Calibre).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "migraciones"))
import zotero_creadores as zc  # noqa: E402

JNE = "Jurado Nacional de Elecciones"
LIBRO = {"calibre_id": 10824, "autores": [JNE]}


def _item(*creadores, key="AAA"):
    return {"itemID": 1, "key": key, "titulo": "Resolución", "citationKey": "deelecciones2022", "creadores": [list(c) for c in creadores]}


def test_une_la_institucion_partida_y_conserva_la_clave():
    p = zc.plan([_item(("Jurado Nacional", "De Elecciones", 0, 8))], {"AAA": LIBRO})
    c = p["cambios"][0]
    assert c["creadores"][1] == [["", JNE, 1, 8]] and c["citationKey"] == "deelecciones2022"


def test_conserva_el_orden_y_el_rol_de_los_demas():
    p = zc.plan([_item(("Ana", "Ruiz", 0, 8), ("Jurado Nacional", "De Elecciones", 0, 8), ("Luis", "Vega", 0, 10))],
                {"AAA": {"calibre_id": 1, "autores": ["Ana, Ruiz", JNE]}})
    assert p["cambios"][0]["creadores"][1] == [["Ana", "Ruiz", 0, 8], ["", JNE, 1, 8], ["Luis", "Vega", 0, 10]]


def test_no_toca_personas_ni_lo_que_ya_esta_bien():
    items = [_item(("Luis", "Company", 0, 8)), _item(("", JNE, 1, 8), key="BBB")]
    assert zc.plan(items, {"AAA": {"calibre_id": 1, "autores": ["Luis Company"]}, "BBB": LIBRO})["cambios"] == []


def test_solo_las_claves_pedidas_y_dice_las_que_no_cambian():
    items = [_item(("Jurado Nacional", "De Elecciones", 0, 8), key=k) for k in ("AAA", "BBB")]
    p = zc.plan(items, {"AAA": LIBRO, "BBB": LIBRO}, {"BBB", "ZZZ"})
    assert [c["key"] for c in p["cambios"]] == ["BBB"] and p["faltan"] == ["ZZZ"]
