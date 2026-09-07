#!/usr/bin/env bash
# lib/ingestar.sh — añade a Calibre las filas con decision=ingestar, registra el calibre_id en el temario del
# curso (bibliografia:) y retira el original a ORIGINALES_DIR (reversible). Requiere el lock y Calibre cerrado.
ingestar_tsv() { # $1 tsv  $2 aplicar(0/1)  → escribe $REPORTES_DIR/ingesta_<fecha>.tsv con los ids
    local tsv="$1" aplicar="$2" salida="$REPORTES_DIR/ingesta_$(date +%Y%m%d_%H%M%S).tsv" n=0 ok=0
    set +e   # dentro del bucle cada fila se trata por separado: un fallo no aborta la ingesta
    printf "calibre_id\tcurso\ttitulo\tautor\truta_original\n" > "$salida"
    while IFS=$'\t' read -r dec clase pags mb autor titulo cid ruta; do
        [ "$dec" = "ingestar" ] || continue; n=$((n+1))
        local f="$DOCS/$ruta" tags="$TAGS_BASE,curso:$cid"
        if [ "$aplicar" != 1 ]; then log_info "[simular] calibredb add -t \"$titulo\" -a \"$autor\" -T \"$tags\" \"$ruta\""; continue; fi
        local out id
        # QIR_DUPLICADOS=1 añade aunque Calibre ya tenga un libro con el mismo título/autor (-d)
        out="$("$CALIBREDB" add --with-library "$BIBLIOTECA" ${QIR_DUPLICADOS:+-d} -t "$titulo" -a "$autor" -T "$tags" "$f" 2>&1)" || { log_error "calibredb add falló: $ruta :: $out"; continue; }
        id="$(printf '%s' "$out" | grep -iE 'a[ñn]adid|added' | grep -oE '[0-9]+' | tail -1 || true)"
        [ -n "$id" ] || { log_warn "sin id devuelto para $ruta :: $out"; continue; }
        local cdir; cdir="$(printf '%s' "$f" | sed -E 's#/(06_RECURSOS|08_INVESTIGACION)/.*##')"
        python3 "$SCRIPT_DIR/lib/temario_bib.py" "$cdir" "$id" "$titulo" "$autor" "$ruta" || log_warn "no se pudo registrar en temario.yml: $cdir"
        mkdir -p "$ORIGINALES_DIR/$(dirname "$ruta")" && mv "$f" "$ORIGINALES_DIR/$ruta"
        printf "%s\t%s\t%s\t%s\t%s\n" "$id" "$cid" "$titulo" "$autor" "$ruta" >> "$salida"; ok=$((ok+1))
        log_info "id=$id ← $ruta"
    done < <(tail -n +2 "$tsv")
    set -e
    log_info "filas ingestar=$n · añadidos=$ok · registro: $salida"
}
