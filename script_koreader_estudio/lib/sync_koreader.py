#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/sync_koreader.py — Núcleo de la sincronización KOReader → Calibre.

Se ejecuta con:  calibre-debug -e sync_koreader.py   (lo orquesta main.sh)

Lee las DOS fuentes que KOReader ya genera:
  1. Sidecars `<libro>.sdr/metadata.<ext>.lua` (junto a cada archivo de la
     biblioteca): percent_finished, summary.status, summary.modified.
  2. `statistics.sqlite3` (tabla book + page_stat_data): tiempo total leído,
     primera/última sesión. El emparejamiento es por el MD5 parcial de KOReader
     (md5 de bloques de 1KB en offsets 0, 1024·4^i), verificado contra esta
     biblioteca.

Escribe (solo si cambió) en columnas existentes del plugin KOReader Sync
(#ko_*), en #leído/#read_date y en #ko_tiempo. Simulación por defecto:
solo escribe si QKO_APLICAR=1.
"""

import os
import re
import sys
import csv
import glob
import hashlib
import sqlite3
from datetime import datetime, timezone

# ── Configuración por entorno (la exporta main.sh desde config.sh) ──────────
BIBLIOTECA = os.environ.get("QKO_BIBLIOTECA", "")
KOREADER_CONFIG = os.environ.get("QKO_KOREADER_CONFIG", "")
HASH_DIR = os.path.join(KOREADER_CONFIG, "hashdocsettings") if KOREADER_CONFIG else ""
STATS_DB = os.environ.get("QKO_STATS_DB", "")
APLICAR = os.environ.get("QKO_APLICAR", "0") == "1"
REPORTE = os.environ.get("QKO_REPORTE", "/tmp/koreader_sync_reporte.tsv")
FORMATOS = set(os.environ.get("QKO_FORMATOS", "PDF EPUB DJVU MOBI AZW3 FB2 CBZ CBR").split())

C = {k: "#" + os.environ.get("QKO_COL_" + k, v) for k, v in {
    "MD5": "ko_md5", "PROGFLOAT": "ko_progfloat", "PROGINT": "ko_progint",
    "STATUS": "ko_status", "START": "ko_start", "FINISH": "ko_finish",
    "LASTMOD": "ko_lastmod", "LASTSYNC": "ko_lastsync", "TIEMPO": "ko_tiempo",
    "LEIDO": "leído", "READ_DATE": "read_date",
}.items()}

RE_PERCENT = re.compile(r'\["percent_finished"\]\s*=\s*([0-9.eE+-]+)')
RE_STATUS = re.compile(r'\["status"\]\s*=\s*"([^"]*)"')


def md5_parcial(ruta):
    """MD5 parcial de KOReader: bloques de 1KB en offsets 0 y 1024·4^i (i=0..10).
    Verificado contra statistics.sqlite3 de esta máquina."""
    m = hashlib.md5()
    try:
        with open(ruta, "rb") as f:
            for off in [0] + [1024 * (4 ** i) for i in range(0, 11)]:
                f.seek(off)
                bloque = f.read(1024)
                if not bloque:
                    break
                m.update(bloque)
        return m.hexdigest()
    except OSError:
        return None


def parsear_sidecar(candidato):
    try:
        with open(candidato, encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except OSError:
        return None
    out = {"mtime": os.path.getmtime(candidato)}
    m = RE_PERCENT.search(texto)
    if m:
        try:
            frac = float(m.group(1))
            out["frac"] = frac / 100.0 if frac > 1.0 else frac
        except ValueError:
            pass
    m = RE_STATUS.search(texto)
    if m:
        out["status"] = m.group(1).strip().lower()
    return out


def leer_sidecar(ruta_formato, md5=None):
    """Sidecar del archivo en cualquiera de sus dos ubicaciones — junto al
    libro (modo "doc") o central por hash (modo "hash", layout de
    docsettings.lua: hashdocsettings/<md5[0:2]>/<md5>.sdr). Si existen ambos,
    gana el de modificación más reciente."""
    base, ext = os.path.splitext(ruta_formato)
    nombre = "metadata." + ext.lstrip(".").lower() + ".lua"
    cands = []
    sdr_doc = base + ".sdr"
    doc_meta = os.path.join(sdr_doc, nombre)
    if os.path.isfile(doc_meta):
        cands.append(doc_meta)
    elif os.path.isdir(sdr_doc):
        lua = sorted(glob.glob(os.path.join(glob.escape(sdr_doc), "metadata.*.lua")))
        if lua:
            cands.append(lua[0])
    if md5 and HASH_DIR:
        hash_meta = os.path.join(HASH_DIR, md5[:2], md5 + ".sdr", nombre)
        if os.path.isfile(hash_meta):
            cands.append(hash_meta)
    if not cands:
        return None
    return parsear_sidecar(max(cands, key=os.path.getmtime))


def leer_stats(ruta_db):
    """statistics.sqlite3 → {md5: {...}} con tiempo total y sesiones."""
    stats = {}
    if not (ruta_db and os.path.isfile(ruta_db)):
        return stats
    con = sqlite3.connect("file:%s?mode=ro" % ruta_db, uri=True)
    try:
        libros = con.execute(
            "SELECT id, md5, total_read_time, total_read_pages, pages, last_open FROM book"
        ).fetchall()
        sesiones = dict(
            (r[0], (r[1], r[2]))
            for r in con.execute(
                "SELECT id_book, MIN(start_time), MAX(start_time + duration) FROM page_stat_data GROUP BY id_book"
            )
        )
        for id_book, md5, t_total, p_leidas, p_total, last_open in libros:
            ini, fin = sesiones.get(id_book, (None, None))
            stats[md5] = {
                "seg": t_total or 0,
                "pag_leidas": p_leidas or 0,
                "pag_total": p_total or 0,
                "last_open": last_open,
                "primera": ini,
                "ultima": fin or last_open,
            }
    finally:
        con.close()
    return stats


def ts_a_dt(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def dt_vacio(v):
    """Calibre usa una fecha centinela (~año 101) para 'sin fecha'."""
    return v is None or (hasattr(v, "year") and v.year < 1900)


def casi_igual(a, b):
    if a is None or b is None:
        return a == b
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return False
    if hasattr(a, "timestamp") and hasattr(b, "timestamp"):
        return abs(a.timestamp() - b.timestamp()) < 60
    return a == b


def main():
    from calibre.library import db as calibre_db

    api = calibre_db(BIBLIOTECA).new_api
    ids = sorted(api.all_book_ids())
    stats = leer_stats(STATS_DB)

    def actuales(campo):
        try:
            return api.all_field_for(campo, ids)
        except Exception:
            return {i: api.field_for(campo, i) for i in ids}

    act = {campo: actuales(nombre) for campo, nombre in C.items()}

    updates = {campo: {} for campo in C}      # campo → {book_id: valor}
    filas_reporte = []
    n_sidecar = n_stats = 0

    for bid in ids:
        rutas = []
        for fmt in (api.formats(bid) or ()):
            if fmt.upper() not in FORMATOS:
                continue
            ruta = api.format_abspath(bid, fmt)
            if ruta and os.path.exists(ruta):
                rutas.append(ruta)
        if not rutas:
            continue

        # MD5 parcial por formato: empareja con estadísticas Y localiza el
        # sidecar en la ubicación hash.
        md5s = {ruta: md5_parcial(ruta) for ruta in rutas}

        # Sidecar más reciente entre los formatos del libro (doc o hash)
        sc = None
        for ruta in rutas:
            s = leer_sidecar(ruta, md5s.get(ruta))
            if s and (sc is None or s["mtime"] > sc["mtime"]):
                sc = s

        # Estadísticas: primer formato cuyo hash esté en statistics.sqlite3
        md5, st = None, None
        for ruta in rutas:
            h = md5s.get(ruta)
            if h and h in stats:
                md5, st = h, stats[h]
                break
        if md5 is None:
            md5 = md5s.get(rutas[0])

        leido_manual = bool(act["LEIDO"].get(bid))
        if not (sc or st or leido_manual):
            continue
        if sc:
            n_sidecar += 1
        if st:
            n_stats += 1

        # Estado: manda el sidecar; sin sidecar, un #leído manual = complete
        status = (sc or {}).get("status")
        if not status and leido_manual:
            status = "complete"
        frac = (sc or {}).get("frac")
        completo = status == "complete"

        ultima_ts = (st or {}).get("ultima")
        ultima_dt = ts_a_dt(ultima_ts) or (ts_a_dt(sc["mtime"]) if sc else None)

        plan = {}
        def poner(campo, valor):
            if valor is not None and not casi_igual(act[campo].get(bid), valor):
                plan[campo] = valor

        poner("MD5", md5)
        if frac is not None:
            poner("PROGFLOAT", round(frac, 6))
            poner("PROGINT", int(round(frac * 100)))
        elif completo and act["PROGFLOAT"].get(bid) is None:
            poner("PROGFLOAT", 1.0)
            poner("PROGINT", 100)
        poner("STATUS", status)
        if st:
            poner("TIEMPO", int(round(st["seg"] / 60.0)))
            if dt_vacio(act["START"].get(bid)):
                poner("START", ts_a_dt(st["primera"]))
        if ultima_dt is not None:
            poner("LASTMOD", ultima_dt)
        if completo:
            if not leido_manual:
                poner("LEIDO", True)
            if dt_vacio(act["FINISH"].get(bid)) and ultima_dt is not None:
                poner("FINISH", ultima_dt)
            if dt_vacio(act["READ_DATE"].get(bid)) and ultima_dt is not None:
                poner("READ_DATE", ultima_dt)

        if plan:
            plan["LASTSYNC"] = datetime.now(tz=timezone.utc)
            for campo, valor in plan.items():
                updates[campo][bid] = valor
            filas_reporte.append({
                "id": bid,
                "titulo": api.field_for("title", bid),
                "serie": api.field_for("series", bid) or "",
                "pct": "" if frac is None else "%.1f" % (frac * 100),
                "estado": status or "",
                "min": "" if not st else int(round(st["seg"] / 60.0)),
                "ultima": "" if ultima_dt is None else ultima_dt.astimezone().strftime("%Y-%m-%d %H:%M"),
                "campos": ",".join(sorted(k for k in plan if k != "LASTSYNC")),
            })

    # ── Reporte TSV ──────────────────────────────────────────────────────────
    filas_reporte.sort(key=lambda r: str(r["ultima"]), reverse=True)
    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)
    with open(REPORTE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "titulo", "serie", "pct", "estado", "min", "ultima", "campos"], delimiter="\t")
        w.writeheader()
        w.writerows(filas_reporte)

    # ── Aplicar ──────────────────────────────────────────────────────────────
    n_cambios = sum(len(v) for v in updates.values())
    if APLICAR and n_cambios:
        for campo, valores in updates.items():
            if valores:
                api.set_field(C[campo], valores)

    # ── Resumen ──────────────────────────────────────────────────────────────
    modo = "APLICADO" if APLICAR else "SIMULACIÓN (nada escrito)"
    print("── Sincronización KOReader → Calibre ─────────────────────")
    print("  Modo               : %s" % modo)
    print("  Libros en biblioteca: %d" % len(ids))
    print("  Con sidecar .sdr    : %d" % n_sidecar)
    print("  Con estadísticas    : %d" % n_stats)
    print("  Libros a actualizar : %d  (%d valores)" % (len(filas_reporte), n_cambios))
    print("  Reporte TSV         : %s" % REPORTE)
    if filas_reporte:
        print()
        print("  %-5s %-44s %6s %-10s %6s  %s" % ("id", "título", "%", "estado", "min", "última"))
        for r in filas_reporte[:25]:
            print("  %-5s %-44s %6s %-10s %6s  %s" % (
                r["id"], str(r["titulo"])[:44], r["pct"], r["estado"], r["min"], r["ultima"]))
        if len(filas_reporte) > 25:
            print("  … y %d más (ver reporte TSV)." % (len(filas_reporte) - 25))


if __name__ == "__main__":
    if not BIBLIOTECA:
        print("✗ Falta QKO_BIBLIOTECA en el entorno.", file=sys.stderr)
        raise SystemExit(1)
    main()
