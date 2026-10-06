#!/usr/bin/env bash
# systemd/instalar.sh — instala, verifica o retira los tres timers de usuario de la biblioteca (ola 2a, K6).
#
# Las plantillas de esta carpeta (ecosistema-lectura, ecosistema-metadatos, koreader-calibre-sync) llevan
# @RAIZ@ en lugar de la carpeta del repo; al instalarlas se escribe `%h/<ruta bajo el HOME>` (nunca la
# carpeta de inicio literal, RQ-RUT-02). Las unidades instaladas son exactamente las plantillas
# renderizadas: `--verificar` lo comprueba. ~/.dotfiles no las gestiona (decisiones §4.5).
#
# Uso:
#   systemd/instalar.sh                    simula: muestra qué escribiría y en qué difiere de lo instalado
#   systemd/instalar.sh --aplicar          escribe las unidades, daemon-reload y enable --now de los timers
#   systemd/instalar.sh --verificar        0 si lo instalado = las plantillas renderizadas; 1 y diff si no
#   systemd/instalar.sh --desinstalar [--aplicar]   detiene y retira (simula sin --aplicar)
# Opciones: --unidades "a b" (por defecto las tres) · --destino DIR (otra carpeta; sin systemctl) ·
#           --renderizar DIR (solo escribe las unidades renderizadas en DIR, para systemd-analyze verify).
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
UNIDADES="ecosistema-lectura ecosistema-metadatos koreader-calibre-sync"
DESTINO="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SYSTEMCTL=1
MODO=simular
ACCION=instalar
RENDER_DIR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --aplicar) MODO=aplicar ;;
        --verificar) ACCION=verificar ;;
        --desinstalar) ACCION=desinstalar ;;
        --unidades) UNIDADES="${2:?--unidades necesita una lista}"; shift ;;
        --destino) DESTINO="${2:?--destino necesita una carpeta}"; SYSTEMCTL=0; shift ;;
        --renderizar) ACCION=renderizar; RENDER_DIR="${2:?--renderizar necesita una carpeta}"; shift ;;
        -h|--ayuda|--help) sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "✗ Opción desconocida: $1 (usa --ayuda)" >&2; exit 2 ;;
    esac
    shift
done

# La raíz como la ve systemd: %h/<relativa> si cuelga del HOME; si no, absoluta.
raiz_systemd() {
    case "$RAIZ/" in
        "$HOME"/*) printf '%%h/%s' "${RAIZ#"$HOME"/}" ;;
        *) printf '%s' "$RAIZ" ;;
    esac
}

renderizar() {   # renderizar ARCHIVO → stdout
    local r; r="$(raiz_systemd)"
    sed "s|@RAIZ@|$r|g" "$AQUI/$1"
}

archivos() {
    local u
    for u in $UNIDADES; do
        [ -f "$AQUI/$u.service" ] && [ -f "$AQUI/$u.timer" ] || { echo "✗ Sin plantilla: $u" >&2; exit 2; }
        printf '%s\n' "$u.service" "$u.timer"
    done
}

difiere() {   # difiere ARCHIVO → 0 si lo instalado difiere de la plantilla renderizada
    ! diff -q <(renderizar "$1") "$DESTINO/$1" >/dev/null 2>&1
}

case "$ACCION" in
    renderizar)
        mkdir -p "$RENDER_DIR"
        for f in $(archivos); do renderizar "$f" > "$RENDER_DIR/$f"; done
        echo "── Unidades renderizadas en $RENDER_DIR"
        ;;
    verificar)
        distintas=0
        for f in $(archivos); do
            if difiere "$f"; then
                distintas=$((distintas + 1))
                echo "✗ $DESTINO/$f no es la plantilla renderizada:"
                diff <(renderizar "$f") "$DESTINO/$f" 2>&1 | sed 's/^/    /' || true
            fi
        done
        [ "$distintas" -eq 0 ] && echo "✓ Las unidades instaladas son las plantillas ($UNIDADES)."
        [ "$distintas" -eq 0 ]
        ;;
    instalar)
        for f in $(archivos); do
            if difiere "$f"; then
                echo "· $DESTINO/$f cambiaría:"
                diff <(renderizar "$f") "$DESTINO/$f" 2>&1 | sed 's/^/    /' || true
            else
                echo "= $DESTINO/$f ya es la plantilla."
            fi
        done
        if [ "$MODO" != aplicar ]; then
            echo "· Simulación: nada escrito. Con --aplicar se instalan y se activan los timers."
            exit 0
        fi
        mkdir -p "$DESTINO"
        for f in $(archivos); do renderizar "$f" > "$DESTINO/$f"; done
        if [ "$SYSTEMCTL" = 1 ]; then
            systemctl --user daemon-reload
            for u in $UNIDADES; do systemctl --user enable --now "$u.timer"; done
        fi
        echo "✓ Instaladas en $DESTINO: $UNIDADES"
        ;;
    desinstalar)
        if [ "$MODO" != aplicar ]; then
            echo "· Simulación: se detendrían y retirarían: $UNIDADES (de $DESTINO). Con --aplicar se hace."
            exit 0
        fi
        if [ "$SYSTEMCTL" = 1 ]; then
            for u in $UNIDADES; do systemctl --user disable --now "$u.timer" 2>/dev/null || true; done
        fi
        for f in $(archivos); do rm -f -- "$DESTINO/$f"; done
        [ "$SYSTEMCTL" = 1 ] && systemctl --user daemon-reload
        echo "✓ Retiradas de $DESTINO: $UNIDADES"
        ;;
esac
