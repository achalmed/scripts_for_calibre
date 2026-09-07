#!/usr/bin/env bash
# config.sh — script_ingesta_recursos. Todo lo editable vive aquí; lib/ no lleva rutas ni valores fijos.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS="${DOCS_ROOT:-$HOME/Documents}"
AREAS="$DOCS/10 Class/areas"
BIBLIOTECA="${QIR_BIBLIOTECA:-$DOCS/biblioteca}"
CALIBREDB="${CALIBREDB:-calibredb}"
LOCK_ESCRITURA_CALIBRE="$SCRIPT_DIR/../.lock_calibre_write"
BACKUPS_DIR="$SCRIPT_DIR/backups"; BACKUPS_CONSERVAR=3
REPORTES_DIR="$SCRIPT_DIR/reportes"
CATALOGACION_DIR="$SCRIPT_DIR/../script_catalogacion_biblioteca"   # hogar canónico de fichas y resumen_catalogacion.tsv
# A dónde se retira el original del curso (reversible con UNDO.sh de la reparación)
ORIGINALES_DIR="${QIR_ORIGINALES:-$DOCS/meta/reparaciones/F5.4_biblioteca_2026-09-06/originales}"
# Carpetas del estándar 00–09 que contienen material externo candidato
CARPETAS_ESCANEO=("06_RECURSOS" "08_INVESTIGACION")
# Cursos que NO se escanean (material de estudiante o administrativo que no es bibliografía; decisión D2)
CURSOS_EXCLUIDOS=("Academic_Class-Languages/course_00_curso_base")
# Un PDF de menos páginas en carpetas ambiguas se manda a revisar
MIN_PAGINAS_LIBRO=100
# Autor del PDF que no significa nada (cuentas de Windows, iniciales de digitadores…)
AUTORES_GENERICOS='^(lenovo|usuario|user|dncpr01|mtizon|luis|carolina|balabarca|hp|admin|windows|acer|toshiba|personal autorizado|win98|andres|jorge)$'
# Autor del PDF que identifica material propio (no va a Calibre)
AUTOR_PROPIO='achalma'
# Convención de la biblioteca para lo anónimo (script_catalogacion_biblioteca eliminó «Desconocido»)
AUTOR_DESCONOCIDO="Unknown"
# Duplicado = mismo título normalizado y páginas iguales (±TOLERANCIA) que un libro ya catalogado
DEDUPE_TOLERANCIA_PAGINAS=0
