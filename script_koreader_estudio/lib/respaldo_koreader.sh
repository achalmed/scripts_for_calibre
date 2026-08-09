# lib/respaldo_koreader.sh — Respaldo de los datos valiosos de KOReader hacia
# el repo de dotfiles (~/.dotfiles/koreader-data), TODO EN TEXTO para que git
# lo versione bien: dump SQL de las estadísticas + sidecars .lua + historial.
# Los datos vivos siguen en ~/.config/koreader (principio de mínima captura);
# esto es un respaldo versionado. Publicar al remoto = `dotfiles sync-push`.
# settings.reader.lua NO se respalda aquí: contiene el bloque kosync
# (credenciales) y el escáner de sensibles de los dotfiles lo vetaría.

respaldar_koreader() {
    [ -d "$KOREADER_CONFIG" ] || return 0
    mkdir -p "$RESPALDO_KOREADER_DIR/hashdocsettings"

    # 1) Estadísticas → dump SQL (texto, restaurable con: sqlite3 nueva.db < statistics.sql)
    if [ -f "$STATS_DB" ] && command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "file:$STATS_DB?mode=ro" .dump \
            > "$RESPALDO_KOREADER_DIR/statistics.sql" 2>/dev/null || true
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

    # 3) Commit local en el repo de dotfiles (solo si hay cambios)
    if git -C "$DOTFILES_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        if [ -n "$(git -C "$DOTFILES_DIR" status --porcelain -- koreader-data 2>/dev/null)" ]; then
            git -C "$DOTFILES_DIR" add -- koreader-data 2>/dev/null || true
            git -C "$DOTFILES_DIR" commit -q \
                -m "chore(koreader-data): respaldo automático $(date '+%F %H:%M')" \
                -- koreader-data 2>/dev/null || true
        fi
    fi
    echo "── Respaldo KOReader → $RESPALDO_KOREADER_DIR ✓ (commit local; publica con sync-push)"
}
