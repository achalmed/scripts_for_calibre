#!/usr/bin/env python3
"""lib/adjuntos_zotero.py — lo que una campaña sobre la biblioteca escribe en Zotero, en un solo sitio (ola 2a, K4).

Sustituye a los diez `aplicar_zotero.py` de las campañas de 2026-09-30 y 2026-10-01 (nueve idénticos):
cuando Calibre mueve la carpeta o el archivo de un libro (al cambiar autor o título), Zotero debe
reescribir en la misma operación la ruta de su adjunto enlazado, o el PDF queda huérfano (RQ-BIB-03).

Uso (simula por defecto; `--aplicar` escribe con Zotero cerrado, LOCK_ZOTERO y respaldo verificado de
zotero.sqlite, por la puerta lib/escribir.py):
    adjuntos_zotero.py rutas   HECHOS.tsv    [--aplicar] [--salida DIR]   libro<TAB>ruta vieja<TAB>ruta nueva
    adjuntos_zotero.py titulos PROPUESTA.tsv [--aplicar] [--salida DIR]   libro<TAB>título viejo<TAB>nuevo[<TAB>…]
    adjuntos_zotero.py autores AUTORES.tsv   [--aplicar] [--salida DIR]   libro<TAB>autores viejos<TAB>nuevos (« & »)
    adjuntos_zotero.py verificar [--rutas HECHOS.tsv]                     adjuntos `attachments:` que no resuelven
Opciones comunes: --zotero DB (ZOTERO_DB de core/env), --biblioteca DIR (BIBLIOTECA_DIR de core/env).

- rutas: `attachments:<vieja>` → `attachments:<nueva>` (relativas a la biblioteca = baseAttachmentPath);
  tras aplicar, cada ruta nueva debe resolver: si alguna no, sale 1.
- titulos: el título del ítem enlazado (#zotero_key) pasa al nuevo solo si era el viejo.
- autores: los creadores primarios se rehacen con la grafía nueva solo si eran el espejo de la vieja
  (mismas palabras); «Nombre, Apellidos» → firstName/lastName; sin coma → campo único.
Escribe <salida>/zotero.tsv con lo hecho (y lo que un deshacer necesita). Salida 0 · 1 fallo · 75 candado.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path

LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB.parent.parent / "core"))
import escribir  # noqa: E402  (la puerta)


def _env():
    import env  # core/env.py: rutas reales salvo que el entorno las cambie
    return env


def _ro(ruta) -> sqlite3.Connection:
    return sqlite3.connect(Path(ruta).resolve().as_uri() + "?mode=ro", uri=True)


def _palabras(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {t for t in "".join(ch if ch.isalnum() else " " for ch in s).split() if len(t) > 1}


def _persona(nombre):
    a = nombre.replace("|", ",").strip()
    if "," in a:
        fn, ln = [x.strip() for x in a.split(",", 1)]
        return (fn, ln, 0)
    return ("", a, 1)


def _filas(tsv, minimo):
    for linea in open(tsv, encoding="utf-8"):
        if not linea.strip() or linea.startswith("#"):
            continue
        partes = linea.rstrip("\n").split("\t")
        if len(partes) < minimo:
            raise SystemExit(f"✗ {tsv}: fila con menos de {minimo} columnas: {linea.strip()[:80]}")
        yield partes


def _claves(biblioteca):
    """{libro: clave de Zotero} desde #zotero_key (por etiqueta), en solo lectura."""
    c = _ro(Path(biblioteca) / "metadata.db")
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    claves = {b: (k or "").strip() for b, k in c.execute(f"select book, value from custom_column_{col}")}
    c.close()
    return claves


def rotos(zotero, biblioteca, solo: set[str] | None = None) -> list[str]:
    """Rutas `attachments:` (relativas a la biblioteca) que no resuelven; con `solo`, entre esas."""
    z = _ro(zotero)
    rutas = [p for (p,) in z.execute("select path from itemAttachments where path like 'attachments:%'")]
    z.close()
    base = Path(biblioteca)
    fuera = []
    for p in rutas:
        rel = p[len("attachments:"):]
        if solo is not None and rel not in solo:
            continue
        if not (base / rel).exists():
            fuera.append(rel)
    return fuera


def _rutas(cur, tsv, out, aplicar):
    n = 0
    for libro, viejo, nuevo, *_ in _filas(tsv, 3):
        if aplicar:
            k = escribir.z_rewrite_attachment_paths(cur, f"attachments:{viejo}", f"attachments:{nuevo}")
        else:
            k = cur.execute("select count(*) from itemAttachments where path = ?", (f"attachments:{viejo}",)).fetchone()[0]
        if k:
            n += k
            out.write(f"ruta\t{libro}\t{viejo}\t{nuevo}\t{k}\n")
    return {"rutas de adjunto": n}


def _item(cur, claves, libro):
    key = claves.get(int(libro))
    r = key and cur.execute("select itemID from items where key = ?", (key,)).fetchone()
    return (key, r[0]) if r else (key, None)


