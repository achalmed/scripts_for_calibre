"""tests/studio/conftest.py — el temporal de las pruebas de Biblioteca Studio va al disco, no a /tmp (tmpfs: es RAM)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASETEMP = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pytest" / "biblioteca-studio-studio" / "basetemp"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Como tests/calibre: solo si nadie pidió otro --basetemp y la corrida es de este repo."""
    if config.option.basetemp:
        return
    args = [Path(a.split("::")[0]).resolve() for a in (config.args or [])]
    if args and all(REPO in a.parents or a == REPO for a in args):
        BASETEMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(BASETEMP)
