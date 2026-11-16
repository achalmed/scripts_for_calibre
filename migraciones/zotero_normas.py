#!/usr/bin/env python3
"""migraciones/zotero_normas.py — ZOTERO-NORMAS (2026-11-15): las normas de Zotero con el número, el código y el título
corto que les puso mal el RIS viejo.

Objetivo: hasta el 2026-11-15, `biblioteca.ris` escribía en un `statute` la serie de Calibre como su código (`code`) y el
  índice de la serie como el número de la ley (`publicLawNumber`): la Ley 32069 tenía por número «1» y por código «Marco
  legal 05 - Contrataciones». El RIS ya está corregido en core (`tests/test_ris_norma.py`); esta campaña arregla las
  normas que ya están en Zotero.
Método: lee una copia de `zotero.sqlite` (solo lectura) y la biblioteca de Calibre por `#zotero_key`; por cada norma
  viva propone el número de la ley (el del identificador `norma:` de Calibre o, sin él, el «N.° …» del título), quita el
  código si es la serie de Calibre y pone el título corto («Ley N.° 27506») si falta. Lo ensaya sobre otra copia:
  aplica, lee de vuelta cada valor, deshace y comprueba que todo vuelve a ser como antes. Solo con `--aplicar` lo
  escribe en la base real por la puerta (Zotero cerrado, candado y respaldo verificado: `lib/escribir.py`), marca cada
  ítem como no sincronizado (zotero.org recibe el cambio) y deja el deshacer en `$RESPALDOS_DIR`.
Límite: la fecha de la norma no se toca (Calibre y Zotero guardan casi siempre solo el año o el de la edición; la fecha
  exacta se trae aparte desde el archivo del Congreso). Las que no tienen número («Constitución Política…», una NIC, un
  informe) se listan para revisarlas a mano. Título, autores, citationKey y adjuntos no cambian.

    python3 migraciones/zotero_normas.py                 # simula: plan, ensayo y deshacer probado
    python3 migraciones/zotero_normas.py --aplicar       # además lo escribe por la puerta
    python3 migraciones/zotero_normas.py --deshacer <deshacer.json>   # vuelve atrás lo aplicado (por la puerta)
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))
import escribir as E  # noqa: E402
import escribir_zotero as Z  # noqa: E402

sys.path.insert(0, str(E.CORE / "py-common"))
sys.path.insert(0, str(E.CORE))
import biblioteca as bib  # noqa: E402
import env  # noqa: E402  (core/env.py: ZOTERO_DB)

CAMPANA = "zotero-normas"
CAMPOS = ("publicLawNumber", "code", "shortTitle")
NUMERO_EN_TITULO = re.compile(r"N\.° ([\w-]+)")
TITULO_CORTO = re.compile(r"^(.+?N\.° [\w-]+)\.\s")


# ------------------------------------------------------------------ leer
def leer_normas(ruta) -> list[dict]:
    """Las normas vivas de un zotero.sqlite (solo lectura): itemID, key, título y los campos que la campaña mira."""
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        filas = c.execute("""
            SELECT i.itemID, i.key, f.fieldName, v.value
            FROM items i JOIN itemTypes t ON t.itemTypeID = i.itemTypeID
            LEFT JOIN itemData d ON d.itemID = i.itemID LEFT JOIN fields f ON f.fieldID = d.fieldID
            LEFT JOIN itemDataValues v ON v.valueID = d.valueID
            WHERE t.typeName = 'statute' AND i.itemID NOT IN (SELECT itemID FROM deletedItems)""").fetchall()
    finally:
        c.close()
    normas: dict[int, dict] = {}
    for item_id, key, campo, valor in filas:
        n = normas.setdefault(item_id, {"itemID": item_id, "key": key, "titulo": "", **{k: "" for k in CAMPOS}})
        if campo in ("nameOfAct", "title") and valor and not n["titulo"]:
            n["titulo"] = valor
        elif campo in CAMPOS:
            n[campo] = valor or ""
    return sorted(normas.values(), key=lambda n: n["key"])


def calibre_por_clave() -> dict[str, dict]:
    """{zotero_key: datos del libro de Calibre} (solo lectura)."""
    with bib.conn() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM books")]
    salida = {}
    for bid in ids:
        d = bib.datos(bid)
        if d and d.get("zotero_key"):
            salida[d["zotero_key"]] = d
    return salida


# ------------------------------------------------------------------ el plan (puro)
def numero_de(norma: dict, libro: dict | None) -> str:
    clave = ((libro or {}).get("identificadores") or {}).get("norma") or ""
    if clave:
        return clave.rsplit("_", 1)[-1].upper()
    m = NUMERO_EN_TITULO.search(norma.get("titulo") or "")
    return m.group(1).upper() if m else ""


def es_serie(codigo: str, libro: dict | None) -> bool:
    """¿El código es la serie de Calibre (lo que puso el RIS viejo) y no un código de verdad?"""
    serie = (libro or {}).get("serie") or ""
    return bool(codigo) and (codigo == serie or codigo.startswith("Marco legal"))


def plan(normas: list[dict], libros: dict[str, dict]) -> dict:
    """{cambios: [{itemID, key, titulo, campos: {campo: [antes, después]}}], revisar: [...], sin_cambio: n}. Pura.
    Un «después» vacío quita el campo."""
    cambios, revisar, iguales = [], [], 0
    for n in normas:
        libro = libros.get(n["key"])
        numero = numero_de(n, libro)
        if not numero:
            revisar.append({"key": n["key"], "titulo": n["titulo"], "motivo": "sin número de norma"})
            continue
        campos = {}
        if n["publicLawNumber"] != numero:
            campos["publicLawNumber"] = [n["publicLawNumber"], numero]
        if es_serie(n["code"], libro):
            campos["code"] = [n["code"], ""]
        m = TITULO_CORTO.match(n["titulo"] or "")
        if m and not n["shortTitle"]:
            campos["shortTitle"] = ["", m.group(1)]
        if campos:
            cambios.append({"itemID": n["itemID"], "key": n["key"], "titulo": n["titulo"],
                            "calibre_id": (libro or {}).get("calibre_id", ""), "campos": campos})
        else:
            iguales += 1
    return {"campana": CAMPANA, "fecha": date.today().isoformat(), "cambios": cambios, "revisar": revisar, "sin_cambio": iguales}


# ------------------------------------------------------------------ escribir (por la puerta)
def aplicar(cur, p: dict, sentido: int = 1) -> int:
    """Escribe el plan (sentido 1) o lo deshace (-1) con las primitivas de la puerta. Devuelve cuántos campos tocó."""
    n = 0
    for c in p["cambios"]:
        for campo, (antes, despues) in c["campos"].items():
            valor = despues if sentido == 1 else antes
            if valor:
                Z.z_set_field(cur, c["itemID"], campo, valor)
            else:
                Z.z_del_field(cur, c["itemID"], campo)
            n += 1
    return n


def verificar(ruta, p: dict, sentido: int = 1) -> list[str]:
    """Lee de vuelta cada campo; devuelve las diferencias (vacía si todo quedó como debía)."""
    actuales = {n["itemID"]: n for n in leer_normas(ruta)}
    mal = []
    for c in p["cambios"]:
        for campo, (antes, despues) in c["campos"].items():
            esperado = despues if sentido == 1 else antes
            leido = actuales.get(c["itemID"], {}).get(campo, "")
            if leido != esperado:
                mal.append(f"{c['key']} {campo}: se esperaba «{esperado}», quedó «{leido}»")
    return mal


@contextlib.contextmanager
def _puerta_de_copia(ruta):
    """La puerta abierta solo para una COPIA de trabajo (el ensayo): nunca para la base real."""
    if os.path.realpath(ruta) == os.path.realpath(env.ZOTERO_DB):
        raise E.PuertaCerrada("el ensayo no se hace sobre la base real")
    antes = {k: os.environ.get(k) for k in ("PUERTA_ZOTERO", "PUERTA_ZOTERO_DB")}
    os.environ.update(PUERTA_ZOTERO=E.ABIERTA, PUERTA_ZOTERO_DB=str(ruta))
    try:
        yield
    finally:
        for k, v in antes.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def ensayar(copia, p: dict) -> list[str]:
    """Aplica sobre la copia, verifica, deshace y verifica de nuevo. Devuelve los problemas."""
    with _puerta_de_copia(copia):
        con = Z.conexion_zotero(copia)
        with con:
            aplicar(con.cursor(), p, 1)
        problemas = verificar(copia, p, 1)
        with con:
            aplicar(con.cursor(), p, -1)
        con.close()
    return problemas + [f"deshacer: {x}" for x in verificar(copia, p, -1)]


# ------------------------------------------------------------------ registro
def registrar(p: dict, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "plan.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(carpeta / "propuesta.tsv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["zotero_key", "calibre_id", "titulo", "campo", "antes", "despues"])
        for c in p["cambios"]:
            for campo, (antes, despues) in c["campos"].items():
                w.writerow([c["key"], c["calibre_id"], c["titulo"][:120], campo, antes, despues or "(se quita)"])
        for r in p["revisar"]:
            w.writerow([r["key"], "", r["titulo"][:120], "(revisar a mano)", "", r["motivo"]])
    cuenta = {k: sum(k in c["campos"] for c in p["cambios"]) for k in CAMPOS}
    (carpeta / "resumen.md").write_text(
        "---\ntipo: informe\nestado: activo\n---\n"
        f"# {carpeta.name}/ — la campaña ZOTERO-NORMAS (número, código y título corto de las normas)\n\n"
        f"- Normas con cambios: {len(p['cambios'])}; sin cambio: {p['sin_cambio']}; a revisar a mano: {len(p['revisar'])}.\n"
        f"- Número de la ley puesto: {cuenta['publicLawNumber']}; código (la serie de Calibre) quitado: {cuenta['code']}; "
        f"título corto puesto: {cuenta['shortTitle']}.\n- La fecha no se toca (`migraciones/zotero_normas.py`, Límite).\n",
        encoding="utf-8")


def resumen(p: dict) -> str:
    cuenta = {k: sum(k in c["campos"] for c in p["cambios"]) for k in CAMPOS}
    lineas = [f"normas con cambios: {len(p['cambios'])} · sin cambio: {p['sin_cambio']} · a revisar a mano: {len(p['revisar'])}",
              f"  número de la ley: {cuenta['publicLawNumber']} · código (serie) quitado: {cuenta['code']} · título corto: {cuenta['shortTitle']}"]
    lineas += [f"  revisar: {r['key']} {r['titulo'][:80]}" for r in p["revisar"]]
    return "\n".join(lineas)


# ------------------------------------------------------------------ principal
def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("--aplicar", action="store_true", help="escribir en la base real por la puerta")
    a.add_argument("--deshacer", metavar="JSON", help="volver atrás una aplicación (el deshacer.json que dejó)")
    args = a.parse_args(argv)
    real = Path(env.ZOTERO_DB)
    trabajo = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "migraciones" / CAMPANA

    if args.deshacer:
        p = json.loads(Path(args.deshacer).read_text(encoding="utf-8"))
        with E.puerta("migraciones", zotero=real):
            con = Z.conexion_zotero(real)
            with con:
                n = aplicar(con.cursor(), p, -1)
            con.close()
        mal = verificar(real, p, -1)
        print(f"deshecho: {n} campos" + ("" if not mal else "\n" + "\n".join(mal)))
        return 1 if mal else 0

    copia = E.copia_de_trabajo(real, trabajo / "plan.sqlite")
    p = plan(leer_normas(copia), calibre_por_clave())
    registrar(p, REPO / "migraciones" / f"{CAMPANA}-{p['fecha']}")
    print(resumen(p))
    ensayo = E.copia_de_trabajo(real, trabajo / "ensayo.sqlite")
    problemas = ensayar(ensayo, p)
    if problemas:
        print("✗ el ensayo falló:\n" + "\n".join(problemas[:20]))
        return 1
    print(f"✓ ensayo sobre una copia: {sum(len(c['campos']) for c in p['cambios'])} campos escritos, leídos de vuelta y deshechos")
    if not args.aplicar:
        print("Simulación: la base real no se tocó (--aplicar para escribir por la puerta).")
        return 0
    try:
        with E.puerta("migraciones", zotero=real):
            # Lo que se deshace es lo que había en la base real al abrir la puerta (no en la copia del plan).
            p = plan(leer_normas(real), calibre_por_clave())
            deshacer = E.raiz_respaldos() / "migraciones" / "zotero" / f"{CAMPANA}-{date.today().isoformat()}-deshacer.json"
            deshacer.parent.mkdir(parents=True, exist_ok=True)
            deshacer.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
            con = Z.conexion_zotero(real)
            with con:
                n = aplicar(con.cursor(), p, 1)
            con.close()
    except E.PuertaCerrada as e:
        print(f"✗ {e}")
        return 75
    mal = verificar(real, p, 1)
    print(f"aplicado: {n} campos en {len(p['cambios'])} normas; deshacer: {deshacer}" + ("" if not mal else "\n" + "\n".join(mal)))
    return 1 if mal else 0


if __name__ == "__main__":
    raise SystemExit(main())
