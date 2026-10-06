#!/usr/bin/env bash
# main.sh — Ecosistema de lectura, Fase 2: Zotero (readingTime) → Calibre.
# Orquestación sin lógica; simulación por defecto; --aplicar escribe.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/../lib/escribir.sh"     # la puerta de escritura (K2): core/env, detección, candado, respaldo
source "$SCRIPT_DIR/../lib/leer.sh"         # lecturas de SQLite con CORE_PYTHON (K6)
source "$SCRIPT_DIR/lib/checks.sh"
source "$SCRIPT_DIR/lib/setup_columnas.sh"
source "$SCRIPT_DIR/lib/orquestar_metadatos.sh"

MODO="simulacion"
DESDE_TIMER=0
ACCION="sync"
RIS=0

ayuda() {
    cat <<'EOF'
Uso: ./main.sh [opciones]

  (sin opciones)        Simulación: columnas que faltan + qué sincronizaría.
  --aplicar             Crea columnas, respalda metadata.db y escribe de verdad
                        (requiere Calibre cerrado; Zotero puede estar abierto).
  --metadatos           Fase 3: orquesta script_sincronizar_zotero (metadatos y
                        etiquetas bidireccionales) si Calibre Y Zotero están
                        cerrados y alguna base cambió. Con --aplicar escribe.
  --enlazar             Fase 4: reporte de libros sin #zotero_key con su candidato
                        en Zotero (adjunto/ISBN/título) y de las claves anómalas.
                        Con --ris escribe además el .ris de los libros sin ningún
                        candidato (para Zotero: Archivo → Importar, enlazar).
                        Con --aplicar escribe #zotero_key SOLO de los candidatos
                        «adjunto» (el ítem enlaza el PDF del libro); Calibre cerrado.
  --instalar-timer      Activa los timers (lectura 30 min; metadatos 04:30) desde las
                        plantillas de systemd/ (systemd/instalar.sh --aplicar).
  --desinstalar-timer   Los detiene y retira (systemd/instalar.sh --desinstalar --aplicar).
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
        --ris) RIS=1 ;;
        --instalar-timer) ACCION="timer_on" ;;
        --desinstalar-timer) ACCION="timer_off" ;;
        --ayuda|-h|--help) ayuda; exit 0 ;;
        *) echo "✗ Opción desconocida: $1 (usa --ayuda)" >&2; exit 1 ;;
    esac
    shift
done

# Los timers se instalan desde las plantillas versionadas de systemd/ (K6): %h, sin anaconda en el PATH.
accion_timer_on() {
    "$SCRIPT_DIR/../systemd/instalar.sh" --aplicar --unidades "ecosistema-lectura ecosistema-metadatos"
}

accion_timer_off() {
    "$SCRIPT_DIR/../systemd/instalar.sh" --desinstalar --aplicar --unidades "ecosistema-lectura ecosistema-metadatos"
}

accion_metadatos() {
    puerta_candado_calibre
    # El hijo (sincronizar_zotero) hereda el lock por fd: que no intente retomarlo (C5).
    export ECOSISTEMA_LOCK_HELD=1
    comprobar_entorno
    orquestar_metadatos
}

accion_enlazar() {
    comprobar_entorno
    mkdir -p "$REPORTES_DIR"
    local ts pares ris=""
    ts="$(date +%Y%m%d_%H%M%S)"
    pares="$REPORTES_DIR/enlazar_${ts}_pares.tsv"
    [ "$RIS" = 1 ] && ris="$REPORTES_DIR/enlazar_${ts}.ris"
    QEL_BIBLIOTECA="$BIBLIOTECA" QEL_ZOTERO_DB="$ZOTERO_DB" \
    QEL_REPORTE="$REPORTES_DIR/enlazar_${ts}.tsv" QEL_PARES="$pares" QEL_RIS="$ris" \
        "$CORE_PYTHON" "$SCRIPT_DIR/lib/enlazar_reporte.py"
    local n; n="$(wc -l < "$pares")"
    if [ "$MODO" != "aplicar" ]; then
        echo "· Simulación: --enlazar --aplicar escribiría $n claves «adjunto» (lista: $pares)."
        return 0
    fi
    [ "$n" -gt 0 ] || { echo "· Nada que enlazar por adjunto."; return 0; }
    puerta_calibre_abrir ecosistema_lectura "$BIBLIOTECA"
    local bid key hechas=0
    while IFS=$'\t' read -r bid key; do
        calibredb_escribe set_custom "$COL_ZKEY" "$bid" "$key" >/dev/null
        hechas=$((hechas + 1))
    done < "$pares"
    echo "· $hechas claves escritas en #$COL_ZKEY (respaldo previo: $(puerta_respaldos))."
    return 0
}

accion_sync() {
    # Candado COMPARTIDO con script_koreader_estudio: ambos escriben metadata.db.
    puerta_candado_calibre

    comprobar_entorno

    if [ "$DESDE_TIMER" = 1 ] && calibre_abierto; then
        echo "· Calibre está abierto; el timer lo reintentará luego."
        exit 0
    fi
    if [ "$MODO" = "aplicar" ]; then
        # La puerta: Calibre cerrado, candado y respaldo verificado antes de crear columnas o escribir.
        puerta_calibre_abrir ecosistema_lectura "$BIBLIOTECA"
    fi

    setup_columnas

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
