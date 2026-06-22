#!/usr/bin/env bash
# ==============================================================================
# lib/validator.sh
# Input and environment validation.
# All checks that must pass before business logic runs live here,
# keeping main.sh and domain modules free of defensive boilerplate.
# ==============================================================================

[[ -n "${_VALIDATOR_SH_LOADED:-}" ]] && return 0
readonly _VALIDATOR_SH_LOADED=1

# validate_dependencies()
# Checks that every required external binary is available on PATH.
# Fails fast with a clear installation hint for each missing tool.
#
# Arguments:
#   $@ - list of command names to check (e.g. "exiftool" "calibredb")
#
# Returns:
#   0  all dependencies present
#   EXIT_MISSING_DEP  at least one dependency is absent
validate_dependencies() {
    local missing=0
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Required command not found: '${cmd}'"
            _print_install_hint "$cmd"
            missing=1
        else
            log_debug "Dependency OK: ${cmd} ($(command -v "$cmd"))"
        fi
    done
    return "$missing"
}

# _print_install_hint()
# Prints a context-aware installation hint for known dependencies.
# Keeps error messages actionable instead of just reporting failure.
#
# Arguments:
#   $1 - command name
_print_install_hint() {
    local cmd="$1"
    case "$cmd" in
        exiftool)
            printf '   Install with: sudo apt-get install libimage-exiftool-perl\n'
            printf '   (Arch/Manjaro: sudo pacman -S perl-image-exiftool)\n'
            ;;
        calibredb)
            printf '   Install with: sudo apt-get install calibre\n'
            printf '   Or download from: https://calibre-ebook.com/download\n'
            ;;
        xmllint)
            printf '   Install with: sudo apt-get install libxml2-utils\n'
            ;;
        *)
            printf '   Please install "%s" before running this script.\n' "$cmd"
            ;;
    esac
}

# validate_directory_exists()
# Verifies that a path exists and is a readable directory.
#
# Arguments:
#   $1 - path to check
#   $2 - human-readable label for error messages (e.g. "Root directory")
#
# Returns:
#   0  directory exists and is readable
#   EXIT_NOT_FOUND  path does not exist or is not a directory
validate_directory_exists() {
    local path="$1"
    local label="${2:-Directory}"

    if [[ ! -d "$path" ]]; then
        log_error "${label} does not exist or is not a directory: '${path}'"
        return "${EXIT_NOT_FOUND}"
    fi
    if [[ ! -r "$path" ]]; then
        log_error "${label} is not readable: '${path}'"
        return "${EXIT_NO_PERMISSION}"
    fi
    log_debug "${label} OK: ${path}"
    return 0
}

# validate_calibre_library()
# Checks that a directory is a valid Calibre library root by looking for the
# sentinel metadata.db file. Prevents running calibredb against arbitrary paths.
#
# Arguments:
#   $1 - candidate library root path
#
# Returns:
#   0  valid Calibre library
#   EXIT_NOT_FOUND  metadata.db absent — not a Calibre library
validate_calibre_library() {
    local library_path="$1"

    validate_directory_exists "$library_path" "Calibre library path" || return $?

    if [[ ! -f "${library_path}/${CALIBRE_DB_FILENAME}" ]]; then
        log_error "'${library_path}' does not contain '${CALIBRE_DB_FILENAME}'."
        log_error "Make sure you are pointing to the Calibre library root, not an author subfolder."
        return "${EXIT_NOT_FOUND}"
    fi
    log_debug "Calibre library validated: ${library_path}"
    return 0
}

# validate_file_writable()
# Checks that a file exists and the process has write permission.
#
# Arguments:
#   $1 - file path
#
# Returns:
#   0  file is writable
#   EXIT_NO_PERMISSION  file exists but is not writable
#   EXIT_NOT_FOUND  file does not exist
validate_file_writable() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return "${EXIT_NOT_FOUND}"
    fi
    if [[ ! -w "$file" ]]; then
        return "${EXIT_NO_PERMISSION}"
    fi
    return 0
}
