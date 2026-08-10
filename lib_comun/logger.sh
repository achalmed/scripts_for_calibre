#!/usr/bin/env bash
# lib_comun/logger.sh - Logging centralizado del ecosistema scripts_for_calibre.
# Módulo canónico (antes triplicado idéntico en
# script_catalogacion_biblioteca, script_sincronizar_zotero y
# script_verificar_metadatos). Toda salida al usuario pasa por estas funciones
# para que el formato sea consistente y la redirección sea trivial.
# WARN y ERROR van a stderr para que stdout quede limpio para pipelines.
# Formato: [LEVEL] YYYY-MM-DD HH:MM:SS - msg (ARQUITECTURA.md §5.4).

_log() {
    local level=$1
    shift
    printf '[%s] %s - %s\n' "$level" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_info()  { _log "INFO"  "$@"; }
log_warn()  { _log "WARN"  "$@" >&2; }
log_error() { _log "ERROR" "$@" >&2; }

# log_debug()
# Se emite solo bajo --verbose; usado para trazado por fila.
log_debug() {
    [[ "$VERBOSE" == true ]] && _log "DEBUG" "$@"
    return 0
}
