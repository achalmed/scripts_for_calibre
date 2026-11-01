#!/usr/bin/env bash
# instalar.sh — enlaza el complemento «Ecosistema» en los complementos de KOReader (o lo quita).
#
#   koreader-plugin/instalar.sh                    # SIMULA: dice qué haría
#   koreader-plugin/instalar.sh --aplicar          # crea el enlace simbólico
#   koreader-plugin/instalar.sh --quitar [--aplicar]   # quita el enlace (solo si es un enlace)
#
# La carpeta de KOReader sale de core/env.sh (la de KOREADER_STATS, como en koreader/config.sh);
# QKO_KOREADER_CONFIG la cambia. Nunca sobrescribe ni borra una carpeta real: solo crea o quita el
# enlace simbólico `plugins/ecosistema.koplugin`. KOReader lo carga al reiniciarse.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_SH="$AQUI/../../core/env.sh"
# shellcheck source=/dev/null
[ -f "$ENV_SH" ] && source "$ENV_SH"

MODO="simular"
ACCION="instalar"
ayuda() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
    case "$1" in
        --aplicar) MODO="aplicar" ;;
        --quitar) ACCION="quitar" ;;
        -h|--ayuda|--help) ayuda; exit 0 ;;
        *) echo "✗ Opción desconocida: $1 (usa --ayuda)" >&2; exit 1 ;;
    esac
    shift
done

if [ -n "${QKO_KOREADER_CONFIG:-}" ]; then
    KOREADER_CONFIG="$QKO_KOREADER_CONFIG"
elif [ -n "${KOREADER_STATS:-}" ]; then
    KOREADER_CONFIG="$(dirname "$(dirname "$KOREADER_STATS")")"
else
    KOREADER_CONFIG="${KO_HOME:-${XDG_CONFIG_HOME:-$HOME/.config}/koreader}"
fi
FUENTE="$AQUI/ecosistema.koplugin"
DESTINO="$KOREADER_CONFIG/plugins/ecosistema.koplugin"

[ -f "$FUENTE/main.lua" ] && [ -f "$FUENTE/_meta.lua" ] || { echo "✗ No encuentro el complemento en $FUENTE" >&2; exit 1; }

hacer() {
    if [ "$MODO" = "aplicar" ]; then
        "$@"
    else
        printf '  [simulación] '; printf '%q ' "$@"; echo
    fi
}

echo "Complemento: $FUENTE"
echo "KOReader:    $KOREADER_CONFIG"

if [ "$ACCION" = "instalar" ]; then
    if [ -L "$DESTINO" ] && [ "$(readlink -f "$DESTINO")" = "$(readlink -f "$FUENTE")" ]; then
        echo "✓ Ya está instalado: $DESTINO → $FUENTE"
        exit 0
    fi
    if [ -e "$DESTINO" ] || [ -L "$DESTINO" ]; then
        echo "✗ Ya hay otra cosa en $DESTINO: no la toco. Quítela a mano o con --quitar si es un enlace." >&2
        exit 1
    fi
    [ -d "$KOREADER_CONFIG/plugins" ] || hacer mkdir -p "$KOREADER_CONFIG/plugins"
    hacer ln -s "$FUENTE" "$DESTINO"
    if [ "$MODO" = "aplicar" ]; then
        echo "✓ Instalado: $DESTINO → $FUENTE. Reinicie KOReader para cargarlo."
    else
        echo "Simulación: nada cambió. Para instalar: $0 --aplicar"
    fi
else
    if [ ! -e "$DESTINO" ] && [ ! -L "$DESTINO" ]; then
        echo "✓ No está instalado: nada que quitar."
        exit 0
    fi
    if [ ! -L "$DESTINO" ]; then
        echo "✗ $DESTINO es una carpeta real, no el enlace de este script: no la borro." >&2
        exit 1
    fi
    hacer rm "$DESTINO"
    if [ "$MODO" = "aplicar" ]; then
        echo "✓ Quitado: $DESTINO. Reinicie KOReader para descargarlo."
    else
        echo "Simulación: nada cambió. Para quitarlo: $0 --quitar --aplicar"
    fi
fi
