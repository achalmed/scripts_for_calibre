#!/usr/bin/env bash
# tests/run.sh — corre las pruebas de Biblioteca Studio (tests/studio) con pytest, con la carpeta temporal en disco y sin caché.
# Uso: tests/run.sh [opciones de pytest]   (p. ej. -k operaciones)
# Las de las suites (tests/calibre, tests/fuentes) se corren aparte, como dice CLAUDE.md: son lentas y copian las bases.
# La carpeta temporal va a ~/.cache (no a /tmp, que es RAM). Nada toca la biblioteca real: cada prueba crea una biblioteca
# Calibre de muestra con libros ficticios (studio/muestra.py; calibredb si está, si no una metadata.db mínima) en un
# temporal. Las pruebas en proceso usan el binding del Python que corre pytest; las de QML y la de humo abren un proceso
# hijo con el Python del sistema (/usr/bin/python3, el del Qt con Kirigami) sin pantalla (QT_QPA_PLATFORM=offscreen) y con
# XDG_CONFIG_HOME, XDG_CACHE_HOME y XDG_STATE_HOME temporales: ni las preferencias ni el índice del autor se tocan.
set -euo pipefail

DIR_PRUEBAS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/studio"
BASE_TMP="${XDG_CACHE_HOME:-$HOME/.cache}/pytest/biblioteca-studio-studio"
mkdir -p "$BASE_TMP"

export PYTHONDONTWRITEBYTECODE=1
export QT_QPA_PLATFORM=offscreen
exec python3 -m pytest "$DIR_PRUEBAS" --basetemp "$BASE_TMP" -p no:cacheprovider -q "$@"
