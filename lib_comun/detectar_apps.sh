#!/usr/bin/env bash
# lib_comun/detectar_apps.sh - Detección canónica de apps abiertas.
#
# Semántica ROBUSTA (SINCRONIZACION.md §2.3, auditoría C1/M1): se mira el
# nombre del binario (`ps -eo comm`, el ejecutable, nunca la línea de comando)
# anclado al inicio con regex insensible a mayúsculas. Evita dos trampas:
#   - el auto-match de `pgrep -f "zotero"` contra el propio shell que lo invoca
#     (el patrón aparece en su argv);
#   - `pgrep -x calibre`, que NO ve procesos arrancando y provocó que un skip
#     legítimo se contara como unidad FAILED el 2026-08-09 09:36.
# `^zotero` cubre el lanzador (comm 'zotero') y el binario real ('zotero-bin').
# `^calibre` cubre calibre, calibre-server, calibre-parallel, etc.

# _proceso_activo REGEX  → 0 si algún proceso cuyo comm casa el regex corre.
_proceso_activo() {
    ps -eo comm 2>/dev/null | grep -qiE "$1"
}

# calibre_abierto()  → verdadero si Calibre (GUI o servidor) está abierto.
calibre_abierto() {
    _proceso_activo '^calibre'
}

# zotero_abierto()  → verdadero si Zotero está abierto.
zotero_abierto() {
    _proceso_activo '^zotero'
}
