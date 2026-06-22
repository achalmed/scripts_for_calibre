#!/usr/bin/env bash
# ==============================================================================
# lib/embed_metadata.sh
# Reads Calibre metadata.opf files and embeds their fields into companion PDFs
# using exiftool. Processes the library recursively; each directory that
# contains a metadata.opf is treated as one "book folder".
# ==============================================================================

[[ -n "${_EMBED_METADATA_SH_LOADED:-}" ]] && return 0
readonly _EMBED_METADATA_SH_LOADED=1

# ---------------------------------------------------------------------------
# OPF parsing helpers
# ---------------------------------------------------------------------------

# sanitize_xml_entities()
# Converts HTML/XML character entities to their literal equivalents and trims
# surrounding whitespace. Must run on every raw value extracted from the OPF
# because Calibre sometimes writes entities inside dc:* elements.
#
# Arguments:
#   $1 - raw string that may contain XML entities
#
# Prints:
#   Sanitized string to stdout
sanitize_xml_entities() {
    local raw="$1"
    printf '%s' "$raw" \
        | sed \
            -e 's/&lt;/</g'   \
            -e 's/&gt;/>/g'   \
            -e 's/&amp;/\&/g' \
            -e 's/&quot;/"/g' \
            -e "s/&apos;/'/g" \
            -e "s/&#39;/'/g"  \
        | xargs 2>/dev/null \
        || printf ''
    # xargs is used solely to strip leading/trailing whitespace.
    # The 2>/dev/null suppresses "no input files" on empty strings — the
    # empty-string case is explicitly handled by callers checking [ -z ... ].
}

# extract_opf_field()
# Extracts a single metadata field from a Calibre metadata.opf file.
# Uses grep + sed rather than xmllint to avoid an extra dependency for simple
# single-line dc:* elements. Multi-line values are not supported by Calibre's
# OPF generator for these fields.
#
# Arguments:
#   $1 - field name: title | author | tags | publisher | language | date | description
#   $2 - absolute path to metadata.opf
#
# Prints:
#   Field value (sanitized) to stdout, or empty string if absent
extract_opf_field() {
    local field="$1"
    local opf_file="$2"
    local raw=""

    case "$field" in
        title)
            raw=$(grep -m1 '<dc:title>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:title>//;s/<\/dc:title>.*//')
            ;;
        author)
            # Prefer the opf:file-as attribute (canonical "Surname, Name" form).
            # Fall back to the element content when the attribute is absent,
            # which happens for single-name authors or older Calibre exports.
            raw=$(grep -m1 '<dc:creator' "$opf_file" 2>/dev/null \
                  | sed -n 's/.*opf:file-as="\([^"]*\)".*/\1/p')
            if [[ -z "$raw" ]]; then
                raw=$(grep -m1 '<dc:creator' "$opf_file" 2>/dev/null \
                      | sed -e 's/.*<dc:creator[^>]*>//;s/<\/dc:creator>.*//')
            fi
            ;;
        tags)
            # Multiple <dc:subject> elements → join with semicolons.
            raw=$(grep '<dc:subject>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:subject>//;s/<\/dc:subject>.*//' \
                  | paste -sd ";" -)
            ;;
        publisher)
            raw=$(grep -m1 '<dc:publisher>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:publisher>//;s/<\/dc:publisher>.*//')
            ;;
        language)
            raw=$(grep -m1 '<dc:language>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:language>//;s/<\/dc:language>.*//')
            ;;
        date)
            raw=$(grep -m1 '<dc:date>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:date>//;s/<\/dc:date>.*//')
            ;;
        description)
            raw=$(grep -m1 '<dc:description>' "$opf_file" 2>/dev/null \
                  | sed -e 's/.*<dc:description>//;s/<\/dc:description>.*//')
            ;;
    esac

    sanitize_xml_entities "$raw"
}

# has_minimum_metadata()
# A book folder is skippable only when BOTH title AND author are absent.
# Embedding partial metadata (e.g. only a title) is still useful and valid.
#
# Arguments:
#   $1 - title value
#   $2 - author value
#
# Returns:
#   0  at least one field is populated
#   1  both fields are empty → skip this folder
has_minimum_metadata() {
    local title="$1"
    local author="$2"
    [[ -n "$title" || -n "$author" ]]
}

# ---------------------------------------------------------------------------
# exiftool invocation
# ---------------------------------------------------------------------------

