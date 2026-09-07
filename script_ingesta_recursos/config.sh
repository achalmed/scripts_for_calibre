#!/usr/bin/env bash
# config.sh — script_ingesta_recursos (F5.4, 2026-09-06)
# Ingesta a Calibre del material bibliográfico EXTERNO que vive en los cursos docentes
# (10 Class/areas/*/course_*/06_RECURSOS y 08_INVESTIGACION). Todo lo tunable está aquí.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS="${DOCS_ROOT:-$HOME/Documents}"
AREAS="$DOCS/10 Class/areas"
BIBLIOTECA="${QIR_BIBLIOTECA:-$DOCS/biblioteca}"
CALIBREDB="${CALIBREDB:-calibredb}"
LOCK_ESCRITURA_CALIBRE="$SCRIPT_DIR/../.lock_calibre_write"
BACKUPS_DIR="$SCRIPT_DIR/backups"; BACKUPS_CONSERVAR=3
REPORTES_DIR="$SCRIPT_DIR/reportes"
# Dónde se guardan los originales retirados de los cursos (reversible; UNDO los devuelve)
ORIGINALES_DIR="${QIR_ORIGINALES:-$DOCS/meta/reparaciones/F5.4_biblioteca_2026-09-06/originales}"
# Carpetas de curso que se escanean (relativas a course_NN/)
CARPETAS_ESCANEO=("06_RECURSOS" "08_INVESTIGACION")
# Etiquetas que reciben los libros añadidos (además de curso:<id>)
TAGS_BASE="academic_class,recurso_curso"
# Umbral: 'material' sin regla específica con ≥ este nº de páginas se propone ingestar
MIN_PAGINAS_LIBRO=100
# Autores "genéricos" de pdfinfo que NO se usan como autor (→ Desconocido, campaña de catalogación)
AUTORES_GENERICOS='^(lenovo|usuario|user|dncpr01|mtizon|luis|carolina|balabarca|hp|admin|windows|acer|toshiba)$'
# Si el autor del PDF contiene esto, el documento es propio y NO se ingesta
AUTOR_PROPIO='achalma'
