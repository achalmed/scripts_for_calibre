"""biblioteca_app/servicios/mapa_lectura.py — el mapa de lo leído (pedido del autor, 2026-11-19): lo que la IA estructuró
en las sesiones guiadas de Ñawinchay (los conceptos con su definición y su lugar, sus relaciones y los temas), por libro y
entre libros. Solo lee: el diario de cada libro de Ñawinchay (`<datos>/diario/c<calibre_id>.json`, sus
`estudio.guia.sesiones[*].estructura`) y el contrato que lo junta, `nawinchay/studio/nawinchay_app/mapa.py`, cargado por
ruta (como `manifiesto/`). Sin Ñawinchay o sin sesiones, un mapa vacío. Nada se escribe ni se exporta.

El mapa de TODA la biblioteca (pedido del autor, 2026-11-24; §9.19), sobre lo mismo y sin base nueva:

- `mapa_global()`: un solo barrido de los diarios, con caché por la huella de la carpeta (`_sello`). Cada concepto sabe
  en qué libros aparece y cada relación, de qué libros sale. `mapa_libro` se arma de aquí, así que ver un libro ya no
  reconstruye el mapa de todos los demás (antes era O(n²): un barrido entero por cada libro que se abría).
- `cobertura(libros)`: dónde estoy y qué me falta, por tema, y de qué trata cada tema según OpenAlex (§9.20: las
  materias de la caché de `lib/materias.py`, que la ventana solo lee). Cruza las etiquetas del vocabulario cerrado de Calibre
  (las de `catalogo.leer`, que el área ya tiene) con lo leído en KOReader y con los conceptos del mapa: cuántos libros
  tiene cada tema, cuántos están leídos, en curso o sin abrir, y cuántos conceptos salieron de ellos. Un tema sin
  ningún concepto es un tema que la biblioteca tiene y el lector todavía no.

Los datos de Ñawinchay: `NAWINCHAY_DATOS` o `$XDG_DATA_HOME/nawinchay` (las pruebas y las capturas apuntan a la muestra).
Lo que devuelven `mapa_global` y `_global` es de solo lectura: está en la caché y quien lo reciba no debe modificarlo
(`mapa_libro` entrega copias).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
VACIO = {"conceptos": [], "relaciones": [], "etiquetas": []}
GLOBAL_VACIO = {"conceptos": [], "relaciones": [], "etiquetas": [], "libros": 0, "sesiones": 0}
DIARIO = re.compile(r"^c(\d+)$")

# El estado de lectura de un libro, de `#ko_status` y `#ko_progfloat` de KOReader (la biblioteca real, 2026-11-24:
# 35 «complete», 236 «reading» y 4 524 sin nada de 4 795 libros).
LEIDO, EN_CURSO, SIN_ABRIR = "leido", "en_curso", "sin_abrir"
TERMINADO = 0.95  # un progreso igual o mayor cuenta como leído aunque KOReader no haya puesto «complete»


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


def _sello(carpeta: Path) -> tuple:
    """La huella de los diarios (nombre, tamaño y fecha de cada uno): cambia cuando Ñawinchay escribe, y con ella la
    caché de `_global`. Así el mapa de toda la biblioteca se rehace solo cuando hay algo nuevo que leer."""
    if not carpeta.is_dir():
        return ()
    huellas = []
    for ruta in sorted(carpeta.glob("c*.json")):
        try:
            e = ruta.stat()
        except OSError:
            continue
        huellas.append((ruta.name, e.st_size, e.st_mtime_ns))
    return tuple(huellas)


@lru_cache(maxsize=4)
def _global(sello: tuple) -> dict:
    """El barrido de todos los diarios, cacheado por `sello` (que no se usa dentro: es la clave de la caché).

    Devuelve, además de lo del contrato, `por_libro` (calibre_id → su mapa) y, en cada concepto y cada relación, los
    libros de donde salen."""
    m = contrato()
    carpeta = datos_nawinchay() / "diario"
    if m is None or not carpeta.is_dir():
        return dict(GLOBAL_VACIO, por_libro={})

    conceptos: dict[str, dict] = {}
    relaciones: dict[tuple, dict] = {}
    etiquetas: dict[str, int] = {}
    por_libro: dict[int, dict] = {}
    sesiones = 0

    for ruta in sorted(carpeta.glob("c*.json")):
        casa = DIARIO.match(ruta.stem)
        if not casa:
            continue
        libro = int(casa.group(1))
        propias = _sesiones(ruta)
        if not propias:
            continue
        salida = m.mapa(propias)
        por_libro[libro] = dict(salida, sesiones=len(propias))
        sesiones += len(propias)
        for c in salida["conceptos"]:
            k = m.clave(c["termino"])
            d = conceptos.setdefault(k, {"termino": c["termino"], "definiciones": [], "lugares": [],
                                         "etiquetas": [], "veces": 0, "libros": []})
            d["veces"] += c["veces"]
            if libro not in d["libros"]:
                d["libros"].append(libro)
            for campo in ("definiciones", "lugares", "etiquetas"):
                for v in c[campo]:
                    if v not in d[campo]:
                        d[campo].append(v)
        for r in salida["relaciones"]:
            k = (m.clave(r["de"]), r["tipo"], m.clave(r["a"]))
            d = relaciones.setdefault(k, {"de": r["de"], "tipo": r["tipo"], "a": r["a"], "libros": []})
            if libro not in d["libros"]:
                d["libros"].append(libro)
        for e, n in salida["etiquetas"]:
            etiquetas[e] = etiquetas.get(e, 0) + n

    for d in conceptos.values():
        d["nlibros"] = len(d["libros"])
    lista = sorted(conceptos.values(), key=lambda c: (-c["nlibros"], -c["veces"], m.clave(c["termino"])))
    return {"conceptos": lista, "relaciones": list(relaciones.values()),
            "etiquetas": sorted(([e, n] for e, n in etiquetas.items()), key=lambda x: (-x[1], x[0])),
            "libros": len(por_libro), "sesiones": sesiones, "por_libro": por_libro}


def mapa_global() -> dict:
    """{conceptos, relaciones, etiquetas, libros, sesiones}: el mapa de toda la biblioteca (2026-11-24). Cada concepto
    trae `libros` (los calibre_id donde aparece) y `nlibros`; cada relación, los libros de donde sale. Solo lectura."""
    g = _global(_sello(datos_nawinchay() / "diario"))
    return {k: v for k, v in g.items() if k != "por_libro"}


def mapa_libro(calibre_id: int) -> dict:
    """{conceptos, relaciones, etiquetas, sesiones, otros}: el mapa del libro y, por concepto, en qué otros libros aparece
    (`otros`: término normalizado → número de libros), para ver lo que conecta las lecturas."""
    m = contrato()
    if m is None or calibre_id is None or int(calibre_id) < 0:
        return dict(VACIO, sesiones=0, otros={})
    g = _global(_sello(datos_nawinchay() / "diario"))
    propio = g["por_libro"].get(int(calibre_id))
    if not propio:
        return dict(VACIO, sesiones=0, otros={})
    otros = {m.clave(c["termino"]): c["nlibros"] - 1
             for c in g["conceptos"] if int(calibre_id) in c["libros"] and c["nlibros"] > 1}
    conceptos = [dict(c, otros=otros.get(m.clave(c["termino"]), 0)) for c in propio["conceptos"]]
    return {"conceptos": conceptos, "relaciones": [dict(r) for r in propio["relaciones"]],
            "etiquetas": [list(e) for e in propio["etiquetas"]], "sesiones": propio["sesiones"], "otros": otros}


@lru_cache(maxsize=1)
def _lib_materias():
    """`lib/materias.py` del repo (§9.20), cargado por ruta como hace `catalogo` con `lib/indice.py`; None si no
    está. Solo se le pide la caché: la ventana nunca consulta la red."""
    ruta = REPO / "lib" / "materias.py"
    if not ruta.is_file():
        return None
    s = importlib.util.spec_from_file_location("biblioteca_materias", ruta)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def materias_por_libro() -> dict:
    """{calibre_id: [materias]} de la caché de los catálogos (§9.20), o {} si no hay nada traído todavía."""
    m = _lib_materias()
    try:
        return m.por_libro() if m is not None else {}
    except (OSError, ValueError):
        return {}


def _entero(valor) -> int | None:
    """El calibre_id como número: `catalogo.leer` lo entrega en texto («id»: str) y el mapa lo tiene en número (del
    nombre del diario, `c<calibre_id>.json`). Sin esto no casa ninguno y todo tema diría «0 conceptos»."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def estado_lectura(libro: dict) -> str:
    """`leido`, `en_curso` o `sin_abrir`, de la lectura en KOReader de un libro de `catalogo.leer`."""
    estado = str(libro.get("ko_estado") or "").lower()
    progreso = libro.get("ko_progreso")
    if estado == "complete" or (progreso is not None and progreso >= TERMINADO):
        return LEIDO
    if estado or (progreso is not None and progreso > 0):
        return EN_CURSO
    return SIN_ABRIR


