#!/usr/bin/env bash
# scripts_for_calibre/script_metadatos_calibre/lib/logger.sh — envoltorio (FS2, 2026-09-07): el logger vive en core/shell-lib/logger.sh; aquí solo lo propio de esta suite.
_core_d="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; while [ "$_core_d" != / ] && [ ! -f "$_core_d/core/shell-lib/logger.sh" ]; do _core_d="$(dirname "$_core_d")"; done
[ -f "$_core_d/core/shell-lib/logger.sh" ] || { echo "[ERROR] no encuentro core/shell-lib/logger.sh subiendo desde ${BASH_SOURCE[0]}" >&2; exit 1; }
source "$_core_d/core/shell-lib/logger.sh"; unset _core_d

# propio de metadatos_calibre: sección con tee al archivo y cabecera de sesión
log_section() {
    printf '\n%s\n  %s\n%s\n' "════════════════════════════════════════════════════════════════" "$1" "════════════════════════════════════════════════════════════════" \
        | tee -a "${LOG_FILE:-/dev/null}" 2>/dev/null
}
log_init() {
    if ! touch "$LOG_FILE" 2>/dev/null; then log_warn "Cannot create log file at '${LOG_FILE}'. File logging disabled."; unset LOG_FILE; return; fi
    printf '%s\n%s\n%s\n%s\n' "======================================================" "  ${SCRIPT_NAME:-script} v${SCRIPT_VERSION:-?} — Session log" \
        "  Started : $(date '+%Y-%m-%d %H:%M:%S')" "======================================================" >> "$LOG_FILE"
}
