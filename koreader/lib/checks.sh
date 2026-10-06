# lib/checks.sh — Comprobaciones previas (una responsabilidad: validar entorno)

comprobar_entorno() {
    local errores=0

    if ! command -v calibredb >/dev/null 2>&1; then
        echo "✗ calibredb no está en el PATH." >&2; errores=1
    fi
    if ! command -v calibre-debug >/dev/null 2>&1; then
        echo "✗ calibre-debug no está en el PATH (viene con Calibre)." >&2; errores=1
    fi
    if [ ! -f "$BIBLIOTECA/metadata.db" ]; then
        echo "✗ No se encontró la biblioteca Calibre en: $BIBLIOTECA" >&2; errores=1
    fi
    if [ ! -f "$STATS_DB" ]; then
        echo "⚠ No existe $STATS_DB (¿plugin de estadísticas de KOReader activo?)." >&2
        echo "  Se sincronizará solo con los sidecars .sdr." >&2
    fi
    return "$errores"
}

# Calibre cerrado antes de escribir lo exige la puerta (lib/escribir.sh, puerta_calibre_abrir).

koreader_abierto() {
    pgrep -f "koreader/luajit|/usr/bin/koreader" >/dev/null 2>&1
}

exigir_koreader_cerrado() {
    if koreader_abierto; then
        echo "✗ KOReader está abierto. Ciérralo antes de migrar sidecars." >&2
        return 1
    fi
    return 0
}
