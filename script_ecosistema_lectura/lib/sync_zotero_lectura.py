#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/sync_zotero_lectura.py — Fase 2: Read Time de Zotero → Calibre.

Se ejecuta con:  calibre-debug -e sync_zotero_lectura.py  (lo orquesta main.sh)

Fuente (verificada por inspección, ver ../diseno.md): el plugin Ethereal Style
guarda registros de lectura como notas hijas de un ítem "Addon Item" en
zotero.sqlite. Cada nota:

    <div class="zotero-note znv1">ITEMKEY
    {"readingTime":{"page":N,"data":{"<página>":segundos}}}</div>

ITEMKEY == columna #zotero_key de Calibre (puente de script_sincronizar_zotero).
Este script SOLO LEE zotero.sqlite (modo ro; seguro con Zotero abierto) y
escribe en Calibre: #zot_tiempo (minutos, techo) y #zot_ultima (fecha de la
nota). El tiempo NUNCA se copia entre relojes: #tiempo_estudio (composite)
agrega #ko_tiempo + #zot_tiempo, sin posibilidad de doble conteo.
"""

import os
import re
import csv
import json
import math
import sqlite3
from datetime import datetime, timezone

BIBLIOTECA = os.environ.get("QEL_BIBLIOTECA", "")
ZOTERO_DB = os.environ.get("QEL_ZOTERO_DB", "")
APLICAR = os.environ.get("QEL_APLICAR", "0") == "1"
REPORTE = os.environ.get("QEL_REPORTE", "/tmp/ecosistema_lectura_reporte.tsv")

COL_ZKEY = "#" + os.environ.get("QEL_COL_ZKEY", "zotero_key")
COL_ZTIEMPO = "#" + os.environ.get("QEL_COL_ZTIEMPO", "zot_tiempo")
COL_ZULTIMA = "#" + os.environ.get("QEL_COL_ZULTIMA", "zot_ultima")
COL_ZPROG = "#" + os.environ.get("QEL_COL_ZPROG", "zot_progreso")

RE_KEY = re.compile(r'znv1"[^>]*>\s*([A-Z0-9]{8})')


def leer_registros_zotero(ruta_db):
    """{itemkey: {"seg", "fecha", "paginas"}} desde las notas readingTime."""
    registros = {}
    con = sqlite3.connect("file:%s?mode=ro" % ruta_db, uri=True)
    try:
        filas = con.execute(
            "SELECT n.note, i.dateModified FROM itemNotes n "
            "JOIN items i ON i.itemID = n.itemID "
            "WHERE n.note LIKE '%\"readingTime\"%'"
        ).fetchall()
    finally:
        con.close()

    for note, date_mod in filas:
        m = RE_KEY.search(note)
        if not m:
            continue
        key = m.group(1)
        ini, fin = note.find("{"), note.rfind("}")
        if ini < 0 or fin <= ini:
            continue
        try:
            rt = json.loads(note[ini:fin + 1]).get("readingTime", {})
            data = rt.get("data", {})
            seg = sum(int(v) for v in data.values())
            paginas = int(rt.get("page") or 0)
        except (ValueError, TypeError):
            continue
        try:
            fecha = datetime.strptime(date_mod, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            fecha = None
        # Si hubiera más de una nota por ítem, gana la más reciente (snapshot).
        previo = registros.get(key)
        if previo is None or (fecha and previo["fecha"] and fecha > previo["fecha"]):
            registros[key] = {"seg": seg, "fecha": fecha, "paginas": paginas}
    return registros


def leer_progresos_zotero(ruta_db):
    """{itemkey_padre: última página (índice 0-based, máx entre adjuntos)}
    desde syncedSettings.lastPageIndex_u_<ATTACHKEY> (el lector de Zotero)."""
    progresos = {}
    con = sqlite3.connect("file:%s?mode=ro" % ruta_db, uri=True)
    try:
        filas = con.execute(
            "SELECT ip.key, ss.value FROM syncedSettings ss "
            "JOIN items ia ON ia.key = substr(ss.setting, 17) AND ia.libraryID = ss.libraryID "
            "JOIN itemAttachments att ON att.itemID = ia.itemID "
            "JOIN items ip ON ip.itemID = att.parentItemID "
            "WHERE ss.setting LIKE 'lastPageIndex_u_%'"
        ).fetchall()
    finally:
        con.close()
    for key, valor in filas:
        try:
            pagina = int(json.loads(valor)) if isinstance(valor, str) else int(valor)
        except (ValueError, TypeError):
            continue  # EPUB u otro localizador no numérico: no inventar
        if pagina >= 0 and pagina > progresos.get(key, -1):
            progresos[key] = pagina
    return progresos


def dt_vacio(v):
    return v is None or (hasattr(v, "year") and v.year < 1900)


def main():
    from calibre.library import db as calibre_db

    api = calibre_db(BIBLIOTECA).new_api
    ids = sorted(api.all_book_ids())
    registros = leer_registros_zotero(ZOTERO_DB)
    progresos = leer_progresos_zotero(ZOTERO_DB)

    def actuales(campo):
        try:
            return api.all_field_for(campo, ids)
        except Exception:
            return {i: api.field_for(campo, i) for i in ids}

    zkeys = actuales(COL_ZKEY)
    act_tiempo = actuales(COL_ZTIEMPO)
    act_ultima = actuales(COL_ZULTIMA)
    act_prog = actuales(COL_ZPROG)

    upd_tiempo, upd_ultima, upd_prog, filas_reporte = {}, {}, {}, []
    enlazados = 0

    for bid in ids:
        key = zkeys.get(bid)
        if not key:
            continue
        key = re.sub(r"<[^>]+>", "", str(key)).strip().upper()
        reg = registros.get(key)
        if not reg:
            continue
        enlazados += 1
        minutos = math.ceil(reg["seg"] / 60.0) if reg["seg"] > 0 else 0
        cambios = []
        if act_tiempo.get(bid) != minutos:
            upd_tiempo[bid] = minutos
            cambios.append("ZTIEMPO")
        f = reg["fecha"]
        actual_f = act_ultima.get(bid)
        if f is not None and (dt_vacio(actual_f) or abs(actual_f.timestamp() - f.timestamp()) > 60):
            upd_ultima[bid] = f
            cambios.append("ZULTIMA")
        # Fase 2b: progreso = (última página + 1) / páginas totales del registro
        pct = None
        ultima_pag = progresos.get(key)
        if ultima_pag is not None and reg["paginas"] > 0:
            pct = round(min(1.0, (ultima_pag + 1) / float(reg["paginas"])), 4)
            actual_p = act_prog.get(bid)
            if actual_p is None or abs(float(actual_p) - pct) > 0.005:
                upd_prog[bid] = pct
                cambios.append("ZPROGRESO")
        if cambios:
            filas_reporte.append({
                "id": bid,
                "titulo": api.field_for("title", bid),
                "zotero_key": key,
                "seg": reg["seg"],
                "min": minutos,
                "pct": "" if pct is None else "%.0f%%" % (pct * 100),
                "ultima": "" if f is None else f.astimezone().strftime("%Y-%m-%d %H:%M"),
                "campos": ",".join(cambios),
            })

    filas_reporte.sort(key=lambda r: r["seg"], reverse=True)
    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)
    with open(REPORTE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "titulo", "zotero_key", "seg", "min", "pct", "ultima", "campos"], delimiter="\t")
        w.writeheader()
        w.writerows(filas_reporte)

    if APLICAR:
        if upd_tiempo:
            api.set_field(COL_ZTIEMPO, upd_tiempo)
        if upd_ultima:
            api.set_field(COL_ZULTIMA, upd_ultima)
        if upd_prog:
            api.set_field(COL_ZPROG, upd_prog)

    modo = "APLICADO" if APLICAR else "SIMULACIÓN (nada escrito)"
    print("── Zotero (Ethereal Style) → Calibre ─────────────────────")
    print("  Modo                   : %s" % modo)
    print("  Registros readingTime  : %d" % len(registros))
    print("  Con progreso de lector : %d (lastPageIndex)" % len(progresos))
    print("  Con libro en Calibre   : %d (vía #zotero_key)" % enlazados)
    print("  Libros a actualizar    : %d" % len(filas_reporte))
    print("  Reporte TSV            : %s" % REPORTE)
    if filas_reporte:
        print()
        print("  %-5s %-40s %8s %6s %6s  %s" % ("id", "título", "seg", "min", "pct", "última"))
        for r in filas_reporte[:20]:
            print("  %-5s %-40s %8s %6s %6s  %s" % (
                r["id"], str(r["titulo"])[:40], r["seg"], r["min"], r["pct"], r["ultima"]))
        if len(filas_reporte) > 20:
            print("  … y %d más (ver reporte TSV)." % (len(filas_reporte) - 20))


if __name__ == "__main__":
    if not (BIBLIOTECA and ZOTERO_DB):
        raise SystemExit("✗ Faltan QEL_BIBLIOTECA / QEL_ZOTERO_DB en el entorno.")
    main()
