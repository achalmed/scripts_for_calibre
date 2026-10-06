#!/usr/bin/env bash
# catalogacion/lib/clasificador.sh — Handling of the #clasificador enumerated custom
# column: live enum loading, accent normalization and validation.
# Calibre rejects enum values not present in the column definition, so
# invalid values must be filtered out before calling calibredb.

# Populated by load_clasificador_enum(); consulted by is_valid_clasificador().
CLASIF_ENUM=""

# load_clasificador_enum()
# Reads the allowed enum values from metadata.db so that extending the
# enum in Calibre's preferences takes effect on the next run without
# editing this tool. Falls back to the snapshot in config.sh.
#
# Outputs:
#   Sets the global CLASIF_ENUM as "|value1|value2|...|"
load_clasificador_enum() {
    local live=""
    if [[ -x "$CORE_PYTHON" ]]; then
        # The enum lives as JSON inside custom_columns.display; python
        # parses it reliably (values contain accents and spaces). sql_ro: lib/leer.sh.
        live=$(sql_ro "$CALIBRE_LIBRARY/metadata.db" \
            "SELECT display FROM custom_columns WHERE label='clasificador';" \
            | "$CORE_PYTHON" -c 'import sys,json; print("|".join(json.load(sys.stdin)["enum_values"]))' \
            2>/dev/null) || live=""  # unreadable DB → silent fallback below
    fi
    if [[ -n "$live" ]]; then
        CLASIF_ENUM="|${live}|"
        log_debug "Enum de clasificador leído en vivo de metadata.db"
    else
        CLASIF_ENUM="$CLASIF_ENUM_FALLBACK"
        log_warn "No se pudo leer el enum en vivo; usando la lista fija de respaldo."
    fi
}

# normalize_clasificador()
# The cataloging prompt writes classifier values without accents, but the
# Calibre enum stores them accented; map the known variants.
#
# Arguments:
#   $1 - Raw classifier value from the TSV
# Outputs:
#   Prints the normalized value
normalize_clasificador() {
    case "$1" in
        "Practica")             echo "Práctica" ;;
        "Practica calificada")  echo "Práctica calificada" ;;
        "Practica dirigida")    echo "Práctica dirigida" ;;
        "Modulo")               echo "Módulo" ;;
        "Guia")                 echo "Guía" ;;
        "Capitulo")             echo "Capítulo" ;;
        "Capitulo de libro")    echo "Capítulo de libro" ;;
        "Caso practico")        echo "Caso práctico" ;;
        "Presentacion")         echo "Presentación" ;;
        "Evaluacion")           echo "Evaluación" ;;
        "Sesion")               echo "Sesión" ;;
        "Silabus")              echo "Sílabus" ;;
        "Bibliografia")         echo "Bibliografía" ;;
        "Monografia")           echo "Monografía" ;;
        "Infografia")           echo "Infografía" ;;
        "Grabacion")            echo "Grabación" ;;
        "Resolucion")           echo "Resolución" ;;
        "Transcripcion")        echo "Transcripción" ;;
        "Numero")               echo "Número" ;;
        "Trabajo practico")     echo "Trabajo práctico" ;;
        "Articulo complementario") echo "Artículo complementario" ;;
        "Articulo de revista")  echo "Artículo de revista" ;;
        "Guia de estudio")      echo "Guía de estudio" ;;
        "Informe tecnico")      echo "Informe técnico" ;;
        *)                      unidad_docente "$1"; return ;;
    esac | { read -r v; unidad_docente "$v"; }
}

# unidad_docente()
# Arguments:
#   $1 - Normalized classifier value
# Outputs:
#   El valor del vocabulario de unidad docente (ola 2b, P3a; modelo-de-metadatos.md §3.3) si el valor es docente;
#   si no, el mismo valor (los no docentes se conservan).
unidad_docente() {
    case "$1" in
        "Sesión"|"Clase"|"Notas de sesion"|"Notas de sesión") echo "sesion" ;;
        "Tema") echo "tema" ;;
        "Capítulo"|"Parte") echo "capitulo" ;;
        "Lectura"|"Lectura obligatoria"|"Artículo complementario"|"Material complementario") echo "lectura" ;;
        "Apuntes de clase"|"Apuntes de historia"|"Apuntes de estudio"|"Handout") echo "apuntes" ;;
        "Módulo") echo "modulo" ;;
        "Unidad") echo "unidad" ;;
        "Semana") echo "semana" ;;
        "Sílabus"|"Programa") echo "silabo" ;;
        "Taller") echo "taller" ;;
        "Ejercicio"|"Ejercicios resueltos"|"Solucionario"|"Guía de estudio"|"Recurso educativo") echo "ejercicios" ;;
        "Evaluación") echo "evaluacion" ;;
        *) echo "$1" ;;
    esac
}

# is_valid_clasificador()
# Arguments:
#   $1 - Normalized classifier value
# Returns:
#   0 when the value exists in the enum, 1 otherwise
is_valid_clasificador() {
    [[ "$CLASIF_ENUM" == *"|$1|"* ]]
}
