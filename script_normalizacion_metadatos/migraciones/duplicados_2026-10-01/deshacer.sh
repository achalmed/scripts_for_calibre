#!/usr/bin/env bash
# deshacer.sh — deshace main.sh (duplicados, 2026-10-01); Calibre y Zotero cerrados.
# Devuelve las carpetas de los 13 libros desde la papelera de Calibre (.caltrash/b/<id>) a su ruta y restaura
# metadata.db y zotero.sqlite del respaldo de antes (así vuelven las claves, la nota y los ítems de la papelera).
# Alternativa sin consola: Calibre → Papelera → restaurar, y en Zotero, Papelera → restaurar.
set -euo pipefail
cd "$(dirname "$0")"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
BIB="$BIBLIOTECA_DIR"; ZOT="${ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"
RESP="$PWD/../../backups/$(basename "$PWD")"
pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
pgrep -x "zotero|zotero-bin" >/dev/null && { echo "Zotero está abierto: ciérralo." >&2; exit 1; }
[ -e hechos.tsv ] || { echo "No hay acciones aplicadas que deshacer." >&2; exit 1; }
tomar_lock_calibre
while IFS=$'\t' read -r accion libro detalle; do
    [ "$accion" = calibre_remove ] || continue
    destino="${detalle%% · *}"
    [ -d "$BIB/.caltrash/b/$libro" ] || { echo "  · $libro no está en la papelera de Calibre"; continue; }
    mkdir -p "$BIB/$destino"; mv -n "$BIB/.caltrash/b/$libro"/* "$BIB/$destino/"; rmdir "$BIB/.caltrash/b/$libro"
done < hechos.tsv
cp -- "$(ls -1 "$RESP"/metadata_*.db | head -1)" "$BIB/metadata.db"
cp -- "$(ls -1 "$RESP"/zotero_*.db | head -1)" "$ZOT"
mkdir -p deshecho && mv hechos.tsv deshecho/
echo "deshecho: 13 libros devueltos, metadata.db y zotero.sqlite restaurados"
