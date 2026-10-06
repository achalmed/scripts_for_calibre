# lib/checks.sh — Comprobaciones previas (una responsabilidad: validar entorno)

comprobar_entorno() {
    local errores=0
    command -v calibredb >/dev/null 2>&1 || { echo "✗ calibredb no está en el PATH." >&2; errores=1; }
    command -v calibre-debug >/dev/null 2>&1 || { echo "✗ calibre-debug no está en el PATH." >&2; errores=1; }
    [ -f "$BIBLIOTECA/metadata.db" ] || { echo "✗ Sin biblioteca Calibre en: $BIBLIOTECA" >&2; errores=1; }
    if [ ! -f "$ZOTERO_DB" ]; then
        echo "✗ No existe $ZOTERO_DB." >&2; errores=1
    fi
    return "$errores"
}

# Calibre cerrado antes de escribir lo exige la puerta (lib/escribir.sh, puerta_calibre_abrir). Zotero SÍ
# puede estar abierto en accion_sync: su base solo se lee (modo ro).
