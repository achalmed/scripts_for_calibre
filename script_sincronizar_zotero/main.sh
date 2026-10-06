#!/usr/bin/env bash
# script_sincronizar_zotero/main.sh — Entry point: orchestration only
# Bidirectional metadata sync between the Calibre library and Zotero for
# ZMI-linked books. Simulates by default; --aplicar writes to BOTH
# databases (with both apps closed, backups and integrity checks).

set -euo pipefail

readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=config.sh
source "$PROJECT_DIR/config.sh"
# shellcheck source=../lib/escribir.sh
source "$PROJECT_DIR/../lib/escribir.sh"     # la puerta (K2): core/env, detección, candado, respaldo
# shellcheck source=../../core/shell-lib/logger.sh
source "$SHELL_LIB/logger.sh"
# shellcheck source=lib/validator.sh
source "$PROJECT_DIR/lib/validator.sh"
# shellcheck source=lib/cli.sh
source "$PROJECT_DIR/lib/cli.sh"

# Lock compartido del ecosistema (auditoría C5): toda escritura a metadata.db
# serializa con los timers de scripts_for_calibre. Si nos invoca el orquestador
# (ECOSISTEMA_LOCK_HELD=1) el lock ya viene heredado por fd y no se retoma.
puerta_candado_calibre

# prepare_output_paths()
# Timestamped reports plus the persistent state snapshot path.
prepare_output_paths() {
    local rdir="$PROJECT_DIR/$REPORT_DIR_BASENAME"
    mkdir -p "$rdir"
    local stamp
    stamp="$(date '+%Y%m%d-%H%M%S')"
    REPORT_TSV="$rdir/sync_${stamp}.tsv"
    REPORT_MD="$rdir/sync_${stamp}.md"
    STATE_JSON="$STATE_DIR/ultimo_sync.json"
    PLAN_CALIBRE="$STATE_DIR/plan_calibre.json"
    rm -f -- "$PLAN_CALIBRE"
    export REPORT_TSV REPORT_MD STATE_JSON PLAN_CALIBRE
}

# export_core_env()
# Surfaces config.sh values to the Python core. The config values are
# readonly, so we only mark them for export (never reassign).
export_core_env() {
    export CALIBRE_DB ZOTERO_DB
    export REPAIR_ATTACHMENTS BACKFILL_CALIBRE POPULATE_MIRROR
    export LIMIT ONLY_IDS
    export APPLY="$APPLY_CHANGES"
}

# print_summary()
# Parses the Python core summary line.
print_summary() {
    local line=$1
    local pares acciones zw cw huerfanos espejo
    IFS=$'\t' read -r pares acciones zw cw huerfanos espejo <<<"$line"
    echo
    log_info "===== RESUMEN ====="
    log_info "Pares enlazados analizados : ${pares:-0}"
    log_info "Acciones planificadas      : ${acciones:-0}"
    log_info "  escrituras lado Zotero   : ${zw:-0}"
    log_info "  escrituras lado Calibre  : ${cw:-0} (incluye ${espejo:-0} celdas espejo)"
    log_info "Claves huerfanas           : ${huerfanos:-0}"
    log_info "Reporte TSV : $REPORT_TSV"
    log_info "Reporte MD  : $REPORT_MD"
    if [[ "$APPLY_CHANGES" == true ]]; then
        log_info "APLICADO. Estado guardado en $STATE_JSON"
    else
        log_info "SIMULACION: nada se modifico. Ejecuta con --aplicar para escribir."
    fi
}

main() {
    parse_arguments "$@"
    check_dependencies
    log_info "$TOOL_NAME v$VERSION | politica=$CONFLICT_POLICY | aplicar=$APPLY_CHANGES"

    prepare_output_paths
    export_core_env

    if [[ "$APPLY_CHANGES" == true ]]; then
        ensure_safe_to_apply
    fi

    local summary
    summary="$("$CORE_PYTHON" "$PROJECT_DIR/lib/sincronizador.py")"

    if [[ "$APPLY_CHANGES" == true ]]; then
        if [[ -s "$PLAN_CALIBRE" && "$(cat "$PLAN_CALIBRE")" != "{}" ]]; then
            log_info "Aplicando el plan de Calibre por la API (lib/escribir.py aplicar-plan)..."
            calibre-debug -e "$PUERTA_PY" aplicar-plan "$CALIBRE_LIBRARY" "$PLAN_CALIBRE"
        fi
        puerta_integridad
        log_info "Integridad verificada: ok en ambas bases"
        # La API marca los libros que cambia (metadata_dirtied): basta con regenerar esos OPF. El
        # `--all` (20 s) solo hacía falta cuando se escribía por SQL, que no los marcaba (K3).
        log_info "Regenerando los OPF de los libros cambiados (backup_metadata)..."
        calibredb_escribe backup_metadata
    fi

    print_summary "$summary"
}

main "$@"
