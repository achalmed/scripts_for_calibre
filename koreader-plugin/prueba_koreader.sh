#!/usr/bin/env bash
# prueba_koreader.sh — carga el complemento «Ecosistema» en un KOReader de verdad, sin pantalla y con
# una configuración temporal (KO_HOME), y recorre su menú con un índice, una biblioteca y un repo
# falsos. No toca la configuración real de KOReader, ni la biblioteca, ni Calibre, ni systemd: las
# órdenes externas (xdg-open, systemctl) se registran en vez de ejecutarse y `koreader/main.sh` es un
# doble que sale 75 (Calibre abierto).
#
#   koreader-plugin/prueba_koreader.sh [--conservar]
#
# Todo vive en $XDG_CACHE_HOME/ecosistema-koplugin-koreader/ (el disco) y se borra al terminar, salvo
# con --conservar. Sale 0 si todo lo esperado aparece en la bitácora de la prueba.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOREADER_DIR="${KOREADER_DIR:-/usr/lib/koreader}"
CONSERVAR=0
[ "${1:-}" = "--conservar" ] && CONSERVAR=1

W="${XDG_CACHE_HOME:-$HOME/.cache}/ecosistema-koplugin-koreader"
rm -rf "$W"
mkdir -p "$W/ko/plugins" "$W/ko/patches" "$W/casa" "$W/estado/biblioteca" "$W/notas" \
         "$W/repo/koreader" "$W/bib/Autora, Prueba/Libro de prueba (48)"
trap '[ "$CONSERVAR" = 1 ] || rm -rf "$W"' EXIT

LIBRO="$W/bib/Autora, Prueba/Libro de prueba (48)/Libro de prueba - Autora.pdf"
PDF_MUESTRA="${PDF_MUESTRA:-/usr/share/cups/data/default-testpage.pdf}"
[ -f "$PDF_MUESTRA" ] || { echo "✗ falta un PDF de muestra (PDF_MUESTRA): $PDF_MUESTRA" >&2; exit 3; }
cp "$PDF_MUESTRA" "$LIBRO"

ln -s "$AQUI/ecosistema.koplugin" "$W/ko/plugins/ecosistema.koplugin"

# El doble de koreader/main.sh: anota los argumentos y sale 75, como la puerta con Calibre abierto.
cat > "$W/repo/koreader/main.sh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$(dirname "$0")/../apuntes.args"
echo "✗ Calibre está abierto (o corre otro calibredb): ciérrelo y reintente luego" >&2
exit 75
EOF
chmod +x "$W/repo/koreader/main.sh"

W="$W" python3 - <<'EOF'
import json, os
w = os.environ["W"]
indice = {"esquema": 1, "generado": "prueba", "biblioteca": w + "/bib", "repo": w + "/repo", "notas": w + "/notas",
          "libros": {"48": {"titulo": "Libro de prueba", "autores": ["Autora, Prueba"],
                            "carpeta": "Autora, Prueba/Libro de prueba (48)",
                            "formatos": ["Autora, Prueba/Libro de prueba (48)/Libro de prueba - Autora.pdf"],
                            "zotero_key": "ABCD1234", "clave": "autoraLibroPrueba2026", "apuntes": "",
                            "fichas": ["catalogacion/fichas/48_prueba.md"],
                            "nota": w + "/notas/autoralibroprueba2026.md"}}}
json.dump(indice, open(w + "/estado/biblioteca/indice.json", "w"), ensure_ascii=False)
EOF

# El parche «2-» corre cuando la interfaz ya está lista: espera al lector y recorre el menú.
cat > "$W/ko/patches/2-prueba-ecosistema.lua" <<'EOF'
local UIManager = require("ui/uimanager")
local salida = os.getenv("ECOSISTEMA_PRUEBA_SALIDA")
local function anotar(s)
    local f = io.open(salida, "a"); f:write(tostring(s), "\n"); f:close()
end
local function buscar(tabla, texto, prof)
    if type(tabla) ~= "table" or prof > 6 then return false end
    if tabla.text == texto then return true end
    for _, v in pairs(tabla) do
        if type(v) == "table" and buscar(v, texto, prof + 1) then return true end
    end
    return false
end
-- Los resaltados inventados no tienen posiciones de PDF válidas: se ponen solo mientras el complemento
-- los lee (en el mismo tic, sin repintar) y se quitan enseguida, para que el lector no intente dibujarlos.
local function con_resaltados(fn)
    local anot = require("apps/reader/readerui").instance.annotation.annotations
    local n = #anot
    table.insert(anot, { datetime = "2026-10-31 10:00:00", drawer = "lighten", text = "Un resaltado de prueba.",
                         note = "Con su nota.", pageno = 1, page = 1 })
    table.insert(anot, { datetime = "2026-10-31 10:01:00", drawer = "underscore", text = "Otro resaltado.",
                         pageno = 1, page = 1 })
    local ok, err = pcall(fn)
    for i = #anot, n + 1, -1 do table.remove(anot, i) end
    if not ok then error(err, 0) end
end
local function paso2(eco)
    con_resaltados(function() eco:pasarResaltados() end)   -- segunda vez: no debe duplicar
    eco:copiarClave()
    eco:abrirCalibre(); eco:abrirZotero(); eco:abrirStudio()
    eco:sincronizar()
    UIManager:scheduleIn(1, function()
        anotar("FIN")
        local ui = require("apps/reader/readerui").instance
        if ui then ui:onClose() end
        UIManager:quit()
    end)
