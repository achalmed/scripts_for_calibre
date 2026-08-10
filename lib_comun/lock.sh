#!/usr/bin/env bash
# lib_comun/lock.sh - Candado compartido de escritura a metadata.db.
#
# TODO escritor de metadata.db (timers y ejecuciones manuales) serializa con el
# mismo flock sobre .lock_calibre_write en la raíz del repo (SINCRONIZACION.md
# §2.4, auditoría C5). El descriptor fd 9 se mantiene abierto durante toda la
# vida del proceso: el candado se libera solo al salir.
#
# Réplica del patrón de script_ecosistema_lectura/main.sh y
# script_sincronizar_zotero/main.sh.

# ruta_lock_calibre()
# Devuelve la ruta del .lock_calibre_write en la raíz del repo scripts_for_calibre.
# Respeta la variable LOCK_ESCRITURA_CALIBRE si el config de la suite la define;
# si no, la deriva desde la ubicación de este módulo (lib_comun/ está en la raíz).
ruta_lock_calibre() {
    if [ -n "${LOCK_ESCRITURA_CALIBRE:-}" ]; then
        printf '%s\n' "$LOCK_ESCRITURA_CALIBRE"
        return 0
    fi
    local dir_comun
    dir_comun="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    printf '%s\n' "$dir_comun/../.lock_calibre_write"
}

# tomar_lock_calibre()
# Toma el flock no bloqueante sobre .lock_calibre_write usando fd 9. Si otra
# herramienta lo tiene, sale con exit 0 y un mensaje (un lock ocupado NO es un
# fallo: el timer reintenta a los 30 min). Respeta ECOSISTEMA_LOCK_HELD=1: si el
# orquestador ya heredó el lock por fd, no se re-toma (evita el deadlock del
# hijo contra el padre, C5).
tomar_lock_calibre() {
    [ "${ECOSISTEMA_LOCK_HELD:-0}" = "1" ] && return 0
    local lock
    lock="$(ruta_lock_calibre)"
    exec 9>"$lock"
    if ! flock -n 9; then
        echo "· Otra herramienta del ecosistema está escribiendo en Calibre; reintenta luego." >&2
        exit 0
    fi
}
