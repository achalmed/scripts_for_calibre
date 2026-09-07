#!/usr/bin/env bash
# main.sh — script_ingesta_recursos: material externo de los cursos → Calibre (F5.4, 2026-09-06).
#   ./main.sh --escanear                    escribe reportes/candidatos_<fecha>.tsv (decisión propuesta por fila)
#   ./main.sh --aplicar [--tsv ARCHIVO]     ingesta las filas decision=ingestar (Calibre cerrado; toma el lock; backup de metadata.db)
#   ./main.sh [--tsv ARCHIVO]               simula la ingesta (por defecto)
# Edita el TSV (columna decision) antes de --aplicar si quieres afinar qué entra.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/../lib_comun/logger.sh"
source "$SCRIPT_DIR/../lib_comun/detectar_apps.sh"
source "$SCRIPT_DIR/../lib_comun/lock.sh"
source "$SCRIPT_DIR/../lib_comun/backup_rotado.sh"
source "$SCRIPT_DIR/lib/clasificar.sh"
source "$SCRIPT_DIR/lib/ingestar.sh"
MODO=simular; TSV=""
while [ $# -gt 0 ]; do case "$1" in
    --escanear) MODO=escanear;; --aplicar) MODO=aplicar;; --tsv) TSV="$2"; shift;;
    -h|--help) sed -n '2,7p' "$0"; exit 0;; *) log_error "argumento desconocido: $1"; exit 2;; esac; shift; done
for d in pdfinfo python3 "$CALIBREDB"; do command -v "$d" >/dev/null || { log_error "falta dependencia: $d"; exit 5; }; done
mkdir -p "$REPORTES_DIR"
if [ "$MODO" = escanear ]; then
    out="$REPORTES_DIR/candidatos_$(date +%Y%m%d_%H%M%S).tsv"; escanear "$out"
    log_info "candidatos: $out"; awk -F'\t' 'NR>1{c[$1]++} END{for(k in c) printf "  %s=%d\n", k, c[k]}' "$out"; exit 0
fi
[ -n "$TSV" ] || TSV="$(ls -t "$REPORTES_DIR"/candidatos_*.tsv 2>/dev/null | head -1)"
[ -f "$TSV" ] || { log_error "no hay TSV de candidatos; ejecuta --escanear"; exit 3; }
if [ "$MODO" = aplicar ]; then
    calibre_abierto && { log_error "Calibre está abierto: ciérralo antes de --aplicar"; exit 1; }
    tomar_lock_calibre
    backup_metadata_db "$BIBLIOTECA/metadata.db" "$BACKUPS_DIR" "$BACKUPS_CONSERVAR"
    ingestar_tsv "$TSV" 1
else
    ingestar_tsv "$TSV" 0
fi
