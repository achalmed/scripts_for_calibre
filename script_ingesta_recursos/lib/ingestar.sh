#!/usr/bin/env bash
# lib/ingestar.sh — aplica el TSV de candidatos:
#   ingestar  → calibredb add SIN etiquetas inventadas (título en frase, autor canónico o Unknown), registra el id en
#               `bibliografia:` del temario, retira el original a ORIGINALES_DIR y deja una fila prellenada en
#               reportes/catalogar_<fecha>.tsv (columnas de script_catalogacion_biblioteca) para completar la ficha.
#   duplicado → NO añade nada: enlaza el temario al libro que ya existe y retira la copia del curso.
# Requiere el lock y Calibre cerrado. Un fallo en una fila no aborta las demás.
ingestar_tsv() { # $1 tsv  $2 aplicar(0/1)
    local tsv="$1" aplicar="$2" fecha; fecha="$(date +%Y%m%d_%H%M%S)"
    local salida="$REPORTES_DIR/ingesta_$fecha.tsv" catalogar="$REPORTES_DIR/catalogar_$fecha.tsv" n=0 ok=0 nd=0
    set +e
    printf "calibre_id\tcurso\ttitulo\tautor\truta_original\n" > "$salida"
    printf "id\tautores\ttitulo\ttipo_zotero\tclasificador\teditorial\tfecha\tidentificador\tidioma\ttags\tconfianza\tnota\n" > "$catalogar"
    while IFS=$'\t' read -r dec clase pags mb autor titulo cid ruta dup; do
        case "$dec" in ingestar|duplicado) ;; *) continue;; esac
        local f="$DOCS/$ruta" cdir id
        cdir="$(printf '%s' "$f" | sed -E 's#/(06_RECURSOS|08_INVESTIGACION)/.*##')"
        if [ "$dec" = duplicado ]; then
            case "$dup" in *,*) log_warn "varios candidatos en Calibre ($dup) para $ruta: decide a mano"; continue;; esac
            n=$((n+1))
            if [ "$aplicar" != 1 ]; then log_info "[simular] duplicado de id=$dup: enlazar temario y retirar $ruta"; continue; fi
            python3 "$SCRIPT_DIR/lib/temario_bib.py" "$cdir" "$dup" "$titulo" "$autor" "$ruta" "ya estaba en la biblioteca; la copia del curso se retiró" || log_warn "no se pudo registrar en temario.yml: $cdir"
            mkdir -p "$ORIGINALES_DIR/$(dirname "$ruta")" && mv "$f" "$ORIGINALES_DIR/$ruta"; nd=$((nd+1)); continue
        fi
        n=$((n+1))
        if [ "$aplicar" != 1 ]; then log_info "[simular] calibredb add -t \"$titulo\" -a \"$autor\" \"$ruta\""; continue; fi
        local out
        out="$("$CALIBREDB" add --with-library "$BIBLIOTECA" -d -t "$titulo" -a "$autor" "$f" 2>&1)" || { log_error "calibredb add falló: $ruta :: $out"; continue; }
        id="$(printf '%s' "$out" | grep -iE 'a[ñn]adid|added' | grep -oE '[0-9]+' | tail -1 || true)"
        [ -n "$id" ] || { log_warn "sin id devuelto para $ruta :: $out"; continue; }
        python3 "$SCRIPT_DIR/lib/temario_bib.py" "$cdir" "$id" "$titulo" "$autor" "$ruta" || log_warn "no se pudo registrar en temario.yml: $cdir"
        mkdir -p "$ORIGINALES_DIR/$(dirname "$ruta")" && mv "$f" "$ORIGINALES_DIR/$ruta"
        printf "%s\t%s\t%s\t%s\t%s\n" "$id" "$cid" "$titulo" "$autor" "$ruta" >> "$salida"
        printf "%s\t%s\t%s\t\t\t\t\t\tSpanish\t\tbaja\tingesta $fecha (curso $cid): completar ficha en $CATALOGACION_DIR/fichas\n" "$id" "$autor" "$titulo" >> "$catalogar"
        ok=$((ok+1)); log_info "id=$id ← $ruta"
    done < <(tail -n +2 "$tsv")
    set -e
    log_info "filas=$n · añadidos=$ok · duplicados enlazados=$nd · registro: $salida"
    [ "$ok" -gt 0 ] && log_warn "Los $ok libros nuevos entraron SIN serie, etiquetas ni tipo: completa $catalogar, copia las filas a $CATALOGACION_DIR/resumen_catalogacion.tsv con su ficha y aplica con esa suite."
    return 0
}
