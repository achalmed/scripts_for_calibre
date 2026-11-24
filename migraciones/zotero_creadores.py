#!/usr/bin/env python3
"""migraciones/zotero_creadores.py — ZOTERO-CREADORES (2026-11-23): instituciones que entraron a Zotero partidas en
nombre y apellido.

Objetivo: hasta el 2026-11-23, `biblioteca.es_corporativo` no reconocía a «Jurado Nacional de Elecciones» (ni a las
  municipalidades, «Library of Congress»…) y el RIS las mandaba como «De Elecciones, Jurado Nacional». La detección ya
  está corregida en core (`py-common/test_biblioteca.py`); esta campaña arregla los ítems que ya están en Zotero.
Método: lee una copia de `zotero.sqlite` (solo lectura) y los autores de Calibre; un creador de dos campos cuyo «nombre +
  apellido» es, palabra por palabra, un autor corporativo de Calibre del mismo libro (`#zotero_key`) pasa a un creador de
  un solo campo. Lo ensaya sobre otra copia: aplica, lee de vuelta, deshace y comprueba que todo vuelve a ser como antes.
  Solo con `--aplicar` y las claves elegidas (`--claves`) escribe en la base real por la puerta (Zotero cerrado, candado y
  respaldo verificado: `lib/escribir.py`), marca cada ítem como no sincronizado y deja el deshacer en `$RESPALDOS_DIR`.
Límite: la clave de cita (`citationKey`) no cambia aunque naciera del autor partido: puede estar citada y cambiarla la
  decide el autor. No toca los ítems sin libro en Calibre ni los corporativos con coma («Superintendencia de Banca,
  Seguros y AFP»), que no se partieron por esta causa.

    python3 migraciones/zotero_creadores.py                                      # simula todo lo que está partido
    python3 migraciones/zotero_creadores.py --claves DN4CTW9B,I5LEUR57           # simula esos ítems
    python3 migraciones/zotero_creadores.py --claves DN4CTW9B,I5LEUR57 --aplicar # además los escribe por la puerta
    python3 migraciones/zotero_creadores.py --deshacer <deshacer.json>           # vuelve atrás lo aplicado (por la puerta)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zotero_normas import E, REPO, Z, _puerta_de_copia, bib, env  # noqa: E402

CAMPANA = "zotero-creadores"


# ------------------------------------------------------------------ leer
def leer_items(ruta) -> list[dict]:
    """Los ítems vivos con creadores de un zotero.sqlite (solo lectura): itemID, key, título, citationKey y creadores
    [nombre, apellido, modo, creatorTypeID] en su orden."""
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        filas = c.execute("""
            SELECT i.itemID, i.key, cr.firstName, cr.lastName, cr.fieldMode, ic.creatorTypeID
            FROM items i JOIN itemCreators ic USING(itemID) JOIN creators cr USING(creatorID)
            WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems) ORDER BY i.itemID, ic.orderIndex""").fetchall()
        campos = c.execute("""
            SELECT d.itemID, f.fieldName, v.value FROM itemData d JOIN fields f USING(fieldID)
            JOIN itemDataValues v USING(valueID) WHERE f.fieldName IN ('title', 'nameOfAct', 'citationKey')""").fetchall()
    finally:
        c.close()
    items: dict[int, dict] = {}
    for item_id, key, nombre, apellido, modo, tipo in filas:
        n = items.setdefault(item_id, {"itemID": item_id, "key": key, "titulo": "", "citationKey": "", "creadores": []})
        n["creadores"].append([nombre or "", apellido or "", modo, tipo])
    for item_id, campo, valor in campos:
        if item_id in items:
            items[item_id]["citationKey" if campo == "citationKey" else "titulo"] = valor
    return sorted(items.values(), key=lambda n: n["key"])


def autores_por_clave() -> dict[str, dict]:
    """{zotero_key: {calibre_id, autores}} de los libros con algún autor corporativo (solo lectura)."""
    with bib.conn() as c:
        ids = [r[0] for r in c.execute("SELECT DISTINCT l.book, a.name FROM books_authors_link l JOIN authors a ON a.id = l.author")
               if bib.es_corporativo(r[1])]
    salida = {}
    for bid in sorted(set(ids)):
        d = bib.datos(bid)
        if d and d.get("zotero_key"):
            salida[d["zotero_key"]] = {"calibre_id": bid, "autores": d["autores"]}
    return salida


# ------------------------------------------------------------------ el plan (puro)
def entero(creador: list, autores: list[str]) -> str:
    """El autor corporativo de Calibre que este creador de dos campos parte, o «» si no parte ninguno."""
    nombre, apellido, modo = creador[:3]
    if modo != 0 or not nombre:
        return ""
    for a in autores:
        if "," not in a and bib.es_corporativo(a) and bib.norm(f"{nombre} {apellido}") == bib.norm(a):
            return a
    return ""


def plan(items: list[dict], libros: dict[str, dict], claves: set[str] | None = None) -> dict:
    """{cambios: [{itemID, key, titulo, citationKey, calibre_id, creadores: [antes, después]}], faltan: [claves pedidas
    sin nada que cambiar]}. Pura. El orden y el rol de cada creador se conservan."""
    cambios = []
    for n in items:
        libro = libros.get(n["key"])
        if not libro or (claves is not None and n["key"] not in claves):
            continue
        despues = []
        for c in n["creadores"]:
            a = entero(c, libro["autores"])
            despues.append(["", a, 1, c[3]] if a else c)
        if despues != n["creadores"]:
            cambios.append({"itemID": n["itemID"], "key": n["key"], "titulo": n["titulo"], "citationKey": n["citationKey"],
                            "calibre_id": libro["calibre_id"], "creadores": [n["creadores"], despues]})
    return {"_": "migraciones/zotero_creadores.py: el plan de una campaña ZOTERO-CREADORES (se genera; no se edita)",
            "campana": CAMPANA, "fecha": date.today().isoformat(), "cambios": cambios,
            "faltan": sorted((claves or set()) - {c["key"] for c in cambios})}


# ------------------------------------------------------------------ escribir (por la puerta)
def aplicar(cur, p: dict, sentido: int = 1) -> int:
    """Escribe el plan (sentido 1) o lo deshace (-1) con las primitivas de la puerta. Devuelve cuántos ítems tocó."""
    for c in p["cambios"]:
        antes, despues = c["creadores"] if sentido == 1 else reversed(c["creadores"])
        for tipo in dict.fromkeys(x[3] for x, y in zip(antes, despues) if x != y):
            for nombre, apellido, modo, t in despues:
                if t == tipo:
                    Z.z_creador(cur, nombre, apellido, modo)     # con sus columnas «…Normalized»
            Z.z_set_creators(cur, c["itemID"], [x[:3] for x in despues if x[3] == tipo], tipo)
    return len(p["cambios"])


def verificar(ruta, p: dict, sentido: int = 1) -> list[str]:
    """Lee de vuelta los creadores y la clave de cita; devuelve las diferencias (vacía si todo quedó como debía)."""
    actuales = {n["itemID"]: n for n in leer_items(ruta)}
    mal = []
    for c in p["cambios"]:
        esperado, n = c["creadores"][1 if sentido == 1 else 0], actuales.get(c["itemID"], {})
        if n.get("creadores") != esperado:
            mal.append(f"{c['key']}: se esperaba {esperado}, quedó {n.get('creadores')}")
        if n.get("citationKey") != c["citationKey"]:
            mal.append(f"{c['key']}: la clave de cita cambió de «{c['citationKey']}» a «{n.get('citationKey')}»")
    return mal


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
def _nombre(c: list) -> str:
    return f"{c[1]}, {c[0]}" if c[0] else c[1]


def resumen(p: dict) -> str:
    lineas = [f"ítems con una institución partida: {len(p['cambios'])}"]
    for c in p["cambios"]:
        lineas += [f"  {c['key']} (Calibre {c['calibre_id']}, {c['citationKey'] or 'sin clave'}): «{_nombre(x)}» → «{_nombre(y)}»"
                   for x, y in zip(*c["creadores"]) if x != y]
    return "\n".join(lineas + [f"  {k}: nada que cambiar" for k in p["faltan"]])


def registrar(p: dict, carpeta: Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "plan.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(carpeta / "propuesta.tsv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["zotero_key", "calibre_id", "clave_de_cita", "titulo", "antes", "despues"])
        for c in p["cambios"]:
            w.writerows([c["key"], c["calibre_id"], c["citationKey"], c["titulo"][:120], _nombre(x), _nombre(y)]
                        for x, y in zip(*c["creadores"]) if x != y)
    (carpeta / "resumen.md").write_text(
        "---\ntipo: informe\nestado: activo\n---\n"
        f"# {carpeta.name}/ — la campaña ZOTERO-CREADORES (instituciones partidas en nombre y apellido)\n\n"
        f"- Ítems corregidos a un creador de un solo campo: {len(p['cambios'])}.\n"
        "- Las claves de cita no cambian.\n", encoding="utf-8")


# ------------------------------------------------------------------ principal
def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("--claves", help="solo estos ítems (claves de Zotero separadas por comas); obligatorio con --aplicar")
    a.add_argument("--aplicar", action="store_true", help="escribir en la base real por la puerta")
    a.add_argument("--deshacer", metavar="JSON", help="volver atrás una aplicación (el deshacer.json que dejó)")
    args = a.parse_args(argv)
    claves = {x.strip() for x in args.claves.split(",") if x.strip()} if args.claves else None
    if args.aplicar and not claves:
        a.error("--aplicar pide --claves: cada ítem se elige")
    real = Path(env.ZOTERO_DB)
    trabajo = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "migraciones" / CAMPANA

    if args.deshacer:
        p = json.loads(Path(args.deshacer).read_text(encoding="utf-8"))
        try:
            with E.puerta("migraciones", zotero=real):
                con = Z.conexion_zotero(real)
                with con:
                    n = aplicar(con.cursor(), p, -1)
                con.close()
        except E.PuertaCerrada as e:
            print(f"✗ {e}")
            return 75
        mal = verificar(real, p, -1)
        print(f"deshecho: {n} ítems" + ("" if not mal else "\n" + "\n".join(mal)))
        return 1 if mal else 0

    copia = E.copia_de_trabajo(real, trabajo / "plan.sqlite")
    libros = autores_por_clave()
    p = plan(leer_items(copia), libros, claves)
    print(resumen(p))
    problemas = ensayar(E.copia_de_trabajo(real, trabajo / "ensayo.sqlite"), p)
    if problemas:
        print("✗ el ensayo falló:\n" + "\n".join(problemas[:20]))
        return 1
    print(f"✓ ensayo sobre una copia: {len(p['cambios'])} ítems escritos, leídos de vuelta y deshechos")
    if not args.aplicar:
        print("Simulación: la base real no se tocó (--claves … --aplicar para escribir por la puerta).")
        return 0
    if not p["cambios"]:
        return 0
    destino = REPO / "migraciones" / f"{CAMPANA}-{p['fecha']}"
    for letra in "bcdefgh":
        if not destino.exists():
            break
        destino = REPO / "migraciones" / f"{CAMPANA}-{p['fecha']}-{letra}"
    try:
        with E.puerta("migraciones", zotero=real):
            # Lo que se deshace es lo que había en la base real al abrir la puerta (no en la copia del plan).
            p = plan(leer_items(real), libros, claves)
            deshacer = E.raiz_respaldos() / "migraciones" / "zotero" / f"{destino.name}-deshacer.json"
            deshacer.parent.mkdir(parents=True, exist_ok=True)
            deshacer.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
            con = Z.conexion_zotero(real)
            with con:
                n = aplicar(con.cursor(), p, 1)
            con.close()
    except E.PuertaCerrada as e:
        print(f"✗ {e}")
        return 75
    registrar(p, destino)
    mal = verificar(real, p, 1)
    print(f"aplicado: {n} ítems; deshacer: {deshacer}" + ("" if not mal else "\n" + "\n".join(mal)))
    return 1 if mal else 0


if __name__ == "__main__":
    raise SystemExit(main())
