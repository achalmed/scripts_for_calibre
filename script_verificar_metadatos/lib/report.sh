#!/usr/bin/env bash
# lib/report.sh - Report path setup and the final on-screen summary.

# prepare_report_paths()
# Creates the timestamped output paths and exports them for the Python core.
# Sets globals REPORT_TSV and REPORT_MD.
prepare_report_paths() {
    local dir="$PROJECT_DIR/$REPORT_DIR_BASENAME"
    mkdir -p "$dir"
    local stamp
    stamp="$(date '+%Y%m%d-%H%M%S')"
    REPORT_TSV="$dir/discrepancias_${stamp}.tsv"
    REPORT_MD="$dir/discrepancias_${stamp}.md"
    export REPORT_TSV REPORT_MD
}

# export_python_env()
# Surfaces the config.sh values the Python core reads from the environment.
export_python_env() {
    export OL_ISBN_ENDPOINT OL_SEARCH_ENDPOINT GB_ENDPOINT
    export CROSSREF_ENDPOINT USE_CROSSREF CROSSREF_MAILTO
    export RATE_LIMIT_SECONDS HTTP_TIMEOUT FUZZY_TITLE_THRESHOLD MODE
}

# print_summary()
# Parses the Python core's summary line and prints a human report.
#
# Arguments:
#   $1 - "checked\tfound\tnot_found\tdiscrepancies" line
print_summary() {
    local line=$1
    local checked found not_found disc
    IFS=$'\t' read -r checked found not_found disc <<<"$line"
    echo
    log_info "===== RESUMEN ====="
    log_info "Candidatos verificados : ${checked:-0}"
    log_info "Encontrados en fuente  : ${found:-0}"
    log_info "No encontrados         : ${not_found:-0}"
    log_info "Discrepancias          : ${disc:-0}"
    log_info "Reporte TSV : $REPORT_TSV"
    log_info "Reporte MD  : $REPORT_MD"
    log_info "Solo lectura: nada se modifico en Calibre."
}
