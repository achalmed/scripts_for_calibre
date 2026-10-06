"""El árbol del repo, sin restos (ola 2, F6 y F7).

F6: las fichas provisionales de `ingesta/fichas/` son borradores temporales (D12): la canónica la escribe
`catalogar` en `scripts_for_calibre`. Ninguna queda sin rastrear (las 812 de partida se clasificaron por su
cabecera y su fila en `ingesta.tsv`) y el `.gitignore` las declara temporales, así que `git status` no las
vuelve a acumular.
"""
import subprocess

from conftest import REPO


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout


def test_cero_sin_rastrear_en_fichas_provisionales():
    sueltos = [l for l in _git("status", "--porcelain", "--untracked-files=all", "--", "ingesta/fichas").splitlines()
               if l.startswith("??")]
    assert not sueltos, f"{len(sueltos)} fichas provisionales sin rastrear"


def test_las_fichas_provisionales_son_temporales():
    assert _git("check-ignore", "ingesta/fichas/00000000_prueba.md").strip() == "ingesta/fichas/00000000_prueba.md"
    assert not _git("check-ignore", "ingesta/fichas/.gitkeep").strip()
