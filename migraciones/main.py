#!/usr/bin/env python3
"""migraciones/main.py — una campaña de la migración de metadatos de la biblioteca (ola 2b, P0–P9).

Objetivo: cambiar los metadatos de Calibre por pasos (`pasos/pN.py`), sin riesgo: nada se aplica sin que el ensayo
  sobre una copia cierre en lo previsto y sin que su deshacer devuelva la base exacta.
Método (normativa 9.1; `meta/programa/03-arquitectura/modelo-de-metadatos.md` §7):
  1. plan: el paso lee una copia de la base en solo lectura y devuelve su plan (enumeraciones, campos, columnas
     que se retiran) y su resumen;
  2. ensayo: el plan se aplica a otra copia, en disco ($XDG_CACHE_HOME/migraciones/), por la misma orden de la puerta
     (`lib/escribir.py aplicar-campana`); se verifica (integridad, mismo número de libros, carpetas de libro intactas
     salvo en los pasos que las mueven, cada valor escrito leído de vuelta por la API) y se prueba el deshacer
     (la copia vuelve a la foto de antes, byte a byte);
  3. con --aplicar: la puerta (Calibre cerrado, candado, respaldo verificado), la misma orden sobre la base real, la
     misma verificación y, para deshacer, el respaldo en $RESPALDOS_DIR/biblioteca/migraciones/<paso>/ con su suma y un
     `deshacer.sh`. El registro de la campaña (plan, propuesta legible, resumen) queda en migraciones/<paso>_<fecha>/.
Uso: main.py P1            → plan + ensayo + deshacer probado (no toca la base real)
     main.py P1 --aplicar  → además la aplica en la base real
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(REPO.parent / "core"))
import env  # noqa: E402  (core/env.py)

ESCRIBIR = REPO / "lib" / "escribir.py"
sys.path.insert(0, str(REPO / "lib"))
import escribir  # noqa: E402  (la puerta)
LEER = AQUI / "leer_campos.py"
_PASO_ACTUAL = None
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "migraciones"


def _copia(origen: Path, destino: Path) -> Path:
    return escribir.copia_de_trabajo(origen, destino)   # la copia la hace la puerta (lib/escribir.py)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _paso(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, AQUI / "pasos" / f"{nombre.lower()}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _foto(db: Path) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    f = {"integridad": c.execute("pragma integrity_check").fetchone()[0],
         "libros": c.execute("select count(*) from books").fetchone()[0],
         "rutas": dict(c.execute("select id, path from books").fetchall())}
    c.close()
    return f


def _calibre_debug(*args, env_extra=None) -> subprocess.CompletedProcess:
    e = dict(os.environ, **(env_extra or {}))
    return subprocess.run(["calibre-debug", "-e", *map(str, args)], capture_output=True, text=True, env=e)


def _verificar(biblioteca: Path, plan: dict, antes: dict, mueve: bool, trabajo: Path) -> list[str]:
    errores = []
    despues = _foto(biblioteca / "metadata.db")
    if despues["integridad"] != "ok":
        errores.append(f"integridad: {despues['integridad']}")
    if despues["libros"] != antes["libros"]:
        errores.append(f"libros: {antes['libros']} → {despues['libros']}")
    movidas = [b for b, r in antes["rutas"].items() if despues["rutas"].get(b) != r]
    if movidas and not mueve:
        errores.append(f"{len(movidas)} carpetas de libro cambiaron en un paso que no las mueve (p. ej. {movidas[:5]})")
    extra = getattr(_PASO_ACTUAL, "verificar", None)
    if extra:
        errores += extra(biblioteca / "metadata.db")
    if plan.get("columnas_borrar"):
        c = sqlite3.connect(f"file:{biblioteca / 'metadata.db'}?mode=ro", uri=True)
        quedan = {r[0] for r in c.execute("select label from custom_columns")} & {x.lstrip("#") for x in plan["columnas_borrar"]}
        c.close()
        if quedan:
            errores.append(f"columnas que debían retirarse y siguen: {sorted(quedan)}")
    campos = plan.get("campos") or {}
    if campos:
        pedido = trabajo / "pedido.json"
        leido = trabajo / "leido.json"
        pedido.write_text(json.dumps({c: list(v) for c, v in campos.items()}), encoding="utf-8")
        r = _calibre_debug(LEER, biblioteca, pedido, leido)
        if r.returncode != 0:
            return errores + [f"lectura de vuelta: {r.stderr.strip()[-300:]}"]
        vuelta = json.loads(leido.read_text(encoding="utf-8"))
        for campo, valores in campos.items():
            for libro, esperado in valores.items():
                real = vuelta[campo].get(str(libro))
                if campo == "tags":
                    esperado = sorted(esperado or [])
                if real != esperado and not (esperado in (None, "", []) and real in (None, "", [])):
                    errores.append(f"{campo} del libro {libro}: se esperaba {esperado!r}, quedó {real!r}")
                    if len(errores) > 20:
                        return errores
    return errores


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paso")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args(argv)
    paso = _paso(a.paso)
    global _PASO_ACTUAL
    _PASO_ACTUAL = paso
    hoy = date.today().isoformat()
    real_bib = Path(env.BIBLIOTECA_DIR)
    trabajo = CACHE / a.paso
    if trabajo.exists():
        shutil.rmtree(trabajo)
    lectura = _copia(real_bib / "metadata.db", trabajo / "lectura" / "metadata.db")

    # 1. plan
    c = sqlite3.connect(f"file:{lectura}?mode=ro", uri=True)
    plan, resumen, propuesta = paso.plan(c)
    c.close()
    registro = AQUI / f"{a.paso}_{hoy}"
    registro.mkdir(exist_ok=True)
    (registro / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    (registro / "propuesta.tsv").write_text("\n".join("\t".join(map(str, f)) for f in propuesta) + "\n", encoding="utf-8")
    n_valores = sum(len(v) for v in (plan.get("campos") or {}).values())
    print(f"── {a.paso}: {resumen}")
    print(f"   {n_valores} valores · enumeraciones {list((plan.get('enum_despues') or {}))} · columnas que se retiran "
          f"{plan.get('columnas_borrar') or []}")
    mueve = bool(getattr(paso, "MUEVE_CARPETAS", False))

    # 2. ensayo sobre copia + deshacer probado
    ensayo_bib = trabajo / "ensayo"
    db_ensayo = _copia(real_bib / "metadata.db", ensayo_bib / "metadata.db")
    foto_antes = trabajo / "antes.db"
    shutil.copy2(db_ensayo, foto_antes)
    antes = _foto(db_ensayo)
    r = _calibre_debug(ESCRIBIR, "aplicar-campana", ensayo_bib, registro / "plan.json",
                       env_extra={"PUERTA_CALIBRE": "abierta", "PUERTA_BIBLIOTECA": str(ensayo_bib)})
    if r.returncode != 0:
        print(f"✗ ensayo: la orden falló\n{r.stdout[-800:]}\n{r.stderr[-1500:]}")
        return 1
    errores = _verificar(ensayo_bib, plan, antes, mueve, trabajo)
    if errores:
        print("✗ ensayo: la verificación falló; no se aplica\n  " + "\n  ".join(errores[:20]))
        return 1
    shutil.copy2(foto_antes, db_ensayo)
    if _sha(db_ensayo) != _sha(foto_antes):
        print("✗ ensayo: el deshacer no devolvió la base exacta")
        return 1
    print(f"✓ ensayo: verificación sin errores y deshacer probado ({r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''})")
    resumen_md = [f"# {a.paso} — {hoy}", "", f"- {resumen}", f"- valores: {n_valores}",
                  f"- enumeraciones: {', '.join(plan.get('enum_despues') or {}) or '—'}",
                  f"- columnas que se retiran: {', '.join(plan.get('columnas_borrar') or []) or '—'}",
                  "- ensayo sobre copia: verificación sin errores; deshacer probado (la copia volvió byte a byte)"]
    if not a.aplicar:
        (registro / "resumen.md").write_text("\n".join(resumen_md) + "\n", encoding="utf-8")
        print("· simulación: la base real no se tocó; --aplicar la aplica")
        return 0

    # 3. aplicar en la base real, por la puerta
    destino = Path(env.RESPALDOS_DIR) / "biblioteca" / "migraciones" / f"{a.paso}_{hoy}"
    destino.mkdir(parents=True, exist_ok=True)
    with escribir.puerta("migraciones", calibre=real_bib):
        respaldo = _copia(real_bib / "metadata.db", destino / "metadata.db")
        (destino / "SHA256SUMS").write_text(f"{_sha(respaldo)}  metadata.db\n", encoding="utf-8")
        antes = _foto(real_bib / "metadata.db")
        r = _calibre_debug(ESCRIBIR, "aplicar-campana", real_bib, registro / "plan.json")
        if r.returncode != 0:
            print(f"✗ aplicar: la orden falló; restaura con {destino}/deshacer.sh\n{r.stderr[-1500:]}")
            return 1
        errores = _verificar(real_bib, plan, antes, mueve, trabajo)
    deshacer = destino / "deshacer.sh"
    deshacer.write_text(f"""#!/usr/bin/env bash
# deshacer.sh — devuelve metadata.db a la foto de antes de {a.paso} ({hoy}). Calibre cerrado.
set -euo pipefail
cd "$(dirname "$0")"
sha256sum -c SHA256SUMS
source "{REPO.parent}/core/shell-lib/lock.sh"; source "{REPO.parent}/core/shell-lib/detectar_apps.sh"
calibre_abierto && {{ echo "Cierra Calibre primero." >&2; exit 1; }}
tomar_lock_calibre
cp metadata.db "{real_bib}/metadata.db"
echo "metadata.db restaurada a antes de {a.paso}"
""", encoding="utf-8")
    deshacer.chmod(0o755)
    if errores:
        print("✗ aplicar: la verificación falló; ejecuta " + str(deshacer) + "\n  " + "\n  ".join(errores[:20]))
        return 1
    resumen_md += [f"- aplicada en la base real el {hoy}: verificación sin errores",
                   f"- respaldo y deshacer: `$RESPALDOS_DIR/biblioteca/migraciones/{a.paso}_{hoy}/`"]
    (registro / "resumen.md").write_text("\n".join(resumen_md) + "\n", encoding="utf-8")
    print(f"✓ aplicada y verificada; deshacer: {deshacer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
