#!/usr/bin/env bash
# lib/escribir.sh — la única puerta de escritura de scripts_for_calibre en metadata.db y zotero.sqlite (ola 2a, K2).
# Módulo: se carga con `source` y hereda las opciones de la shell que lo carga; no fija `set -euo pipefail` (normativa 5.18).
#
# Abrir la puerta de Calibre es, en este orden y todo o nada (normativa 9.1, RQ-PRE-06):
#   1. Calibre cerrado (`calibre_abierto` de core/shell-lib/detectar_apps.sh); abierto → devuelve 1;
#   2. el candado único `LOCK_CALIBRE` (core/shell-lib/lock.sh); ocupado → sale 75, «reintentar luego»;
#   3. un respaldo verificado de metadata.db (`backup_metadata_db` de core: copia, cmp, quick_check, rotación);
#      sin respaldo → devuelve 1 y no se escribe.
# Después, y solo después, se escribe con `calibredb_escribe` (calibredb) o con la API de Calibre desde
# Python (`lib/escribir.py`, que exige PUERTA_CALIBRE=abierta). La de Zotero es igual con Zotero cerrado,
# `LOCK_ZOTERO` y un respaldo verificado de zotero.sqlite. Ningún otro archivo del repo escribe en las bases:
# lo comprueba tests/test_puerta.py.
#
# Los respaldos viven fuera del repo, en el estado de usuario: $PUERTA_RESPALDOS/<suite>/{calibre,zotero}/.

_PUERTA_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# core/ es hermano del repo; env.sh respeta lo que ya traiga el entorno (CALIBRE_DB, LOCK_CALIBRE, …).
source "$_PUERTA_LIB/../../core/env.sh"
source "$SHELL_LIB/detectar_apps.sh"
source "$SHELL_LIB/lock.sh"
source "$SHELL_LIB/backup_rotado.sh"

: "${PUERTA_RESPALDOS:=${XDG_STATE_HOME:-$HOME/.local/state}/biblioteca/respaldos}"
: "${PUERTA_CONSERVAR_CALIBRE:=5}"
: "${PUERTA_CONSERVAR_ZOTERO:=3}"
PUERTA_PY="$_PUERTA_LIB/escribir.py"

# puerta_candado_calibre — toma el candado de Calibre una sola vez por proceso (ocupado: sale 75).
puerta_candado_calibre() {
    [ "${_PUERTA_CANDADO_CALIBRE:-0}" = 1 ] && return 0
    tomar_lock_calibre
    _PUERTA_CANDADO_CALIBRE=1
}

# puerta_candado_zotero — ídem con LOCK_ZOTERO (fd 8).
puerta_candado_zotero() {
    [ "${_PUERTA_CANDADO_ZOTERO:-0}" = 1 ] && return 0
    tomar_lock_zotero
    _PUERTA_CANDADO_ZOTERO=1
}

# puerta_calibre_abrir SUITE BIBLIOTECA — Calibre cerrado, candado y respaldo verificado; exporta
# PUERTA_CALIBRE=abierta y PUERTA_BIBLIOTECA. Idempotente para la misma biblioteca.
puerta_calibre_abrir() {
    local suite="${1:?puerta_calibre_abrir: falta la suite}" bib="${2:?puerta_calibre_abrir: falta la biblioteca}"
    if [ "${PUERTA_CALIBRE:-}" = abierta ] && [ "${PUERTA_BIBLIOTECA:-}" = "$bib" ] && [ "${_PUERTA_RESPALDO_CALIBRE:-}" ]; then
        return 0
    fi
    if calibre_abierto; then
        echo "✗ Calibre está abierto: ciérralo antes de escribir en la biblioteca." >&2
        return 1
    fi
    [ -f "$bib/metadata.db" ] || { echo "✗ No hay biblioteca Calibre en: $bib" >&2; return 1; }
    puerta_candado_calibre
    local salida
    salida="$(backup_metadata_db "$bib/metadata.db" "$PUERTA_RESPALDOS/$suite/calibre" "$PUERTA_CONSERVAR_CALIBRE")" || {
        echo "✗ Sin respaldo verificado de metadata.db no se escribe." >&2
        return 1
    }
    echo "$salida"
    _PUERTA_RESPALDO_CALIBRE="${salida#── Backup: }"
    export PUERTA_CALIBRE=abierta PUERTA_BIBLIOTECA="$bib"
}

# puerta_zotero_abrir SUITE ZOTERO_DB — Zotero cerrado, LOCK_ZOTERO y respaldo verificado; exporta
# PUERTA_ZOTERO=abierta y PUERTA_ZOTERO_DB.
puerta_zotero_abrir() {
    local suite="${1:?puerta_zotero_abrir: falta la suite}" db="${2:?puerta_zotero_abrir: falta la base}"
    if [ "${PUERTA_ZOTERO:-}" = abierta ] && [ "${PUERTA_ZOTERO_DB:-}" = "$db" ] && [ "${_PUERTA_RESPALDO_ZOTERO:-}" ]; then
        return 0
    fi
    if zotero_abierto; then
        echo "✗ Zotero está abierto: ciérralo antes de escribir en zotero.sqlite." >&2
        return 1
    fi
    [ -s "$db" ] || { echo "✗ No existe la base de Zotero: $db" >&2; return 1; }
    puerta_candado_zotero
    local salida
    salida="$("$CORE_PYTHON" "$PUERTA_PY" respaldar "$db" "$PUERTA_RESPALDOS/$suite/zotero" zotero "$PUERTA_CONSERVAR_ZOTERO")" || {
        echo "✗ Sin respaldo verificado de zotero.sqlite no se escribe." >&2
        return 1
    }
    echo "── Backup: $salida"
    _PUERTA_RESPALDO_ZOTERO="$salida"
    export PUERTA_ZOTERO=abierta PUERTA_ZOTERO_DB="$db"
}

# puerta_respaldos — las rutas de los respaldos de esta corrida (para mensajes de «restaura esto»).
puerta_respaldos() {
    printf '%s\n' ${_PUERTA_RESPALDO_CALIBRE:+"calibre: $_PUERTA_RESPALDO_CALIBRE"} ${_PUERTA_RESPALDO_ZOTERO:+"zotero: $_PUERTA_RESPALDO_ZOTERO"}
}

# calibredb_escribe SUBCOMANDO ARGS… — calibredb sobre la biblioteca de la puerta, que debe estar abierta.
calibredb_escribe() {
    if [ "${PUERTA_CALIBRE:-}" != abierta ] || [ -z "${PUERTA_BIBLIOTECA:-}" ]; then
        echo "✗ calibredb_escribe: la puerta de Calibre está cerrada (puerta_calibre_abrir primero)." >&2
        return 1
    fi
    local sub="${1:?calibredb_escribe: falta el subcomando}"; shift
    calibredb "$sub" --with-library "$PUERTA_BIBLIOTECA" "$@"
}

# puerta_integridad — PRAGMA integrity_check (solo lectura) de las bases abiertas por la puerta; ≠ ok → 1.
puerta_integridad() {
    local bases=()
    [ "${PUERTA_CALIBRE:-}" = abierta ] && bases+=("$PUERTA_BIBLIOTECA/metadata.db")
    [ "${PUERTA_ZOTERO:-}" = abierta ] && bases+=("$PUERTA_ZOTERO_DB")
    [ "${#bases[@]}" -gt 0 ] || return 0
    "$CORE_PYTHON" "$PUERTA_PY" integridad "${bases[@]}" || {
        echo "✗ INTEGRIDAD FALLIDA. Restaura los respaldos:" >&2
        puerta_respaldos >&2
        return 1
    }
}
