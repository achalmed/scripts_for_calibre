#!/usr/bin/env bash
# ==============================================================================
# lib/register_formats.sh
# Registers PDF files that already exist inside Calibre's folder structure
# as additional formats of their corresponding book record, using calibredb.
#
# Assumption: the script is run from inside one specific author's folder,
# or LIBRARY_PATH + AUTHOR_DIR are provided explicitly.
# ==============================================================================

[[ -n "${_REGISTER_FORMATS_SH_LOADED:-}" ]] && return 0
readonly _REGISTER_FORMATS_SH_LOADED=1

# extract_calibre_book_id()
# Extracts the numeric Calibre book ID from a folder name.
# Calibre names book folders as "Book Title (ID)", e.g. "Thinking Fast (42)".
# Returns an empty string if the folder does not follow this convention.
#
# Arguments:
#   $1 - folder name (basename, not full path)
#
# Prints:
#   Numeric ID string, or empty string if not found
extract_calibre_book_id() {
    local folder_name="$1"
    local id=""
    if [[ "$folder_name" =~ \(([0-9]+)\)$ ]]; then
        id="${BASH_REMATCH[1]}"
    fi
    printf '%s' "$id"
}

# book_already_has_pdf()
# Checks whether a Calibre book record already has at least one PDF format
# registered. Used to differentiate "already registered" from true errors,
# fixing Bug #6 from the original script.
#
# Arguments:
#   $1 - Calibre library path
#   $2 - numeric book ID
#
# Returns:
#   0  book has at least one PDF format
#   1  book has no PDF format (or metadata could not be read)
book_already_has_pdf() {
    local library="$1"
    local book_id="$2"
    calibredb show_metadata --library-path "$library" "$book_id" 2>/dev/null \
        | grep -iq "pdf"
}

# add_pdf_format()
# Calls calibredb to register one PDF as a format of the given book ID.
# Respects --dry-run and --force flags.
#
# Arguments:
#   $1 - Calibre library path
#   $2 - numeric book ID
#   $3 - absolute path to the PDF file
#
# Returns:
#   0  PDF registered successfully
#   1  calibredb reported an error or PDF was already registered
#   2  dry-run mode (no action taken, treated as success for counting)
add_pdf_format() {
    local library="$1"
    local book_id="$2"
    local pdf_path="$3"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run: calibredb add_format --library-path '${library}' ${book_id} '${pdf_path}'"
        return 2
    fi

    local add_flags=(--library-path "$library" "$book_id" "$pdf_path")

    # --dont-replace prevents overwriting when FORCE is not set.
    # When FORCE=true we omit it, letting calibredb replace the existing format.
    [[ "$FORCE" == "false" ]] && add_flags+=(--dont-replace)

    calibredb add_format "${add_flags[@]}" >/dev/null 2>&1
}

