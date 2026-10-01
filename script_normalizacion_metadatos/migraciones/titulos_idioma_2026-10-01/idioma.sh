#!/usr/bin/env bash
# idioma.sh — idioma de los libros de idiomas.tsv (2026-10-01, fase T5): spa → eng/por según el texto del PDF.
# No mueve carpetas (el idioma no está en la ruta); el sincronizador diario lo lleva a Zotero (Calibre manda).
# Uso: idioma.sh (Calibre cerrado). Deshacer: deshacer.sh restaura el metadata.db de antes de main.sh.
set -euo pipefail
cd "$(dirname "$0")"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
source "$DOCS_ROOT/core/shell-lib/backup_rotado.sh"
BIB="$BIBLIOTECA_DIR"
pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
tomar_lock_calibre
backup_metadata_db "$BIB/metadata.db" "$PWD/../../backups/$(basename "$PWD")" 5
while IFS=$'\t' read -r libro viejo nuevo _; do
    [[ "$libro" == \#* || -z "$libro" ]] && continue
    actual="$(sqlite3 -readonly "$BIB/metadata.db" "select g.lang_code from books_languages_link l join languages g on g.id = l.lang_code where l.book = $libro")"
    [ "$actual" = "$viejo" ] || { echo "  · $libro: idioma «$actual», no «$viejo»; se omite"; continue; }
    calibredb --with-library "$BIB" set_metadata "$libro" --field "languages:$nuevo" >/dev/null
    echo "  $libro → $nuevo"
done < idiomas.tsv
calibredb --with-library "$BIB" backup_metadata >/dev/null
echo "hecho"
