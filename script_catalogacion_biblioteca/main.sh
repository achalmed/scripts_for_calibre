#!/usr/bin/env bash
# script_catalogacion_biblioteca/main.sh — Entry point: orchestration only
# Applies the cataloged metadata from resumen_catalogacion.tsv to the
# Calibre library via calibredb. Simulates by default; see --help.

set -euo pipefail

readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=config.sh
source "$PROJECT_DIR/config.sh"
# shellcheck source=../lib_comun/logger.sh
source "$PROJECT_DIR/../lib_comun/logger.sh"
# shellcheck source=lib/validator.sh
source "$PROJECT_DIR/lib/validator.sh"
# shellcheck source=lib/cli.sh
source "$PROJECT_DIR/lib/cli.sh"
# shellcheck source=lib/clasificador.sh
source "$PROJECT_DIR/lib/clasificador.sh"
# shellcheck source=lib/metadata.sh
source "$PROJECT_DIR/lib/metadata.sh"

main() {
    parse_arguments "$@"

    local tsv_path="$PROJECT_DIR/$TSV_BASENAME"
    check_dependencies
    validate_input_file "$tsv_path"
    ensure_calibre_closed

    load_clasificador_enum
    process_tsv_rows "$tsv_path"
    print_summary
}

main "$@"