# process_author_folder()
# Processes all book subfolders for one author.
# Iterates over directories matching the Calibre "Title (ID)" pattern and
# registers any PDFs found inside each one.
#
# Arguments:
#   $1 - absolute path to the author folder
#   $2 - Calibre library root path
#
# Side-effects:
#   Increments REG_ADDED, REG_ALREADY, REG_NO_PDF, REG_ERROR counters
process_author_folder() {
    local author_dir="$1"
    local library="$2"
    local author_name
    author_name="$(basename "$author_dir")"

    log_info "Processing author: ${author_name}"
    printf '  Author: %s\n' "$author_name"

    # Iterate over subdirectories only (each = one book)
    local folder
    while IFS= read -r -d '' folder; do
        local folder_name
        folder_name="$(basename "$folder")"

        local book_id
        book_id="$(extract_calibre_book_id "$folder_name")"

        # Skip folders without a valid Calibre ID — they are not book records
        if [[ -z "$book_id" ]]; then
            log_debug "Skipping folder without Calibre ID: '${folder_name}'"
            continue
        fi

        # Collect PDFs inside this book folder (non-recursive)
        local -a pdfs
        mapfile -t pdfs < <(find "$folder" -maxdepth 1 -type f -iname "*.pdf" 2>/dev/null | sort)

        if [[ ${#pdfs[@]} -eq 0 ]]; then
            log_debug "No PDFs in '${folder_name}' (ID ${book_id})."
            REG_NO_PDF=$((REG_NO_PDF + 1))
            continue
        fi

        for pdf in "${pdfs[@]}"; do
            local pdf_name
            pdf_name="$(basename "$pdf")"
            printf '    ID %-5s → %-50s ' "$book_id" "$pdf_name"

            add_pdf_format "$library" "$book_id" "$pdf"
            local add_status=$?

            if [[ $add_status -eq 2 ]]; then
                # Dry-run branch: count as would-add
                printf '[DRY-RUN]\n'
                REG_ADDED=$((REG_ADDED + 1))
                continue
            fi

            if [[ $add_status -eq 0 ]]; then
                printf 'ADDED ✓\n'
                REG_ADDED=$((REG_ADDED + 1))
                continue
            fi

            # calibredb exited non-zero — determine if it's a real error or
            # simply "format already registered" (Bug #6 fix).
            if book_already_has_pdf "$library" "$book_id"; then
                printf 'already has PDF\n'
                REG_ALREADY=$((REG_ALREADY + 1))
            else
                # Non-zero exit AND no PDF found in metadata → genuine error
                printf 'ERROR ✗\n'
                log_error "calibredb failed for book ID ${book_id}, file '${pdf_name}'."
                REG_ERROR=$((REG_ERROR + 1))
                REG_ERRORS_LIST+=("ID=${book_id} | ${pdf}")
            fi
        done

    done < <(find "$author_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z)
}

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# run_register_formats()
# Main controller for the register operation.
# Validates the Calibre library, then processes author folders found either
# in the current directory or under a provided root.
#
# Reads globals:
#   LIBRARY_PATH, ROOT_DIR, DRY_RUN, VERBOSE, FORCE
#
# Returns:
#   EXIT_SUCCESS  if at least one PDF was added or already existed
#   EXIT_ERROR    if nothing was processed
run_register_formats() {
    validate_dependencies calibredb || exit "${EXIT_MISSING_DEP}"

    # When LIBRARY_PATH is empty, default to the parent of the current dir —
    # matching the original script's convention for running inside an author folder.
    if [[ -z "$LIBRARY_PATH" ]]; then
        LIBRARY_PATH="$(cd .. && pwd)"
        log_info "LIBRARY_PATH not specified; defaulting to parent directory: '${LIBRARY_PATH}'"
    fi

    validate_calibre_library "$LIBRARY_PATH" || exit "${EXIT_NOT_FOUND}"

    # The "root" for register is where author folders live.
    # If ROOT_DIR is set (e.g. from the menu), use it; otherwise use current dir.
    local scan_root="${ROOT_DIR:-$(pwd)}"
    validate_directory_exists "$scan_root" "Author scan root" || exit "${EXIT_NOT_FOUND}"

    log_section "📤  REGISTER PDF FORMATS  (Folder → Calibre)"
    printf '  Library : %s\n' "$LIBRARY_PATH"
    printf '  Scan    : %s\n' "$scan_root"
    [[ "$DRY_RUN"  == "true" ]] && printf '  Mode    : DRY-RUN (no changes will be made)\n'
    [[ "$FORCE"    == "true" ]] && printf '  Mode    : FORCE (will overwrite existing PDF formats)\n'
    printf '\n'

    # Counters
    REG_ADDED=0
    REG_ALREADY=0
    REG_NO_PDF=0
    REG_ERROR=0
    declare -ga REG_ERRORS_LIST=()

    # Determine whether scan_root itself is an author folder (contains book
    # subfolders with IDs) or a library root (contains author subfolders).
    # Heuristic: if a direct child directory contains "(N)" in its name,
    # scan_root is an author folder; otherwise treat each subdirectory as an author.
    local -a direct_children
    mapfile -t direct_children < <(find "$scan_root" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z | tr '\0' '\n')

    local is_author_dir=false
    for child in "${direct_children[@]}"; do
        if [[ "$(basename "$child")" =~ \([0-9]+\)$ ]]; then
            is_author_dir=true
            break
        fi
    done

    if [[ "$is_author_dir" == "true" ]]; then
        # scan_root is one author folder → process it directly
        process_author_folder "$scan_root" "$LIBRARY_PATH"
    else
        # scan_root contains multiple author folders → iterate over them
        local author_dir
        while IFS= read -r -d '' author_dir; do
            process_author_folder "$author_dir" "$LIBRARY_PATH"
            printf '\n'
        done < <(find "$scan_root" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null | sort -z)
    fi

    # Summary
    printf '\n'
    log_section "📊  REGISTER RESULTS"
    printf '  ✓  Added to Calibre    : %d\n' "$REG_ADDED"
    printf '  ℹ  Already had PDF     : %d\n' "$REG_ALREADY"
    printf '  ⏭  No PDF in folder   : %d\n' "$REG_NO_PDF"
    printf '  ✗  Real errors         : %d\n' "$REG_ERROR"

    if [[ "${#REG_ERRORS_LIST[@]}" -gt 0 ]]; then
        printf '\n  Books with errors:\n'
        for entry in "${REG_ERRORS_LIST[@]}"; do
            printf '    • %s\n' "$entry"
        done
    fi

    printf '\n  ⚠  Remember to CLOSE Calibre before running this operation.\n'

    [[ $((REG_ADDED + REG_ALREADY)) -gt 0 ]] && return "${EXIT_SUCCESS}" || return "${EXIT_ERROR}"
}
