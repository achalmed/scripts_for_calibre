#!/usr/bin/env bash
# ==============================================================================
# lib/cli.sh
# Argument parsing, help text, and interactive menu.
# Separating CLI concerns from business logic keeps main.sh readable and
# makes it trivial to add new flags without touching domain modules.
# ==============================================================================

[[ -n "${_CLI_SH_LOADED:-}" ]] && return 0
readonly _CLI_SH_LOADED=1

# parse_arguments()
# Parses all CLI flags and populates global variables used by other modules.
# Unknown flags cause an immediate usage error — fail fast on typos.
#
# Arguments:
#   $@ - all arguments passed to main.sh
#
# Side-effects (sets globals):
#   ACTION, ROOT_DIR, LIBRARY_PATH, VERBOSE, DRY_RUN, FORCE
parse_arguments() {
    # Defaults — defined here so parse_arguments() is self-contained
    ACTION=""
    ROOT_DIR=""
    LIBRARY_PATH=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            embed)
                ACTION="embed"
                shift
                ;;
            register)
                ACTION="register"
                shift
                ;;
            all)
                ACTION="all"
                shift
                ;;
            --root|-r)
                ROOT_DIR="$2"
                shift 2
                ;;
            --library|-l)
                LIBRARY_PATH="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --dry-run|-n)
                DRY_RUN=true
                shift
                ;;
            --force|-f)
                FORCE=true
                shift
                ;;
            --version)
                printf '%s version %s\n' "$SCRIPT_NAME" "$SCRIPT_VERSION"
                printf 'Author: %s\n' "$SCRIPT_AUTHOR"
                exit "${EXIT_SUCCESS}"
                ;;
            --help|-h)
                show_help
                exit "${EXIT_SUCCESS}"
                ;;
            *)
                log_error "Unknown argument: '$1'"
                printf '\n'
                show_help
                exit "${EXIT_USAGE}"
                ;;
        esac
    done
}

# show_help()
# Prints the full usage reference to stdout.
# Written as a heredoc so it is easy to edit without counting quotes.
show_help() {
    cat <<EOF

${SCRIPT_NAME} v${SCRIPT_VERSION} — Calibre Metadata Manager
${SCRIPT_AUTHOR}

USAGE:
  $(basename "$0") COMMAND [OPTIONS]

COMMANDS:
  embed       Read metadata.opf files and embed them into companion PDFs
  register    Add PDF files as additional formats inside the Calibre library
  all         Run both operations in sequence (embed → register)
  (none)      Launch the interactive menu

OPTIONS:
  -r, --root PATH       Root directory to search for metadata.opf files
                        (default: current working directory)
  -l, --library PATH    Calibre library root path
                        (default: parent of current directory)
  -v, --verbose         Print debug-level messages
  -n, --dry-run         Simulate all operations without making any changes
  -f, --force           Overwrite existing PDF formats in Calibre
      --version         Show version information
  -h, --help            Show this help

EXAMPLES:
  # Interactive menu (no arguments)
  $(basename "$0")

  # Embed metadata from OPF into PDFs under ~/Books
  $(basename "$0") embed --root ~/Books

  # Register PDFs inside ~/Books/Author Name into Calibre at ~/Calibre
  $(basename "$0") register --library ~/Calibre

  # Full pipeline, dry-run first to preview changes
  $(basename "$0") all --root ~/Books --library ~/Calibre --dry-run

  # Full pipeline for real, with verbose output
  $(basename "$0") all --root ~/Books --library ~/Calibre --verbose

NOTES:
  • Run with --dry-run before any bulk operation on a large library.
  • 'embed' requires exiftool to be installed.
  • 'register' requires calibredb to be installed and Calibre to be CLOSED.
  • Log file is written to: /tmp/${SCRIPT_NAME}_YYYYMMDD_HHMMSS.log

EOF
}

# show_interactive_menu()
# Presents a numbered menu when the script is run without arguments.
# Returns the chosen action string via the ACTION global variable.
show_interactive_menu() {
    log_section "📚  CALIBRE METADATA MANAGER  v${SCRIPT_VERSION}"
    printf '\n  Select an operation:\n\n'
    printf '    [1]  Embed metadata (OPF → PDF via exiftool)\n'
    printf '    [2]  Register PDFs in Calibre (calibredb add_format)\n'
    printf '    [3]  Run both operations in sequence\n'
    printf '    [q]  Quit\n\n'

    local choice
    while true; do
        printf '  Your choice: '
        read -r choice
        case "$choice" in
            1) ACTION="embed";    break ;;
            2) ACTION="register"; break ;;
            3) ACTION="all";      break ;;
            q|Q)
                log_info "Exiting."
                exit "${EXIT_SUCCESS}"
                ;;
            *)
                printf '  Invalid option. Please enter 1, 2, 3, or q.\n'
                ;;
        esac
    done

    # Collect path interactively only when not supplied via flags
    if [[ -z "$ROOT_DIR" ]] && [[ "$ACTION" == "embed" || "$ACTION" == "all" ]]; then
        printf '\n  Root directory to scan for metadata.opf [default: %s]:\n  > ' "$(pwd)"
        read -r ROOT_DIR
        ROOT_DIR="${ROOT_DIR:-$(pwd)}"
    fi

    if [[ -z "$LIBRARY_PATH" ]] && [[ "$ACTION" == "register" || "$ACTION" == "all" ]]; then
        local default_lib
        default_lib="$(cd .. && pwd)"
        printf '\n  Calibre library path [default: %s]:\n  > ' "$default_lib"
        read -r LIBRARY_PATH
        LIBRARY_PATH="${LIBRARY_PATH:-$default_lib}"
    fi

    printf '\n'
}
