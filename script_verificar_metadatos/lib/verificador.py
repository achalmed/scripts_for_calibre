#!/usr/bin/env python3
"""lib/verificador.py - Network + comparison core for verificar-metadatos.

Reads candidate books as a TSV on stdin (id, isbn, title, authors,
publisher, year, pages), queries a public bibliographic API for each, and
writes a discrepancy report. Pure standard library (urllib), so no pip
dependencies. Read-only: it NEVER writes to Calibre.

Invoked by main.sh; configuration is passed via argv/env, not hardcoded.

Discrepancy report columns (TSV):
    id  campo  valor_calibre  valor_fuente  fuente  confianza

`confianza` is `exacta` for ISBN/id lookups and `aprox:<ratio>` for
title+author matches. Title and author are reported for CONTEXT only; the
tool never suggests overwriting them.
"""
import sys
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

# --- Parameters from the environment (set by main.sh from config.sh) ------
import os
OL_ISBN = os.environ["OL_ISBN_ENDPOINT"]
OL_SEARCH = os.environ["OL_SEARCH_ENDPOINT"]
CROSSREF = os.environ.get("CROSSREF_ENDPOINT", "https://api.crossref.org/works")
USE_CROSSREF = os.environ.get("USE_CROSSREF", "true").lower() == "true"
CROSSREF_MAILTO = os.environ.get("CROSSREF_MAILTO", "")
RATE = float(os.environ.get("RATE_LIMIT_SECONDS", "1"))
TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "20"))
FUZZY = float(os.environ.get("FUZZY_TITLE_THRESHOLD", "0.80"))
MODE = os.environ.get("MODE", "isbn")
REPORT_TSV = os.environ["REPORT_TSV"]
REPORT_MD = os.environ["REPORT_MD"]


def norm(s):
    """Lowercase, strip accents and collapse whitespace for comparison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def ratio(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def year_of(s):
    """Extract the first 4-digit year from a free-form date string."""
    import re
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return m.group(1) if m else ""


def http_json(url):
    """GET a URL and parse JSON; return None on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent":
                                     "verificar-metadatos/1.0 (personal library)"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001 - network is best-effort
        sys.stderr.write(f"  [red] {e}\n")
        return None


def lookup_isbn(isbn):
    """Return a normalized record dict from OpenLibrary by ISBN, or None."""
    url = f"{OL_ISBN}?bibkeys=ISBN:{urllib.parse.quote(isbn)}&format=json&jscmd=data"
    d = http_json(url)
    if not d:
        return None
    vals = list(d.values())
    if not vals:
        return None
    v = vals[0]
    return {
        "title": v.get("title", ""),
        "authors": [a.get("name", "") for a in v.get("authors", [])],
        "publisher": ", ".join(p.get("name", "") for p in v.get("publishers", [])),
        "year": year_of(v.get("publish_date", "")),
        "pages": v.get("number_of_pages"),
        "doi": "",
    }


def search_title(title, authors):
    """Fuzzy title+author search on OpenLibrary; return (record, ratio)."""
    q = {"title": title}
    if authors:
        q["author"] = authors.split(" & ")[0]
    url = f"{OL_SEARCH}?{urllib.parse.urlencode(q)}&limit=1&fields=title,author_name,first_publish_year,publisher,number_of_pages_median"
    d = http_json(url)
    if not d or not d.get("docs"):
        return None, 0.0
    doc = d["docs"][0]
    rec = {
        "title": doc.get("title", ""),
        "authors": doc.get("author_name", []),
        "publisher": ", ".join(doc.get("publisher", [])[:1]),
        "year": str(doc.get("first_publish_year", "") or ""),
        "pages": doc.get("number_of_pages_median"),
        "doi": "",
    }
    return rec, ratio(title, rec["title"])


def search_crossref(title, authors):
    """Fuzzy title+author search on Crossref; return (record, ratio).

    Crossref indexes journal articles, working papers and books, so it is the
    fallback for the publications OpenLibrary (books only) cannot find.
    """
    params = {"query.bibliographic": title, "rows": "1"}
    if authors:
        params["query.author"] = authors.split(" & ")[0]
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    url = f"{CROSSREF}?{urllib.parse.urlencode(params)}"
    d = http_json(url)
    if not d or not d.get("message", {}).get("items"):
        return None, 0.0
    it = d["message"]["items"][0]
    src_title = (it.get("title") or [""])[0]
    auths = [" ".join(filter(None, [a.get("given"), a.get("family")]))
             for a in it.get("author", [])]
    parts = (it.get("issued", {}).get("date-parts") or [[None]])[0]
    ctype = it.get("type", "")
    journal = (it.get("container-title") or [""])[0]
    # For books/monographs the Crossref "publisher" is a real publishing house
    # and belongs in Calibre's publisher field. For journal-article / report /
    # proceedings the container-title is the JOURNAL, which must NOT be written
    # to `publisher` (it goes in Publication); we surface it separately.
    is_book = "book" in ctype or "monograph" in ctype
    rec = {
        "title": src_title,
        "authors": auths,
        "publisher": it.get("publisher", "") if is_book else "",
        "journal": "" if is_book else journal,
        "year": str(parts[0]) if parts and parts[0] else "",
        "pages": None,
        "doi": it.get("DOI", ""),
    }
    return rec, ratio(title, src_title)


