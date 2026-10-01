#!/usr/bin/env bash
# main.sh — acciones A–D de meta/diagnosticos/DUPLICADOS_BIBLIOTECA_2026-10.md (aprobadas el 2026-10-01).
# Uso: main.sh (simula) · main.sh --aplicar (Calibre y Zotero cerrados). Deshacer: deshacer.sh
set -euo pipefail
cd "$(dirname "$0")"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
[ "${1:-}" = "--aplicar" ] || { python3 aplicar.py; exit 0; }
pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null && { echo "Calibre está abierto: ciérralo." >&2; exit 1; }
pgrep -x "zotero|zotero-bin" >/dev/null && { echo "Zotero está abierto: ciérralo." >&2; exit 1; }
[ -e hechos.tsv ] && { echo "Ya aplicada (hay hechos.tsv)." >&2; exit 1; }
tomar_lock_calibre
export ECOSISTEMA_LOCK_HELD=1
python3 aplicar.py --aplicar
python3 ../grafias_autores_2026-09-30/verificar.py
