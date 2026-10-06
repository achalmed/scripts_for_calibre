"""tests/conftest.py — fixtures de las pruebas de scripts_for_calibre (ola 2, K1).

Objetivo: dar a cada prueba una corrida aislada (copias de las bases, biblioteca espejo, HOME y candado
  propios) y los dos árboles que se comparan: la referencia de git y el árbol de trabajo.
Método: las bases reales se copian una sola vez por sesión (solo lectura); cada corrida parte de esa foto,
  así la referencia y el árbol actual ven exactamente los mismos datos aunque un timer escriba entre medias.
Límite: ver `calibre_apoyo.py`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibre_apoyo as ap  # noqa: E402


@dataclass
class Corrida:
    raiz: Path
    biblioteca: Path
    zotero: Path
    koreader: Path
    env: dict

    @property
    def calibre(self) -> Path:
        return self.biblioteca / "metadata.db"


@pytest.fixture(scope="session")
def foto(tmp_path_factory):
    """Copia única, en solo lectura, de las bases reales y de los datos de KOReader."""
    raiz = tmp_path_factory.mktemp("foto")
    ap.copiar_base(ap.REAL_CALIBRE_DB, raiz / "metadata.db")
    ap.copiar_base(ap.REAL_ZOTERO_DB, raiz / "zotero.sqlite")
    ap.copiar_koreader(raiz / "koreader")
    return raiz


@pytest.fixture(scope="session")
def arboles(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("arboles")
    return {"ref": ap.arbol_referencia(raiz / "ref"), "act": ap.arbol_actual(raiz / "act")}


@pytest.fixture
def corrida(tmp_path, foto):
    """Fábrica de corridas aisladas sobre la foto: `corrida("ref")`."""
    def hacer(nombre: str) -> Corrida:
        raiz = tmp_path / nombre
        zot = raiz / "Zotero" / "zotero.sqlite"
        zot.parent.mkdir(parents=True)
        ap.shutil.copyfile(foto / "zotero.sqlite", zot)
        bib = ap.espejo_biblioteca(raiz / "biblioteca", foto / "metadata.db")
        ko = foto / "koreader"
        return Corrida(raiz, bib, zot, ko, ap.entorno(raiz, bib, zot, ko))
    return hacer
