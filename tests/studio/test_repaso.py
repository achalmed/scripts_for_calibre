"""El repaso Leitner de las fichas (decisiones §9.9, `lib/repaso.py`): qué toca hoy, subir y bajar de caja, los intervalos,
la simulación que no escribe, el respaldo del día y la guarda de rutas. Siempre en una `REPASO_DB` temporal."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date, timedelta

import pytest

from conftest import REPO


@pytest.fixture
def repaso(tmp_path, monkeypatch):
    monkeypatch.setenv("REPASO_DB", str(tmp_path / "datos" / "repaso.sqlite"))
    monkeypatch.setenv("PUERTA_RESPALDOS", str(tmp_path / "respaldos"))
    spec = importlib.util.spec_from_file_location("prueba_repaso", REPO / "lib" / "repaso.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["prueba_repaso"] = m
    spec.loader.exec_module(m)
    yield m
    sys.modules.pop("prueba_repaso", None)


HOY = date(2026, 11, 18)


def test_las_cajas_y_sus_intervalos(repaso):
    assert repaso.INTERVALOS == {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}


def test_lo_nunca_repasado_toca_hoy_y_la_simulacion_no_escribe(repaso, tmp_path):
    assert repaso.para_hoy(["a", "b"], hoy=HOY) == ["a", "b"]
    p = repaso.responder("a", True, hoy=HOY)
    assert p["caja"] == 2 and p["nueva"] and not p["escrito"] and p["proxima"] == "2026-11-20"
    assert not (tmp_path / "datos").exists()


def test_la_sabia_sube_una_caja_hasta_la_quinta(repaso):
    esperado = [(2, 2), (3, 4), (4, 8), (5, 16), (5, 16)]
    dia = HOY
    for caja, dias in esperado:
        r = repaso.responder("ficha", True, aplicar=True, hoy=dia)
        assert r["escrito"] and r["caja"] == caja and r["proxima"] == (dia + timedelta(days=dias)).isoformat()
        dia = date.fromisoformat(r["proxima"])
    e = repaso.estado(["ficha"])["ficha"]
    assert e["caja"] == 5 and e["aciertos"] == 5 and e["fallos"] == 0


def test_repasar_luego_baja_a_la_caja_1(repaso):
    repaso.responder("ficha", True, aplicar=True, hoy=HOY)
    repaso.responder("ficha", True, aplicar=True, hoy=HOY + timedelta(days=2))
    r = repaso.responder("ficha", False, aplicar=True, hoy=HOY + timedelta(days=6))
    assert r["caja_antes"] == 3 and r["caja"] == 1 and r["proxima"] == (HOY + timedelta(days=7)).isoformat()
    assert repaso.estado(["ficha"])["ficha"]["fallos"] == 1


def test_que_toca_hoy_y_las_proximas(repaso):
    repaso.responder("sabida", True, aplicar=True, hoy=HOY)          # caja 2: vuelve el 20
    repaso.responder("olvidada", False, aplicar=True, hoy=HOY)       # caja 1: vuelve el 19
    claves = ["sabida", "olvidada", "nueva"]
    assert repaso.para_hoy(claves, hoy=HOY) == ["nueva"]
    assert repaso.proxima(claves, hoy=HOY) == 1
    assert repaso.para_hoy(claves, hoy=HOY + timedelta(days=1)) == ["olvidada", "nueva"]
    assert repaso.para_hoy(claves, hoy=HOY + timedelta(days=2)) == ["olvidada", "nueva", "sabida"]   # la caja más baja primero
    assert repaso.proxima(["nueva"], hoy=HOY) is None


def test_respalda_antes_de_la_primera_escritura_del_dia(repaso, tmp_path):
    repaso.responder("a", True, aplicar=True, hoy=HOY)                 # crea la base: nada que respaldar
    carpeta = tmp_path / "respaldos" / "repaso"
    assert not carpeta.exists()
    repaso.responder("b", True, aplicar=True, hoy=HOY)                 # la primera escritura sobre la base: un respaldo
    repaso.responder("c", True, aplicar=True, hoy=HOY)                 # el mismo día: no otro
    assert len(list(carpeta.glob("repaso_*.sqlite"))) == 1


def test_no_se_abre_dentro_de_calibre_ni_de_zotero(repaso, tmp_path, monkeypatch):
    biblioteca = tmp_path / "biblioteca"
    biblioteca.mkdir()
    monkeypatch.setenv("BIBLIOTECA_DIR", str(biblioteca))
    with pytest.raises(repaso.RutaProhibida):
        repaso.responder("a", True, aplicar=True, ruta=biblioteca / "repaso.sqlite")
    assert not (biblioteca / "repaso.sqlite").exists()
