#!/usr/bin/env bash
# deshacer.sh — deshace main.sh (erratas de título, 2026-09-30); Calibre y Zotero cerrados.
# Devuelve cada archivo y carpeta a su ruta vieja y restaura metadata.db y zotero.sqlite de antes.
set -euo pipefail
cd "$(dirname "$0")"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
BIB="$BIBLIOTECA_DIR"
ZOT="${ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"
RESP="$PWD/../../backups/$(basename "$PWD")"
pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
pgrep -x "zotero|zotero-bin" >/dev/null && { echo "Zotero está abierto: ciérralo." >&2; exit 1; }
[ -e hechos.tsv ] && [ -e carpetas.tsv ] && [ -e "$RESP/zotero.sqlite" ] || { echo "No hay corrección aplicada que deshacer." >&2; exit 1; }
tomar_lock_calibre

while IFS=$'\t' read -r _ viejo nuevo; do
    if [ -e "$BIB/$nuevo" ] && [ ! -e "$BIB/$viejo" ]; then
        mkdir -p "$BIB/$(dirname "$viejo")"; mv -n -- "$BIB/$nuevo" "$BIB/$viejo"
    fi
done < hechos.tsv
while IFS=$'\t' read -r _ viejo nuevo; do
    [ -d "$BIB/$nuevo" ] || continue
    mkdir -p "$BIB/$viejo"
    find "$BIB/$nuevo" -mindepth 1 -maxdepth 1 -exec mv -n -t "$BIB/$viejo" -- {} +
    rmdir --ignore-fail-on-non-empty "$BIB/$nuevo" 2>/dev/null || true
done < carpetas.tsv
tar -C "$BIB" -xzf "$RESP/backup_carpetas.tar.gz" --wildcards "*/metadata.opf"
cp -- "$(ls -1t "$RESP"/metadata_*.db | tail -1)" "$BIB/metadata.db"
cp -- "$RESP/zotero.sqlite" "$ZOT"
mkdir -p deshecho && mv hechos.tsv carpetas.tsv zotero.tsv foto_antes.tsv carpetas_afectadas.txt deshecho/ 2>/dev/null || true
echo "deshecho: archivos, carpetas y bases restaurados"