def _titulos(cur, tsv, out, aplicar, claves):
    hechos = omitidos = 0
    for libro, viejo, nuevo, *_ in _filas(tsv, 3):
        key, item = _item(cur, claves, libro)
        if item is None:
            continue
        actual = escribir.z_get_field(cur, item, "title")
        if actual != viejo:
            omitidos += 1
            out.write(f"omitido\t{libro}\t{key}\tZotero tenía «{actual}»\n")
            continue
        if aplicar:
            escribir.z_set_field(cur, item, "title", nuevo)
        hechos += 1
        out.write(f"titulo\t{libro}\t{key}\t{viejo}\t{nuevo}\n")
    return {"títulos": hechos, "omitidos": omitidos}


def _autores(cur, tsv, out, aplicar, claves):
    hechos = omitidos = 0
    for libro, viejos, nuevos, *_ in _filas(tsv, 3):
        key, item = _item(cur, claves, libro)
        if item is None:
            continue
        actuales = cur.execute(
            "select c.firstName, c.lastName, ic.creatorTypeID from itemCreators ic join creators c"
            " on c.creatorID = ic.creatorID where ic.itemID = ? order by ic.orderIndex", (item,)).fetchall()
        if not actuales:
            continue
        tipo = actuales[0][2]
        primarios = [a for a in actuales if a[2] == tipo]
        espejo = set().union(*(_palabras(f"{fn} {ln}") for fn, ln, _ in primarios))
        if espejo != _palabras(viejos.replace("&", " ")):
            omitidos += 1
            out.write(f"omitido\t{libro}\t{key}\tZotero no era espejo de Calibre\n")
            continue
        antes = " ; ".join(f"{ln}, {fn}" for fn, ln, _ in primarios)
        if aplicar:
            escribir.z_set_creators(cur, item, [_persona(a) for a in nuevos.split(" & ")], tipo)
        hechos += 1
        out.write(f"creadores\t{libro}\t{key}\t{antes}\t{nuevos}\n")
    return {"ítems con creadores rehechos": hechos, "omitidos": omitidos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="adjuntos_zotero.py", description=__doc__.split("\n")[0])
    ap.add_argument("orden", choices=["rutas", "titulos", "autores", "verificar"])
    ap.add_argument("tsv", nargs="?")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--salida")
    ap.add_argument("--rutas", dest="solo_rutas")
    ap.add_argument("--zotero")
    ap.add_argument("--biblioteca")
    a = ap.parse_args(argv)
    env = _env()
    zotero = Path(a.zotero or env.ZOTERO_DB)
    biblioteca = Path(a.biblioteca or env.BIBLIOTECA_DIR)

    if a.orden == "verificar":
        solo = {nuevo for _, _, nuevo, *_ in _filas(a.solo_rutas, 3)} if a.solo_rutas else None
        fuera = rotos(zotero, biblioteca, solo)
        for r in fuera[:50]:
            print(f"  roto: {r}")
        print(f"── {len(fuera)} adjuntos `attachments:` que no resuelven en {biblioteca}"
              + (" (entre las rutas nuevas)" if solo is not None else ""))
        return 1 if fuera else 0

    if not a.tsv:
        ap.error(f"{a.orden} necesita su TSV")
    salida = Path(a.salida or Path(a.tsv).resolve().parent)
    salida.mkdir(parents=True, exist_ok=True)
    claves = _claves(biblioteca) if a.orden != "rutas" else {}

    def hacer(con):
        cur = con.cursor()
        with open(salida / "zotero.tsv", "w", encoding="utf-8") as out:
            if a.orden == "rutas":
                return _rutas(cur, a.tsv, out, a.aplicar)
            if a.orden == "titulos":
                return _titulos(cur, a.tsv, out, a.aplicar, claves)
            return _autores(cur, a.tsv, out, a.aplicar, claves)

    if not a.aplicar:
        con = _ro(zotero)
        cuentas = hacer(con)
        con.close()
        print("── SIMULACIÓN (nada escrito): " + " · ".join(f"{v} {k}" for k, v in cuentas.items())
              + f"; detalle en {salida / 'zotero.tsv'}")
        return 0

    sys.path.insert(0, str(LIB.parent.parent / "core" / "py-common"))
    from candado import Ocupado  # noqa: E402
    try:
        with escribir.puerta("adjuntos_zotero", zotero=zotero):
            con = escribir.conexion_zotero(zotero)
            cuentas = hacer(con)
            con.commit()
            con.close()
    except Ocupado as e:
        print(f"· {e} (salida 75)", file=sys.stderr)
        return 75
    except escribir.PuertaCerrada as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    bien = escribir.integridad(zotero)
    print("── " + " · ".join(f"{v} {k}" for k, v in cuentas.items())
          + f" · integridad {'ok' if bien else 'FALLIDA'}; detalle en {salida / 'zotero.tsv'}")
    if a.orden == "rutas":
        fuera = rotos(zotero, biblioteca, {nuevo for _, _, nuevo, *_ in _filas(a.tsv, 3)})
        if fuera:
            print(f"✗ {len(fuera)} rutas nuevas no resuelven: {fuera[:5]}", file=sys.stderr)
            return 1
        print("── 0 rutas nuevas rotas")
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
