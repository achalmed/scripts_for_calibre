#!/usr/bin/env bash
# main.sh — Ecosistema de lectura, Fase 2: Zotero (readingTime) → Calibre.
# Orquestación sin lógica; simulación por defecto; --aplicar escribe.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/../lib_comun/detectar_apps.sh"
source "$SCRIPT_DIR/../lib_comun/lock.sh"
source "$SCRIPT_DIR/../lib_comun/backup_rotado.sh"
source "$SCRIPT_DIR/lib/checks.sh"
source "$SCRIPT_DIR/lib/setup_columnas.sh"
source "$SCRIPT_DIR/lib/orquestar_metadatos.sh"

MODO="simulacion"
DESDE_TIMER=0
ACCION="sync"

ayuda() {
    cat <<'EOF'
Uso: ./main.sh [opciones]

  (sin opciones)        Simulación: columnas que faltan + qué sincronizaría.
  --aplicar             Crea columnas, respalda metadata.db y escribe de verdad
                        (requiere Calibre cerrado; Zotero puede estar abierto).
  --metadatos           Fase 3: orquesta script_sincronizar_zotero (metadatos y
                        etiquetas bidireccionales) si Calibre Y Zotero están
                        cerrados y alguna base cambió. Con --aplicar escribe.
  --enlazar             Fase 4: SOLO REPORTE de libros sin #zotero_key con su
                        candidato en Zotero (ISBN/título). Nunca escribe.
  --instalar-timer      Activa los timers (lectura 30 min; metadatos 04:30).
  --desinstalar-timer   Los detiene y elimina.
  --desde-timer         (interno) usado por los servicios systemd.
  --ayuda               Esta ayuda.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --aplicar) MODO="aplicar" ;;
        --desde-timer) DESDE_TIMER=1; MODO="aplicar" ;;
        --metadatos) ACCION="metadatos" ;;
        --enlazar) ACCION="enlazar" ;;
        --instalar-timer) ACCION="timer_on" ;;
        --desinstalar-timer) ACCION="timer_off" ;;
        --ayuda|-h|--help) ayuda; exit 0 ;;
        *) echo "✗ Opción desconocida: $1 (usa --ayuda)" >&2; exit 1 ;;
    esac
    shift
done

accion_timer_on() {
    mkdir -p "$HOME/.config/systemd/user"
    local u
    for u in ecosistema-lectura ecosistema-metadatos; do
        sed "s|@MAIN@|$SCRIPT_DIR/main.sh|" \
            "$SCRIPT_DIR/lib/systemd/$u.service" \
            > "$HOME/.config/systemd/user/$u.service"
        cp "$SCRIPT_DIR/lib/systemd/$u.timer" \
            "$HOME/.config/systemd/user/$u.timer"
    done
    systemctl --user daemon-reload
    systemctl --user enable --now ecosistema-lectura.timer ecosistema-metadatos.timer
    echo "✓ Timers activados: lectura (cada 30 min) y metadatos (diario 04:30)."
}

accion_timer_off() {
    systemctl --user disable --now ecosistema-lectura.timer ecosistema-metadatos.timer 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/ecosistema-lectura".{service,timer} \
          "$HOME/.config/systemd/user/ecosistema-metadatos".{service,timer}
    systemctl --user daemon-reload
    echo "✓ Timers desinstalados."
}

accion_metadatos() {
    tomar_lock_calibre
    # El hijo (sincronizar_zotero) hereda el lock por fd: que no intente retomarlo (C5).
    export ECOSISTEMA_LOCK_HELD=1
    comprobar_entorno
    orquestar_metadatos
}

accion_enlazar() {
    comprobar_entorno
    mkdir -p "$REPORTES_DIR"
    QEL_BIBLIOTECA="$BIBLIOTECA" QEL_ZOTERO_DB="$ZOTERO_DB" \
    QEL_REPORTE="$REPORTES_DIR/enlazar_$(date +%Y%m%d_%H%M%S).tsv" \
        python3 "$SCRIPT_DIR/lib/enlazar_reporte.py"
}

accion_sync() {
    # Lock COMPARTIDO con script_koreader_estudio: ambos escriben metadata.db.
    tomar_lock_calibre

    comprobar_entorno

    if [ "$DESDE_TIMER" = 1 ] && calibre_abierto; then
        echo "· Calibre está abierto; el timer lo reintentará luego."
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
    QEL_BIBLIOTECA="$BIBLIOTECA" \
    QEL_ZOTERO_DB="$ZOTERO_DB" \
    QEL_APLICAR="$([ "$MODO" = "aplicar" ] && echo 1 || echo 0)" \
    QEL_REPORTE="$REPORTES_DIR/sync_$(date +%Y%m%d_%H%M%S).tsv" \
    QEL_COL_ZKEY="$COL_ZKEY" QEL_COL_ZTIEMPO="$COL_ZTIEMPO" \
    QEL_COL_ZULTIMA="$COL_ZULTIMA" QEL_COL_ZPROG="$COL_ZPROG" \
        calibre-debug -e "$SCRIPT_DIR/lib/sync_zotero_lectura.py"

    if [ "$MODO" = "simulacion" ]; then
        echo ""
        echo "· Esto fue una SIMULACIÓN. Ejecuta con --aplicar para escribir."
    fi
}

case "$ACCION" in
    timer_on)   accion_timer_on ;;
    timer_off)  accion_timer_off ;;
    metadatos)  accion_metadatos ;;
    enlazar)    accion_enlazar ;;
    sync)       accion_sync ;;
esac
