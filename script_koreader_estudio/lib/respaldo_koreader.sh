# lib/respaldo_koreader.sh — Respaldo de los datos valiosos de KOReader hacia
# su repo git de datos ($RESPALDO_KOREADER_DIR = core/env.sh KOREADER_RESPALDO_DIR,
# ~/.local/share/koreader-respaldo; hasta FG3 fue ~/.dotfiles/koreader-data), todo
# en texto para que git lo versione bien: dump SQL + sidecars .lua + historial.
# Los datos vivos siguen en ~/.config/koreader; esto es un respaldo versionado.
# Publicar al remoto = `git -C "$RESPALDO_KOREADER_DIR" push`.
# settings.reader.lua NO se respalda aquí: contiene el bloque kosync (credenciales).

respaldar_koreader() {
    [ -d "$KOREADER_CONFIG" ] || return 0
    mkdir -p "$RESPALDO_KOREADER_DIR/hashdocsettings"

    # 1) Estadísticas → dump SQL (texto, restaurable con: sqlite3 nueva.db < statistics.sql)
    #    Con CORE_PYTHON (lib/leer.sh, K6): los timers no llevan sqlite3 en el PATH.
    if [ -f "$STATS_DB" ]; then
        volcar_sqlite "$STATS_DB" > "$RESPALDO_KOREADER_DIR/statistics.sql" 2>/dev/null || true
    fi

    # 2) Sidecars hash (lua de texto) + historial
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$KOREADER_CONFIG/hashdocsettings/" \
            "$RESPALDO_KOREADER_DIR/hashdocsettings/" 2>/dev/null || true
    else
        cp -a "$KOREADER_CONFIG/hashdocsettings/." \
            "$RESPALDO_KOREADER_DIR/hashdocsettings/" 2>/dev/null || true
    fi
    cp -a "$KOREADER_CONFIG/history.lua" "$RESPALDO_KOREADER_DIR/" 2>/dev/null || true

    # 3) Commit local en el repo de datos de lectura (solo si hay cambios)
    if git -C "$RESPALDO_KOREADER_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        if [ -n "$(git -C "$RESPALDO_KOREADER_DIR" status --porcelain 2>/dev/null)" ]; then
            git -C "$RESPALDO_KOREADER_DIR" add -A 2>/dev/null || true
            git -C "$RESPALDO_KOREADER_DIR" commit -q \
                -m "respaldo automático $(date '+%F %H:%M')" 2>/dev/null || true
        fi
    fi
    echo "── Respaldo KOReader → $RESPALDO_KOREADER_DIR ✓ (commit local; publica con git push desde ese repo)"
}
