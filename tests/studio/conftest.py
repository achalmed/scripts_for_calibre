"""tests/studio/conftest.py — utilidades de las pruebas de Biblioteca Studio (fase 5 QML, 2026-11-02).

El temporal va al disco (XDG_CACHE_HOME), no a /tmp (tmpfs: es RAM). Nada toca la biblioteca real ni el índice del
autor: cada prueba parte de la muestra de `studio/muestra.py` (una biblioteca Calibre mínima con libros ficticios creada
con `calibredb` si está, si no una `metadata.db` mínima; una `zotero.sqlite` mínima; un repo de datos con ledgers,
fichas, entrada y un `fuentes.yml`; el índice) en una carpeta temporal, y el entorno (`core/env` respeta las variables)
apunta ahí.

Dos clases de prueba:
- en proceso (servicios, modelos, controladores): con el binding del Python que corre pytest (basta QtCore y QtGui) y
  `QT_QPA_PLATFORM=offscreen`; QSettings apunta a una carpeta temporal;
- en un proceso hijo (cada QML, la ventana entera, `--smoke`): con el Python del sistema (/usr/bin/python3), el único
  cuyo Qt trae Kirigami, y `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` y `XDG_STATE_HOME` temporales.

    tests/run.sh            # = python3 -m pytest tests/studio --basetemp ~/.cache/pytest/biblioteca-studio-studio -p no:cacheprovider
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "studio"
BASETEMP = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pytest" / "biblioteca-studio-studio" / "basetemp"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import muestra as muestra_mod  # noqa: E402

HAY_BINDING = importlib.util.find_spec("PySide6") is not None or importlib.util.find_spec("PyQt6") is not None
requiere_binding = pytest.mark.skipif(not HAY_BINDING, reason="sin PySide6 ni PyQt6")

_VARIABLES_CORE = ("DOCS_ROOT", "INDEX_DIR", "CORE_DIR", "META_DIR", "RESPALDOS_DIR", "GIT_DIR", "GIT_WORK_TREE")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.basetemp:
        return
    args = [Path(a.split("::")[0]).resolve() for a in (config.args or [])]
    if args and all(REPO in a.parents or a == REPO for a in args):
        BASETEMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(BASETEMP)


def _python_del_sistema() -> str | None:
    candidato = "/usr/bin/python3"
    if not Path(candidato).is_file():
        return None
    r = subprocess.run([candidato, "-c", "import importlib.util as u; print(bool(u.find_spec('PySide6') or u.find_spec('PyQt6')))"],
                       capture_output=True, text=True)
    return candidato if r.stdout.strip() == "True" else None


PYTHON_SISTEMA = _python_del_sistema()
requiere_sistema = pytest.mark.skipif(PYTHON_SISTEMA is None, reason="sin binding de Qt en /usr/bin/python3 (Kirigami)")


def _calibredb_responde() -> bool:
    """¿`calibredb` está y puede crear una biblioteca? (con Calibre abierto y sin `unshare`, no.)"""
    if not muestra_mod.hay_calibredb():
        return False
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import muestra, pathlib, tempfile, json\n"
                        "m = muestra.crear(pathlib.Path(sys.argv[2]) / 'sonda'); print(m.con_calibre)", str(STUDIO), str(BASETEMP.parent / "sonda-calibre")],
                       capture_output=True, text=True, timeout=180)
    return r.stdout.strip().endswith("True")


HAY_CALIBREDB = _calibredb_responde()
requiere_calibredb = pytest.mark.skipif(not HAY_CALIBREDB, reason="calibredb no está o no responde (Calibre abierto)")


@pytest.fixture
def muestra(tmp_path):
    """La biblioteca de muestra en un temporal (con calibredb si responde; si no, la metadata.db mínima)."""
    return muestra_mod.crear(tmp_path / "muestra", con_calibre=HAY_CALIBREDB)


@pytest.fixture
def entorno(muestra, monkeypatch):
    """El entorno del proceso apunta a la muestra (core/env respeta las variables); QSettings y la caché, en temporal."""
    for k, v in muestra.entorno.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("XDG_CACHE_HOME", str(muestra.raiz / "cache"))
    from gui_comun.qt import QSettings
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(muestra.raiz / "config"))
    return muestra


def entorno_gui(tmp_path: Path, muestra, **extra: str) -> dict:
    """Entorno de un proceso hijo con GUI: sin pantalla, QSettings, caché y estado en temporal, la muestra como biblioteca."""
    env = {k: v for k, v in os.environ.items() if k not in _VARIABLES_CORE}
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    })
    env.update(muestra.entorno)
    env.update(extra)
    return env


def correr_python(guion: str, env: dict, *args: str, plazo: int = 150) -> subprocess.CompletedProcess:
    """Corre `guion` con el Python del sistema (el de Kirigami); argv[1] es la carpeta studio/."""
    return subprocess.run([PYTHON_SISTEMA or sys.executable, "-c", guion, str(STUDIO), *args], env=env, capture_output=True,
                          text=True, timeout=plazo)


@pytest.fixture(scope="session")
def app():
    """Una QGuiApplication offscreen para las pruebas en proceso."""
    from gui_comun.qt import QGuiApplication
    QGuiApplication.setOrganizationName("biblioteca-studio-pruebas")
    QGuiApplication.setApplicationName("biblioteca-studio-pruebas")
    instancia = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    yield instancia
