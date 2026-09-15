#!/usr/bin/env bash
# main.sh — KOReader → Calibre: seguimiento de estudio (orquestación, sin lógica)
#
# Simulación por defecto; --aplicar para escribir. Ver README.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/../lib_comun/detectar_apps.sh"
source "$SCRIPT_DIR/../lib_comun/lock.sh"
source "$SCRIPT_DIR/../lib_comun/backup_rotado.sh"
source "$SCRIPT_DIR/lib/checks.sh"
source "$SCRIPT_DIR/lib/setup_columnas.sh"
source "$SCRIPT_DIR/lib/respaldo_koreader.sh"

MODO="simulacion"
DESDE_TIMER=0
ACCION="sync"
APUNTES_ID=""
APUNTES_RUTA=""
APUNTES_TEXTO=""

ayuda() {
    cat <<'EOF'
Uso: ./main.sh [opciones]

  (sin opciones)        Simulación: muestra columnas que faltan y qué se
                        sincronizaría (no escribe nada).
  --aplicar             Crea columnas faltantes, hace backup de metadata.db y
                        sincroniza de verdad (requiere Calibre cerrado).
  --migrar-sdr          Migra los sidecars .sdr de las carpetas de libros a la
                        ubicación hash central de KOReader (con --aplicar).
  --apuntes ID RUTA [TEXTO]
                        Escribe en #apuntes del libro ID un enlace clicable al
                        archivo .md indicado (TEXTO opcional para el enlace).
  --instalar-timer      Instala y activa el timer systemd de usuario (cada 30
                        min; se salta la ejecución si Calibre está abierto).
  --desinstalar-timer   Detiene y elimina el timer.
  --desde-timer         (interno) usado por el servicio systemd.
  --ayuda               Esta ayuda.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --aplicar) MODO="aplicar" ;;
        --desde-timer) DESDE_TIMER=1; MODO="aplicar" ;;
        --apuntes)
            ACCION="apuntes"
            APUNTES_ID="${2:?falta el ID del libro}"; APUNTES_RUTA="${3:?falta la ruta del .md}"
            APUNTES_TEXTO="${4:-}"; shift 3 ;;
        --migrar-sdr) ACCION="migrar" ;;
        --instalar-timer) ACCION="timer_on" ;;
        --desinstalar-timer) ACCION="timer_off" ;;
        --ayuda|-h|--help) ayuda; exit 0 ;;
        *) echo "✗ Opción desconocida: $1 (usa --ayuda)" >&2; exit 1 ;;
    esac
    shift
done

# --- Acción: enlace de apuntes ---------------------------------------------
accion_apuntes() {
    # Lock compartido (auditoría C5): calibredb set_custom escribe metadata.db
    # y debe serializar con los timers, igual que accion_sync.
    tomar_lock_calibre
    exigir_calibre_cerrado
    [ -f "$APUNTES_RUTA" ] || { echo "✗ No existe el archivo: $APUNTES_RUTA" >&2; exit 1; }
    local abs texto html
    abs="$(readlink -f "$APUNTES_RUTA")"
    texto="${APUNTES_TEXTO:-$(basename "$APUNTES_RUTA" .md)}"
    html="$(python3 - "$abs" "$texto" <<'EOF'
import sys, urllib.parse
ruta, texto = sys.argv[1], sys.argv[2]
obs = "obsidian://open?path=" + urllib.parse.quote(ruta, safe="")
fil = "file://" + urllib.parse.quote(ruta)
print('<div><p><a href="%s">📝 %s</a></p>'
      '<p style="font-size:small"><a href="%s">(abrir como archivo)</a></p></div>'
      % (obs, texto, fil))
EOF
)"
    calibredb set_custom --with-library "$BIBLIOTECA" \
        "$COL_APUNTES" "$APUNTES_ID" "$html"
    echo "✓ #$COL_APUNTES del libro $APUNTES_ID → enlace a: $abs"
}

# --- Acción: timer systemd de usuario --------------------------------------
accion_timer_on() {
    mkdir -p "$HOME/.config/systemd/user"
    sed "s|@MAIN@|$SCRIPT_DIR/main.sh|" \
        "$SCRIPT_DIR/lib/systemd/koreader-calibre-sync.service" \
        > "$HOME/.config/systemd/user/koreader-calibre-sync.service"
    cp "$SCRIPT_DIR/lib/systemd/koreader-calibre-sync.timer" \
        "$HOME/.config/systemd/user/koreader-calibre-sync.timer"
    systemctl --user daemon-reload
    systemctl --user enable --now koreader-calibre-sync.timer
    echo "✓ Timer activado (cada 30 min). Ver: systemctl --user list-timers"
}

accion_timer_off() {
    systemctl --user disable --now koreader-calibre-sync.timer 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/koreader-calibre-sync.service" \
          "$HOME/.config/systemd/user/koreader-calibre-sync.timer"
    systemctl --user daemon-reload
    echo "✓ Timer desinstalado."
}

