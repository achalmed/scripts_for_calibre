#!/usr/bin/env bash
# ==============================================================================
#  script_metadatos_calibre/config.sh — Global configuration, constants, and default values
# Global configuration, constants, and default values.
# All tuneable parameters live here so operators never need to touch
# business-logic files.
# ==============================================================================

# --- Script identity ----------------------------------------------------------
readonly SCRIPT_NAME="calibre-metadata-manager"
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_AUTHOR="Edison Achalma"

# --- Exit codes (aligned with POSIX + common conventions) --------------------
readonly EXIT_SUCCESS=0
readonly EXIT_ERROR=1
readonly EXIT_USAGE=2
readonly EXIT_NOT_FOUND=3
readonly EXIT_NO_PERMISSION=4
readonly EXIT_MISSING_DEP=5

# --- Runtime defaults (can be overridden by CLI flags) -----------------------
VERBOSE=false
DRY_RUN=false
FORCE=false           # Overwrite even if book already has PDF registered

# --- Paths --------------------------------------------------------------------
# LOG_DIR: writable directory for persistent log files.
# Using /tmp keeps it session-scoped and avoids cluttering the library.
LOG_DIR="/tmp"
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME}_$(date +%Y%m%d_%H%M%S).log"

# CALIBRE_DB_FILENAME: sentinel file that proves a directory is a valid
# Calibre library root (prevents operating on the wrong folder).
readonly CALIBRE_DB_FILENAME="metadata.db"

# --- Limpieza de JSON huérfanos (auditoría A7) --------------------------------
# El incrustador rival (scripts_for_zotero/script_inscrustar_metadatos_pdf)
# sembraba un sidecar JSON junto a cada PDF. Con "Calibre manda" el estado de
# Zotero es derivado y esos JSON son basura; esta acción los localiza y borra.
# ORPHAN_JSON_ROOT: biblioteca Calibre donde buscar (override con --root).
ORPHAN_JSON_ROOT="${BIBLIOTECA_DIR:-$HOME/Documents/biblioteca}"
readonly ORPHAN_JSON_NAME="zotero_metadata.json"

# --- exiftool field mapping ---------------------------------------------------
# Mapea nombres lógicos de metadato → nombre de tag de exiftool. Centralizado
# aquí para que embed_metadata.sh NUNCA hardcodee cadenas de tag (auditoría A7:
# antes las re-hardcodeaba ignorando este mapa). _build_exiftool_args itera
# sobre estos mapas; añadir/quitar un tag es editar solo el config.
#
# Grupo A — PDF InfoDict (básico, universal en todos los lectores).
# NOTA (A7): publisher va a -Publisher (InfoDict estándar), NO a -PDF:Producer
# (que identifica el software productor y confundía "editorial" con "productor").
declare -A EXIFTOOL_TAG_MAP=(
    [title]="-Title"
    [author]="-Author"
    [publisher]="-Publisher"
    [tags]="-Keywords"
    [language]="-Language"
    [date]="-CreateDate"
)

# Grupo B — XMP Dublin Core (XMP-dc): estándar moderno, Calibre-compatible.
# Absorbido del incrustador rival scripts_for_zotero/script_inscrustar_metadatos_pdf
# (auditoría A7). Se escribe ADEMÁS del InfoDict para los mismos campos lógicos.
declare -A EXIFTOOL_XMP_TAG_MAP=(
    [title]="-XMP-dc:Title"
    [author]="-XMP-dc:Creator"
    [publisher]="-XMP-dc:Publisher"
    [tags]="-XMP-dc:Subject"
    [language]="-XMP-dc:Language"
    [date]="-XMP-dc:Date"
)

# Fields to strip from the PDF on every write (removes tool fingerprints).
readonly EXIFTOOL_STRIP_FIELDS=("-Creator=" "-CreatorTool=")

# --- OPF XPath-like grep targets ---------------------------------------------
# Each value is the dc: element name as it appears in Calibre's metadata.opf.
readonly OPF_FIELDS=("title" "author" "tags" "publisher" "language" "date" "description")