# build_exiftool_command()
# Assembles the exiftool argument array for one PDF.
# Only non-empty metadata fields are included — writing empty strings would
# overwrite existing tags with blanks, which is destructive.
#
# Arguments:
#   $1 - absolute path to the PDF
#   $2 - title
#   $3 - author
#   $4 - publisher
#   $5 - tags (semicolon-separated)
#   $6 - language
#   $7 - date
#
# Side-effect:
#   Populates the EXIFTOOL_CMD array in the caller's scope (use nameref or
#   call via a wrapper that reads the array).
_build_exiftool_args() {
    # Reset — reused across loop iterations
    EXIFTOOL_CMD=(exiftool -q -overwrite_original)

    local title="$1" author="$2" publisher="$3" tags="$4" language="$5" date="$6" pdf="$7"

    [[ -n "$title" ]]     && EXIFTOOL_CMD+=(-Title="$title")
    [[ -n "$author" ]]    && EXIFTOOL_CMD+=(-Author="$author")
    [[ -n "$publisher" ]] && EXIFTOOL_CMD+=(-PDF:Producer="$publisher")
    [[ -n "$tags" ]]      && EXIFTOOL_CMD+=(-Keywords="$tags")
    [[ -n "$language" ]]  && EXIFTOOL_CMD+=(-Language="$language")
    [[ -n "$date" ]]      && EXIFTOOL_CMD+=(-CreateDate="$date")

    # Strip tool-generated fields that Calibre does not use and that reveal
    # the authoring application (privacy + cleanliness).
    EXIFTOOL_CMD+=(-Creator= -CreatorTool=)

    EXIFTOOL_CMD+=("$pdf")
}

# embed_metadata_into_pdf()
# Runs exiftool for a single PDF file. Handles dry-run mode and captures
# exiftool's stderr separately so it appears in the log.
#
# Arguments:
#   $1 - pdf path
#   remaining - all metadata fields (title author publisher tags language date)
#
# Returns:
#   0  success or dry-run
#   1  exiftool reported an error
embed_metadata_into_pdf() {
    local pdf="$1" title="$2" author="$3" publisher="$4" tags="$5" language="$6" date="$7"

    validate_file_writable "$pdf"
    local writable_status=$?
    if [[ $writable_status -eq "${EXIT_NOT_FOUND}" ]]; then
        log_warn "PDF disappeared before processing: '${pdf}'"
        return 1
    elif [[ $writable_status -eq "${EXIT_NO_PERMISSION}" ]]; then
        log_error "PDF is not writable: '${pdf}'"
        return 1
    fi

    _build_exiftool_args "$title" "$author" "$publisher" "$tags" "$language" "$date" "$pdf"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY-RUN] Would run: ${EXIFTOOL_CMD[*]}"
        return 0
    fi

    local err_tmp
    err_tmp="$(mktemp)" || { log_error "Cannot create temp file for exiftool stderr."; return 1; }

    if "${EXIFTOOL_CMD[@]}" 2>"$err_tmp"; then
        rm -f "$err_tmp"
        return 0
    else
        log_error "exiftool failed on '$(basename "$pdf")':"
        # Log the exiftool error output without suppressing it
        while IFS= read -r err_line; do
            log_error "  exiftool: ${err_line}"
        done < "$err_tmp"
        rm -f "$err_tmp"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Directory-level processing
# ---------------------------------------------------------------------------

