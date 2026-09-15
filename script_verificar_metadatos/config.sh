#!/usr/bin/env bash
# script_verificar_metadatos/config.sh — Central configuration for verificar-metadatos
# Every user-editable value lives here; lib/ modules never hardcode paths.

# shellcheck disable=SC2034  # variables are consumed by main.sh and lib/ modules

readonly VERSION="1.0.0"
readonly TOOL_NAME="verificar-metadatos"

# Calibre library whose metadata will be checked (read-only).
readonly CALIBRE_LIBRARY="${BIBLIOTECA_DIR:-$HOME/Documents/biblioteca}"
readonly METADATA_DB="$CALIBRE_LIBRARY/metadata.db"

# --- Providers (public bibliographic APIs, no API key required) ---------
# OpenLibrary is the primary source: lenient rate limits and rich data.
# Google Books is only a fallback because the anonymous quota is often 429.
readonly OL_ISBN_ENDPOINT="https://openlibrary.org/api/books"
readonly OL_SEARCH_ENDPOINT="https://openlibrary.org/search.json"
# Crossref indexes journal articles, working papers and books by DOI. Used
# as a fallback in --modo titulo when OpenLibrary (books only) finds nothing,
# which is what happens for Report / Journal Article. Returns year, publisher
# and, valuably, a DOI we may not have. Set USE_CROSSREF=false to disable.
readonly CROSSREF_ENDPOINT="https://api.crossref.org/works"
readonly USE_CROSSREF="true"
# Crossref pide un contacto en el User-Agent (el "polite pool"). Se toma de
# CROSSREF_MAILTO_OVERRIDE si está definida en el entorno; si no, el valor por
# defecto de abajo (edítalo o exporta la variable para no dejar tu correo aquí).
readonly CROSSREF_MAILTO="${CROSSREF_MAILTO_OVERRIDE:-achalmed.18@gmail.com}"

# Seconds to wait between network calls (be polite; avoid throttling).
readonly RATE_LIMIT_SECONDS="1"
# Per-request network timeout, in seconds.
readonly HTTP_TIMEOUT="20"

# Identifier types (in the Calibre `identifiers` table) considered
# reliably verifiable by exact lookup, in priority order.
readonly VERIFIABLE_ID_TYPES="isbn google amazon goodreads"

# In --modo titulo, only books of these Item types (and WITHOUT a verifiable
# id) get a title+author search. The point is to EXCLUDE the unfindable bulk
# (Presentation = slides, Manuscript = exams/handouts/lecture notes, and the
# untyped bucket) and query only the plausibly-catalogued types. Values are
# PIPE-separated because some contain spaces (e.g. "Book Section").
readonly TITULO_ITEM_TYPES="Book|Book Section|Journal Article|Thesis|Report|Magazine Article|Document"

# When searching by title+author (no ISBN), a candidate from the provider
# is accepted as "the same book" only if the fuzzy title similarity is at
# least this ratio (0..1). Below it, the match is reported as "dudoso" and
# no field discrepancies are emitted (avoids false positives).
readonly FUZZY_TITLE_THRESHOLD="0.80"

# Output directory (reports are timestamped inside it).
readonly REPORT_DIR_BASENAME="reportes"

# --- Runtime option defaults (overridden by CLI flags in lib/cli.sh) ----
MODE="isbn"        # isbn = only books with a verifiable id; titulo = also
                   # try title+author search for books without one.
LIMIT="0"          # 0 = no limit; otherwise stop after N candidates.
ONLY_IDS=""        # comma-separated book ids to restrict the run (debug).
VERBOSE=false
