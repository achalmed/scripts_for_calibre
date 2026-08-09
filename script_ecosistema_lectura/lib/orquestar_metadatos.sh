# lib/orquestar_metadatos.sh — Fase 3: correr script_sincronizar_zotero
# (metadatos + etiquetas bidireccionales) SOLO cuando es seguro y necesario:
# Calibre y Zotero cerrados + alguna base cambió desde la última pasada.

# Detección CANÓNICA (auditoría C1): `ps -eo comm` ve procesos arrancando que
# `pgrep -x` no ve — esa divergencia convirtió un skip legítimo en unidad
# FAILED el 2026-08-09 09:36. Misma semántica que sincronizar/lib/validator.sh.
zotero_abierto() {
    ps -eo comm | grep -qiE '^zotero'
}

calibre_abierto_estricto() {
    ps -eo comm | grep -qiE '^calibre'
}

orquestar_metadatos() {
    if [ ! -x "$SINCRONIZAR_ZOTERO_DIR/main.sh" ]; then
        echo "✗ No encuentro $SINCRONIZAR_ZOTERO_DIR/main.sh" >&2
        return 1
    fi
    if calibre_abierto || calibre_abierto_estricto; then
        echo "· Calibre está abierto; la orquestación reintentará luego."
        return 0
    fi
    if zotero_abierto; then
        echo "· Zotero está abierto; la orquestación reintentará luego."
        return 0
    fi

    # ¿Cambió algo desde la última orquestación aplicada?
    mkdir -p "$ESTADO_DIR"
    local marca="$ESTADO_DIR/ultima_orquestacion_epoch"
    local ultimo=0
    [ -f "$marca" ] && ultimo=$(cat "$marca" 2>/dev/null || echo 0)
    local mt_cal mt_zot reciente
    mt_cal=$(stat -c %Y "$BIBLIOTECA/metadata.db" 2>/dev/null || echo 0)
    mt_zot=$(stat -c %Y "$ZOTERO_DB" 2>/dev/null || echo 0)
    reciente=$(( mt_cal > mt_zot ? mt_cal : mt_zot ))
    if [ "$reciente" -le "$ultimo" ] && [ "$MODO" = "aplicar" ]; then
        echo "· Sin cambios en las bases desde la última orquestación; nada que hacer."
        return 0
    fi

    echo "── Orquestando script_sincronizar_zotero ($MODO) ─────────"
    local inicio; inicio=$(date +%s)
    if [ "$MODO" = "aplicar" ]; then
        bash "$SINCRONIZAR_ZOTERO_DIR/main.sh" --aplicar </dev/null
        date +%s > "$marca"
    else
        bash "$SINCRONIZAR_ZOTERO_DIR/main.sh" </dev/null
    fi
    echo "── Orquestación terminada en $(( $(date +%s) - inicio ))s"
}
