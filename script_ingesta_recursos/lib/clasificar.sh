#!/usr/bin/env bash
# lib/clasificar.sh — escanea los cursos y produce el TSV de candidatos con una decisión propuesta.
# Columnas: decision  clase  paginas  MB  autor  titulo  curso  ruta  duplicado_id
# decision: ingestar (externo nuevo: va a Calibre) · duplicado (ya está en Calibre: solo se enlaza) ·
#           omitir (propio/estudiantes/plantillas/admin) · revisar (ambiguo)
# autor: nombre canónico de la biblioteca («Nombre, Apellidos») si el Author del PDF coincide por tokens; si no, Unknown.
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
        */deck_*|*/build/*) echo propio_compilado;;
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
        estudiante|backup_reorg|plantilla|administrativo|propio_curso|propio_compilado) echo omitir;;
        referencia|lectura|taller|unidad|diapositivas) echo ingestar;;
        material) [ "$pags" -ge "$MIN_PAGINAS_LIBRO" ] && echo ingestar || echo revisar;;
        *) echo revisar;;
    esac
}
titulo_de() { # $1 archivo → título en frase: Title del PDF si es útil; si no, nombre de archivo sin numeración
    local t; t="$(pdfinfo "$1" 2>/dev/null | awk -F': *' '/^Title/{print $2}' || true)"
    if [ -z "$t" ] || printf '%s' "$t" | grep -qiE '^(untitled|documento|presentaci[oó]n de powerpoint|powerpoint presentation|t[ií]tulo principal|mesa de trabajo.*|microsoft word.*|slide 1|diapositiva 1|instituto nacional de estadistica.*|index|topics|chapter outline.*|t[0-9]+\.[0-9]+.*|exposici[oó]n .*|.*\.(docx?|pptx?|tex))$'; then
        t="$(basename "$1")"
    fi
    python3 "$SCRIPT_DIR/lib/biblioteca.py" titulo "$(printf '%s' "$t" | sed 's/	/ /g')"
}
autor_de() { # $1 archivo → autor canónico de la biblioteca o $AUTOR_DESCONOCIDO (nunca se inventa una grafía nueva)
    local a c; a="$(pdfinfo "$1" 2>/dev/null | awk -F': *' '/^Author/{print $2}' | sed 's/	/ /g' || true)"
    if [ -z "$a" ] || printf '%s' "$a" | grep -qiE "$AUTORES_GENERICOS"; then printf '%s' "$AUTOR_DESCONOCIDO"; return; fi
    if printf '%s' "$a" | grep -qiE "$AUTOR_PROPIO"; then printf '%s' "$a"; return; fi
    c="$(python3 "$SCRIPT_DIR/lib/biblioteca.py" autor "$a")"
    printf '%s' "${c:-$AUTOR_DESCONOCIDO}"
}
escanear() { # → escribe TSV en $1
    local out="$1"; printf "decision\tclase\tpaginas\tMB\tautor\ttitulo\tcurso\truta\tduplicado_id\n" > "$out"
    local curso carpeta f rel clase pags mb autor titulo dec cid dup ex
    for curso in "$AREAS"/Academic_Class-*/course_*/; do
        for ex in "${CURSOS_EXCLUIDOS[@]}"; do case "$curso" in *"$ex"/) continue 2;; esac; done
        cid="$(curso_id "${curso%/}")"
        for carpeta in "${CARPETAS_ESCANEO[@]}"; do
            [ -d "$curso$carpeta" ] || continue
            while IFS= read -r -d '' f; do
                rel="${f#$curso}"; clase="$(clase_de "$rel")"
                pags="$(pdfinfo "$f" 2>/dev/null | awk -F': *' '/^Pages/{print $2}' || true)"; mb="$(du -m "$f" | cut -f1 || true)"
                autor="$(autor_de "$f")"; titulo="$(titulo_de "$f")"; dec="$(decision_de "$clase" "${pags:-0}" "$autor")"
                dup=""; [ "$dec" = ingestar ] && dup="$(python3 "$SCRIPT_DIR/lib/biblioteca.py" duplicado "$titulo" "${pags:-0}" "$DEDUPE_TOLERANCIA_PAGINAS")"
                [ -n "$dup" ] && dec=duplicado
                printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$dec" "$clase" "${pags:-0}" "$mb" "$autor" "$titulo" "$cid" "${f#$DOCS/}" "$dup" >> "$out"
            done < <(find "$curso$carpeta" -type f -iname '*.pdf' -print0)
        done
    done
}