def compare(row, rec, confianza):
    """Yield discrepancy tuples (id, field, calibre, source) for one book."""
    bid, isbn, title, authors, publisher, year, pages = row
    out = []

    # Year: only flag when both known and different.
    if year and rec["year"] and year != rec["year"]:
        out.append((bid, "año", year, rec["year"]))

    # Publisher: flag when Calibre is empty (fill opportunity) or clearly
    # different (fuzzy < 0.6). Substring either way counts as a match.
    rp = rec["publisher"]
    if rp:
        if not publisher:
            out.append((bid, "editorial (vacia)", "", rp))
        elif norm(publisher) not in norm(rp) and norm(rp) not in norm(publisher) \
                and ratio(publisher, rp) < 0.6:
            out.append((bid, "editorial", publisher, rp))

    # Pages: flag only sizeable differences (>5) to avoid edition noise.
    rpg = rec["pages"]
    if rpg and pages and str(pages).isdigit():
        if abs(int(pages) - int(rpg)) > 5:
            out.append((bid, "paginas", pages, str(rpg)))
    elif rpg and not pages:
        out.append((bid, "paginas (vacia)", "", str(rpg)))

    # Title/author reported for CONTEXT only (never a change suggestion),
    # and only when they differ enough to be worth a human glance.
    if rec["title"] and ratio(title, rec["title"]) < 0.95:
        out.append((bid, "titulo (informativo)", title, rec["title"]))
    ra = " & ".join(rec["authors"])
    if ra and authors and ratio(authors, ra) < 0.7:
        out.append((bid, "autor (informativo)", authors, ra))

    # A DOI we may not have is a genuinely useful find (Crossref).
    if rec.get("doi"):
        out.append((bid, "doi (encontrado)", "", rec["doi"]))
    # Journal name (articles): informational; belongs in Publication, never in
    # the publisher field.
    if rec.get("journal"):
        out.append((bid, "revista (informativo)", "", rec["journal"]))

    return out


def main():
    rows = [ln.rstrip("\n").split("\t") for ln in sys.stdin if ln.strip()]
    total = len(rows)
    checked = found = not_found = 0
    discrepancies = []

    for n, row in enumerate(rows, 1):
        if len(row) < 7:
            continue
        bid, isbn, title, authors, publisher, year, pages = row[:7]
        sys.stderr.write(f"[{n}/{total}] id={bid} {title[:50]}\n")

        rec, conf, source = None, "exacta", "OpenLibrary"
        if isbn:
            rec = lookup_isbn(isbn)
            time.sleep(RATE)
        if rec is None and MODE == "titulo":
            rec, r = search_title(title, authors)
            time.sleep(RATE)
            if rec and r >= FUZZY:
                conf = f"aprox:{r:.2f}"
            else:
                rec = None  # match too weak -> treat as not found
        if rec is None and MODE == "titulo" and USE_CROSSREF:
            rec, r = search_crossref(title, authors)
            time.sleep(RATE)
            if rec and r >= FUZZY:
                conf, source = f"aprox:{r:.2f}", "Crossref"
            else:
                rec = None

        checked += 1
        if rec is None:
            not_found += 1
            continue
        found += 1
        for d in compare(row, rec, conf):
            discrepancies.append((*d, source, conf))

    # --- write reports ----------------------------------------------------
    with open(REPORT_TSV, "w", encoding="utf-8") as f:
        f.write("id\tcampo\tvalor_calibre\tvalor_fuente\tfuente\tconfianza\n")
        for d in discrepancies:
            f.write("\t".join(str(x) for x in d) + "\n")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Reporte de discrepancias de metadatos\n\n")
        f.write(f"- Candidatos verificados: **{checked}**\n")
        f.write(f"- Encontrados en la fuente: **{found}**\n")
        f.write(f"- No encontrados: **{not_found}**\n")
        f.write(f"- Discrepancias detectadas: **{len(discrepancies)}**\n\n")
        f.write("> Solo lectura. Revisa y corrige a mano en Calibre lo que "
                "creas oportuno. Titulo y autor se muestran solo como "
                "contexto: NO los cambies (Zotero enlaza por carpeta).\n\n")
        if discrepancies:
            f.write("| id | campo | valor en Calibre | valor en la fuente | confianza |\n")
            f.write("|----|-------|------------------|--------------------|----------|\n")
            for bid, campo, cal, src, _fuente, conf in discrepancies:
                cal = (cal or "(vacio)").replace("|", "\\|")
                src = (src or "").replace("|", "\\|")
                f.write(f"| {bid} | {campo} | {cal} | {src} | {conf} |\n")
        else:
            f.write("_Sin discrepancias._\n")

    # machine-readable summary line for main.sh
    print(f"{checked}\t{found}\t{not_found}\t{len(discrepancies)}")


if __name__ == "__main__":
    main()
