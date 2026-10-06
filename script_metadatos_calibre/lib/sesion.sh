#!/usr/bin/env bash
# script_metadatos_calibre/lib/sesion.sh — la cabecera de sesión y las secciones de esta suite (con copia al log).
# Módulo: se carga con `source` desde main.sh, después del logger de core/shell-lib (K9: sin logger propio).

# log_section TÍTULO — sección con tee al archivo de la sesión.
log_section() {
    printf '\n%s\n  %s\n%s\n' "════════════════════════════════════════════════════════════════" "$1" "════════════════════════════════════════════════════════════════" \
        | tee -a "${LOG_FILE:-/dev/null}" 2>/dev/null
}

# log_init — abre el archivo de la sesión; si no se puede, sigue sin él.
log_init() {
    if ! touch "$LOG_FILE" 2>/dev/null; then log_warn "Cannot create log file at '${LOG_FILE}'. File logging disabled."; unset LOG_FILE; return; fi
    printf '%s\n%s\n%s\n%s\n' "======================================================" "  ${SCRIPT_NAME:-script} v${SCRIPT_VERSION:-?} — Session log" \
        "  Started : $(date '+%Y-%m-%d %H:%M:%S')" "======================================================" >> "$LOG_FILE"
}
