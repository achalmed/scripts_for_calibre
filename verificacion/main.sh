#!/usr/bin/env bash
# verificacion/main.sh — Entry point: orchestration only
# Verifies Calibre metadata against public bibliographic APIs and writes a
# discrepancy report. READ-ONLY: it never modifies the Calibre library.

set -euo pipefail

readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=config.sh
source "$PROJECT_DIR/config.sh"
# shellcheck source=../../core/shell-lib/logger.sh
source "$SHELL_LIB/logger.sh"
# shellcheck source=../lib/leer.sh
source "$PROJECT_DIR/../lib/leer.sh"        # lecturas en solo lectura con CORE_PYTHON (K6)
# shellcheck source=lib/cli.sh
source "$PROJECT_DIR/lib/cli.sh"
# shellcheck source=lib/db.sh
source "$PROJECT_DIR/lib/db.sh"
# shellcheck source=lib/report.sh
source "$PROJECT_DIR/lib/report.sh"

main() {
    parse_arguments "$@"
    check_dependencies

    log_info "$TOOL_NAME v$VERSION | modo=$MODE | biblioteca=$CALIBRE_LIBRARY"
    local n
    n="$(count_candidates)"
    log_info "Candidatos seleccionados: $n"
    if [[ "$n" -eq 0 ]]; then
        log_warn "No hay candidatos para este modo/seleccion. Nada que hacer."
        exit 0
    fi

    prepare_report_paths
    export_python_env

    # Pipe the candidate TSV through the Python core; capture its summary.
    local summary
    summary="$(select_candidates | "$CORE_PYTHON" "$PROJECT_DIR/lib/verificador.py")"

    print_summary "$summary"
}

main "$@"
