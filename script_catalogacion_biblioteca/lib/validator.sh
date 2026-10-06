#!/usr/bin/env bash
# script_catalogacion_biblioteca/lib/validator.sh — Pre-flight checks: dependencies, input file and
# Calibre state. Everything is validated before any logic runs.

# check_dependencies()
# Verifies required binaries. sqlite3/python3 are optional (the enum
# falls back to the snapshot in config.sh without them).
#
# Returns:
#   0 on success; exits 5 when a required dependency is missing
check_dependencies() {
    if ! command -v calibredb >/dev/null 2>&1; then
        log_error "calibredb no está instalado o no está en el PATH."
        exit 5
    fi
    if ! command -v sqlite3 >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
        log_warn "sqlite3/python3 no disponibles: se usará la lista fija de clasificadores (snapshot 2026-07-27)."
    fi
}

# validate_input_file()
# Arguments:
#   $1 - Path to the TSV file
# Returns:
#   0 on success; exits 3 when the file does not exist
validate_input_file() {
    local tsv_path=$1
    if [[ ! -f "$tsv_path" ]]; then
        log_error "No existe el archivo de entrada: $tsv_path"
        exit 3
    fi
}

# ensure_calibre_closed()
# Con --aplicar abre la puerta (K5, P1): Calibre cerrado (detección canónica `ps -eo comm`, que ve
# también los procesos que arrancan), el candado compartido con los timers y un respaldo verificado
# de metadata.db, todo antes de la primera fila: mejor fallar pronto que dejar 113 filas a medias.
#
# Returns:
#   0 on success; exits 1 with Calibre open or without backup; 75 with the lock taken
ensure_calibre_closed() {
    [[ "$APPLY_CHANGES" == true ]] || return 0
    puerta_calibre_abrir catalogacion_biblioteca "$CALIBRE_LIBRARY" || exit 1
}
