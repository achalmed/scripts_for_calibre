"""tests/fuentes/test_muestra_parafrasis.py — la muestra aleatoria del 20 % de las paráfrasis para cotejarlas a mano
(FLUJO_DE_CONOCIMIENTO C14.3, `fichas/lib/muestra.py` y `fichas/main.py muestra`): el tamaño, la semilla que reproduce la
muestra, la simulación que no escribe, el registro en `registro/` del escrito y la anotación de cada cotejo.

Sobre un escrito de juguete en un temporal: ninguna prueba toca escritura ni las bases.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
MAIN = REPO / "fichas" / "main.py"
_spec = importlib.util.spec_from_file_location("prueba_fichas_muestra", REPO / "fichas" / "lib" / "muestra.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def _escrito(tmp_path: Path, n_parafrasis: int = 12) -> Path:
    escrito = tmp_path / "reports" / "2026-11-18-informe-de-juguete"
    fichas = escrito / "fuentes" / "fichas"
    fichas.mkdir(parents=True)
    (escrito / "proyecto.yaml").write_text("titulo: Informe de juguete\n", encoding="utf-8")
    for i in range(1, n_parafrasis + 1):
        (fichas / f"autor2020-parafrasis-{i:02d}.md").write_text(
            f"---\ntipo: ficha_parafrasis\nclave_bibtex: autor2020\npagina: {i}\n---\n\n## Paráfrasis\n\nIdea {i}.\n", encoding="utf-8")
    (fichas / "autor2020-textual-01.md").write_text("---\ntipo: ficha_textual\nclave_bibtex: autor2020\npagina: 1\n---\n\nCita.\n",
                                                    encoding="utf-8")
    return fichas


def _correr(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(MAIN), *map(str, args)], capture_output=True, text=True)


@pytest.mark.parametrize("n,esperado", [(0, 0), (1, 1), (4, 1), (5, 1), (6, 2), (10, 2), (12, 3), (100, 20)])
def test_el_tamano_es_el_20_por_ciento_hacia_arriba_y_al_menos_una(n, esperado):
    assert M.tamano(n, 0.2) == esperado


def test_la_misma_semilla_da_la_misma_muestra_y_solo_de_parafrasis(tmp_path):
    fichas = _escrito(tmp_path)
    rutas = M.parafrasis([(p, {"tipo": "ficha_parafrasis" if "parafrasis" in p.name else "ficha_textual"})
                          for p in fichas.glob("*.md")])
    assert len(rutas) == 12
    a, b = M.sacar(rutas, 0.2, 2026), M.sacar(list(reversed(rutas)), 0.2, 2026)
    assert a["fichas"] == b["fichas"] and len(a["fichas"]) == 3 and a["semilla"] == 2026
    assert all("parafrasis" in p.name for p in a["fichas"])
    with pytest.raises(ValueError):
        M.sacar(rutas, 0)


def test_la_orden_simula_y_con_aplicar_registra_en_el_escrito(tmp_path):
    fichas = _escrito(tmp_path)
    r = _correr("muestra", fichas, "--semilla", 7)
    assert r.returncode == 0, r.stderr
    assert "semilla 7 · 3 de 12 (20%)" in r.stdout and "simulación" in r.stdout
    assert not (fichas.parents[1] / "registro").exists(), "simular no escribe"
    r = _correr("muestra", fichas, "--semilla", 7, "--aplicar")
    assert r.returncode == 0, r.stderr
    registro = fichas.parents[1] / "registro" / next(iter(p.name for p in (fichas.parents[1] / "registro").glob("*.yml")))
    d = yaml.safe_load(registro.read_text(encoding="utf-8"))
    assert d["tipo"] == "muestra_parafrasis" and d["semilla"] == 7 and d["poblacion"] == 12 and d["muestra"] == 3
    assert [f["resultado"] for f in d["fichas"]] == ["", "", ""]
    simulada = [l.strip("  · ") for l in _correr("muestra", fichas, "--semilla", 7).stdout.splitlines() if l.startswith("  · ")]
    assert simulada == [f["ficha"] for f in d["fichas"]], "la semilla reproduce la muestra registrada"
    # otra muestra el mismo día no pisa la primera
    assert _correr("muestra", fichas, "--semilla", 8, "--aplicar").returncode == 0
    assert len(list((fichas.parents[1] / "registro").glob("muestra-parafrasis-*.yml"))) == 2


def test_anotar_el_cotejo_simula_exige_nota_al_que_difiere_y_resume(tmp_path):
    fichas = _escrito(tmp_path)
    _correr("muestra", fichas, "--semilla", 7, "--aplicar")
    registro = next((fichas.parents[1] / "registro").glob("*.yml"))
    primera, segunda = [f["ficha"] for f in yaml.safe_load(registro.read_text(encoding="utf-8"))["fichas"]][:2]
    antes = registro.read_text(encoding="utf-8")
    r = _correr("muestra-resultado", registro, primera, "coincide")
    assert r.returncode == 0 and "simulación" in r.stdout and registro.read_text(encoding="utf-8") == antes
    assert _correr("muestra-resultado", registro, primera, "coincide", "--aplicar").returncode == 0
    r = _correr("muestra-resultado", registro, segunda, "difiere", "--aplicar")
    assert r.returncode == 2 and "nota" in r.stdout, "lo que difiere lleva nota"
    r = _correr("muestra-resultado", registro, segunda, "difiere", "--nota", "invierte la causalidad", "--aplicar")
    assert r.returncode == 1 and "1 coinciden · 1 difieren · 1 por cotejar" in r.stdout
    r = _correr("muestra-resultado", registro)
    assert "invierte la causalidad" in r.stdout and r.returncode == 1
    assert _correr("muestra-resultado", registro, "otra.md", "coincide").returncode == 2


def test_fuera_de_un_escrito_pide_el_registro(tmp_path):
    suelta = tmp_path / "fichas"
    suelta.mkdir()
    (suelta / "a-parafrasis-01.md").write_text("---\ntipo: ficha_parafrasis\n---\n\nx\n", encoding="utf-8")
    r = _correr("muestra", suelta)
    assert r.returncode == 2 and "--registro" in r.stdout
    assert _correr("muestra", suelta, "--registro", tmp_path / "m.yml", "--aplicar").returncode == 0
    assert (tmp_path / "m.yml").is_file()
