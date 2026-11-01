"""studio/biblioteca_app/__init__.py — paquete de Biblioteca Studio; al importarse encuentra gui_comun (instalado o el repo gui-comun/)."""

import sys as _sys
from pathlib import Path as _Path

# gui_comun, el marco común de los studios: instalado (pip install gui-comun) o, en el espacio de trabajo, el repo
# gui-comun/ que se encuentra subiendo carpetas desde aquí; se añade al final para no tapar ningún módulo del studio.
try:
    import gui_comun as _gc  # noqa: F401
except ImportError:
    _d = _Path(__file__).resolve().parent
    while _d != _d.parent and not (_d / "gui-comun" / "gui_comun").is_dir():
        _d = _d.parent
    if not (_d / "gui-comun" / "gui_comun").is_dir():
        raise ImportError("falta gui_comun: pip install gui-comun, o el repo gui-comun/ junto a este") from None
    _sys.path.append(str(_d / "gui-comun"))
    del _d
