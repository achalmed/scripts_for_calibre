#!/usr/bin/env python3
"""lib/repaso.py — el repaso de las fichas para estudiantes (decisiones §9.9): práctica de recuperación con repaso espaciado,
en el sistema Leitner de cinco cajas. El ÚNICO escritor de `repaso.sqlite`.

Objetivo: que cada ficha de un escrito se pueda estudiar sin mirar: la tarjeta muestra la pregunta (el tema o la
  categoría de la ficha y su obra), «Mostrar la ficha» revela la cita, y quien estudia dice si la sabía.
Método: Leitner. Una ficha nueva entra en la caja 1. «La sabía» la sube una caja (hasta la 5); «Repasar luego» la baja a
  la 1. Cada caja vuelve cada tanto: la 1 cada día, la 2 cada 2 días, la 3 cada 4, la 4 cada 8 y la 5 cada 16
  (`INTERVALOS`). Toca hoy lo que nunca se repasó y lo que vence hoy o antes.
Fundamento: la práctica de recuperación (Roediger y Karpicke, 2006: recordar fija más que releer) y el repaso espaciado
  (Cepeda et al., 2006: repasos separados retienen más que los seguidos).
Límite: la base es del usuario (`$XDG_DATA_HOME/biblioteca/repaso.sqlite` o `REPASO_DB`), no de Calibre ni de Zotero, así
  que no pasa por la puerta; la conexión de escritura pasa por la guarda de rutas de la base de lectura
  (`comprobar_ruta`: nunca dentro de la biblioteca ni de la carpeta de Zotero) y, antes de la primera escritura de cada
  día, deja un respaldo verificado (`lib/escribir.respaldar`) en `<respaldos de la puerta>/repaso/`. Una ficha se nombra
  por su clave (`<familia>/<escrito>/<nombre>`), no por su ruta: el estado sobrevive a una mudanza de `escritura/`.

    python3 lib/repaso.py estado [--claves a b …]           # el estado de cada ficha con repaso (JSON)
    python3 lib/repaso.py responder <clave> --sabia|--luego [--aplicar]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from lectura_base.lib.base import RutaProhibida, comprobar_ruta  # noqa: E402  (la misma guarda que la base de lectura)

INTERVALOS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}          # caja → días hasta el siguiente repaso
CAJAS = tuple(INTERVALOS)
__all__ = ["INTERVALOS", "RutaProhibida", "ruta_base", "estado", "para_hoy", "proxima", "responder", "plan"]

SQL_ESQUEMA = """
CREATE TABLE IF NOT EXISTS tarjetas (
    clave TEXT PRIMARY KEY,
    caja INTEGER NOT NULL DEFAULT 1,
    proxima TEXT NOT NULL,
    ultima TEXT NOT NULL DEFAULT '',
    aciertos INTEGER NOT NULL DEFAULT 0,
    fallos INTEGER NOT NULL DEFAULT 0,
    alta TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS tarjetas_proxima ON tarjetas(proxima);
"""


def ruta_base() -> Path:
    """`REPASO_DB` si viene en el entorno; si no, `$XDG_DATA_HOME/biblioteca/repaso.sqlite` (junto a la base de lectura)."""
    if os.environ.get("REPASO_DB"):
        return Path(os.environ["REPASO_DB"]).expanduser()
    datos = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return datos / "biblioteca" / "repaso.sqlite"


# ------------------------------------------------------------------------------------------------------------- leer
def _lector(ruta: Path) -> sqlite3.Connection | None:
    if not ruta.is_file():
        return None
    c = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def estado(claves=None, ruta: Path | None = None) -> dict[str, dict]:
    """{clave: {caja, proxima, ultima, aciertos, fallos}} de las fichas con repaso (todas, o solo las de `claves`)."""
    c = _lector(Path(ruta or ruta_base()))
    if c is None:
        return {}
    try:
        filas = {r["clave"]: {"caja": r["caja"], "proxima": r["proxima"], "ultima": r["ultima"], "aciertos": r["aciertos"],
                              "fallos": r["fallos"]} for r in c.execute("SELECT * FROM tarjetas")}
    finally:
        c.close()
    if claves is None:
        return filas
    return {k: filas[k] for k in claves if k in filas}


def _vence(e: dict | None, hoy: date) -> bool:
    return e is None or e["proxima"] <= hoy.isoformat()


def para_hoy(claves, ruta: Path | None = None, hoy: date | None = None) -> list[str]:
    """Las fichas que tocan hoy: las nunca repasadas y las que vencen hoy o antes; primero las de caja más baja (lo menos
    sabido) y, en cada caja, la más atrasada. Una nueva cuenta como de la caja 1, después de las vencidas de esa caja."""
    hoy = hoy or date.today()
    claves = list(dict.fromkeys(claves))
    e = estado(claves, ruta)
    tocan = [k for k in claves if _vence(e.get(k), hoy)]
    return sorted(tocan, key=lambda k: (e[k]["caja"], e[k]["proxima"]) if k in e else (1, "9999"))


def proxima(claves, ruta: Path | None = None, hoy: date | None = None) -> int | None:
    """En cuántos días vence la próxima ficha que no toca hoy (None si no hay ninguna)."""
    hoy = hoy or date.today()
    fechas = [v["proxima"] for v in estado(list(claves), ruta).values() if v["proxima"] > hoy.isoformat()]
    if not fechas:
        return None
    return (date.fromisoformat(min(fechas)) - hoy).days


def plan(clave: str, sabia: bool, ruta: Path | None = None, hoy: date | None = None) -> dict:
    """Lo que haría `responder` (sin escribir): la caja de antes y la de después, y la fecha del siguiente repaso."""
    hoy = hoy or date.today()
    antes = estado([clave], ruta).get(clave)
    caja = antes["caja"] if antes else 1
    nueva = min(caja + 1, max(CAJAS)) if sabia else 1
    return {"clave": clave, "sabia": bool(sabia), "caja_antes": caja if antes else 0, "caja": nueva,
            "proxima": (hoy + timedelta(days=INTERVALOS[nueva])).isoformat(), "nueva": antes is None}


# ----------------------------------------------------------------------------------------------------------- escribir
def _respaldar_del_dia(ruta: Path) -> Path | None:
    """Un respaldo verificado antes de la primera escritura de cada día (la misma función de la puerta: copia por la API
    de SQLite, quick_check y rotación). Nada que respaldar si la base aún no existe."""
    if not ruta.is_file():
        return None
    sys.path.insert(0, str(RAIZ / "lib"))
    import escribir  # noqa: E402  (lib/escribir.py: respaldar y la raíz de respaldos)
    carpeta = escribir.raiz_respaldos() / "repaso"
    if any(carpeta.glob(f"repaso_{date.today():%Y%m%d}_*")):
        return None
    return escribir.respaldar(ruta, carpeta, "repaso", int(os.environ.get("REPASO_CONSERVAR", 7)))


def _escritor(ruta: Path) -> sqlite3.Connection:
    real = comprobar_ruta(ruta)                         # RutaProhibida dentro de Calibre o de Zotero
    real.parent.mkdir(parents=True, exist_ok=True)
    _respaldar_del_dia(real)
    c = sqlite3.connect(real)
    c.executescript(SQL_ESQUEMA)
    return c


def responder(clave: str, sabia: bool, aplicar: bool = False, ruta: Path | None = None, hoy: date | None = None) -> dict:
    """«La sabía» (sube una caja) o «Repasar luego» (vuelve a la 1). Sin `aplicar`, solo el plan; con él, lo escribe."""
    if not clave:
        raise ValueError("falta la clave de la ficha")
    hoy = hoy or date.today()
    ruta = Path(ruta or ruta_base())
    p = plan(clave, sabia, ruta, hoy)
    if not aplicar:
        return {**p, "escrito": False}
    momento = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c = _escritor(ruta)
    try:
        with c:
            c.execute("INSERT INTO tarjetas(clave, caja, proxima, ultima, aciertos, fallos, alta) VALUES (?, ?, ?, ?, ?, ?, ?) "
                      "ON CONFLICT(clave) DO UPDATE SET caja = excluded.caja, proxima = excluded.proxima, ultima = excluded.ultima, "
                      "aciertos = tarjetas.aciertos + excluded.aciertos, fallos = tarjetas.fallos + excluded.fallos",
                      (clave, p["caja"], p["proxima"], momento, int(bool(sabia)), int(not sabia), momento))
    finally:
        c.close()
    return {**p, "escrito": True}


# ---------------------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="El repaso Leitner de las fichas (base propia: simula sin --aplicar)")
    sub = ap.add_subparsers(dest="orden", required=True)
    e = sub.add_parser("estado")
    e.add_argument("--claves", nargs="*")
    r = sub.add_parser("responder")
    r.add_argument("clave")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--sabia", action="store_true")
    g.add_argument("--luego", action="store_true")
    r.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    if a.orden == "estado":
        salida = estado(a.claves)
    else:
        salida = responder(a.clave, a.sabia, a.aplicar)
    print(json.dumps(salida, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
