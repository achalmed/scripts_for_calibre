"""biblioteca_app/servicios/mapa_lectura.py — el mapa de lo leído (pedido del autor, 2026-11-19): lo que la IA estructuró
en las sesiones guiadas de Ñawinchay (los conceptos con su definición y su lugar, sus relaciones y los temas), por libro y
entre libros. Solo lee: el diario de cada libro de Ñawinchay (`<datos>/diario/c<calibre_id>.json`, sus
`estudio.guia.sesiones[*].estructura`) y el contrato que lo junta, `nawinchay/studio/nawinchay_app/mapa.py`, cargado por
ruta (como `manifiesto/`). Sin Ñawinchay o sin sesiones, un mapa vacío. Nada se escribe ni se exporta.

Los datos de Ñawinchay: `NAWINCHAY_DATOS` o `$XDG_DATA_HOME/nawinchay` (las pruebas y las capturas apuntan a la muestra).
"""
from __future__ import annotations

import importlib.util
import json
import os
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
VACIO = {"conceptos": [], "relaciones": [], "etiquetas": []}


def datos_nawinchay() -> Path:
    if os.environ.get("NAWINCHAY_DATOS"):
        return Path(os.environ["NAWINCHAY_DATOS"])
    xdg = os.environ.get("XDG_DATA_HOME") or str(Path(os.path.expanduser("~")) / ".local" / "share")
    return Path(xdg) / "nawinchay"


@lru_cache(maxsize=1)
def contrato():
    """`nawinchay_app/mapa.py` del espacio de trabajo (el repo hermano `nawinchay/`), o None si no está."""
    d = REPO
    while d != d.parent:
        ruta = d / "nawinchay" / "studio" / "nawinchay_app" / "mapa.py"
        if ruta.is_file():
            s = importlib.util.spec_from_file_location("nawinchay_mapa", ruta)
            m = importlib.util.module_from_spec(s)
            s.loader.exec_module(m)
            return m
        d = d.parent
    return None


def _sesiones(ruta: Path) -> list[dict]:
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sesiones = ((d.get("estudio") or {}).get("guia") or {}).get("sesiones") or []
    return [s for s in sesiones if isinstance(s, dict) and s.get("estructura")]


def mapa_libro(calibre_id: int) -> dict:
    """{conceptos, relaciones, etiquetas, sesiones, otros}: el mapa del libro y, por concepto, en qué otros libros aparece
    (`otros`: término normalizado → número de libros), para ver lo que conecta las lecturas."""
    m = contrato()
    carpeta = datos_nawinchay() / "diario"
    if m is None or calibre_id is None or int(calibre_id) < 0 or not carpeta.is_dir():
        return dict(VACIO, sesiones=0, otros={})
    propias = _sesiones(carpeta / f"c{int(calibre_id)}.json")
    if not propias:
        return dict(VACIO, sesiones=0, otros={})
    salida = m.mapa(propias)
    claves = {m.clave(c["termino"]) for c in salida["conceptos"]}
    otros: dict[str, int] = {}
    for ruta in carpeta.glob("c*.json"):
        if ruta.stem == f"c{int(calibre_id)}":
            continue
        ajenos = {m.clave(c["termino"]) for c in m.mapa(_sesiones(ruta))["conceptos"]}
        for k in claves & ajenos:
            otros[k] = otros.get(k, 0) + 1
    for c in salida["conceptos"]:
        c["otros"] = otros.get(m.clave(c["termino"]), 0)
    return dict(salida, sesiones=len(propias), otros=otros)
