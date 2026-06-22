#!/usr/bin/env bash
# ==============================================================================
# config.sh
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

# --- exiftool field mapping ---------------------------------------------------
# Maps logical metadata names to exiftool tag names.
# Centralised here so embed_metadata.sh never hard-codes tag strings.
declare -A EXIFTOOL_TAG_MAP=(
    [title]="-Title"
    [author]="-Author"
    [publisher]="-PDF:Producer"
    [tags]="-Keywords"
    [language]="-Language"
    [date]="-CreateDate"
)

# Fields to strip from the PDF on every write (removes tool fingerprints).
readonly EXIFTOOL_STRIP_FIELDS=("-Creator=" "-CreatorTool=")

# --- OPF XPath-like grep targets ---------------------------------------------
# Each value is the dc: element name as it appears in Calibre's metadata.opf.
readonly OPF_FIELDS=("title" "author" "tags" "publisher" "language" "date" "description")
