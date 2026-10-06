# lib/setup_columnas.sh — Crea las columnas de la Fase 2 si faltan (idempotente)

columna_existe() {
    sqlite3 "file:$BIBLIOTECA/metadata.db?mode=ro" \
        "SELECT label FROM custom_columns;" 2>/dev/null | grep -qx "$1"
}

crear_columna() {
    local label="$1" nombre="$2" tipo="$3" display="${4:-}"
    if columna_existe "$label"; then
        echo "  = #$label ya existe, no se toca."
        return 0
    fi
    if [ "$MODO" = "simulacion" ]; then
        echo "  → [SIMULACIÓN] crearía #$label («$nombre», $tipo)"
        return 0
    fi
    local salida
    if [ -n "$display" ]; then
        salida=$(calibredb_escribe add_custom_column \
            --display "$display" "$label" "$nombre" "$tipo" 2>&1) || {
                echo "$salida" | grep -qi "UNIQUE" \
                    && { echo "  = #$label ya existía (paralelo)."; return 0; } \
                    || { echo "$salida" >&2; return 1; }
            }
    else
        salida=$(calibredb_escribe add_custom_column \
            "$label" "$nombre" "$tipo" 2>&1) || {
                echo "$salida" | grep -qi "UNIQUE" \
                    && { echo "  = #$label ya existía (paralelo)."; return 0; } \
                    || { echo "$salida" >&2; return 1; }
            }
    fi
    echo "  ✓ creada #$label («$nombre», $tipo)"
}

setup_columnas() {
    echo "── Columnas (Fase 2/2b) ──────────────────────────────────"
    crear_columna "$COL_ZTIEMPO" "Tiempo Zotero (min)" int '{"number_format": "{0:,d} min"}'
    crear_columna "$COL_ZULTIMA" "Última lectura (Zotero)" datetime
    crear_columna "$COL_ZPROG" "Progreso Zotero" float '{"number_format": "{0:.0%}"}'

    # Tiempo total = ko_tiempo + zot_tiempo. Trampas conocidas: field() devuelve
    # el valor FORMATEADO ('19 min') → raw_field() para aritmética; el test de
    # vacío se hace con field().
    local tpl
    tpl=$(python3 -c "
import json
tpl = (\"program:\n\"
       \"\ta = field('#${COL_KOTIEMPO}');\n\"
       \"\tb = field('#${COL_ZTIEMPO}');\n\"
       \"\tx = if a then raw_field('#${COL_KOTIEMPO}') else 0 fi;\n\"
       \"\ty = if b then raw_field('#${COL_ZTIEMPO}') else 0 fi;\n\"
       \"\ts = add(x, y);\n\"
       \"\tif s ># 0 then strcat(format_number(s, '{0:.0f}'), ' min') else '' fi\")
print(json.dumps({'composite_template': tpl, 'composite_sort': 'number',
                  'make_category': False, 'contains_html': False,
                  'use_decorations': 0}))
")
    crear_columna "$COL_TTOTAL" "Tiempo total de estudio" composite "$tpl"
}
