# lib/setup_columnas.sh — Crea las columnas nuevas si faltan (idempotente)

# Devuelve los labels de columnas personalizadas existentes (lectura sqlite ro).
columnas_existentes() {
    etiquetas_calibre "$BIBLIOTECA" 2>/dev/null   # lib/leer.sh (CORE_PYTHON, solo lectura)
}

columna_existe() {
    columnas_existentes | grep -qx "$1"
}

# Uso: crear_columna <label> <nombre> <datatype> [display_json]
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
    # Tolerante a carreras: si otra instancia la creó entre la consulta y el
    # add, el UNIQUE de calibre falla y aquí se trata como "ya existe".
    local salida
    if [ -n "$display" ]; then
        salida=$(calibredb_escribe add_custom_column \
            --display "$display" "$label" "$nombre" "$tipo" 2>&1) || {
                echo "$salida" | grep -qi "UNIQUE" \
                    && { echo "  = #$label ya existía (creada en paralelo)."; return 0; } \
                    || { echo "$salida" >&2; return 1; }
            }
    else
        salida=$(calibredb_escribe add_custom_column \
            "$label" "$nombre" "$tipo" 2>&1) || {
                echo "$salida" | grep -qi "UNIQUE" \
                    && { echo "  = #$label ya existía (creada en paralelo)."; return 0; } \
                    || { echo "$salida" >&2; return 1; }
            }
    fi
    echo "  ✓ creada #$label («$nombre», $tipo)"
}

setup_columnas() {
    echo "── Columnas ──────────────────────────────────────────────"

    # Minutos de lectura (desde statistics.sqlite3)
    crear_columna "$COL_TIEMPO" "Tiempo de lectura (min)" int \
        '{"number_format": "{0:,d} min"}'

    # Barra de progreso (composite sobre #ko_progfloat, fracción 0–1).
    # Trampas del lenguaje de plantillas, documentadas con sangre:
    #  · field() devuelve el valor FORMATEADO ('4.35%') → aritmética rota;
    #    se usa para detectar vacío y raw_field() para calcular.
    #  · substr(s, 0, 0) devuelve la cadena entera, no '' → casos n=0 y n=10
    #    explícitos.
    # Progreso mostrado = max(KOReader, Zotero): regla de conflicto del DISEÑO.
    # Requiere que #zot_progreso exista (la crea lectura).
    local tpl_barra
    tpl_barra=$("$CORE_PYTHON" -c "
import json
tpl = (\"program:\n\"
       \"\ta = field('#${COL_PROGFLOAT}');\n\"
       \"\tb = field('#zot_progreso');\n\"
       \"\tx = if a then raw_field('#${COL_PROGFLOAT}') else -1 fi;\n\"
       \"\ty = if b then raw_field('#zot_progreso') else -1 fi;\n\"
       \"\tpr = if x >=# y then x else y fi;\n\"
       \"\tif pr >=# 0 then\n\"
       \"\t\tpct = multiply(pr, 100);\n\"
       \"\t\tn = round(divide(pct, 10));\n\"
       \"\t\tif n ==# 0 then bar = '▱▱▱▱▱▱▱▱▱▱'\n\"
       \"\t\telif n >=# 10 then bar = '▰▰▰▰▰▰▰▰▰▰'\n\"
       \"\t\telse\n\"
       \"\t\t\tllenos = format_number(n, '{0:.0f}');\n\"
       \"\t\t\tvacios = format_number(subtract(10, n), '{0:.0f}');\n\"
       \"\t\t\tbar = strcat(substr('▰▰▰▰▰▰▰▰▰▰', 0, llenos), substr('▱▱▱▱▱▱▱▱▱▱', 0, vacios))\n\"
       \"\t\tfi;\n\"
       \"\t\tstrcat(bar, ' ', format_number(pct, '{0:.0f}'), '%')\n\"
       \"\telse '' fi\")
print(json.dumps({'composite_template': tpl, 'composite_sort': 'text',
                  'make_category': False, 'contains_html': False,
                  'use_decorations': 0}))
")
    crear_columna "$COL_BARRA" "Progreso (barra)" composite "$tpl_barra"

    # Estado de estudio (composite sobre #ko_status y #ko_progfloat)
    local tpl_estado
    tpl_estado=$("$CORE_PYTHON" -c "
import json
tpl = (\"program:\n\"
       \"\tst = field('#${COL_STATUS}');\n\"
       \"\tpr = field('#${COL_PROGFLOAT}');\n\"
       \"\tzp = field('#zot_progreso');\n\"
       \"\tzt = field('#zot_tiempo');\n\"
       \"\tif st == 'complete' then '✅ Finalizado'\n\"
       \"\telif st == 'abandoned' then '⏸ Abandonado'\n\"
       \"\telif st == 'reading' then '📖 En proceso'\n\"
       \"\telif pr then '📖 En proceso'\n\"
       \"\telif zp then '📖 En proceso'\n\"
       \"\telif zt then '📖 En proceso'\n\"
       \"\telse '⬜ Pendiente' fi\")
print(json.dumps({'composite_template': tpl, 'composite_sort': 'text',
                  'make_category': True, 'contains_html': False,
                  'use_decorations': 0}))
")
    crear_columna "$COL_ESTADO" "Estado de estudio" composite "$tpl_estado"

    # Apuntes (comments: HTML con enlace file:// clicable en Detalles del libro)
    crear_columna "$COL_APUNTES" "Apuntes" comments
}