# process_book_folder()
# Processes one directory: reads its metadata.opf, validates the fields,
# finds all PDFs, and embeds the metadata into each one.
#
# Arguments:
#   $1 - absolute path to the book folder (must contain metadata.opf)
#   $2 - position label for progress display (e.g. "3/42")
#
# Side-effects:
#   Increments EMBED_OK, EMBED_ERROR, EMBED_SKIP counters
process_book_folder() {
    local dir="$1"
    local progress="$2"
    local opf="${dir}/metadata.opf"
    local folder_label
    folder_label="$(basename "$dir")"

    printf '\n📁 [%s] %s\n' "$progress" "$folder_label"
    log_debug "Processing folder: ${dir}"

    if [[ ! -r "$opf" ]]; then
        log_warn "Cannot read metadata.opf in '${dir}'. Skipping."
        EMBED_SKIP=$((EMBED_SKIP + 1))
        return
    fi

    # Extract all metadata fields
    local title author tags publisher language date
    title=$(extract_opf_field "title" "$opf")
    author=$(extract_opf_field "author" "$opf")
    tags=$(extract_opf_field "tags" "$opf")
    publisher=$(extract_opf_field "publisher" "$opf")
    language=$(extract_opf_field "language" "$opf")
    date=$(extract_opf_field "date" "$opf")

    # Validate: skip only when there is truly nothing useful to write
    if ! has_minimum_metadata "$title" "$author"; then
        log_warn "No usable metadata in '${opf}' (title and author both empty). Skipping."
        EMBED_SKIP=$((EMBED_SKIP + 1))
        return
    fi

    # Display found metadata
    log_debug "  Title     : ${title:-<empty>}"
    log_debug "  Author    : ${author:-<empty>}"
    log_debug "  Publisher : ${publisher:-<empty>}"
    log_debug "  Tags      : ${tags:-<empty>}"
    log_debug "  Language  : ${language:-<empty>}"
    log_debug "  Date      : ${date:-<empty>}"
    [[ -n "$title" ]]     && printf '   • Title    : %s\n' "$title"
    [[ -n "$author" ]]    && printf '   • Author   : %s\n' "$author"
    [[ -n "$publisher" ]] && printf '   • Publisher: %s\n' "$publisher"

    # Find PDFs in this directory only (non-recursive: each folder = one book)
    local -a pdfs
    mapfile -t pdfs < <(find "$dir" -maxdepth 1 -type f -iname "*.pdf" 2>/dev/null | sort)

    if [[ ${#pdfs[@]} -eq 0 ]]; then
        log_info "   No PDF files found in '${folder_label}'."
        EMBED_SKIP=$((EMBED_SKIP + 1))
        return
    fi

    printf '   PDFs found: %d\n' "${#pdfs[@]}"

    for pdf in "${pdfs[@]}"; do
        local pdf_name
        pdf_name="$(basename "$pdf")"
        printf '      → %-50s ' "$pdf_name"

        if embed_metadata_into_pdf "$pdf" "$title" "$author" "$publisher" "$tags" "$language" "$date"; then
            printf '✓\n'
            EMBED_OK=$((EMBED_OK + 1))
        else
            printf '✗\n'
            EMBED_ERROR=$((EMBED_ERROR + 1))
            EMBED_ERRORS_LIST+=("${pdf}")
        fi
    done
}

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# run_embed_metadata()
# Main controller for the embed operation.
# Discovers all book folders under ROOT_DIR and processes each one.
#
# Reads globals:
#   ROOT_DIR, DRY_RUN, VERBOSE
#
# Returns:
#   EXIT_SUCCESS  if at least one PDF was processed successfully
#   EXIT_ERROR    if no PDFs were processed
run_embed_metadata() {
    validate_dependencies exiftool || exit "${EXIT_MISSING_DEP}"
    validate_directory_exists "$ROOT_DIR" "Root directory" || exit "${EXIT_NOT_FOUND}"

    log_section "📥  EMBED METADATA  (OPF → PDF)"
    printf '  Root : %s\n' "$ROOT_DIR"
    [[ "$DRY_RUN" == "true" ]] && printf '  Mode : DRY-RUN (no files will be modified)\n'
    printf '\n'

    # Counters — local to this run
    EMBED_OK=0
    EMBED_ERROR=0
    EMBED_SKIP=0
    declare -ga EMBED_ERRORS_LIST=()

    log_info "Scanning for metadata.opf files under '${ROOT_DIR}'..."
    local -a opf_dirs
    mapfile -t opf_dirs < <(
        find "$ROOT_DIR" -type f -name "metadata.opf" -print0 2>/dev/null \
        | xargs -0 -r -n1 dirname 2>/dev/null \
        | sort -u
    )

    local total_dirs="${#opf_dirs[@]}"
    if [[ $total_dirs -eq 0 ]]; then
        log_warn "No metadata.opf files found under '${ROOT_DIR}'."
        return "${EXIT_ERROR}"
    fi
    log_info "Found ${total_dirs} book folder(s) with metadata.opf."

    local i=0
    for dir in "${opf_dirs[@]}"; do
        i=$((i + 1))
        process_book_folder "$dir" "${i}/${total_dirs}"
    done

    # Summary
    printf '\n'
    log_section "📊  EMBED RESULTS"
    printf '  ✓  Successfully embedded : %d\n' "$EMBED_OK"
    printf '  ✗  Errors                : %d\n' "$EMBED_ERROR"
    printf '  ⏭  Skipped               : %d\n' "$EMBED_SKIP"
    printf '  📁 Total folders scanned : %d\n' "$total_dirs"

    if [[ "${#EMBED_ERRORS_LIST[@]}" -gt 0 ]]; then
        printf '\n  Files with errors:\n'
        for f in "${EMBED_ERRORS_LIST[@]}"; do
            printf '    • %s\n' "$f"
        done
    fi

    [[ $EMBED_OK -gt 0 ]] && return "${EXIT_SUCCESS}" || return "${EXIT_ERROR}"
}
