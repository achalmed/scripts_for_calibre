#!/usr/bin/env bash
# lib/logger.sh - Centralized logging. All user-facing output goes through
# these functions so formatting stays consistent and redirection is trivial.
# WARN and ERROR go to stderr so stdout stays clean for pipelines.

_log() {
    local level=$1
    shift
    printf '[%s] %s - %s\n' "$level" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_info()  { _log "INFO"  "$@"; }
log_warn()  { _log "WARN"  "$@" >&2; }
log_error() { _log "ERROR" "$@" >&2; }

# log_debug()
# Emitted only under --verbose; used for per-row tracing.
log_debug() {
    [[ "$VERBOSE" == true ]] && _log "DEBUG" "$@"
    return 0
}
