#!/usr/bin/env python3
"""lib/escribir.py — la única puerta de escritura de scripts-biblioteca, lado Python (ola 2a, K2 y F2; fundidas en la fase E).

Objetivo: que ningún otro archivo del repo escriba en metadata.db ni en zotero.sqlite (normativa 9.1,
  RQ-PRE-06; lo comprueba tests/test_puerta.py).
Método:
  - Calibre se escribe con su API (`set_campos`, dentro de `calibre-debug`) o con `calibredb`
    (`calibredb_escribe` de lib/escribir.sh), nunca por SQL: el SQL directo choca con los disparadores
    de Calibre (title_sort) y deja los OPF rancios;
  - Zotero se escribe por SQL (no hay otra vía con la app cerrada) con las primitivas `z_*` de
    lib/escribir_zotero.py, que marcan cada ítem tocado como no sincronizado para que la cuenta lo suba;
  - toda escritura exige la puerta abierta: PUERTA_CALIBRE / PUERTA_ZOTERO = «abierta», que pone
    lib/escribir.sh tras comprobar la app cerrada, tomar el candado y respaldar verificado, o el gestor
    `puerta()` de aquí para las herramientas que son solo Python.
Uso como CLI (lo llama lib/escribir.sh):
    escribir.py respaldar BASE CARPETA PREFIJO N   → respaldo verificado y rotado; imprime su ruta
    escribir.py integridad BASE…                   → PRAGMA integrity_check (solo lectura) = ok en todas
    calibre-debug -e escribir.py aplicar-plan BIBLIOTECA PLAN.json   → {campo: {libro: valor}} por la API
    calibre-debug -e escribir.py aplicar-campana BIBLIOTECA PLAN.json → una campaña de migraciones/ (ola 2b)
Límite: la API de Calibre solo existe dentro de `calibre-debug`; fuera, `set_campos` no se puede llamar.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LIB = Path(__file__).resolve().parent
CORE = LIB.parent.parent / "core"
ABIERTA = "abierta"


class PuertaCerrada(RuntimeError):
    """Se intentó escribir sin abrir la puerta."""


def exigir(base: str, ruta: str | os.PathLike | None = None) -> None:
    """Falla si la puerta de `base` («calibre» o «zotero») no está abierta para `ruta`."""
    if os.environ.get(f"PUERTA_{base.upper()}") != ABIERTA:
        raise PuertaCerrada(f"la puerta de {base} está cerrada: ábrela con lib/escribir.sh o escribir.puerta()")
    if ruta is not None:
        esperado = os.environ.get("PUERTA_BIBLIOTECA" if base == "calibre" else "PUERTA_ZOTERO_DB", "")
        if not esperado or os.path.realpath(esperado) != os.path.realpath(ruta):
            raise PuertaCerrada(f"la puerta de {base} se abrió para «{esperado}», no para «{ruta}»")


# ------------------------------------------------------------------ respaldo e integridad
def _ro(ruta) -> sqlite3.Connection:
    return sqlite3.connect(Path(ruta).resolve().as_uri() + "?mode=ro", uri=True)


def integridad(*bases) -> bool:
    ok = True
    for b in bases:
        c = _ro(b)
        r = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        if r != "ok":
            print(f"integridad de {b}: {r}", file=sys.stderr)
            ok = False
    return ok


def respaldar(base, carpeta, prefijo: str, conservar: int = 3) -> Path:
    """Copia consistente (API de respaldo de SQLite desde una conexión de solo lectura) a un temporal,
    `quick_check` = ok, renombrado atómico y, solo entonces, rotación a los `conservar` más recientes."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{prefijo}_", suffix=".tmp", dir=carpeta)
    os.close(fd)
    try:
        src, dst = _ro(base), sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        c = _ro(tmp)
        bien = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        c.close()
        if not bien:
            raise RuntimeError(f"PRAGMA quick_check no dio «ok» en la copia de {base}")
        final = carpeta / f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{Path(base).suffix or '.db'}"
        os.replace(tmp, final)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    viejos = sorted(carpeta.glob(f"{prefijo}_*"), key=lambda p: p.stat().st_mtime, reverse=True)[conservar:]
    for v in viejos:
        v.unlink(missing_ok=True)
    return final


