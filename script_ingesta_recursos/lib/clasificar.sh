#!/usr/bin/env bash
# lib/clasificar.sh — escanea los cursos y produce el TSV de candidatos con una decisión propuesta.
# Columnas: decision  clase  paginas  MB  autor_pdf  titulo  curso  ruta
# decision: ingestar (externo: va a Calibre) · omitir (propio/estudiantes/plantillas/admin) · revisar (ambiguo)
curso_id() { # $1 = dir del curso → id de temario.yml
    local ty="$1/temario.yml"
    [ -f "$ty" ] && awk -F': *' '/^curso:/{print $2; exit}' "$ty" || basename "$1"
}
clase_de() { # $1 ruta relativa dentro del curso
    case "$1" in
        05_ESTUDIANTES/*) echo estudiante;; *_ESTANDARIZACION/*|*/_backup*) echo backup_reorg;;
        */plantillas/*|*/imagenes/*|*/images/*) echo plantilla;;
        00_ADMINISTRACION/*|*silabo*|*syllabus*|*temario*) echo administrativo;;
        */informacion_del_curso/*|*/ejercicios/*|*/actividades/*|*/homeworks/*) echo propio_curso;;
        08_INVESTIGACION/referencias/*) echo referencia;;
        */lectura*) echo lectura;; */talleres/*) echo taller;;
        */presentaciones/*|*deck_completo*|*slide*) echo diapositivas;;
        */unidades/*) echo unidad;; *) echo material;;
    esac
}
decision_de() { # $1 clase $2 paginas $3 autor
    local clase="$1" pags="${2:-0}" autor="$3"
    if printf '%s' "$autor" | grep -qiE "$AUTOR_PROPIO"; then echo omitir; return; fi
    case "$clase" in
        estudiante|backup_reorg|plantilla|administrativo|propio_curso) echo omitir;;
        referencia|lectura|taller|unidad|diapositivas) echo ingestar;;
        material) [ "$pags" -ge "$MIN_PAGINAS_LIBRO" ] && echo ingestar || echo revisar;;
        *) echo revisar;;
    esac
}
titulo_de() { # $1 archivo → título limpio (Title del PDF si es útil; si no, nombre sin numeración)
    local t; t="$(pdfinfo "$1" 2>/dev/null | awk -F': *' '/^Title/{print $2}' || true)"
    if [ -z "$t" ] || printf '%s' "$t" | grep -qiE '^(untitled|documento|presentaci[oó]n de powerpoint|powerpoint presentation|t[ií]tulo principal|mesa de trabajo.*|microsoft word.*|slide 1|diapositiva 1|instituto nacional de estadistica.*|index|topics|.*\.(docx?|pptx?|tex))$'; then
        t="$(basename "$1" .pdf | sed -E 's/^[0-9]+([ ._-][0-9]+)*[ ._-]+//; s/_/ /g')"
    fi
    printf '%s' "$t" | sed 's/\t/ /g'
}
autor_de() { # $1 archivo → autor o "Desconocido"
    local a; a="$(pdfinfo "$1" 2>/dev/null | awk -F': *' '/^Author/{print $2}' | sed 's/\t/ /g' || true)"
    if [ -z "$a" ] || printf '%s' "$a" | grep -qiE "$AUTORES_GENERICOS"; then a="Desconocido"; fi
    printf '%s' "$a"
}
escanear() { # → escribe TSV en $1
    local out="$1"; printf "decision\tclase\tpaginas\tMB\tautor_pdf\ttitulo\tcurso\truta\n" > "$out"
    local curso carpeta f rel clase pags mb autor titulo dec cid
    for curso in "$AREAS"/Academic_Class-*/course_*/; do
        cid="$(curso_id "${curso%/}")"
        for carpeta in "${CARPETAS_ESCANEO[@]}"; do
            [ -d "$curso$carpeta" ] || continue
            while IFS= read -r -d '' f; do
                rel="${f#$curso}"; clase="$(clase_de "$rel")"
                pags="$(pdfinfo "$f" 2>/dev/null | awk -F': *' '/^Pages/{print $2}' || true)"; mb="$(du -m "$f" | cut -f1 || true)"
                autor="$(autor_de "$f")"; titulo="$(titulo_de "$f")"; dec="$(decision_de "$clase" "${pags:-0}" "$autor")"
                printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$dec" "$clase" "${pags:-0}" "$mb" "$autor" "$titulo" "$cid" "${f#$DOCS/}" >> "$out"
            done < <(find "$curso$carpeta" -type f -iname '*.pdf' -print0)
        done
    done
}
