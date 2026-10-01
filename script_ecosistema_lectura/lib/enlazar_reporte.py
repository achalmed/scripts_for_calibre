#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib/enlazar_reporte.py — Fase 4: el puente Calibre → Zotero (#zotero_key). Este script SOLO LEE;
quien escribe es main.sh (`--enlazar --aplicar`, con calibredb, Calibre cerrado y lock).

Para cada libro de Calibre sin #zotero_key busca su ítem en Zotero, del candidato más firme al más débil:
  adjunto  el ítem padre que enlaza un archivo de la carpeta «… (<id>)/» del libro: determinista, el único
           que `--aplicar` escribe (si hay un solo padre);
  ISBN     ISBN exacto normalizado;           ┐ para que Edison confirme:
  titulo   título normalizado, único;         ┘ se pegan a mano en la columna ZKey.
Además reporta las anomalías del puente: claves que no existen en Zotero y claves que no son las del ítem
que enlaza el PDF del libro.

Variables: QEL_BIBLIOTECA, QEL_ZOTERO_DB, QEL_REPORTE (TSV), QEL_RIS (si se da: RIS de los libros sin
ningún candidato, desde Calibre tal como está hoy — `biblioteca.ris()`), QEL_PARES (si se da: TSV
`id<TAB>clave` de los candidatos «adjunto», lo que `--aplicar` escribe).
"""

import os
import re
import csv
import sqlite3
import sys
import unicodedata
from pathlib import Path

BIBLIOTECA = os.environ.get("QEL_BIBLIOTECA", "")
ZOTERO_DB = os.environ.get("QEL_ZOTERO_DB", "")
REPORTE = os.environ.get("QEL_REPORTE", "/tmp/enlazar_reporte.tsv")
RIS = os.environ.get("QEL_RIS", "")
PARES = os.environ.get("QEL_PARES", "")
COL_ZKEY_ID = "13"  # custom_column_13 = #zotero_key

os.environ.setdefault("BIBLIOTECA", BIBLIOTECA)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "py-common"))
import biblioteca as bib  # noqa: E402


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
    con_key = dict(cal.execute("SELECT book, value FROM custom_column_%s" % COL_ZKEY_ID).fetchall())

    # Índices de Zotero: ISBN→key y título-normalizado→keys (solo ítems padre vivos)
    vivos = {k for (k,) in zot.execute(
        "SELECT i.key FROM items i JOIN itemTypes t ON t.itemTypeID = i.itemTypeID "
        "WHERE t.typeName NOT IN ('attachment','note','annotation') "
        "AND i.itemID NOT IN (SELECT itemID FROM deletedItems)")}
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

    # Adjuntos enlazados de la biblioteca: la carpeta «… (<id>)» dice de qué libro son.
    zot_adjunto = {}
    for path, padre in zot.execute(
            "SELECT a.path, p.key FROM itemAttachments a JOIN items p ON p.itemID = a.parentItemID "
            "WHERE a.linkMode = 2 AND a.path LIKE 'attachments:%' "
            "AND a.itemID NOT IN (SELECT itemID FROM deletedItems) "
            "AND p.itemID NOT IN (SELECT itemID FROM deletedItems)"):
        m = re.search(r"\((\d+)\)/[^/]*$", path)
        if m:
            zot_adjunto.setdefault(int(m.group(1)), set()).add(padre)
    # Desempate de una importación repetida: si un libro tiene varios ítems y algunos solo están en
    # colecciones que se mandaron a la papelera, esos son el duplicado descartado; cuenta el de la viva.
    descartados = {k for (k,) in zot.execute(
        "SELECT i.key FROM items i WHERE i.itemID IN (SELECT itemID FROM collectionItems) "
        "AND i.itemID NOT IN (SELECT ci.itemID FROM collectionItems ci "
        "                     WHERE ci.collectionID NOT IN (SELECT collectionID FROM deletedCollections))")}
    for b, ks in zot_adjunto.items():
        vivos_b = ks - descartados
        if len(ks) > 1 and vivos_b:
            zot_adjunto[b] = vivos_b

    # Un ítem que ya enlaza el archivo de OTRO libro es de ese libro (otra edición, o un duplicado de
    # Calibre): no es candidato por ISBN ni por título, y el libro necesita su propio ítem (va al RIS).
    de_otro = {}
    for b, ks in zot_adjunto.items():
        for k in ks:
            de_otro.setdefault(k, set()).add(b)

    def libres(keys, bid):
        return [k for k in keys if not (de_otro.get(k, set()) - {bid})]

    filas_rep, cuenta, pares, sin_candidato = [], {}, [], []
    for bid, titulo, autores, isbn in sin_key:
        candidato, via = "", ""
        n = norm_isbn(isbn)
        padres = sorted(zot_adjunto.get(bid, ()))
        por_titulo = zot_titulo.get(norm_titulo(titulo), [])
        if len(padres) == 1:
            candidato, via = padres[0], "adjunto"
            pares.append((bid, padres[0]))
        elif len(padres) > 1:
            candidato, via = " / ".join(padres[:3]), "adjunto_ambiguo"
        elif n and n in zot_isbn and libres([zot_isbn[n]], bid):
            candidato, via = zot_isbn[n], "ISBN"
        elif len(libres(por_titulo, bid)) == 1:
            candidato, via = libres(por_titulo, bid)[0], "titulo"
        elif len(libres(por_titulo, bid)) > 1:
            candidato, via = " / ".join(libres(por_titulo, bid)[:3]), "titulo_ambiguo"
        elif por_titulo or (n and n in zot_isbn):
            candidato = " / ".join(por_titulo[:3] or [zot_isbn[n]])
            via = "ya_de_otro_libro"
        via = via or "sin_candidato"
        if via in ("sin_candidato", "ya_de_otro_libro"):
            sin_candidato.append(bid)
        cuenta[via] = cuenta.get(via, 0) + 1
        filas_rep.append({
            "id": bid, "titulo": titulo, "autores": autores or "",
            "isbn": isbn or "", "candidato_zotero": candidato, "via": via,
        })
    # Anomalías de los libros que SÍ tienen clave
    for bid, key in sorted(con_key.items()):
        padres = zot_adjunto.get(bid, set())
        if key not in vivos:
            via = "clave_inexistente"
        elif padres and key not in padres:
            via = "clave_distinta_del_adjunto"
        else:
            continue
        cuenta[via] = cuenta.get(via, 0) + 1
        t = cal.execute("SELECT title FROM books WHERE id = ?", (bid,)).fetchone()[0]
        filas_rep.append({"id": bid, "titulo": t, "autores": "", "isbn": "",
                          "candidato_zotero": f"{key} → {' / '.join(sorted(padres))}".strip(" →"), "via": via})

    os.makedirs(os.path.dirname(REPORTE), exist_ok=True)
    with open(REPORTE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "titulo", "autores", "isbn", "candidato_zotero", "via"], delimiter="\t")
        w.writeheader()
        w.writerows(filas_rep)
    if PARES:
        with open(PARES, "w", encoding="utf-8") as fh:
            fh.writelines(f"{b}\t{k}\n" for b, k in pares)
    if RIS:
        entradas = [bib.ris(b) for b in sin_candidato]
        Path(RIS).write_text("\n".join(e for e in entradas if e), encoding="utf-8")

    print("── Enlazador Calibre→Zotero ──────────────────────────────")
    print("  Libros sin #zotero_key : %d" % len(sin_key))
    for via in ("adjunto", "adjunto_ambiguo", "ISBN", "titulo", "titulo_ambiguo", "ya_de_otro_libro", "sin_candidato",
                "clave_inexistente", "clave_distinta_del_adjunto"):
        if cuenta.get(via):
            print("  %-23s: %d" % (via, cuenta[via]))
    print("  Reporte TSV            : %s" % REPORTE)
    if RIS:
        print("  RIS (sin ítem propio)  : %s  ← Zotero: Archivo → Importar → «enlazar a los archivos»" % RIS)
    print("  (adjunto: lo escribe --aplicar; ISBN/título: pega la clave en la columna ZKey a mano.)")


if __name__ == "__main__":
    main()