def _app_abierta(patron: str) -> bool:
    """Mismo criterio que core/shell-lib/detectar_apps.sh: el nombre del binario (`ps -eo comm`)."""
    import re
    salida = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
    return any(re.match(patron, l.strip(), re.I) for l in salida.splitlines())


def _respaldo_calibre(db, carpeta, conservar: int) -> str:
    """El respaldo verificado de core (`backup_metadata_db`), el mismo que usa lib/escribir.sh."""
    r = subprocess.run(["bash", "-c", 'source "$1"; backup_metadata_db "$2" "$3" "$4"', "_",
                        str(CORE / "shell-lib" / "backup_rotado.sh"), str(db), str(carpeta), str(conservar)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"sin respaldo verificado de {db}: {r.stderr.strip()}")
    return r.stdout.strip().removeprefix("── Backup: ")


@contextmanager
def puerta(suite: str, calibre: str | os.PathLike | None = None, zotero: str | os.PathLike | None = None,
           respaldos: str | os.PathLike | None = None):
    """La puerta para herramientas que son solo Python: app cerrada, candado y respaldo verificado de cada
    base pedida (`calibre` = carpeta de la biblioteca; `zotero` = zotero.sqlite). Ocupado: `Ocupado` (75)."""
    sys.path.insert(0, str(CORE / "py-common"))
    from candado import candado  # noqa: E402  (core/py-common/candado.py)
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    raiz = Path(respaldos or os.environ.get("PUERTA_RESPALDOS") or estado / "biblioteca" / "respaldos") / suite
    antes = {k: os.environ.get(k) for k in ("PUERTA_CALIBRE", "PUERTA_BIBLIOTECA", "PUERTA_ZOTERO", "PUERTA_ZOTERO_DB")}
    pilas = []
    try:
        if calibre is not None:
            if _app_abierta(r"^calibre"):
                raise PuertaCerrada("Calibre está abierto: ciérralo antes de escribir en la biblioteca")
            cm = candado("calibre"); cm.__enter__(); pilas.append(cm)
            r = _respaldo_calibre(Path(calibre) / "metadata.db", raiz / "calibre",
                                  int(os.environ.get("PUERTA_CONSERVAR_CALIBRE", 5)))
            print(f"── Backup: {r}")
            os.environ.update(PUERTA_CALIBRE=ABIERTA, PUERTA_BIBLIOTECA=str(calibre))
        if zotero is not None:
            if _app_abierta(r"^zotero"):
                raise PuertaCerrada("Zotero está abierto: ciérralo antes de escribir en zotero.sqlite")
            cm = candado("zotero"); cm.__enter__(); pilas.append(cm)
            r = respaldar(zotero, raiz / "zotero", "zotero", int(os.environ.get("PUERTA_CONSERVAR_ZOTERO", 3)))
            print(f"── Backup: {r}")
            os.environ.update(PUERTA_ZOTERO=ABIERTA, PUERTA_ZOTERO_DB=str(zotero))
        yield
    finally:
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for cm in reversed(pilas):
            cm.__exit__(None, None, None)


# ------------------------------------------------------------------ Calibre (API, dentro de calibre-debug)
def set_campos(api, cambios: dict) -> int:
    """{campo: {libro: valor}} → `api.set_field` por campo; devuelve cuántos valores pidió escribir."""
    exigir("calibre", api.backend.library_path)
    n = 0
    for campo, valores in cambios.items():
        if valores:
            api.set_field(campo, valores)
            n += len(valores)
    return n


def _fecha(v):
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-":
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return v


def aplicar_plan(biblioteca, plan_json) -> int:
    """Un plan {campo: {libro: valor}} escrito por otra herramienta (p. ej. sincronizar_zotero), por la API.
    `identifiers` se fusiona con los que el libro ya tiene (nunca borra); `pubdate` admite texto ISO."""
    from calibre.library import db as calibre_db
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))
    api = calibre_db(str(biblioteca)).new_api
    cambios = {}
    for campo, valores in plan.items():
        v = {int(b): x for b, x in valores.items()}
        if campo == "identifiers":
            v = {b: {**(api.field_for("identifiers", b) or {}), **x} for b, x in v.items()}
        elif campo == "pubdate":
            v = {b: _fecha(x) for b, x in v.items()}
        cambios[campo] = v
    return set_campos(api, cambios)


