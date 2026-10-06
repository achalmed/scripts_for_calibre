"""migraciones/pasos/p6.py — P6: identificadores y columnas sin uso (modelo-de-metadatos.md §7, P6).

Salen de `identifiers` los residuos del plugin ZMI (`zkey`, `zkey_file`, `zcollection`: ningún script los lee; el
enlace con Zotero es `#zotero_key`) y los de tiendas (`amazon`, `google`, `goodreads`, `mobi-asin`, `asin`,
`grrating`, `uri`); `doi` queda sin URL y `isbn` sin guiones. Se retiran las columnas vacías que ninguna suite lee
ni escribe. Desvío del modelo, con motivo: `#estudio` (vacía, pero la usan 10 archivos de código),
`#zotero_automatic_tags` y `#zotero_issn` (las escribe `sincronizar-zotero`) se conservan."""
import re

FUERA = {"zkey", "zkey_file", "zcollection", "amazon", "google", "goodreads", "mobi-asin", "asin", "grrating", "uri"}
COLUMNAS = ["#zotero_doi", "#zotero_issue", "#zotero_notes", "#zotero_series_text", "#zotero_series_title",
            "#zotero_volume", "#ko_review"]


def plan(c):
    col = dict(c.execute("select label, id from custom_columns").fetchall())
    for etiqueta in COLUMNAS:
        n = c.execute(f"select count(*) from custom_column_{col[etiqueta.lstrip('#')]}").fetchone()[0]
        if n:
            raise SystemExit(f"P6: {etiqueta} tiene {n} valores; no se retira una columna con datos")
    ids = {}
    for b, tipo, val in c.execute("select book, type, val from identifiers"):
        ids.setdefault(b, {})[tipo] = val
    cambios, propuesta = {}, [("libro", "antes", "después")]
    for b, d in ids.items():
        n = {k: v for k, v in d.items() if k not in FUERA}
        if "doi" in n:
            n["doi"] = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", n["doi"].strip(), flags=re.I)
        if "isbn" in n:
            n["isbn"] = re.sub(r"[\s-]", "", n["isbn"])
        if n != d:
            cambios[str(b)] = n
            propuesta.append((b, ";".join(f"{k}:{v}" for k, v in sorted(d.items())), ";".join(f"{k}:{v}" for k, v in sorted(n.items()))))
    return ({"campos": {"identifiers": cambios}, "columnas_borrar": COLUMNAS},
            f"{len(cambios)} libros con identificadores depurados; se retiran {len(COLUMNAS)} columnas vacías sin uso", propuesta)
