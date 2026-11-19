"""fichas/lib/muestra.py — la muestra aleatoria de las fichas de paráfrasis para cotejarlas a mano (FLUJO_DE_CONOCIMIENTO
C14.3; fundamento §8.2, etapa 2; Jergas y Baethge, 2015).

Objetivo: que el cotejo a mano de las paráfrasis (que el script no puede verificar palabra por palabra) sea una muestra
  reproducible y no una elección a ojo, y que su semilla y su resultado queden escritos.
Método: se toman las `ficha_parafrasis` de una carpeta en orden de nombre; `random.Random(semilla).sample` saca
  ⌈proporción × n⌉ (al menos una); el registro es un YAML en `registro/` del escrito (la carpeta que tiene
  `proyecto.yaml`), con la semilla, la proporción, la fecha y cada ficha con `resultado` por llenar (`coincide`,
  `difiere`) y su nota. La misma semilla sobre las mismas fichas da la misma muestra.
Límite: solo lee las fichas; escribe solo el registro, y únicamente con `aplicar` (normativa 5.10).
"""
from __future__ import annotations

import math
import os
import random
import secrets
from datetime import date
from pathlib import Path

import yaml

RESULTADOS = ("coincide", "difiere")
CABECERA = ("# Muestra de paráfrasis para cotejar a mano (FLUJO_DE_CONOCIMIENTO C14.3). La escribe\n"
            "# `fichas/main.py muestra`; los resultados, `fichas/main.py muestra-resultado`.\n")


def parafrasis(fichas: list[tuple[Path, dict]]) -> list[Path]:
    """Las rutas de las fichas de paráfrasis, en orden de nombre (para que la semilla reproduzca la muestra)."""
    return sorted((p for p, meta in fichas if meta.get("tipo") == "ficha_parafrasis"), key=lambda p: p.name)


def tamano(n: int, proporcion: float) -> int:
    """⌈proporción × n⌉, al menos una si hay alguna y nunca más que n."""
    if n <= 0:
        return 0
    return min(n, max(1, math.ceil(round(n * proporcion, 9))))


def sacar(rutas: list[Path], proporcion: float = 0.2, semilla: int | None = None) -> dict:
    """La muestra: {semilla, proporcion, poblacion, fichas}. Sin semilla, una nueva, que queda en el resultado."""
    if not 0 < proporcion <= 1:
        raise ValueError("la proporción va entre 0 y 1 (0.2 es el 20 %)")
    semilla = secrets.randbelow(10**6) if semilla is None else int(semilla)
    k = tamano(len(rutas), proporcion)
    elegidas = sorted(random.Random(semilla).sample(sorted(rutas, key=lambda p: p.name), k), key=lambda p: p.name)
    return {"semilla": semilla, "proporcion": proporcion, "poblacion": len(rutas), "fichas": elegidas}


def raiz_del_escrito(carpeta: Path) -> Path | None:
    """La carpeta del escrito (la que tiene `proyecto.yaml`) que contiene a `carpeta`, o None."""
    for p in [carpeta, *carpeta.parents]:
        if (p / "proyecto.yaml").is_file():
            return p
    return None


def registro(muestra: dict, carpeta: Path, hoy: date | None = None) -> dict:
    """El contenido del registro, con las rutas relativas a la carpeta de las fichas."""
    hoy = hoy or date.today()
    return {"tipo": "muestra_parafrasis", "fecha": hoy.isoformat(), "carpeta": carpeta.name,
            "semilla": muestra["semilla"], "proporcion": muestra["proporcion"], "poblacion": muestra["poblacion"],
            "muestra": len(muestra["fichas"]),
            "fichas": [{"ficha": str(p.relative_to(carpeta)) if p.is_relative_to(carpeta) else p.name, "resultado": "", "nota": ""}
                       for p in muestra["fichas"]]}


def destino(carpeta: Path, hoy: date | None = None) -> Path:
    """`registro/muestra-parafrasis-<fecha>.yml` del escrito (con sufijo -2, -3… si ese día ya hubo otra)."""
    raiz = raiz_del_escrito(carpeta)
    if raiz is None:
        raise ValueError(f"{carpeta} no está dentro de un escrito (sin proyecto.yaml): indique --registro")
    base = raiz / "registro" / f"muestra-parafrasis-{(hoy or date.today()).isoformat()}"
    p, n = base.with_suffix(".yml"), 2
    while p.exists():
        p, n = base.parent / f"{base.name}-{n}.yml", n + 1
    return p


def escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(f".{ruta.name}.guardando")
    tmp.write_text(CABECERA + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    os.replace(tmp, ruta)


def leer(ruta: Path) -> dict:
    d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    if d.get("tipo") != "muestra_parafrasis":
        raise ValueError(f"{ruta.name} no es un registro de muestra de paráfrasis")
    return d


def anotar(datos: dict, ficha: str, resultado: str, nota: str = "") -> dict:
    """Anota el resultado del cotejo de una ficha de la muestra (por su nombre o su ruta relativa)."""
    if resultado not in RESULTADOS:
        raise ValueError(f"el resultado es {' o '.join(RESULTADOS)}")
    if resultado == "difiere" and not nota.strip():
        raise ValueError("una paráfrasis que difiere del original lleva su nota (qué cambia el sentido)")
    for f in datos.get("fichas") or []:
        if f["ficha"] == ficha or Path(f["ficha"]).name == Path(ficha).name:
            f["resultado"], f["nota"] = resultado, nota.strip()
            return datos
    raise LookupError(f"{ficha} no está en la muestra")


def resumen(datos: dict) -> dict:
    fichas = datos.get("fichas") or []
    c = {r: sum(1 for f in fichas if f.get("resultado") == r) for r in RESULTADOS}
    return {"muestra": len(fichas), "cotejadas": c["coincide"] + c["difiere"], **c,
            "por_cotejar": len(fichas) - c["coincide"] - c["difiere"]}
