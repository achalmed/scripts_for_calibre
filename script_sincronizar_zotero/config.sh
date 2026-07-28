#!/usr/bin/env bash
# config.sh - Central configuration for sincronizar-zotero.
# Every user-editable value lives here; lib/ modules never hardcode paths.

# shellcheck disable=SC2034  # variables are consumed by main.sh and lib/ modules

readonly VERSION="1.0.0"
readonly TOOL_NAME="sincronizar-zotero"

# --- Databases ----------------------------------------------------------
readonly CALIBRE_LIBRARY="/home/achalmaedison/Documents/biblioteca"
readonly CALIBRE_DB="$CALIBRE_LIBRARY/metadata.db"
readonly ZOTERO_DIR="/home/achalmaedison/Zotero"
readonly ZOTERO_DB="$ZOTERO_DIR/zotero.sqlite"

# Zotero resolves linked attachments ("attachments:...") against this base
# directory (extensions.zotero.baseAttachmentPath). It must equal the
# Calibre library root for the ZMI linkage to work.
readonly ZOTERO_BASE_ATTACHMENT_PATH="$CALIBRE_LIBRARY"

# --- Link key -----------------------------------------------------------
# Calibre custom column that stores the Zotero PARENT item key (ZMI).
readonly CAL_COL_ZOTERO_KEY="13"

# --- Direction policy (decided by the user, 2026-07-28) -----------------
# "calibre" -> on conflict Calibre wins for core fields (title, date,
# publisher, isbn, series, pages, language, tags, edition) EXCEPT authors
# where Zotero keeps richer supersets (never delete co-authors).
readonly CONFLICT_POLICY="calibre"

# Repair broken Zotero attachment paths and stale {path} lines in Extra.
readonly REPAIR_ATTACHMENTS="true"

# Backfill Calibre from Zotero where Calibre is empty (pubdate placeholder
# 0101, missing ISBN). Title/authors are NEVER written to Calibre.
readonly BACKFILL_CALIBRE="true"

# Populate the zotero_* mirror columns in Calibre with the final Zotero
# state after applying changes.
readonly POPULATE_MIRROR="true"

# --- Output -------------------------------------------------------------
readonly REPORT_DIR_BASENAME="reportes"
readonly STATE_DIR_BASENAME="estado"

# --- Runtime option defaults (overridden by CLI flags in lib/cli.sh) ----
APPLY_CHANGES=false   # false = simulation; true only with --aplicar
LIMIT="0"             # 0 = no limit; N = only first N linked pairs (test)
ONLY_IDS=""           # comma-separated Calibre book ids (debug)
VERBOSE=false