def aplicar_campana(biblioteca, plan_json) -> int:
    """Una campaña de `migraciones/` (ola 2b) por la API: `enum_antes` ({columna: valores}, la unión de los viejos y
    los nuevos, para que ningún valor nuevo se rechace), `campos` ({campo: {libro: valor}}), `enum_despues` (la
    enumeración final) y `columnas_borrar` ([etiquetas]; Calibre las borra al reabrir la base). Devuelve cuántos
    valores escribió. Exige la puerta abierta."""
    from calibre.library import db as calibre_db
    exigir("calibre", biblioteca)
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))

    def enumeracion(legacy, cambios):
        mapa = legacy.custom_column_label_map
        for etiqueta, valores in (cambios or {}).items():
            col = mapa[etiqueta.lstrip("#")]
            display = dict(col["display"])
            display["enum_values"] = list(valores)
            legacy.set_custom_column_metadata(col["num"], display=display)

    legacy = calibre_db(str(biblioteca))
    enumeracion(legacy, plan.get("enum_antes"))
    legacy.close()
    legacy = calibre_db(str(biblioteca))
    api = legacy.new_api
    n = 0
    for campo, valores in (plan.get("campos") or {}).items():
        v = {int(b): x for b, x in valores.items()}
        if campo == "pubdate":
            v = {b: _fecha(x) for b, x in v.items()}
        if v:
            api.set_field(campo, v)
            n += len(v)
    enumeracion(legacy, plan.get("enum_despues"))
    for etiqueta in plan.get("columnas_borrar") or []:
        legacy.delete_custom_column(label=etiqueta.lstrip("#"))
    legacy.close()
    if plan.get("columnas_borrar"):
        calibre_db(str(biblioteca)).close()   # al reabrir, Calibre borra las columnas marcadas
    return n


# ------------------------------------------------------------------ calibredb (ingesta)
# Lo que usaba la puerta de scripts_for_fuentes (F2): `ingesta` y sus módulos cargan este archivo por ruta y
# escriben con `calibredb`; las órdenes de lectura pasan siempre, las demás exigen la puerta abierta.
SALIDA_CERRADA = 75
LECTURAS = {"list", "search", "show_metadata", "list_categories", "export", "catalog"}
ENTORNO = {"LC_ALL": "C", "LANG": "C"}   # la salida de calibredb en inglés («Added book ids»)


def abierta() -> bool:
    return os.environ.get("PUERTA_CALIBRE") == ABIERTA


def exigir_puerta() -> None:
    """Corta el proceso con 75 si la puerta no está abierta: nada se escribe (ni Calibre ni ledgers)."""
    if not abierta():
        print("[ERROR] puerta de Calibre cerrada: escriba a través de ingesta/main.sh … --aplicar "
              "(Calibre cerrado, candado y respaldo verificado); reintente luego (salida 75)", file=sys.stderr)
        sys.exit(SALIDA_CERRADA)


def calibredb(biblioteca, orden: str, *args, **kw) -> subprocess.CompletedProcess:
    """`calibredb --with-library BIBLIOTECA ORDEN ARGS…`; las órdenes que no son de lectura exigen la puerta."""
    if orden not in LECTURAS and not abierta():
        raise PuertaCerrada(f"calibredb {orden} sin la puerta abierta (lib/escribir.sh)")
    entorno = dict(os.environ, **ENTORNO)
    return subprocess.run([os.environ.get("CALIBREDB", "calibredb"), "--with-library", str(biblioteca), orden,
                           *map(str, args)], capture_output=True, text=True, errors="replace", env=entorno, **kw)


# ------------------------------------------------------------------ CLI
def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    orden, args = argv[0], argv[1:]
    if orden == "respaldar":
        base, carpeta, prefijo, n = args
        print(respaldar(base, carpeta, prefijo, int(n)))
        return 0
    if orden == "integridad":
        return 0 if integridad(*args) else 1
    if orden == "aplicar-campana":
        biblioteca, plan = args
        print(f"── Calibre: {aplicar_campana(biblioteca, plan)} valores escritos por la API (campaña)")
        return 0
    if orden == "aplicar-plan":
        biblioteca, plan = args
        n = aplicar_plan(biblioteca, plan)
        print(f"── Calibre: {n} valores enviados a la API (solo se escriben los que cambian)")
        return 0
    print(f"orden desconocida: {orden}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except PuertaCerrada as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
