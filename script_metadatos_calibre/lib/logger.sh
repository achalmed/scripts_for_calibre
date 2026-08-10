#!/usr/bin/env bash
# ==============================================================================
# lib/logger.sh
# Centralised logging functions with three severity levels.
# All output is simultaneously written to stdout/stderr AND to a log file,
# giving both real-time feedback and an audit trail.
# ==============================================================================

# Guard against double-sourcing
[[ -n "${_LOGGER_SH_LOADED:-}" ]] && return 0
readonly _LOGGER_SH_LOADED=1

# _log_write()
# Internal helper that formats and dispatches a log line.
# All public log_* functions delegate here to avoid repeating formatting logic.
#
# Arguments:
#   $1 - severity label  (INFO | WARN | ERROR | DEBUG)
#   $2 - message text
#   $3 - file descriptor (1=stdout, 2=stderr)
_log_write() {
    local level="$1"
    local message="$2"
    local fd="$3"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local line="[${level}] ${timestamp} - ${message}"

    # Print to the requested file descriptor
    printf '%s\n' "$line" >&"$fd"

    # Append to the persistent log file when the variable is set and writable.
    # We redirect errors to /dev/null here intentionally: if the log file path
    # becomes unavailable mid-run we must not abort the main operation.
    if [[ -n "${LOG_FILE:-}" ]]; then
        printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null
    fi
}

# log_info()
# Informational messages — normal progress updates the user should see.
#
# Arguments:
#   $1 - message text
log_info() {
    _log_write "INFO " "$1" 1
}

# log_warn()
# Non-fatal anomalies — execution continues but the operator should review.
#
# Arguments:
#   $1 - message text
log_warn() {
    _log_write "WARN " "$1" 2
}

# log_error()
# Fatal or significant failures — always sent to stderr for easy piping.
#
# Arguments:
#   $1 - message text
log_error() {
    _log_write "ERROR" "$1" 2
}

# log_debug()
# Verbose developer detail — printed only when VERBOSE=true.
#
# Arguments:
#   $1 - message text
log_debug() {
    [[ "${VERBOSE:-false}" == "true" ]] && _log_write "DEBUG" "$1" 1 || true
}

# log_section()
# Prints a visual separator with a title, useful for grouping output by phase.
#
# Arguments:
#   $1 - section title
log_section() {
    local title="$1"
    printf '\n%s\n  %s\n%s\n' \
        "════════════════════════════════════════════════════════════════" \
        "$title" \
        "════════════════════════════════════════════════════════════════" \
        | tee -a "${LOG_FILE:-/dev/null}" 2>/dev/null
}

# log_init()
# Creates the log file and writes the session header.
# Must be called once at startup, after LOG_FILE is set in config.sh.
log_init() {
    if ! touch "$LOG_FILE" 2>/dev/null; then
        # If we cannot create the log file, warn and continue without it.
        # Unsetting LOG_FILE disables file logging in _log_write gracefully.
        log_warn "Cannot create log file at '${LOG_FILE}'. File logging disabled."
        unset LOG_FILE
        return
    fi
    printf '%s\n%s\n%s\n%s\n' \
        "======================================================" \
        "  ${SCRIPT_NAME:-script} v${SCRIPT_VERSION:-?} — Session log" \
        "  Started : $(date '+%Y-%m-%d %H:%M:%S')" \
        "======================================================" \
        >> "$LOG_FILE"
}