def cobertura(libros: list[dict], mapa: dict | None = None, materias: dict | None = None) -> dict:
    """{temas: [ … ], libros, leidos, en_curso, sin_abrir, conceptos}: dónde estoy y qué me falta (2026-11-24).

    `libros` son los de `catalogo.leer` (etiquetas del vocabulario cerrado y lectura de KOReader); `mapa`, el de
    `mapa_global` (si no se da, se lee). Por tema: cuántos libros tiene, cuántos leídos, en curso y sin abrir, y
    cuántos conceptos del mapa salieron de sus libros. Los temas van de menos a más estudiado (el que más libros sin
    abrir tiene, primero), que es el orden en que esto se mira."""
    g = mapa if mapa is not None else mapa_global()
    de_materia = materias if materias is not None else materias_por_libro()
    de_concepto: dict[int, int] = {}
    for c in g["conceptos"]:
        for b in c["libros"]:
            de_concepto[b] = de_concepto.get(b, 0) + 1

    temas: dict[str, dict] = {}
    total = {LEIDO: 0, EN_CURSO: 0, SIN_ABRIR: 0}
    for libro in libros:
        estado = estado_lectura(libro)
        total[estado] += 1
        b = _entero(libro.get("id"))
        conceptos = de_concepto.get(b, 0)
        suyas = de_materia.get(b) or []
        for etiqueta in libro.get("etiquetas") or []:
            t = temas.setdefault(etiqueta, {"tema": etiqueta, "libros": 0, LEIDO: 0, EN_CURSO: 0, SIN_ABRIR: 0,
                                            "conceptos": 0, "con_materias": 0, "_materias": {}})
            t["libros"] += 1
            t[estado] += 1
            t["conceptos"] += conceptos
            if suyas:
                t["con_materias"] += 1
                for nombre in suyas:
                    t["_materias"][nombre] = t["_materias"].get(nombre, 0) + 1

    for t in temas.values():                 # las tres materias que más se repiten: de qué trata el tema según OpenAlex
        t["materias"] = [n for n, _ in sorted(t.pop("_materias").items(), key=lambda x: (-x[1], x[0]))[:3]]
    lista = sorted(temas.values(), key=lambda t: (-t[SIN_ABRIR], -t["libros"], t["tema"]))
    return {"temas": lista, "libros": len(libros), LEIDO: total[LEIDO], EN_CURSO: total[EN_CURSO],
            SIN_ABRIR: total[SIN_ABRIR], "conceptos": len(g["conceptos"]),
            "con_materias": sum(1 for l in libros if de_materia.get(_entero(l.get("id"))))}
