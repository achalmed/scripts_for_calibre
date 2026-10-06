#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/migrar_sdr.py — Migra los sidecars .sdr desde las carpetas de los libros
(modo "doc") a la ubicación central por hash de KOReader (modo "hash"):

    ~/.config/koreader/hashdocsettings/<md5[0:2]>/<md5>.sdr/metadata.<ext>.lua

Layout y algoritmo tomados del código instalado de KOReader
(frontend/docsettings.lua: getSidecarDir "hash" + util.partialMD5).

Se MUEVEN los archivos (no se copian): al terminar no queda duplicidad.
Un .sdr puede servir a dos formatos del mismo libro (metadata.pdf.lua y
metadata.epub.lua): cada metadata va al hash de SU archivo; los extras
compartidos (cover.*, custom_metadata.lua) se copian a cada destino.

Simulación por defecto; escribe solo con QKO_APLICAR=1. KOReader cerrado.
"""

import os
import sys
import shutil
import hashlib

BIB = os.environ.get("QKO_BIBLIOTECA", "")
KCFG = os.environ.get("QKO_KOREADER_CONFIG", "")
APLICAR = os.environ.get("QKO_APLICAR", "0") == "1"
# Con QKO_ELIMINAR_HUERFANOS=1, los .sdr sin libro ni candidato de rescate se
# eliminan (ya están respaldados en el tar pre-migración).
ELIMINAR_HUERFANOS = os.environ.get("QKO_ELIMINAR_HUERFANOS", "0") == "1"
HASH_DIR = os.path.join(KCFG, "hashdocsettings")


def md5_parcial(ruta):
    """MD5 parcial de KOReader (verificado contra statistics.sqlite3)."""
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


def destino_de(md5):
    return os.path.join(HASH_DIR, md5[:2], md5 + ".sdr")


def mover(origen, dest_dir, nombre):
    """Mueve origen a dest_dir/nombre; si existe, el más nuevo queda como
    titular y el otro pasa a .old."""
    destino = os.path.join(dest_dir, nombre)
    if not APLICAR:
        return "moveria"
    os.makedirs(dest_dir, exist_ok=True)
    if os.path.exists(destino):
        if os.path.getmtime(origen) > os.path.getmtime(destino):
            shutil.move(destino, destino + ".old")
            shutil.move(origen, destino)
            return "conflicto_gana_origen"
        os.remove(origen)
        return "conflicto_gana_destino"
    shutil.move(origen, destino)
    return "movido"


def main():
    if not (BIB and KCFG):
        print("✗ Faltan QKO_BIBLIOTECA / QKO_KOREADER_CONFIG.", file=sys.stderr)
        return 1

    sdr_dirs = []
    for raiz, dirs, _files in os.walk(BIB):
        for d in list(dirs):
            if d.endswith(".sdr"):
                dirs.remove(d)          # no descender dentro del .sdr
                sdr_dirs.append(os.path.join(raiz, d))

    migrados, huerfanos, conflictos, extras = 0, 0, 0, 0
    rescatados, eliminados = 0, 0
    detalle_huerfanos = []

    for sdr in sorted(sdr_dirs):
        base = sdr[:-4]                  # ruta sin ".sdr"
        contenido = sorted(os.listdir(sdr))
        metas = [f for f in contenido
                 if f.startswith("metadata.") and f.endswith(".lua")]
        otros = [f for f in contenido
                 if f not in metas and not f.endswith(".lua.old")]
        olds = [f for f in contenido if f.endswith(".lua.old")]

        destinos = []
        for meta in metas:
            ext = meta[len("metadata."):-len(".lua")]
            libro = base + "." + ext
            if not os.path.isfile(libro):
                # Rescate: si en la carpeta hay EXACTAMENTE un archivo de esa
                # extensión, es el libro renombrado por Calibre → se re-empareja
                # por contenido (hash) y el progreso se recupera.
                carpeta = os.path.dirname(sdr)
                cands = [f for f in os.listdir(carpeta)
                         if f.lower().endswith("." + ext.lower())
                         and os.path.isfile(os.path.join(carpeta, f))]
                if len(cands) == 1:
                    libro = os.path.join(carpeta, cands[0])
                    rescatados += 1
                else:
                    huerfanos += 1
                    detalle_huerfanos.append(
                        "%s (falta .%s; candidatos: %d)" % (sdr, ext, len(cands)))
                    continue
            h = md5_parcial(libro)
            if not h:
                huerfanos += 1
                detalle_huerfanos.append(sdr + " (no se pudo hashear)")
                continue
            tgt = destino_de(h)
            res = mover(os.path.join(sdr, meta), tgt, meta)
            if res.startswith("conflicto"):
                conflictos += 1
            migrados += 1
            destinos.append(tgt)
            # backup .old que acompaña a esta metadata
            old = meta + ".old"
            if old in olds and APLICAR:
                mover(os.path.join(sdr, old), tgt, old)

        # extras compartidos (cover.jpg, custom_metadata.lua…) a cada destino
        for f in otros:
            for tgt in destinos:
                if APLICAR:
                    os.makedirs(tgt, exist_ok=True)
                    if not os.path.exists(os.path.join(tgt, f)):
                        shutil.copy2(os.path.join(sdr, f), os.path.join(tgt, f))
            if destinos:
                extras += 1
                if APLICAR:
                    os.remove(os.path.join(sdr, f))

        # eliminar el .sdr si quedó vacío; o entero si es huérfano sin rescate
        if APLICAR:
            try:
                if not os.listdir(sdr):
                    os.rmdir(sdr)
                elif ELIMINAR_HUERFANOS and metas and not destinos:
                    shutil.rmtree(sdr)
                    eliminados += 1
            except OSError:
                pass

    modo = "APLICADO" if APLICAR else "SIMULACIÓN (nada movido)"
    print("── Migración de sidecars a ubicación hash ────────────────")
    print("  Modo                  : %s" % modo)
    print("  Carpetas .sdr halladas: %d" % len(sdr_dirs))
    print("  Metadatas migradas    : %d (de ellas, rescatadas de renombrados: %d)" % (migrados, rescatados))
    print("  Extras (covers, etc.) : %d" % extras)
    print("  Conflictos resueltos  : %d (gana el más reciente; el otro queda .old)" % conflictos)
    print("  Huérfanos eliminados  : %d (respaldados en el tar pre-migración)" % eliminados)
    print("  Huérfanos restantes   : %d" % huerfanos)
    for linea in detalle_huerfanos[:10]:
        print("     · %s" % linea)
    if len(detalle_huerfanos) > 10:
        print("     · … y %d más" % (len(detalle_huerfanos) - 10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
