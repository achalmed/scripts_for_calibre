# config.sh — Configuración de script_ecosistema_lectura (Fase 2 del DISEÑO)
# Zotero (Ethereal Style readingTime) → Calibre. Todo lo editable vive aquí.

BIBLIOTECA="${QEL_BIBLIOTECA:-/home/achalmaedison/Documents/biblioteca}"
ZOTERO_DB="${QEL_ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTES_DIR="$SCRIPT_DIR/reportes"
BACKUPS_DIR="$SCRIPT_DIR/backups"
BACKUPS_CONSERVAR=5

# Lock COMPARTIDO con script_koreader_estudio: ambos escriben metadata.db;
# nunca deben correr a la vez (los timers reintentan a los 30 min).
LOCK_ESCRITURA_CALIBRE="$SCRIPT_DIR/../.lock_calibre_write"

# ── Columnas de Calibre (labels sin #) ───────────────────────────────────────
COL_ZKEY="zotero_key"        # puente Calibre↔Zotero (ya existente, de ZMI)
COL_ZTIEMPO="zot_tiempo"     # minutos leídos según Zotero/Ethereal Style (nueva)
COL_ZULTIMA="zot_ultima"     # última actividad de lectura en Zotero (nueva)
COL_ZPROG="zot_progreso"     # fracción 0–1 leída según el lector de Zotero (Fase 2b)
COL_TTOTAL="tiempo_estudio"  # composite: ko_tiempo + zot_tiempo (nueva)
COL_KOTIEMPO="ko_tiempo"     # minutos según KOReader (de script_koreader_estudio)

# ── Fase 3: orquestación de metadatos/etiquetas (sincronizar_zotero) ─────────
SINCRONIZAR_ZOTERO_DIR="$SCRIPT_DIR/../script_sincronizar_zotero"
ESTADO_DIR="$SCRIPT_DIR/estado"
