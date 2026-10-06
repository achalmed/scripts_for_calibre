# comun.py — maquinaria compartida y registro de procedencia de las fuentes.
#
# NO reimplementa red ni hash: usa `core/py-common/red.py` (stdlib puro; ola 2, F4), el mismo módulo que
# cargará datafw. Lo que
# sí es propio de este sistema es el LEDGER: qué documento se adquirió, de dónde,
# cuándo y con qué hash — el puente que después usa ingesta/ para
# catalogarlo en Calibre sin volver a preguntarse de dónde salió.

import csv
import sys
from datetime import datetime
from pathlib import Path

import config

sys.path.insert(0, str(config.PY_COMMON))
import red                                           # noqa: E402  core/py-common/red.py

COLUMNAS = ["fecha", "sha256", "fuente", "tipo", "referencia", "titulo",
            "url", "origen", "archivo", "bytes", "estado"]


def descargar(url, destino_dir, base, ext="pdf"):
    """Descarga con validación por bytes mágicos. Devuelve (ruta, sha256, bytes).

    El 200 con página de error HTML es la trampa clásica de los portales del
    Estado: por eso se comprueban los primeros bytes y no solo el código.
    """
    return red.descargar(url, destino_dir, base, ext, user_agent=config.USER_AGENT, timeout=config.TIMEOUT,
                         pausa=config.PAUSA, max_bytes=config.LIMITE_MB * 1024 * 1024)


def leer_ledger():
    if not config.LEDGER.exists():
        return {}
    with open(config.LEDGER, encoding="utf-8", newline="") as f:
        return {r["sha256"]: r for r in csv.DictReader(f, delimiter="\t") if r.get("sha256")}


def anotar(fila):
    """Añade (o actualiza por hash) una fila de procedencia."""
    filas = leer_ledger()
    fila = {**{c: "" for c in COLUMNAS}, **fila}
    fila["fecha"] = fila["fecha"] or datetime.now().isoformat(timespec="seconds")
    filas[fila["sha256"]] = fila
    with open(config.LEDGER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in sorted(filas.values(), key=lambda x: x["fecha"]):
            w.writerow({c: r.get(c, "") for c in COLUMNAS})


def ya_adquirido(sha):
    return sha in leer_ledger()
