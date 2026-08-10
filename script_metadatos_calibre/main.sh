#!/usr/bin/env bash
# ==============================================================================
# main.sh — Calibre Metadata Manager
# Single entry point for all operations:
#   • embed    : OPF metadata → PDF files (via exiftool)
#   • register : PDF files → Calibre book records (via calibredb)
#   • all      : both in sequence
#
# Usage:
#   ./main.sh [COMMAND] [OPTIONS]
#   ./main.sh --help
#
# Run without arguments to launch the interactive menu.
# ==============================================================================

set -uo pipefail
# Note: -e is intentionally omitted at the top level so that a failure in
# one book folder does not abort processing of the remaining folders.
# Each module uses explicit return-code checks and counters to track failures.

# ------------------------------------------------------------------------------
# Resolve paths relative to this script's location, not the caller's CWD.
# This makes the script work correctly when invoked as an absolute path or
# from a different directory (e.g. from a cron job or alias).
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------------------------------------------------------------
# Source all modules in dependency order.
# config.sh must come first (defines constants used by all others).
# logger.sh second (logging used by validators and domain modules).
# ------------------------------------------------------------------------------
# shellcheck source=config.sh
source "${SCRIPT_DIR}/config.sh"

# shellcheck source=lib/logger.sh
source "${SCRIPT_DIR}/lib/logger.sh"

# shellcheck source=lib/validator.sh
source "${SCRIPT_DIR}/lib/validator.sh"

# shellcheck source=lib/cli.sh
source "${SCRIPT_DIR}/lib/cli.sh"

# shellcheck source=lib/embed_metadata.sh
source "${SCRIPT_DIR}/lib/embed_metadata.sh"

# shellcheck source=lib/register_formats.sh
source "${SCRIPT_DIR}/lib/register_formats.sh"

# ------------------------------------------------------------------------------
# main()
# Orchestrates the full execution flow:
#   1. Initialise logging
#   2. Parse CLI arguments (or show interactive menu if none provided)
#   3. Apply sensible defaults for paths
#   4. Dispatch to the requested action module(s)
# ------------------------------------------------------------------------------
main() {
    # Initialise log file before any other output so the full session is captured
    log_init

    # ------------------------------------------------------------------
    # Phase 1: Determine user intent
    # ------------------------------------------------------------------
    if [[ $# -eq 0 ]]; then
        # No arguments → interactive menu
        show_interactive_menu
    else
        parse_arguments "$@"
    fi

    # ------------------------------------------------------------------
    # Phase 2: Apply path defaults that depend on runtime context
    # ------------------------------------------------------------------

    # ROOT_DIR: used by both embed (where to find metadata.opf files) and
    # register (where to find author folders). Defaults to CWD.
    ROOT_DIR="${ROOT_DIR:-$(pwd)}"

    # LIBRARY_PATH: used only by register. Defaults to the parent of CWD
    # (the classic layout when running from inside an author folder).
    LIBRARY_PATH="${LIBRARY_PATH:-}"

    # ------------------------------------------------------------------
    # Phase 3: Dispatch
    # ------------------------------------------------------------------
    local overall_status=0

    case "${ACTION}" in
        embed)
            run_embed_metadata || overall_status=$?
            ;;

        register)
            run_register_formats || overall_status=$?
            ;;

        all)
            # Run embed first; always attempt register even if embed had errors,
            # because some PDFs may have been processed successfully.
            run_embed_metadata   || true
            printf '\n'
            run_register_formats || overall_status=$?
            ;;

        *)
            log_error "Unknown action: '${ACTION}'"
            show_help
            exit "${EXIT_USAGE}"
            ;;
    esac

    # ------------------------------------------------------------------
    # Phase 4: Final footer
    # ------------------------------------------------------------------
    printf '\n'
    log_section "✅  SESSION COMPLETE"
    printf '  Log file : %s\n' "${LOG_FILE:-<disabled>}"
    printf '  Duration : %d seconds\n' "$SECONDS"
    printf '  Finished : %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '\n'

    exit "$overall_status"
}

# Invoke main with all CLI arguments forwarded
main "$@"
