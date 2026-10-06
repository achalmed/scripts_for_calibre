#!/usr/bin/env bash
# ==============================================================================
#  metadatos-pdf/lib/limpiar_json_huerfanos.sh — Localiza y (con --aplicar) borra los sidecar zotero_metadata.json huérfanos junto a los PDF de la biblioteca
# Localiza y (con --aplicar) borra los sidecar 'zotero_metadata.json' que el
# incrustador rival (scripts_for_zotero/script_inscrustar_metadatos_pdf)
# sembraba junto a los PDFs de la biblioteca. Con la política "Calibre manda"
# el estado de Zotero es derivado y esos JSON son huérfanos (auditoría A7).
#
# SEGURO POR DEFECTO: solo LISTA. Borra únicamente con --aplicar.
# ==============================================================================

[[ -n "${_LIMPIAR_JSON_HUERFANOS_SH_LOADED:-}" ]] && return 0
readonly _LIMPIAR_JSON_HUERFANOS_SH_LOADED=1

# run_limpiar_json_huerfanos()
# Recorre ROOT_DIR (o ORPHAN_JSON_ROOT si no se pasó --root) buscando ficheros
# con nombre ORPHAN_JSON_NAME y los lista. Con APPLY=true los borra uno a uno.
#
# Lee globals: ROOT_DIR, APPLY, ORPHAN_JSON_ROOT, ORPHAN_JSON_NAME
# Devuelve: EXIT_SUCCESS siempre que la búsqueda sea válida.
run_limpiar_json_huerfanos() {
    # main.sh rellena ROOT_DIR con el CWD por defecto (Fase 2); para esta acción
    # eso no sirve. Solo se respeta ROOT_DIR si el usuario pasó --root explícito;
    # si no, se usa la raíz de biblioteca del config (ORPHAN_JSON_ROOT).
    local raiz="$ORPHAN_JSON_ROOT"
    [[ "${ROOT_DIR_EXPLICITO:-false}" == "true" ]] && raiz="$ROOT_DIR"

    validate_directory_exists "$raiz" "Raíz de búsqueda" || exit "${EXIT_NOT_FOUND}"

    log_section "🧹  LIMPIAR JSON HUÉRFANOS  (${ORPHAN_JSON_NAME})"
    printf '  Raíz : %s\n' "$raiz"
    if [[ "${APPLY:-false}" == "true" ]]; then
        printf '  Modo : APLICAR (se borrarán los ficheros encontrados)\n\n'
    else
        printf '  Modo : SIMULACIÓN (solo se listan; usa --aplicar para borrar)\n\n'
    fi

    local -a huerfanos
    mapfile -t huerfanos < <(
        find "$raiz" -type f -name "$ORPHAN_JSON_NAME" 2>/dev/null | sort
    )

    local total="${#huerfanos[@]}"
    if [[ $total -eq 0 ]]; then
        log_info "No se encontró ningún '${ORPHAN_JSON_NAME}' bajo '${raiz}'."
        return "${EXIT_SUCCESS}"
    fi

    local borrados=0 errores=0 f
    for f in "${huerfanos[@]}"; do
        if [[ "${APPLY:-false}" == "true" ]]; then
            if rm -f "$f" 2>/dev/null; then
                printf '   🗑  %s\n' "$f"
                borrados=$((borrados + 1))
            else
                log_error "No se pudo borrar: '${f}'"
                errores=$((errores + 1))
            fi
        else
            printf '   • %s\n' "$f"
        fi
    done

    printf '\n'
    log_section "📊  RESULTADO"
    printf '  📄 Huérfanos encontrados : %d\n' "$total"
    if [[ "${APPLY:-false}" == "true" ]]; then
        printf '  🗑  Borrados              : %d\n' "$borrados"
        printf '  ✗  Errores               : %d\n' "$errores"
    else
        printf '  ⓘ  SIMULACIÓN: nada se borró. Ejecuta con --aplicar para borrar.\n'
    fi

    return "${EXIT_SUCCESS}"
}
