#!/usr/bin/env bash
# lib/leer.sh — lecturas de SQLite en solo lectura con CORE_PYTHON, sin el binario sqlite3 (ola 2a, K6).
# Módulo: se carga con `source` y hereda las opciones de la shell que lo carga; no fija `set -euo pipefail` (normativa 5.18).
#
# Los timers corren con un PATH mínimo, sin anaconda (P221), y el sistema no trae `sqlite3`: toda lectura
# de metadata.db, zotero.sqlite o statistics.sqlite3 desde Bash pasa por aquí (mode=ro; abrir no escribe).
[ -n "${CORE_PYTHON:-}" ] || source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../core/env.sh"

# sql_ro BASE CONSULTA — filas separadas por tabuladores, sin cabecera; NULL → vacío.
sql_ro() {
    "$CORE_PYTHON" - "$1" "$2" <<'PY'
import sqlite3, sys
from pathlib import Path
c = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + "?mode=ro", uri=True)
for fila in c.execute(sys.argv[2]):
    print("\t".join("" if v is None else str(v) for v in fila))
PY
}

# etiquetas_calibre BIBLIOTECA — las etiquetas de las columnas personalizadas, una por línea.
etiquetas_calibre() {
    sql_ro "$1/metadata.db" "SELECT label FROM custom_columns"
}

# volcar_sqlite BASE — volcado SQL en texto (restaurable con `sqlite3 nueva.db < volcado.sql`).
volcar_sqlite() {
    "$CORE_PYTHON" - "$1" <<'PY'
import sqlite3, sys
from pathlib import Path
c = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + "?mode=ro", uri=True)
for linea in c.iterdump():
    print(linea)
PY
}
