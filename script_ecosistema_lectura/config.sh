# config.sh — Configuración de script_ecosistema_lectura (Fase 2 del DISEÑO)
# Zotero (Ethereal Style readingTime) → Calibre. Todo lo editable vive aquí.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../core/env.sh"   # rutas: core/env (K6, P217)

# Rutas: las de core/env; QEL_* las cambia solo para esta suite (pruebas).
BIBLIOTECA="${QEL_BIBLIOTECA:-$BIBLIOTECA_DIR}"
ZOTERO_DB="${QEL_ZOTERO_DB:-$ZOTERO_DB}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTES_DIR="$SCRIPT_DIR/reportes"
# Respaldos de metadata.db: los hace la puerta (lib/escribir.sh) fuera del repo; el candado es
# LOCK_CALIBRE de core/env, compartido con script_koreader_estudio y los demás escritores.

# --- Columnas de Calibre (labels sin #) ------------------------------------
COL_ZKEY="zotero_key"        # puente Calibre↔Zotero (ya existente, de ZMI)
COL_ZTIEMPO="zot_tiempo"     # minutos leídos según Zotero/Ethereal Style (nueva)
COL_ZULTIMA="zot_ultima"     # última actividad de lectura en Zotero (nueva)
COL_ZPROG="zot_progreso"     # fracción 0–1 leída según el lector de Zotero (Fase 2b)
COL_TTOTAL="tiempo_estudio"  # composite: ko_tiempo + zot_tiempo (nueva)
COL_KOTIEMPO="ko_tiempo"     # minutos según KOReader (de script_koreader_estudio)

# --- Fase 3: orquestación de metadatos/etiquetas (sincronizar_zotero) ------
SINCRONIZAR_ZOTERO_DIR="$SCRIPT_DIR/../script_sincronizar_zotero"
# La marca de la última orquestación vive en el estado de usuario, fuera del repo (K6).
ESTADO_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/biblioteca/ecosistema_lectura"
ESTADO_DIR_VIEJO="$SCRIPT_DIR/estado"   # hasta la ola 2a; se lee una vez para no perder la marca
