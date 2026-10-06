#!/usr/bin/env bash
# script_verificar_metadatos/lib/cli.sh — Argument parsing, dependency checks and --help text

# show_help()
# Prints usage and exits.
show_help() {
    cat <<EOF
$TOOL_NAME v$VERSION - Verifica metadatos de la biblioteca Calibre contra
bases bibliograficas publicas (OpenLibrary) y reporta discrepancias.

Esta herramienta es de SOLO LECTURA: nunca escribe en Calibre. Genera un
reporte (TSV + Markdown) con las diferencias entre lo que tienes y lo que
dicen las fuentes, para que TU decidas que corregir a mano. Nunca propone
cambiar titulo ni autor (Zotero enlaza por carpeta y los perderia).

USO:
  ./main.sh [opciones]

OPCIONES:
  --modo isbn      Verifica solo los libros con identificador fiable
                   (ISBN/Google/Amazon/Goodreads). Coincidencia exacta.
                   Es el modo por defecto.
  --modo titulo    Para los libros publicados (Item type = Book en config.sh)
                   SIN identificador, busca por titulo+autor (coincidencia
                   aproximada; se marca el nivel de confianza). Complementa al
                   modo isbn: no re-verifica lo que aquel ya cubrio.
  --limite N       Procesa como maximo N candidatos (util para pruebas).
  --ids a,b,c      Verifica solo esos ids de libro (depuracion).
  --verbose        Traza cada consulta.
  -h, --help       Muestra esta ayuda.

EJEMPLOS:
  ./main.sh --limite 5              # prueba rapida sobre 5 libros con ISBN
  ./main.sh --modo isbn            # todos los libros con identificador
  ./main.sh --modo titulo          # ademas busca por titulo+autor
  ./main.sh --ids 425,739          # solo esos dos libros

Salida: $REPORT_DIR_BASENAME/discrepancias_<fecha>.{tsv,md}
EOF
    exit 0
}

# parse_arguments()
# Populates the runtime option globals from argv.
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --modo)    MODE="${2:?--modo requiere un valor: isbn|titulo}"; shift 2 ;;
            --limite)  LIMIT="${2:?--limite requiere un numero}"; shift 2 ;;
            --ids)     ONLY_IDS="${2:?--ids requiere una lista}"; shift 2 ;;
            --verbose) VERBOSE=true; shift ;;
            -h|--help) show_help ;;
            *) log_error "Opcion desconocida: $1 (usa --help)"; exit 2 ;;
        esac
    done
    case "$MODE" in
        isbn|titulo) ;;
        *) log_error "Modo invalido: $MODE (usa isbn o titulo)"; exit 2 ;;
    esac
    [[ "$LIMIT" =~ ^[0-9]+$ ]] || { log_error "--limite debe ser un entero"; exit 2; }
}

# check_dependencies()
# Verifies the external commands the tool relies on are present.
# (curl NO se chequea: el core Python hace las peticiones con urllib, no curl.)
check_dependencies() {
    local missing=()
    for cmd in "$CORE_PYTHON"; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Faltan dependencias: ${missing[*]}"
        exit 1
    fi
    [[ -r "$METADATA_DB" ]] || { log_error "No puedo leer $METADATA_DB"; exit 1; }
}
