#!/usr/bin/env bash
# calibre-plugin/instalar.sh — empaqueta el complemento «Ecosistema» y lo instala en Calibre (calibre-customize).
# Uso: ./instalar.sh            simula: dice qué haría
#      ./instalar.sh --aplicar  empaqueta en dist/ecosistema.zip y lo instala (con Calibre cerrado)
#      ./instalar.sh --quitar [--aplicar]   lo quita
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP="$DIR/dist/ecosistema.zip"
APLICAR=false; QUITAR=false
for a in "$@"; do case "$a" in --aplicar) APLICAR=true ;; --quitar) QUITAR=true ;; *) echo "opción desconocida: $a" >&2; exit 2 ;; esac; done
if pgrep -x calibre >/dev/null 2>&1 || pgrep -f '^/[^ ]*calibre( |$)' >/dev/null 2>&1; then
    echo "Calibre está abierto: ciérralo antes de instalar o quitar el complemento." >&2; exit 75
fi
if $QUITAR; then
    if $APLICAR; then calibre-customize -r "Ecosistema"; else echo "[simulación] calibre-customize -r Ecosistema"; fi
    exit 0
fi
if ! $APLICAR; then
    echo "[simulación] empaquetaría $DIR/ecosistema en $ZIP y ejecutaría: calibre-customize -a $ZIP"
    exit 0
fi
mkdir -p "$DIR/dist"
rm -f "$ZIP"
( cd "$DIR/ecosistema" && python3 -c "import sys, zipfile, pathlib
z = zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED)
for p in sorted(pathlib.Path('.').iterdir()):
    if p.is_file() and p.suffix in ('.py', '.txt'):
        z.write(p, p.name)
z.close()" "$ZIP" )
calibre-customize -a "$ZIP"
echo "✓ Instalado. En Calibre: Preferencias → Barras de herramientas y menús → añade «Ecosistema» a la barra principal."
