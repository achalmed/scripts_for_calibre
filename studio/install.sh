#!/usr/bin/env bash
# install.sh — instala Biblioteca Studio: su acceso directo en el menú de aplicaciones, con su icono, y el esquema
# biblioteca-studio:// que usan los complementos de Calibre, KOReader y Zotero (gui_comun.lanzador).
# Uso: studio/install.sh [-n]        instala (con -n, solo dice qué escribiría)
#      studio/install.sh --quitar    quita el acceso directo, su icono y el esquema
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$(command -v python3)}"
if [[ "${1:-}" == "--quitar" ]]; then
    shift
    exec "$PYTHON" "$DIR/main.py" --quitar-lanzador "$@"
fi
exec "$PYTHON" "$DIR/main.py" --instalar-lanzador "$@"
