#!/usr/bin/env bash
# lib/validator.sh - Write preconditions: apps closed, databases sane,
# backups taken. All writes are gated through ensure_safe_to_apply().

# validate_database()
# A database must exist, be non-empty and contain the expected table.
# (Guards against the known trap of accidental 0-byte metadata.db files.)
#
# Arguments:
#   $1 - Database path
#   $2 - Table that must exist
validate_database() {
    local db=$1 table=$2
    [[ -s "$db" ]] || { log_error "Base inexistente o vacia: $db"; exit 1; }
    sqlite3 "file:$db?mode=ro" "SELECT 1 FROM $table LIMIT 1;" >/dev/null 2>&1 \
        || { log_error "Base sin tabla '$table' (¿fichero corrupto?): $db"; exit 1; }
}

# ensure_apps_closed()
# Calibre and Zotero must both be closed before writing to their databases.
ensure_apps_closed() {
    if pgrep -f "calibre-gui|calibre-parallel|/calibre\b" >/dev/null 2>&1; then
        log_error "Calibre esta abierto. Cierralo antes de --aplicar."
        exit 1
    fi
    if pgrep -x zotero >/dev/null 2>&1 || pgrep -f "zotero/zotero" >/dev/null 2>&1; then
        log_error "Zotero esta abierto. Cierralo antes de --aplicar."
        exit 1
    fi
}

# backup_databases()
# Timestamped copies of both databases before any write. Sets globals
# BACKUP_CAL and BACKUP_ZOT for the summary.
backup_databases() {
    local dir="$PROJECT_DIR/$STATE_DIR_BASENAME/backups"
    mkdir -p "$dir"
    local stamp
    stamp="$(date '+%Y%m%d-%H%M%S')"
    BACKUP_CAL="$dir/metadata.db.$stamp"
    BACKUP_ZOT="$dir/zotero.sqlite.$stamp"
    cp "$CALIBRE_DB" "$BACKUP_CAL"
    cp "$ZOTERO_DB" "$BACKUP_ZOT"
    log_info "Backup Calibre: $BACKUP_CAL"
    log_info "Backup Zotero : $BACKUP_ZOT"
}

# verify_integrity()
# Post-write integrity check on both databases; aborts loudly on failure
# so the user can restore the backups.
verify_integrity() {
    local r1 r2
    r1=$(sqlite3 "$CALIBRE_DB" "PRAGMA integrity_check;" | head -1)
    r2=$(sqlite3 "$ZOTERO_DB" "PRAGMA integrity_check;" | head -1)
    if [[ "$r1" != "ok" || "$r2" != "ok" ]]; then
        log_error "INTEGRIDAD FALLIDA (calibre=$r1, zotero=$r2)."
        log_error "Restaura los backups: $BACKUP_CAL / $BACKUP_ZOT"
        exit 1
    fi
    log_info "Integridad verificada: ok en ambas bases"
}

# ensure_safe_to_apply()
# Single gate called by main.sh before the Python core runs with --aplicar.
ensure_safe_to_apply() {
    ensure_apps_closed
    backup_databases
}