end
UIManager:scheduleIn(4, function()
    local ok, err = pcall(function()
        local ui = require("apps/reader/readerui").instance
        anotar("LECTOR " .. tostring(ui ~= nil))
        local eco = ui and ui.ecosistema
        anotar("COMPLEMENTO " .. tostring(eco ~= nil))
        if not eco then UIManager:quit() return end
        ui.menu:onShowMenu(nil, true)
        anotar("EN_EL_MENU " .. tostring(buscar(ui.menu.tab_item_table, "Ecosistema", 0)))
        UIManager:close(ui.menu.menu_container)
        -- Las órdenes externas se anotan en vez de ejecutarse.
        eco.lanzar = function(_, args) anotar("LANZAR " .. table.concat(args, " ")) end
        local ejecutar = eco.ejecutar
        eco.ejecutar = function(self, args, fin)
            if args[1] == "systemctl" then
                anotar("EJECUTAR " .. table.concat(args, " ")); fin(0, ""); return
            end
            return ejecutar(self, args, fin)
        end
        eco.avisar = function(_, t) anotar("AVISO " .. t:gsub("\n", " | ")) end
        local show = UIManager.show
        UIManager.show = function(um, w, ...)
            if w and w.buttons_table and w.title then
                anotar("VISTA " .. w.title)
                anotar(w.text)
                anotar("FIN_VISTA")
                return w.buttons_table[1][2].callback()   -- «Añadir a los apuntes»
            end
            return show(um, w, ...)
        end
        eco:queEs()
        con_resaltados(function() eco:pasarResaltados() end)
        -- el doble de main.sh tarda un momento; el aviso llega por el sondeo
        UIManager:scheduleIn(4, function()
            local ok2, err2 = pcall(paso2, eco)
            if not ok2 then anotar("ERROR " .. tostring(err2)); UIManager:quit() end
        end)
    end)
    if not ok then anotar("ERROR " .. tostring(err)); UIManager:quit() end
end)
EOF

export ECOSISTEMA_PRUEBA_SALIDA="$W/bitacora.txt"
: > "$ECOSISTEMA_PRUEBA_SALIDA"
(
    cd "$KOREADER_DIR"
    env -u DISPLAY -u WAYLAND_DISPLAY KO_HOME="$W/ko" HOME="$W/casa" XDG_STATE_HOME="$W/estado" \
        XDG_CONFIG_HOME="$W/casa/.config" XDG_DATA_HOME="$W/casa/.local/share" \
        SDL_VIDEO_DRIVER=dummy SDL_VIDEODRIVER=dummy SDL_AUDIO_DRIVER=dummy LC_ALL=en_US.UTF-8 \
        timeout 90 ./luajit reader.lua "$LIBRO" > "$W/koreader.log" 2>&1
) || echo "· KOReader salió con $? (ver $W/koreader.log)"

echo "=== bitácora de la prueba ==="
cat "$ECOSISTEMA_PRUEBA_SALIDA"
echo "=== la nota que quedó ==="
cat "$W/notas/autoralibroprueba2026.md" 2>/dev/null || echo "(no se creó)"
echo "=== argumentos que recibió koreader/main.sh ==="
cat "$W/repo/apuntes.args" 2>/dev/null || echo "(no se llamó)"
echo "=== errores del registro de KOReader que nombran el complemento ==="
grep -E "ecosistema\.koplugin|ecosistema_logica|Ecosistema:|Error when loading|Failed to" "$W/koreader.log" || echo "(ninguno)"

fallos=0
esperar() {
    if grep -qF -- "$1" "$2"; then echo "✓ $3"; else echo "✗ $3"; fallos=$((fallos + 1)); fi
}
B="$ECOSISTEMA_PRUEBA_SALIDA"; N="$W/notas/autoralibroprueba2026.md"
esperar "COMPLEMENTO true" "$B" "el complemento carga en el lector"
esperar "EN_EL_MENU true" "$B" "«Ecosistema» está en el menú principal"
esperar "Clave para citar: autoraLibroPrueba2026" "$B" "Qué es este libro"
esperar "VISTA Añadir 2 resaltados" "$B" "vista previa de los resaltados"
esperar "se enlazará desde Biblioteca Studio" "$B" "salida 75 de --apuntes avisada sin fallar"
esperar "ya están en los apuntes" "$B" "la segunda pasada no duplica"
esperar "LANZAR xdg-open calibre://show-book/_hex_-626962/48" "$B" "abrir en Calibre"
esperar "LANZAR xdg-open zotero://select/library/items/ABCD1234" "$B" "abrir en Zotero"
esperar "LANZAR xdg-open biblioteca-studio://libro/48" "$B" "abrir en Biblioteca Studio"
esperar "EJECUTAR systemctl --user start --no-block koreader-calibre-sync.service" "$B" "sincronizar"
if grep -qx "FIN" "$B" && ! grep -q "^ERROR" "$B"; then echo "✓ el recorrido termina sin errores"; else
    echo "✗ el recorrido termina sin errores"; fallos=$((fallos + 1)); fi
if grep -q "stack traceback" "$W/koreader.log"; then echo "✗ KOReader sin trazas de error"; fallos=$((fallos + 1)); else
    echo "✓ KOReader sin trazas de error"; fi
esperar "tipo: lectura" "$N" "la nota nueva lleva su encabezado"
esperar "> Un resaltado de prueba." "$N" "la nota tiene el resaltado"
if [ "$(grep -c '^## Resaltados de KOReader' "$N" 2>/dev/null)" = 1 ]; then
    echo "✓ un solo bloque"
else
    echo "✗ un solo bloque"; fallos=$((fallos + 1))
fi
esperar "--apuntes" "$W/repo/apuntes.args" "se pidió el enlace por koreader/main.sh --apuntes"
echo "$fallos fallos"
[ "$fallos" = 0 ]
