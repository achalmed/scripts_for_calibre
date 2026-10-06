#!/usr/bin/env bash
# script_sincronizar_zotero/lib/cli.sh — Argument parsing, dependency checks and --help text

# show_help()
# Prints usage and exits.
show_help() {
    cat <<EOF
$TOOL_NAME v$VERSION - Sincronizador bidireccional de metadatos entre la
biblioteca Calibre y Zotero para los libros enlazados via ZMI (#zotero_key).

Que hace (segun el contrato del prompt de catalogacion y la politica
"Calibre manda" decidida por el usuario):

  Calibre -> Zotero   titulo, autores*, fecha, editorial, ISBN, serie,
                      paginas, idioma, tags, edicion, abstract (comments).
                      * autores: solo si Zotero esta vacio/Unknown o difiere;
                        si Zotero tiene MAS autores (coautores), se conserva
                        y solo se reporta. Formatos por sistema respetados:
                        Zotero "Apellido, Nombre" / Calibre "Nombre, Apellido".
  Zotero -> Calibre   relleno de vacios (año placeholder 0101, ISBN) y
                      poblacion de las columnas espejo zotero_* de Calibre.
                      Titulo y autor JAMAS se escriben en Calibre.
  Reparacion          rutas de adjuntos rotas en Zotero (carpetas renombradas)
                      y linea {path} desactualizada en el campo Extra.

Simulacion POR DEFECTO: sin --aplicar solo genera reportes.

USO:
  ./main.sh [opciones]

OPCIONES:
  --aplicar        Escribe los cambios (requiere Calibre Y Zotero cerrados;
                   hace copia previa de ambas bases y verifica integridad).
  --limite N       Procesa solo los primeros N pares enlazados (prueba).
  --ids a,b,c      Solo esos ids de libro de Calibre (depuracion).
  --verbose        Traza detallada.
  -h, --help       Esta ayuda.

EJEMPLOS:
  ./main.sh                      # simulacion completa + reportes
  ./main.sh --limite 20          # simulacion sobre 20 pares
  ./main.sh --aplicar            # aplicar (con ambas apps cerradas)

Salida: $REPORT_DIR_BASENAME/sync_<fecha>.{tsv,md} y resumen en pantalla.
Estado: $STATE_DIR_BASENAME/ultimo_sync.json (snapshot para diffs futuros).
EOF
    exit 0
}

# parse_arguments()
# Populates the runtime option globals from argv.
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --aplicar) APPLY_CHANGES=true; shift ;;
            --limite)  LIMIT="${2:?--limite requiere un numero}"; shift 2 ;;
            --ids)     ONLY_IDS="${2:?--ids requiere una lista}"; shift 2 ;;
            --verbose) VERBOSE=true; shift ;;
            -h|--help) show_help ;;
            *) log_error "Opcion desconocida: $1 (usa --help)"; exit 2 ;;
        esac
    done
    [[ "$LIMIT" =~ ^[0-9]+$ ]] || { log_error "--limite debe ser un entero"; exit 2; }
}

# check_dependencies()
# Verifies the external commands and databases the tool relies on.
check_dependencies() {
    local missing=()
    for cmd in "$CORE_PYTHON" calibredb calibre-debug; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Faltan dependencias: ${missing[*]}"
        exit 1
    fi
    validate_database "$CALIBRE_DB" "books"
    validate_database "$ZOTERO_DB" "items"
}
