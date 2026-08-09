#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/enlazar_reporte.py — Fase 4 (solo reporte, NUNCA escribe): para cada libro
de Calibre sin #zotero_key, busca su ítem candidato en Zotero por ISBN exacto
(normalizado) o por título normalizado. El resultado es un TSV para que Edison
confirme; el enlace se escribe a mano (o en una fase posterior con --aplicar).
"""

import os
import re
import csv
import sqlite3
import unicodedata

BIBLIOTECA = os.environ.get("QEL_BIBLIOTECA", "")
ZOTERO_DB = os.environ.get("QEL_ZOTERO_DB", "")
REPORTE = os.environ.get("QEL_REPORTE", "/tmp/enlazar_reporte.tsv")
COL_ZKEY_ID = "13"  # custom_column_13 = #zotero_key


def norm_titulo(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def norm_isbn(v):
    v = re.sub(r"[^0-9Xx]", "", v or "")
    return v.upper() or None


def main():
    cal = sqlite3.connect("file:%s/metadata.db?mode=ro" % BIBLIOTECA, uri=True)
    zot = sqlite3.connect("file:%s?mode=ro" % ZOTERO_DB, uri=True)

    sin_key = cal.execute(
        "SELECT b.id, b.title, "
        " (SELECT GROUP_CONCAT(a.name, ' & ') FROM books_authors_link l "
        "  JOIN authors a ON a.id=l.author WHERE l.book=b.id), "
        " (SELECT val FROM identifiers WHERE book=b.id AND type='isbn') "
        "FROM books b WHERE b.id NOT IN (SELECT book FROM custom_column_%s) "
        "ORDER BY b.id" % COL_ZKEY_ID
    ).fetchall()

    # Índices de Zotero: ISBN→key y título-normalizado→keys (solo ítems padre vivos)
    zot_isbn, zot_titulo = {}, {}
    filas = zot.execute(
        "SELECT i.key, f.fieldName, v.value FROM items i "
        "JOIN itemData d ON d.itemID = i.itemID "
        "JOIN fields f ON f.fieldID = d.fieldID AND f.fieldName IN ('ISBN','title') "
        "JOIN itemDataValues v ON v.valueID = d.valueID "
        "JOIN itemTypes t ON t.itemTypeID = i.itemTypeID "
        "WHERE t.typeName NOT IN ('attachment','note','annotation') "
        "AND i.itemID NOT IN (SELECT itemID FROM deletedItems)"
    ).fetchall()
    for key, campo, valor in filas:
        if campo == "ISBN":
            for isbn in re.split(r"[,;\s]+", valor or ""):
                n = norm_isbn(isbn)
                if n:
                    zot_isbn[n] = key
        else:
            zot_titulo.setdefault(norm_titulo(valor), []).append(key)

    filas_rep, n_isbn, n_titulo = [], 0, 0
    for bid, titulo, autores, isbn in sin_key:
        candidato, via = "", ""
        n = norm_isbn(isbn)
        if n and n in zot_isbn:
            candidato, via = zot_isbn[n], "ISBN"
            n_isbn += 1
        else:
            keys = zot_titulo.get(norm_titulo(titulo), [])
            if len(keys) == 1:
                candidato, via = keys[0], "titulo"
                n_titulo += 1
            elif len(keys) > 1:
                candidato, via = " / ".join(keys[:3]), "titulo_ambiguo"
        filas_rep.append({
            "id": bid, "titulo": titulo, "autores": autores or "",
            "isbn": isbn or "", "candidato_zotero": candidato, "via": via or "sin_candidato",
        })

    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)
    with open(REPORTE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "titulo", "autores", "isbn", "candidato_zotero", "via"], delimiter="\t")
        w.writeheader()
        w.writerows(filas_rep)

    print("── Enlazador Calibre→Zotero (SOLO REPORTE) ───────────────")
    print("  Libros sin #zotero_key : %d" % len(filas_rep))
    print("  Candidato por ISBN     : %d" % n_isbn)
    print("  Candidato por título   : %d" % n_titulo)
    print("  Sin candidato/ambiguos : %d" % (len(filas_rep) - n_isbn - n_titulo))
    print("  Reporte TSV            : %s" % REPORTE)
    print("  (Para enlazar: pega la clave en la columna ZKey del libro en Calibre.)")


if __name__ == "__main__":
    main()
