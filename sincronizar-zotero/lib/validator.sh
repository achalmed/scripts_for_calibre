#!/usr/bin/env bash
# sincronizar-zotero/lib/validator.sh — Precondiciones de escritura: apps cerradas, bases sanas
# y la puerta (lib/escribir.sh). Toda escritura pasa por ensure_safe_to_apply().

# validate_database()
# A database must exist, be non-empty and contain the expected table.
# (Guards against the known trap of accidental 0-byte metadata.db files.)
# Se lee con CORE_PYTHON en solo lectura: los timers no llevan sqlite3 en el PATH (K6).
#
# Arguments:
#   $1 - Database path
#   $2 - Table that must exist
validate_database() {
    local db=$1 table=$2
    [[ -s "$db" ]] || { log_error "Base inexistente o vacia: $db"; exit 1; }
    "$CORE_PYTHON" - "$db" "$table" <<'PY' >/dev/null 2>&1 \
        || { log_error "Base sin tabla '$table' (¿fichero corrupto?): $db"; exit 1; }
import sqlite3, sys
from pathlib import Path
c = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + "?mode=ro", uri=True)
c.execute(f"SELECT 1 FROM {sys.argv[2]} LIMIT 1").fetchall()
PY
}

# ensure_apps_closed()
# Calibre and Zotero must both be closed before writing to their databases.
# La detección canónica (`ps -eo comm`) es la de core/shell-lib/detectar_apps.sh
# (calibre_abierto / zotero_abierto), que la puerta (lib/escribir.sh) ya cargó.
ensure_apps_closed() {
    if calibre_abierto; then
        log_error "Calibre esta abierto. Cierralo antes de --aplicar."
        exit 1
    fi
    # zotero launcher (comm 'zotero') o binario real (comm 'zotero-bin').
    if zotero_abierto; then
        log_error "Zotero esta abierto. Cierralo antes de --aplicar."
        exit 1
    fi
}

# ensure_safe_to_apply()
# La puerta antes de que el núcleo Python escriba con --aplicar (K3): las dos apps
# cerradas, los candados de Calibre y de Zotero y un respaldo VERIFICADO de cada
# base fuera del repo (lib/escribir.sh; antes, copias sin verificar en estado/backups).
ensure_safe_to_apply() {
    ensure_apps_closed
    puerta_calibre_abrir sincronizar_zotero "$CALIBRE_LIBRARY"
    puerta_zotero_abrir sincronizar_zotero "$ZOTERO_DB"
}
