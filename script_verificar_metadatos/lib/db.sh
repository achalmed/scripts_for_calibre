#!/usr/bin/env bash
# lib/db.sh - The single place that reads metadata.db. Emits a candidate
# TSV that lib/verificador.py consumes. Keeping all SQL here means the
# Python side never needs to know the Calibre schema.

# select_candidates()
# Prints one TAB-separated row per book to verify, with columns:
#   id  isbn  title  authors  publisher  year  pages
# `isbn` is the best available exact identifier (isbn preferred, then
# google/amazon/goodreads); empty when the book has none.
#
# Behaviour depends on globals:
#   MODE       - "isbn": only books that HAVE a verifiable id.
#                "titulo": all books (those without an id get an empty
#                isbn column so the Python side falls back to title search).
#   ONLY_IDS   - when set, restricts to that comma-separated id list.
#   LIMIT      - when > 0, caps the number of rows.
select_candidates() {
    local id_filter="" limit_clause=""
    if [[ -n "$ONLY_IDS" ]]; then
        # sanitize: keep digits and commas only
        local safe="${ONLY_IDS//[^0-9,]/}"
        id_filter="AND b.id IN ($safe)"
    fi
    [[ "$LIMIT" -gt 0 ]] && limit_clause="LIMIT $LIMIT"

    # Verifiable-id subquery: pick one id per book, preferring isbn.
    local id_expr="
      (SELECT i.val FROM identifiers i
        WHERE i.book=b.id
        ORDER BY CASE i.type
                   WHEN 'isbn' THEN 1 WHEN 'google' THEN 2
                   WHEN 'amazon' THEN 3 WHEN 'goodreads' THEN 4 ELSE 5 END
        LIMIT 1)"

    # Selection differs per mode:
    #   isbn  -> books that HAVE a verifiable id (exact lookup).
    #   titulo-> books WITHOUT a verifiable id whose Item type is publishable
    #            (title+author search). The two modes are complementary, so a
    #            titulo run never re-checks what an isbn run already did.
    local having=""
    if [[ "$MODE" == "isbn" ]]; then
        having="AND EXISTS(SELECT 1 FROM identifiers i
            WHERE i.book=b.id AND i.type IN ('isbn','google','amazon','goodreads'))"
    else
        # Build the quoted IN list from the PIPE-separated config value.
        # Pipe (not space) because item-type values contain spaces.
        local in_list="" t types=()
        IFS='|' read -ra types <<<"$TITULO_ITEM_TYPES"
        for t in "${types[@]}"; do in_list+="'${t//\'/\'\'}',"; done
        in_list="${in_list%,}"
        having="AND NOT EXISTS(SELECT 1 FROM identifiers i
            WHERE i.book=b.id AND i.type IN ('isbn','google','amazon','goodreads'))
          AND EXISTS(SELECT 1 FROM books_custom_column_39_link l
            JOIN custom_column_39 it ON it.id=l.value AND it.value IN ($in_list)
            WHERE l.book=b.id)"
    fi

    sqlite3 -noheader -separator $'\t' "$METADATA_DB" "
      SELECT b.id,
             COALESCE($id_expr, ''),
             REPLACE(b.title, char(9), ' '),
             COALESCE((SELECT GROUP_CONCAT(a.name, ' & ')
                        FROM books_authors_link l JOIN authors a ON a.id=l.author
                        WHERE l.book=b.id), ''),
             COALESCE((SELECT p.name FROM books_publishers_link l
                        JOIN publishers p ON p.id=l.publisher
                        WHERE l.book=b.id), ''),
             COALESCE(strftime('%Y', b.pubdate), ''),
             COALESCE((SELECT c.value FROM custom_column_31 c WHERE c.book=b.id), '')
      FROM books b
      WHERE 1=1 $having $id_filter
      GROUP BY b.id
      ORDER BY b.id
      $limit_clause;"
}

# count_candidates()
# Prints how many books match the current MODE/ONLY_IDS selection.
count_candidates() {
    select_candidates | grep -c . || true
}
