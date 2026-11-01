#!/usr/bin/env bash
# build.sh — empaqueta la extensión «Ecosistema» en dist/ecosistema-<versión>.xpi (un zip con manifest.json en la raíz).
#
# Objetivo: un .xpi instalable desde Zotero → Herramientas → Complementos → Instalar desde archivo.
# Método: lee la versión de manifest.json, comprueba la sintaxis de cada .js con node (si está) y comprime solo lo que
#   la extensión necesita; no escribe fuera de zotero-plugin/dist/.
# Uso:    ./build.sh            # construye y lista el contenido
#         ./build.sh --dry-run  # dice qué empaquetaría, sin escribir
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST="$AQUI/dist"
SIMULAR=0
[[ "${1:-}" == "--dry-run" ]] && SIMULAR=1

VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$AQUI/manifest.json")"
XPI="$DIST/ecosistema-$VERSION.xpi"
ARCHIVOS=(manifest.json bootstrap.js prefs.js content locale)

if command -v node >/dev/null; then
    for js in "$AQUI/bootstrap.js" "$AQUI"/content/*.js; do
        node --check "$js"
    done
fi

if (( SIMULAR )); then
    echo "[simulación] empaquetaría en $XPI:"
    ( cd "$AQUI" && find "${ARCHIVOS[@]}" -type f | sort )
    exit 0
fi

mkdir -p "$DIST"
rm -f "$XPI"
( cd "$AQUI" && zip -q -r -X "$XPI" "${ARCHIVOS[@]}" )
echo "✓ $XPI"
unzip -l "$XPI"
