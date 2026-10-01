#!/usr/bin/env bash
# deshacer.sh — deshace main.sh (campaña de grafías de autores, 2026-09-30); Calibre y Zotero cerrados.
# Devuelve cada archivo y cada carpeta a su ruta vieja y restaura metadata.db y zotero.sqlite de antes.
set -euo pipefail
cd "$(dirname "$0")"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
BIB="$BIBLIOTECA_DIR"
ZOT="${ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"
RESP="$PWD/../../backups/grafias_autores_2026-09-30"
pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
pgrep -x "zotero|zotero-bin" >/dev/null && { echo "Zotero está abierto: ciérralo." >&2; exit 1; }
[ -e hechos.tsv ] && [ -e carpetas.tsv ] && [ -e "$RESP/backup_bases.tar.gz" ] || { echo "No hay campaña aplicada que deshacer." >&2; exit 1; }
tomar_lock_calibre

# 1. formatos: ruta nueva → ruta vieja (Calibre también los renombró)
while IFS=$'\t' read -r _ viejo nuevo; do
    if [ -e "$BIB/$nuevo" ] && [ ! -e "$BIB/$viejo" ]; then
        mkdir -p "$BIB/$(dirname "$viejo")"; mv -n -- "$BIB/$nuevo" "$BIB/$viejo"
    fi
done < hechos.tsv
# 2. lo demás de cada carpeta (cover.jpg, metadata.opf, data/): carpeta nueva → vieja
while IFS=$'\t' read -r _ viejo nuevo; do
    [ -d "$BIB/$nuevo" ] || continue
    mkdir -p "$BIB/$viejo"
    find "$BIB/$nuevo" -mindepth 1 -maxdepth 1 -exec mv -n -t "$BIB/$viejo" -- {} +
    rmdir -p --ignore-fail-on-non-empty "$BIB/$nuevo" 2>/dev/null || true
done < carpetas.tsv
# 2b. los metadata.opf se regeneraron con los nombres nuevos: vuelven los de antes
tar -C "$BIB" -xzf "$RESP/backup_carpetas.tar.gz" --wildcards "*/metadata.opf"
# 3. bases de antes
tmp="$(mktemp -d)"; tar -C "$tmp" -xzf "$RESP/backup_bases.tar.gz"
cp -- "$tmp/respaldo/metadata.db" "$BIB/metadata.db"
cp -- "$tmp/respaldo/zotero.sqlite" "$ZOT"
if [ -e "$tmp/respaldo/notes.db" ]; then cp -- "$tmp/respaldo/notes.db" "$BIB/.calnotes/notes.db"; else rm -f -- "$BIB/.calnotes/notes.db"; fi
rm -rf -- "$tmp"
mkdir -p deshecho && mv hechos.tsv carpetas.tsv autores.tsv zotero.tsv deshecho/ 2>/dev/null || true
echo "deshecho: archivos, carpetas y bases restaurados (las tablas de la pasada quedan en deshecho/)"
