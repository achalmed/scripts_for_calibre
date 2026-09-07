#!/usr/bin/env bash
# lib/cli.sh - Argument parsing and help text.

# show_help()
# Prints usage information (Spanish, per project convention).
show_help() {
    cat <<EOF
Uso: ./main.sh [OPCIONES]

Aplica a la biblioteca Calibre los metadatos catalogados en
${TSV_BASENAME} (libros sin autor identificados). Por defecto SIMULA:
imprime los comandos calibredb sin ejecutarlos.

Opciones:
  --aplicar        Ejecuta los cambios de verdad (requiere Calibre cerrado)
  --dry-run        Fuerza la simulación (modo por defecto)
  --solo-alta      Procesa solo filas con confianza=alta
  --ids LISTA      Procesa solo los ids indicados (separados por coma)
  -v, --verbose    Muestra trazas por fila (nivel DEBUG)
  -h, --help       Muestra esta ayuda
  --version        Muestra la versión

Ejemplos:
  ./main.sh                      # simular todo
  ./main.sh --solo-alta          # simular solo confianza alta
  ./main.sh --aplicar            # aplicar todo (Calibre cerrado)
  ./main.sh --aplicar --solo-alta
  ./main.sh --aplicar --ids 10011,10012   # solo dos libros recién ingresados

Códigos de salida: 0 éxito · 1 error general · 2 argumentos ·
3 archivo no encontrado · 5 dependencia faltante
EOF
}

# parse_arguments()
# Parses CLI flags into the global option variables declared in config.sh.
#
# Arguments:
#   $@ - Raw CLI arguments
# Returns:
#   0 on success; exits 2 on unknown flag or conflicting flags
parse_arguments() {
    local dry_run_requested=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --aplicar)    APPLY_CHANGES=true; shift ;;
            --dry-run)    dry_run_requested=true; shift ;;
            --solo-alta)  ONLY_HIGH_CONFIDENCE=true; shift ;;
            --ids)
                [[ $# -ge 2 && "$2" =~ ^[0-9]+(,[0-9]+)*$ ]] || { log_error "--ids necesita una lista como 10011,10012"; exit 2; }
                ONLY_IDS=",$2,"; shift 2 ;;
            --verbose|-v) VERBOSE=true; shift ;;
            --help|-h)    show_help; exit 0 ;;
            --version)    printf '%s %s\n' "$TOOL_NAME" "$VERSION"; exit 0 ;;
            *)
                log_error "Argumento desconocido: $1"
                show_help >&2
                exit 2 ;;
        esac
    done
    if [[ "$dry_run_requested" == true && "$APPLY_CHANGES" == true ]]; then
        log_error "--dry-run y --aplicar son incompatibles."
        exit 2
    fi
}
