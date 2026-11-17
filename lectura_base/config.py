"""lectura_base/config.py — de dónde lee y dónde escribe la base de lectura (todo por el entorno; `core/env` lo fija).

- `LECTURA_DB`: la base (por omisión `$XDG_DATA_HOME/biblioteca/lectura.sqlite`, `lib/base.ruta_base`).
- `CALIBRE_DB`, `BIBLIOTECA_DIR`: Calibre, en solo lectura (títulos, archivos y `#ko_md5`).
- `ZOTERO_DB`: Zotero (se lee de una copia; se escribe solo por la puerta).
- `KOREADER_DIR` o `KOREADER_STATS`, y `KOREADER_RESPALDO_DIR` si la carpeta viva no está.
- `OKULAR_DOCDATA`: la carpeta docdata de Okular (por omisión `$XDG_DATA_HOME/okular/docdata`).
- `YACHAY_CLIENTE` o `YACHAY_DIR`: el cliente de Yachay con token (fase 3b).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parent
REPO = SUITE.parent
DOCS = REPO.parent


def cargar_entorno() -> None:
    """Las variables de core/env.py que falten en el entorno (las del entorno mandan: así la muestra y las pruebas
    apuntan a sus copias)."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    env = DOCS / "core" / "env.py"
    if not env.is_file():
        return
    import importlib.util
    s = importlib.util.spec_from_file_location("core_env", env)
    m = importlib.util.module_from_spec(s)
    try:
        s.loader.exec_module(m)
    except Exception:  # noqa: BLE001 — sin core/env valen las del entorno
        return
    for k in ("CALIBRE_DB", "BIBLIOTECA_DIR", "ZOTERO_DB", "ZOTERO_DIR", "KOREADER_STATS", "KOREADER_RESPALDO_DIR",
              "RESPALDOS_DIR", "ARCHDISK_DIR", "DOCS_ROOT"):
        v = getattr(m, k, None)
        if v and not os.environ.get(k):
            os.environ[k] = str(v)


def logger(verbose: bool = False):
    """El logger único de core (`core/py-common/logger.py`); sin core, el de la biblioteca estándar."""
    sys.path.insert(0, str(DOCS / "core" / "py-common"))
    try:
        from logger import configurar  # noqa: E402
        return configurar("lectura_base", verbose=verbose)
    except Exception:  # noqa: BLE001
        import logging
        logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="[%(levelname)s] %(message)s")
        return logging.getLogger("lectura_base")
