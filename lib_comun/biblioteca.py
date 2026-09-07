#!/usr/bin/env python3
"""lib_comun/biblioteca.py — envoltorio de compatibilidad (FS2, 2026-09-07): el resolutor vive en core/py-common/biblioteca.py.

Quien hacía `sys.path.insert(0, LIB_COMUN); import biblioteca as bib` sigue funcionando; el código nuevo apunta a core/py-common.
"""
import importlib.util
import sys
from pathlib import Path

_ruta = Path(__file__).resolve().parent.parent.parent / "core" / "py-common" / "biblioteca.py"
_spec = importlib.util.spec_from_file_location("biblioteca_core", _ruta)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
globals().update({k: v for k, v in vars(_core).items() if not k.startswith("__")})

if __name__ == "__main__":
    sys.exit(_core.main(sys.argv[1:]))
