#!/usr/bin/env bash
# main.sh — repaso final de títulos (2026-10-01): «simultáneas» (7) y Ricœur, que los detectores dejaron pasar.
# Aprobada por el usuario el 2026-10-01 («un último repaso de duplicados y títulos»), sobre meta/diagnosticos/TITULOS_CALIBRE_2026-09.md. Mismo patrón que titulos_erratas_2026-09-30:
# cambiar el título renombra carpeta y archivo, y Zotero enlaza el PDF por esa ruta.
# Uso: main.sh [--simular <biblioteca> <zotero.sqlite>]   (por defecto, los reales; Calibre y Zotero cerrados)
# Deshacer: deshacer.sh
set -euo pipefail
cd "$(dirname "$0")"
AQUI="$PWD"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
source "$DOCS_ROOT/core/shell-lib/backup_rotado.sh"
BIB="$BIBLIOTECA_DIR"
ZOT="${ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"
SAL="$AQUI"
if [ "${1:-}" = "--simular" ]; then
    BIB="$2"; ZOT="$3"; SAL="$(mktemp -d)"; echo "· simulacro sobre $BIB (tablas en $SAL)"
    export LOCK_ESCRITURA_CALIBRE="$SAL/.lock"
else
    pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
    pgrep -x "zotero|zotero-bin" >/dev/null && { echo "Zotero está abierto: ciérralo." >&2; exit 1; }
    [ -e hechos.tsv ] && { echo "Ya aplicada (hay hechos.tsv); para repetir, primero deshacer.sh." >&2; exit 1; }
fi

tomar_lock_calibre
export ECOSISTEMA_LOCK_HELD=1

echo "1/5 respaldo"
RESP="$AQUI/../../backups/$(basename "$AQUI")"
[ "$SAL" = "$AQUI" ] || RESP="$SAL/backups"
mkdir -p "$RESP"
backup_metadata_db "$BIB/metadata.db" "$RESP" 5
cp -- "$ZOT" "$RESP/zotero.sqlite"
python3 foto.py "$BIB/metadata.db" propuesta.tsv "$SAL/foto_antes.tsv"
awk -F'\t' '$1=="carpeta"{print $4}' "$SAL/foto_antes.tsv" > "$SAL/carpetas_afectadas.txt"
tar -C "$BIB" -czf "$RESP/backup_carpetas.tar.gz" -T "$SAL/carpetas_afectadas.txt"

echo "2/5 Calibre (calibredb set_metadata)"
while IFS=$'\t' read -r libro _ nuevo _; do
    [[ "$libro" == \#* || -z "$libro" ]] && continue
    # set_metadata no recalcula title_sort; en esta biblioteca sort = título literal
    calibredb --with-library "$BIB" set_metadata "$libro" --field "title:$nuevo" --field "sort:$nuevo" >/dev/null
    echo "  $libro → $nuevo"
done < propuesta.tsv
python3 foto.py "$BIB/metadata.db" propuesta.tsv --comparar "$SAL/foto_antes.tsv" "$SAL"
echo "  $(wc -l < "$SAL/hechos.tsv") formatos movidos · $(wc -l < "$SAL/carpetas.tsv") carpetas movidas"

echo "3/5 Zotero"
python3 aplicar_zotero.py "$ZOT" "$BIB/metadata.db" "$SAL" "$AQUI/propuesta.tsv"

echo "4/5 OPF"
calibredb --with-library "$BIB" backup_metadata >/dev/null

echo "5/5 verificación"
python3 ../grafias_autores_2026-09-30/verificar.py "$BIB" "$ZOT"
echo "hecho · deshacer: deshacer.sh"
