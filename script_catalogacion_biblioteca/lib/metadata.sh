#!/usr/bin/env bash
# lib/metadata.sh - Domain logic: TSV row processing, calibredb argument
# construction and execution/simulation, plus the final summary.

# Run counters (read by print_summary).
TOTAL_ROWS=0
APPLIED_ROWS=0
SKIPPED_LOW_CONFIDENCE=0
OMITTED_CLASIFICADORES=()

# map_language_to_code()
# The TSV stores Calibre-style full language names; calibredb expects
# ISO 639-2 codes.
#
# Arguments:
#   $1 - Language name from the TSV
# Outputs:
#   Prints the ISO code (or the input untouched when unknown)
map_language_to_code() {
    case "$1" in
        Spanish|Español|spanish)       echo "spa" ;;
        English|english)               echo "eng" ;;
        Portuguese|Português|portuguese) echo "por" ;;
        *)                             echo "$1" ;;
    esac
}

# build_field_arguments()
# Translates one TSV row into calibredb "-f field:value" pairs. Empty
# fields are skipped so existing metadata is never blanked out.
#
# Arguments:
#   $1..$10 - id autores titulo tipo_zotero clasificador editorial fecha
#             identificador idioma tags
# Outputs:
#   Sets the global FIELD_ARGS array
build_field_arguments() {
    local id=$1 autores=$2 titulo=$3 tipo_zotero=$4 clasificador=$5
    local editorial=$6 fecha=$7 identificador=$8 idioma=$9 tags=${10}
    FIELD_ARGS=()
    [[ -n "$autores" ]]   && FIELD_ARGS+=(-f "authors:$autores")
    [[ -n "$titulo" ]]    && FIELD_ARGS+=(-f "title:$titulo")
    [[ -n "$editorial" ]] && FIELD_ARGS+=(-f "publisher:$editorial")
    [[ -n "$fecha" ]]     && FIELD_ARGS+=(-f "pubdate:$fecha")
    [[ -n "$tags" ]]      && FIELD_ARGS+=(-f "tags:$tags")
    [[ -n "$idioma" ]]    && FIELD_ARGS+=(-f "languages:$(map_language_to_code "$idioma")")
    # "tipo:valor" is required by calibredb's identifier syntax; skip malformed ones.
    [[ -n "$identificador" && "$identificador" == *:* ]] \
        && FIELD_ARGS+=(-f "identifiers:$identificador")
    [[ -n "$tipo_zotero" ]] && FIELD_ARGS+=(-f "#item_type:$tipo_zotero")
    append_clasificador_argument "$id" "$clasificador"
}

# append_clasificador_argument()
# Adds #clasificador when the (normalized) value exists in the enum;
# otherwise records the omission for the summary report.
#
# Arguments:
#   $1 - Book id
#   $2 - Raw classifier value
append_clasificador_argument() {
    local id=$1 raw=$2 normalized
    [[ -n "$raw" ]] || return 0
    normalized=$(normalize_clasificador "$raw")
    if is_valid_clasificador "$normalized"; then
        FIELD_ARGS+=(-f "#clasificador:$normalized")
    else
        OMITTED_CLASIFICADORES+=("$id: $raw")
    fi
}

# run_calibredb()
# Executes the command, or prints it quoted when simulating.
#
# Arguments:
#   $@ - Full calibredb command
run_calibredb() {
    if [[ "$APPLY_CHANGES" == true ]]; then
        "$@"
    else
        printf '[SIMULACIÓN] '; printf '%q ' "$@"; printf '\n'
    fi
}

# process_tsv_rows()
# Reads the TSV and applies (or simulates) one calibredb call per row.
#
# Arguments:
#   $1 - Path to the TSV file
process_tsv_rows() {
    local tsv_path=$1
    local id autores titulo tipo_zotero clasificador editorial fecha
    local identificador idioma tags confianza nota
    # A literal tab in IFS is "IFS whitespace" in Bash and collapses
    # consecutive empty fields, misaligning columns; translating tabs to
    # the non-whitespace separator \037 preserves empty fields.
    while IFS=$'\037' read -r id autores titulo tipo_zotero clasificador \
            editorial fecha identificador idioma tags confianza nota; do
        [[ "$id" == "id" || -z "$id" ]] && continue
        [[ -n "$ONLY_IDS" && "$ONLY_IDS" != *",$id,"* ]] && continue
        TOTAL_ROWS=$((TOTAL_ROWS + 1))
        if [[ "$ONLY_HIGH_CONFIDENCE" == true && "$confianza" != "alta" ]]; then
            SKIPPED_LOW_CONFIDENCE=$((SKIPPED_LOW_CONFIDENCE + 1))
            log_debug "Fila $id omitida (confianza=$confianza)"
            continue
        fi
        build_field_arguments "$id" "$autores" "$titulo" "$tipo_zotero" \
            "$clasificador" "$editorial" "$fecha" "$identificador" "$idioma" "$tags"
        [[ ${#FIELD_ARGS[@]} -eq 0 ]] && continue
        run_calibredb calibredb set_metadata --with-library "$CALIBRE_LIBRARY" \
            "$id" "${FIELD_ARGS[@]}"
        APPLIED_ROWS=$((APPLIED_ROWS + 1))
    done < <(tr '\t' '\037' < "$tsv_path")
}

# print_summary()
# Reports counters and every classifier omitted for not being in the enum.
print_summary() {
    local mode="simulados"
    [[ "$APPLY_CHANGES" == true ]] && mode="ejecutados"
    echo
    log_info "===== RESUMEN ====="
    log_info "Filas procesadas: $TOTAL_ROWS"
    log_info "Comandos $mode: $APPLIED_ROWS"
    [[ "$ONLY_HIGH_CONFIDENCE" == true ]] \
        && log_info "Omitidas por confianza != alta: $SKIPPED_LOW_CONFIDENCE"
    if [[ ${#OMITTED_CLASIFICADORES[@]} -gt 0 ]]; then
        log_warn "Clasificadores fuera del enum de Calibre (campo omitido; amplía el enum y re-ejecuta):"
        printf '  %s\n' "${OMITTED_CLASIFICADORES[@]}" >&2
    fi
    [[ "$APPLY_CHANGES" == false ]] \
        && log_info "Nada se modificó. Ejecuta con --aplicar (con Calibre cerrado) para escribir."
    # Without this, the guard above returns 1 when applying and, as the
    # last command of main(), turns a successful run into exit code 1.
    return 0
}
