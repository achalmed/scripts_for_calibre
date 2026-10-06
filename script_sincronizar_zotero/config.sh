#!/usr/bin/env bash
# script_sincronizar_zotero/config.sh — Central configuration for sincronizar-zotero
# Every user-editable value lives here; lib/ modules never hardcode paths.

# shellcheck disable=SC2034  # variables are consumed by main.sh and lib/ modules

readonly VERSION="1.0.0"
readonly TOOL_NAME="sincronizar-zotero"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../core/env.sh"   # rutas: core/env (K6, P217)

# --- Databases (core/env: BIBLIOTECA_DIR, ZOTERO_DB) ------------------------
readonly CALIBRE_LIBRARY="$BIBLIOTECA_DIR"
readonly CALIBRE_DB="$CALIBRE_LIBRARY/metadata.db"
readonly ZOTERO_DB

# Zotero resolves linked attachments ("attachments:...") against this base
# directory (extensions.zotero.baseAttachmentPath). It must equal the
# Calibre library root for the ZMI linkage to work.
readonly ZOTERO_BASE_ATTACHMENT_PATH="$CALIBRE_LIBRARY"

# --- Link key -----------------------------------------------------------
# La clave del ítem padre de Zotero vive en la columna #zotero_key de Calibre (ZMI);
# lib/sincronizador.py resuelve todas las columnas por etiqueta, nunca por número (K3).

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
# El estado (último sync, plan de Calibre) vive en el estado de usuario, fuera del repo (K6).
readonly STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/biblioteca/sincronizar_zotero"

# --- Runtime option defaults (overridden by CLI flags in lib/cli.sh) ----
APPLY_CHANGES=false   # false = simulation; true only with --aplicar
LIMIT="0"             # 0 = no limit; N = only first N linked pairs (test)
ONLY_IDS=""           # comma-separated Calibre book ids (debug)
VERBOSE=false