# --- Acción: migrar sidecars .sdr a la ubicación hash de KOReader ----------
accion_migrar() {
    comprobar_entorno
    exigir_koreader_cerrado
    if [ "$MODO" = "aplicar" ]; then
        mkdir -p "$BACKUPS_DIR"
        local ts; ts="$(date +%Y%m%d_%H%M%S)"
        tar czf "$BACKUPS_DIR/koreader_premigracion_${ts}_config.tar.gz" \
            -C "$KOREADER_CONFIG" settings.reader.lua settings 2>/dev/null || true
        (cd "$BIBLIOTECA" && find . -type d -name "*.sdr" -print0 \
            | tar czf "$BACKUPS_DIR/koreader_premigracion_${ts}_sdrs.tar.gz" --null -T -) 2>/dev/null || true
        echo "── Backups pre-migración en $BACKUPS_DIR (config + sdrs)"
    fi
    QKO_BIBLIOTECA="$BIBLIOTECA" QKO_KOREADER_CONFIG="$KOREADER_CONFIG" \
    QKO_APLICAR="$([ "$MODO" = "aplicar" ] && echo 1 || echo 0)" \
        python3 "$SCRIPT_DIR/lib/migrar_sdr.py"
    if [ "$MODO" = "aplicar" ]; then
        local cfg="$KOREADER_CONFIG/settings.reader.lua"
        if grep -q '\["document_metadata_folder"\] = "hash"' "$cfg" 2>/dev/null; then
            echo "── KOReader ya estaba en modo hash."
        elif grep -q '\["document_metadata_folder"\]' "$cfg" 2>/dev/null; then
            cp "$cfg" "$BACKUPS_DIR/settings.reader.lua_$(date +%Y%m%d_%H%M%S)"
            sed -i 's/\["document_metadata_folder"\] = "[a-z]*"/\["document_metadata_folder"\] = "hash"/' "$cfg"
            echo "── KOReader configurado: document_metadata_folder = \"hash\" ✓"
        else
            echo "⚠ No encontré document_metadata_folder en settings.reader.lua;"
            echo "  actívalo en KOReader: Configuración → Documento → Ubicación de metadatos → hash."
        fi
        respaldar_koreader
    else
        echo ""
        echo "· Esto fue una SIMULACIÓN. Ejecuta: ./main.sh --migrar-sdr --aplicar"
    fi
}

# --- Acción principal: setup + sync ----------------------------------------
accion_sync() {
    # Lock COMPARTIDO entre las herramientas que escriben metadata.db
    # (script_koreader_estudio y script_ecosistema_lectura): nunca a la vez.
    tomar_lock_calibre

    comprobar_entorno

    if [ "$DESDE_TIMER" = 1 ] && calibre_abierto; then
        echo "· Calibre está abierto; el timer lo reintentará luego. Nada que hacer."
        exit 0
    fi
    if [ "$MODO" = "aplicar" ]; then
        exigir_calibre_cerrado
    fi

    setup_columnas

    if [ "$MODO" = "aplicar" ]; then
        backup_metadata_db "$BIBLIOTECA/metadata.db" "$BACKUPS_DIR" "$BACKUPS_CONSERVAR"
    fi

    mkdir -p "$REPORTES_DIR"
    QKO_BIBLIOTECA="$BIBLIOTECA" \
    QKO_KOREADER_CONFIG="$KOREADER_CONFIG" \
    QKO_STATS_DB="$STATS_DB" \
    QKO_APLICAR="$([ "$MODO" = "aplicar" ] && echo 1 || echo 0)" \
    QKO_REPORTE="$REPORTES_DIR/sync_$(date +%Y%m%d_%H%M%S).tsv" \
    QKO_FORMATOS="$FORMATOS_LEIBLES" \
    QKO_COL_MD5="$COL_MD5" QKO_COL_PROGFLOAT="$COL_PROGFLOAT" \
    QKO_COL_PROGINT="$COL_PROGINT" QKO_COL_STATUS="$COL_STATUS" \
    QKO_COL_START="$COL_START" QKO_COL_FINISH="$COL_FINISH" \
    QKO_COL_LASTMOD="$COL_LASTMOD" QKO_COL_LASTSYNC="$COL_LASTSYNC" \
    QKO_COL_TIEMPO="$COL_TIEMPO" QKO_COL_LEIDO="$COL_LEIDO" \
    QKO_COL_READ_DATE="$COL_READ_DATE" \
        calibre-debug -e "$SCRIPT_DIR/lib/sync_koreader.py"

    if [ "$MODO" = "simulacion" ]; then
        echo ""
        echo "· Esto fue una SIMULACIÓN. Ejecuta con --aplicar para escribir."
    else
        respaldar_koreader
    fi
}

case "$ACCION" in
    apuntes)   accion_apuntes ;;
    migrar)    accion_migrar ;;
    timer_on)  accion_timer_on ;;
    timer_off) accion_timer_off ;;
    sync)      accion_sync ;;
esac
