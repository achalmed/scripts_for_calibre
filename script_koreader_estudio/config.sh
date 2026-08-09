# config.sh — Configuración de script_koreader_estudio
# Todas las rutas y nombres editables viven aquí; lib/ nunca hardcodea valores.

# ── Rutas principales ────────────────────────────────────────────────────────
BIBLIOTECA="${QKO_BIBLIOTECA:-/home/achalmaedison/Documents/biblioteca}"
KOREADER_CONFIG="${QKO_KOREADER_CONFIG:-$HOME/.config/koreader}"
STATS_DB="$KOREADER_CONFIG/settings/statistics.sqlite3"

# ── Carpetas de trabajo del script ───────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTES_DIR="$SCRIPT_DIR/reportes"
BACKUPS_DIR="$SCRIPT_DIR/backups"
BACKUPS_CONSERVAR=5          # cuántos backups de metadata.db conservar

# ── Columnas de Calibre (labels sin #) ───────────────────────────────────────
# Existentes (creadas por el plugin KOReader Sync) que este script POBLA:
COL_MD5="ko_md5"             # MD5 parcial (algoritmo KOReader)
COL_PROGFLOAT="ko_progfloat" # progreso como fracción 0–1 (convención del plugin)
COL_PROGINT="ko_progint"     # progreso como porcentaje entero 0–100
COL_STATUS="ko_status"       # reading / complete / abandoned
COL_START="ko_start"         # fecha de primera lectura (stats)
COL_FINISH="ko_finish"       # fecha en que se terminó
COL_LASTMOD="ko_lastmod"     # última actividad de lectura
COL_LASTSYNC="ko_lastsync"   # última sincronización de este script
COL_LEIDO="leído"            # bool ya existente en la biblioteca
COL_READ_DATE="read_date"    # fecha del estado leído (ya existente)

# Nuevas (las crea --aplicar si faltan):
COL_TIEMPO="ko_tiempo"       # minutos totales de lectura (stats)
COL_ESTADO="estado_estudio"  # composite: Pendiente/En proceso/Finalizado/Abandonado
COL_BARRA="barra"            # composite: barra de progreso ▰▰▰▱▱ 42%
COL_APUNTES="apuntes"        # comments: enlace clicable al .md de apuntes

# ── Comportamiento ───────────────────────────────────────────────────────────
FORMATOS_LEIBLES="PDF EPUB DJVU MOBI AZW3 FB2 CBZ CBR"  # formatos que KOReader abre

# ── Respaldo continuo de los datos de KOReader ───────────────────────────────
# Los datos VIVOS quedan en ~/.config/koreader (filosofía de mínima captura de
# los dotfiles); aquí se respaldan EN TEXTO (dump SQL + sidecars .lua) dentro
# del repo de dotfiles, con commit local automático. Publicar = dotfiles
# sync-push. settings.reader.lua se excluye (contiene bloque kosync/credenciales).
DOTFILES_DIR="$HOME/.dotfiles"
RESPALDO_KOREADER_DIR="$DOTFILES_DIR/koreader-data"
