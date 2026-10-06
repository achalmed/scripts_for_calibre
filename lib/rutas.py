"""lib/rutas.py — las rutas que guardan los ledgers, relativas a DOCS_ROOT (ola 2, F5; RQ-RUT-01, RQ-SEC-01).

`ingesta/ingesta.tsv` y `ingesta/pendientes.tsv` guardaban rutas absolutas de la máquina (`origen`,
`ruta_calibre`). Desde F5 una ruta bajo la raíz del workspace se escribe relativa a ella
(`datafw/data/raw/…`, `biblioteca/<Autor>/<Título (id)>/…`), y al leer:

- absoluta                                  → tal cual (filas viejas o fuera de la raíz);
- relativa que empieza por una carpeta de la raíz (`datafw`, `escritura`, `scripts_for_fuentes`,
  `biblioteca`…)                            → DOCS_ROOT / ruta;
- cualquier otra relativa                   → relativa a la zona de entrada, como siempre (incluidas las del
  CIL histórico, `02_investigacion/…`, que ya no existen y se conservan como texto).

Se carga por ruta (cada sub-suite tiene su propio `lib`):

    spec = importlib.util.spec_from_file_location("rutas", RAIZ / "lib" / "rutas.py")
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def docs_root() -> Path:
    """DOCS_ROOT de core/env.py (respeta el entorno), buscado desde este archivo."""
    if os.environ.get("DOCS_ROOT") and (Path(os.environ["DOCS_ROOT"]) / "core" / "env.py").is_file():
        return Path(os.environ["DOCS_ROOT"])
    d = Path(__file__).resolve()
    while d != d.parent and not (d / "core" / "env.py").is_file():
        d = d.parent
    s = importlib.util.spec_from_file_location("core_env", d / "core" / "env.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return Path(m.DOCS_ROOT)


def a_texto(ruta, docs=None) -> str:
    """Texto para el ledger: relativo a DOCS_ROOT si la ruta cae dentro; si no, absoluto."""
    if ruta in (None, ""):
        return ""
    docs = Path(docs) if docs else docs_root()
    p = Path(ruta)
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.relative_to(docs))
    except ValueError:
        try:
            return str(p.relative_to(docs.resolve()))
        except ValueError:
            return str(p)


def resolver(texto, entrada, docs=None):
    """Ruta absoluta de un texto del ledger (ver la cabecera); None si está vacío."""
    if not texto:
        return None
    p = Path(texto)
    if p.is_absolute():
        return p
    docs = Path(docs) if docs else docs_root()
    if p.parts and (docs / p.parts[0]).is_dir():
        return docs / p
    return Path(entrada) / p
