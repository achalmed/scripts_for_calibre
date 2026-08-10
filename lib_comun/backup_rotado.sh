#!/usr/bin/env bash
# lib_comun/backup_rotado.sh - Respaldo con rotación por antigüedad.
#
# Política común (ARQUITECTURA.md §5.5): SIEMPRE respaldar antes de escribir un
# almacén, SIEMPRE rotando. Extraído del copy-paste idéntico de
# script_koreader_estudio/main.sh (~159-173) y
# script_ecosistema_lectura/main.sh (~112-119).

# backup_metadata_db RUTA_DB DIR_BACKUPS N
# Copia RUTA_DB a DIR_BACKUPS/metadata_<YYYYMMDD_HHMMSS>.db y conserva solo los
# N más recientes (poda los antiguos por antigüedad). Imprime la ruta del
# backup creado. Falla si la copia falla (no se debe escribir sin respaldo).
backup_metadata_db() {
    local db="$1" dir="$2" conservar="${3:-5}"
    mkdir -p "$dir"
    local backup="$dir/metadata_$(date +%Y%m%d_%H%M%S).db"
    cp "$db" "$backup"
    # Rotación: conservar los N más recientes; podar el resto.
    ls -1t "$dir"/metadata_*.db 2>/dev/null \
        | tail -n +"$((conservar + 1))" | xargs -r rm -f
    echo "── Backup: $backup"
}
