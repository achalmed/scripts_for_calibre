#!/usr/bin/env python3
"""lib/sincronizador.py - Nucleo del sincronizador Calibre <-> Zotero.

Lee ambas bases, calcula el plan de sincronizacion segun el contrato ZMI
(prompt_para_zotero_1_catalogacion.md) y la politica "Calibre manda", genera
reportes TSV+MD y, con APPLY=true, escribe en ambas bases via SQL directo
(con las apps cerradas; los backups y el integrity_check los hace main.sh).

Reglas duras implementadas (no configurables):
  - Titulo y autores JAMAS se escriben en Calibre (Zotero enlaza adjuntos
    por la ruta de carpeta Autor/Titulo (id)).
  - Autores: comparacion SEMANTICA (conjuntos de tokens, tolerante al
    intercambio nombre/apellido que dejo invertir_nombres). Si Zotero tiene
    un SUPERCONJUNTO (coautores extra), se conserva y solo se reporta.
    Editores/traductores de Zotero se preservan siempre.
  - Formato por sistema, nunca homogenizar: Calibre "Nombre, Apellido"
    (separador interno '|'), Zotero firstName/lastName separados.
  - TIPO de item: manda el Item type de Calibre (custom_column_39). El cambio
    de tipo migra los campos via baseFieldMappings; lo que no cabe en el tipo
    nuevo se preserva en Extra como linea "Etiqueta: valor" (CSL). Los
    creadores con rol invalido en el tipo nuevo pasan al rol primario.
  - Idioma: Calibre manda SIEMPRE (Zotero quedo mal poblado); se escribe el
    codigo ISO 639-1 normalizado.
  - Valoracion: estrellas. Calibre rating (2-10) <-> tag de estrellas de
    Zotero (⭐..⭐⭐⭐⭐⭐). Calibre manda en conflicto; si Calibre no tiene
    valoracion y Zotero si, se rellena Calibre (2 puntos por estrella).
  - Etiquetas personales de Zotero (emoji no-estrella, #hashtags) se
    preservan; variantes obsoletas de vocabulario se reemplazan.
  - Campo Extra de Zotero: se edita linea a linea; solo se actualiza la
    linea de ruta {path} (y se anexan las migraciones de tipo); las lineas
    "CSL Variable: Value" existentes se preservan.
  - Vacio en el origen NUNCA borra en el destino.
  - Leido y Generos de Calibre jamas se propagan.
  - Escrituras Zotero marcan synced=0 y actualizan (client)dateModified
    para que la cuenta zotero.org suba los cambios.

Entradas por entorno (exportadas por main.sh desde config.sh):
  CALIBRE_DB, ZOTERO_DB, CAL_COL_ZOTERO_KEY, APPLY, LIMIT, ONLY_IDS,
  REPORT_TSV, REPORT_MD, STATE_JSON, REPAIR_ATTACHMENTS, BACKFILL_CALIBRE,
  POPULATE_MIRROR
"""
import html
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

CAL_DB = os.environ["CALIBRE_DB"]
ZOT_DB = os.environ["ZOTERO_DB"]
COL_ZKEY = int(os.environ.get("CAL_COL_ZOTERO_KEY", "13"))
APPLY = os.environ.get("APPLY", "false") == "true"
LIMIT = int(os.environ.get("LIMIT", "0"))
ONLY_IDS = {int(x) for x in os.environ.get("ONLY_IDS", "").split(",") if x.strip().isdigit()}
REPORT_TSV = os.environ["REPORT_TSV"]
REPORT_MD = os.environ["REPORT_MD"]
STATE_JSON = os.environ["STATE_JSON"]
DO_ATTACH = os.environ.get("REPAIR_ATTACHMENTS", "true") == "true"
DO_BACKFILL = os.environ.get("BACKFILL_CALIBRE", "true") == "true"
DO_MIRROR = os.environ.get("POPULATE_MIRROR", "true") == "true"

NOW_SQL = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# Idioma: Calibre usa ISO 639-2 (spa); el contrato pide ISO 639-1 en Zotero.
LANG_2TO1 = {"spa": "es", "eng": "en", "por": "pt", "fra": "fr", "ita": "it",
             "deu": "de", "ger": "de", "cat": "ca", "pol": "pl"}
LANG_NAMES = {"spanish": "es", "english": "en", "espanol": "es", "español": "es",
              "portuguese": "pt", "french": "fr", "italian": "it", "german": "de"}

# Item type de Calibre (custom_column_39) -> typeName de Zotero. Los tipos
# sin equivalente nativo usan el sustituto del contrato + "Type: <csl>" en
# Extra (se anexa en la migracion).
TYPE_MAP = {
    "Artwork": "artwork", "Audio Recording": "audioRecording", "Bill": "bill",
    "Blog Post": "blogPost", "Book": "book", "Book Section": "bookSection",
    "Case": "case", "Conference Paper": "conferencePaper",
    "Dictionary Entry": "dictionaryEntry", "Document": "document",
    "Email": "email", "Encyclopedia Article": "encyclopediaArticle",
    "Film": "film", "Forum Post": "forumPost", "Hearing": "hearing",
    "Instant Message": "instantMessage", "Interview": "interview",
    "Journal Article": "journalArticle", "Letter": "letter",
    "Magazine Article": "magazineArticle", "Manuscript": "manuscript",
    "Map": "map", "Newspaper Article": "newspaperArticle", "Patent": "patent",
    "Podcast": "podcast", "Presentation": "presentation",
    "Radio Broadcast": "radioBroadcast", "Report": "report",
    "Software": "computerProgram", "Statute": "statute", "Thesis": "thesis",
    "TV Broadcast": "tvBroadcast", "Video Recording": "videoRecording",
    "Webpage": "webpage", "Dataset": "dataset",
    # sustitutos del contrato para tipos no nativos
    "Figure": "artwork", "Musical Score": "manuscript", "Pamphlet": "report",
    "Book Review": "journalArticle", "Treaty": "document",
}
STAR_RE = re.compile(r"^[⭐★]+$")

# --- Esquema de Zotero cargado en main(): campos/creadores validos por tipo
TYPE_ID = {}          # typeName -> itemTypeID
VALID_FIELDS = {}     # typeName -> set(fieldName)
BASE_OF = {}          # fieldName -> baseFieldName
TARGET_FIELD = {}     # (typeName, baseFieldName) -> fieldName especifico
VALID_CREATORS = {}   # typeName -> set(creatorTypeID)
PRIMARY_CREATOR = {}  # typeName -> creatorTypeID primario
FIELD_NAME = {}       # fieldID -> fieldName

# Columnas espejo zotero_* de Calibre (colnum -> extractor sobre el estado
# Zotero FINAL). Formato Zotero preservado (autores "Apellido, Nombre; ...").
MIRROR_COLS = {
    25: lambda z: z.get("title", ""),
    33: lambda z: "; ".join(
        (f"{ln}, {fn}" if fn else ln) for ln, fn, fm in z.get("creators", [])),
    35: lambda z: (z.get("date", "") or "").split(" ")[0],
    19: lambda z: year_of(z.get("date", "")),
    20: lambda z: z.get("publisher", ""),
    21: lambda z: z.get("series", ""),
    22: lambda z: z.get("seriesNumber", ""),
    12: lambda z: z.get("typeName", ""),
    9:  lambda z: z.get("ISBN", ""),
    10: lambda z: z.get("ISSN", ""),
    16: lambda z: z.get("numPages", ""),
    17: lambda z: z.get("place", ""),
    26: lambda z: z.get("url", ""),
    7:  lambda z: z.get("extra", ""),
    14: lambda z: "; ".join(sorted(z.get("tags_manual", []))),
    34: lambda z: "; ".join(sorted(z.get("tags_auto", []))),
    36: lambda z: z.get("dateAdded", ""),
    37: lambda z: z.get("dateModified", ""),
}


def norm(s):
    """Minusculas, sin acentos, espacios colapsados (solo para comparar)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def year_of(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return m.group(1) if m else ""


def strip_html(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def is_personal_tag(t):
    """Etiquetas personales de Zotero que el sync preserva: hashtags y
    emoji/simbolos NO-estrella (las estrellas las gestiona la valoracion).
    Las variantes obsoletas de vocabulario NO son personales."""
    t = t.strip()
    if STAR_RE.match(t):
        return False
    return t.startswith("#") or any(ord(c) >= 0x2000 for c in t)


def field_label(fname):
    """fieldName camelCase -> etiqueta legible para lineas de Extra.
    numPages -> 'Num Pages'? No: mapa explicito para los comunes."""
    known = {"numPages": "Number Of Pages", "ISBN": "ISBN", "ISSN": "ISSN",
             "publisher": "Publisher", "series": "Series",
             "seriesNumber": "Series Number", "edition": "Edition",
             "place": "Place", "archive": "Archive",
             "libraryCatalog": "Library Catalog", "callNumber": "Call Number",
             "numberOfVolumes": "Number Of Volumes", "volume": "Volume"}
    if fname in known:
        return known[fname]
    s = re.sub(r"(?<!^)(?=[A-Z])", " ", fname)
    return s[:1].upper() + s[1:]


def lang_base(v):
    """Normaliza cualquier variante de idioma a codigo base ISO 639-1."""
    v = (v or "").strip()
    if not v:
        return ""
    low = norm(v)
    if low in LANG_NAMES:
        return LANG_NAMES[low]
    code = low.split("-")[0]
    if code in LANG_2TO1:
        return LANG_2TO1[code]
    return code[:2]


def parse_cal_author(name):
    """Calibre 'Nombre| Apellido' (o 'Nombre, Apellido') -> (first, last, mode).
    Sin separador -> institucion (fieldMode=1, todo en lastName)."""
    if "|" in name:
        fn, ln = name.split("|", 1)
        return fn.strip(), ln.strip(), 0
    if "," in name:
        fn, ln = name.split(",", 1)
        return fn.strip(), ln.strip(), 0
    return "", name.strip(), 1


def person_tokens(fn, ln):
    """Conjunto de tokens de una persona, tolerante a orden invertido."""
    return frozenset(norm(fn).replace(".", "").split()) | \
        frozenset(norm(ln).replace(".", "").split())


def cal_stars(rating):
    """Calibre rating 0-10 -> numero de estrellas 1-5 (medias redondean up)."""
    if not rating:
        return 0
    return min(5, int(rating / 2 + 0.5))


class Plan:
    """Acumula acciones; cada accion es una fila del reporte."""

    def __init__(self):
        self.rows = []          # (book_id, zkey, campo, accion, antes, despues)
        self.zot_writes = []    # callables sobre cursor zotero
        self.cal_writes = []    # callables sobre cursor calibre

    def add(self, bid, zkey, campo, accion, antes, despues):
        self.rows.append((bid, zkey, campo, accion,
                          str(antes or "")[:200], str(despues or "")[:200]))


def load_zotero_schema(con):
    """Puebla los mapas de validez de campos/creadores por tipo."""
    for tid, tname in con.execute("SELECT itemTypeID, typeName FROM itemTypes"):
        TYPE_ID[tname] = tid
    for fid, fname in con.execute("SELECT fieldID, fieldName FROM fields"):
        FIELD_NAME[fid] = fname
    for tname, fname in con.execute(
            "SELECT t.typeName, f.fieldName FROM itemTypeFields itf "
            "JOIN itemTypes t ON t.itemTypeID=itf.itemTypeID "
            "JOIN fields f ON f.fieldID=itf.fieldID"):
        VALID_FIELDS.setdefault(tname, set()).add(fname)
    for tname, base, fname in con.execute(
            "SELECT t.typeName, fb.fieldName, ff.fieldName FROM baseFieldMappings m "
            "JOIN itemTypes t ON t.itemTypeID=m.itemTypeID "
            "JOIN fields fb ON fb.fieldID=m.baseFieldID "
            "JOIN fields ff ON ff.fieldID=m.fieldID"):
        TARGET_FIELD[(tname, base)] = fname
        BASE_OF[fname] = base
    for tname, ctid, prim in con.execute(
            "SELECT t.typeName, itc.creatorTypeID, itc.primaryField "
            "FROM itemTypeCreatorTypes itc "
            "JOIN itemTypes t ON t.itemTypeID=itc.itemTypeID"):
        VALID_CREATORS.setdefault(tname, set()).add(ctid)
        if prim:
            PRIMARY_CREATOR[tname] = ctid


def read_calibre(con):
    """Estado Calibre por book id (solo libros con #zotero_key)."""
    books = {}
    for bid, key in con.execute(
            f"SELECT book, TRIM(value) FROM custom_column_{COL_ZKEY} "
            "WHERE TRIM(COALESCE(value,''))<>''"):
        books[bid] = {"zkey": key}
    if not books:
        return books
    q = f"({','.join(str(b) for b in books)})"
    for bid, title, pubdate, sidx, path in con.execute(
            f"SELECT id, title, pubdate, series_index, path FROM books WHERE id IN {q}"):
        books[bid].update(title=title, pubdate=pubdate or "",
                          series_index=sidx, path=path)
    for bid, names in con.execute(
            f"SELECT l.book, GROUP_CONCAT(a.name, '###') FROM books_authors_link l "
            f"JOIN authors a ON a.id=l.author WHERE l.book IN {q} GROUP BY l.book"):
        books[bid]["authors"] = (names or "").split("###")
    for sql, field in (
            (f"SELECT l.book, p.name FROM books_publishers_link l JOIN publishers p ON p.id=l.publisher WHERE l.book IN {q}", "publisher"),
            (f"SELECT l.book, s.name FROM books_series_link l JOIN series s ON s.id=l.series WHERE l.book IN {q}", "series"),
            (f"SELECT book, val FROM identifiers WHERE type='isbn' AND book IN {q}", "isbn"),
            (f"SELECT book, value FROM custom_column_31 WHERE book IN {q}", "pages"),
            (f"SELECT book, value FROM custom_column_40 WHERE book IN {q}", "edition"),
            (f"SELECT book, text FROM comments WHERE book IN {q}", "comments"),
            (f"SELECT l.book, r.rating FROM books_ratings_link l JOIN ratings r ON r.id=l.rating WHERE l.book IN {q}", "rating")):
        for bid, v in con.execute(sql):
            if bid in books:
                books[bid][field] = v
    langs = dict(con.execute("SELECT id, lang_code FROM languages"))
    for bid, lid in con.execute(
            f"SELECT book, lang_code FROM books_languages_link WHERE book IN {q}"):
        if bid in books:
            books[bid]["language"] = langs.get(lid, "")
    for bid, tags in con.execute(
            f"SELECT l.book, GROUP_CONCAT(t.name, '###') FROM books_tags_link l "
            f"JOIN tags t ON t.id=l.tag WHERE l.book IN {q} GROUP BY l.book"):
        books[bid]["tags"] = set((tags or "").split("###")) - {""}
    for bid, v in con.execute(
            f"SELECT l.book, c.value FROM books_custom_column_39_link l "
            f"JOIN custom_column_39 c ON c.id=l.value WHERE l.book IN {q}"):
        books[bid]["cal_item_type"] = v
    for bid, name, fmt in con.execute(
            f"SELECT book, name, format FROM data WHERE book IN {q} "
            "ORDER BY book, format='PDF' DESC"):
        books[bid].setdefault("files", []).append((name, fmt))
    return books


def read_zotero(con):
    """Estado Zotero: items por key, con campos, creadores, tags y adjuntos."""
    items = {}
    for iid, key, tname in con.execute(
            "SELECT i.itemID, i.key, t.typeName FROM items i "
            "JOIN itemTypes t ON t.itemTypeID=i.itemTypeID "
            "WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)"):
        items[key] = {"itemID": iid, "typeName": tname}
    by_id = {v["itemID"]: v for v in items.values()}
    for iid, fname, val in con.execute(
            "SELECT d.itemID, f.fieldName, v.value FROM itemData d "
            "JOIN fields f ON f.fieldID=d.fieldID "
            "JOIN itemDataValues v ON v.valueID=d.valueID"):
        if iid in by_id:
            by_id[iid][fname] = val
    for iid, ln, fn, fm in con.execute(
            "SELECT ic.itemID, c.lastName, c.firstName, c.fieldMode "
            "FROM itemCreators ic JOIN creators c ON c.creatorID=ic.creatorID "
            "ORDER BY ic.itemID, ic.orderIndex"):
        if iid in by_id:
            by_id[iid].setdefault("creators", []).append((ln or "", fn or "", fm))
    for iid, tag, ttype in con.execute(
            "SELECT it.itemID, t.name, it.type FROM itemTags it "
            "JOIN tags t ON t.tagID=it.tagID"):
        if iid in by_id:
            k = "tags_manual" if ttype == 0 else "tags_auto"
            by_id[iid].setdefault(k, set()).add(tag)
    for iid, key, dadd, dmod in con.execute(
            "SELECT itemID, key, dateAdded, dateModified FROM items"):
        if iid in by_id:
            by_id[iid]["dateAdded"] = dadd
            by_id[iid]["dateModified"] = dmod
    for aid, akey, parent, path in con.execute(
            "SELECT ia.itemID, i.key, ia.parentItemID, ia.path FROM itemAttachments ia "
            "JOIN items i ON i.itemID=ia.itemID WHERE ia.linkMode=2"):
        if parent in by_id:
            by_id[parent].setdefault("attachments", []).append(
                {"itemID": aid, "key": akey, "path": path or ""})
    return items


# ----------------------------------------------------------------------
# Escrituras Zotero (SQL directo). Todas marcan el item como modificado.
# ----------------------------------------------------------------------

def z_touch(cur, item_id):
    cur.execute(
        "UPDATE items SET synced=0, dateModified=?, clientDateModified=? WHERE itemID=?",
        (NOW_SQL, NOW_SQL, item_id))


def z_field_id(cur, name):
    return cur.execute("SELECT fieldID FROM fields WHERE fieldName=?",
                       (name,)).fetchone()[0]


def z_value_id(cur, value):
    r = cur.execute("SELECT valueID FROM itemDataValues WHERE value=?",
                    (value,)).fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO itemDataValues(value) VALUES (?)", (value,))
    return cur.lastrowid


def z_set_field(cur, item_id, field, value):
    fid = z_field_id(cur, field)
    vid = z_value_id(cur, value)
    if cur.execute("SELECT 1 FROM itemData WHERE itemID=? AND fieldID=?",
                   (item_id, fid)).fetchone():
        cur.execute("UPDATE itemData SET valueID=? WHERE itemID=? AND fieldID=?",
                    (vid, item_id, fid))
    else:
        cur.execute("INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)",
                    (item_id, fid, vid))
    z_touch(cur, item_id)


def z_get_field(cur, item_id, field):
    r = cur.execute(
        "SELECT v.value FROM itemData d JOIN itemDataValues v ON v.valueID=d.valueID "
        "JOIN fields f ON f.fieldID=d.fieldID WHERE d.itemID=? AND f.fieldName=?",
        (item_id, field)).fetchone()
    return r[0] if r else ""


def z_change_type(cur, item_id, new_type, csl_type=None):
    """Cambia el tipo del item migrando campos y creadores sin perder datos.

    - Campo valido en el tipo nuevo: se conserva tal cual.
    - Campo con equivalente via baseFieldMappings: se traslada.
    - Resto: se anexa al Extra como linea "Etiqueta: valor" (CSL).
    - Creadores con rol invalido: pasan al rol primario del tipo nuevo.
    - csl_type: para tipos sustitutos del contrato, anexa "Type: <csl>".
    """
    new_tid = TYPE_ID[new_type]
    valid = VALID_FIELDS.get(new_type, set())
    to_extra = []
    for fid, vid in cur.execute(
            "SELECT fieldID, valueID FROM itemData WHERE itemID=?",
            (item_id,)).fetchall():
        fname = FIELD_NAME[fid]
        if fname in valid or fname == "extra":
            continue
        val = cur.execute("SELECT value FROM itemDataValues WHERE valueID=?",
                          (vid,)).fetchone()[0]
        base = BASE_OF.get(fname, fname)
        target = TARGET_FIELD.get((new_type, base),
                                  base if base in valid else None)
        cur.execute("DELETE FROM itemData WHERE itemID=? AND fieldID=?",
                    (item_id, fid))
        if target and target in valid:
            tfid = z_field_id(cur, target)
            if not cur.execute("SELECT 1 FROM itemData WHERE itemID=? AND fieldID=?",
                               (item_id, tfid)).fetchone():
                cur.execute(
                    "INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)",
                    (item_id, tfid, vid))
                continue
        to_extra.append(f"{field_label(fname)}: {val}")
    if csl_type:
        to_extra.append(f"Type: {csl_type}")
    if to_extra:
        extra = z_get_field(cur, item_id, "extra")
        lines = [l for l in extra.split("\n") if l.strip()] if extra else []
        for line in to_extra:
            if line not in lines:
                lines.append(line)
        z_set_field(cur, item_id, "extra", "\n".join(lines))
    # creadores: roles invalidos -> rol primario del tipo nuevo
    vc = VALID_CREATORS.get(new_type, set())
    prim = PRIMARY_CREATOR.get(new_type)
    if prim:
        cur.execute(
            "UPDATE itemCreators SET creatorTypeID=? WHERE itemID=? "
            f"AND creatorTypeID NOT IN ({','.join(str(c) for c in vc)})",
            (prim, item_id))
    cur.execute("UPDATE items SET itemTypeID=? WHERE itemID=?", (new_tid, item_id))
    z_touch(cur, item_id)


def z_set_creators(cur, item_id, persons, ctype_id):
    """Reemplaza los creadores del rol primario conservando el resto."""
    others = cur.execute(
        "SELECT creatorID, creatorTypeID FROM itemCreators "
        "WHERE itemID=? AND creatorTypeID!=? ORDER BY orderIndex",
        (item_id, ctype_id)).fetchall()
    cur.execute("DELETE FROM itemCreators WHERE itemID=?", (item_id,))
    idx = 0
    for fn, ln, fm in persons:
        r = cur.execute(
            "SELECT creatorID FROM creators WHERE firstName=? AND lastName=? AND fieldMode=?",
            (fn, ln, fm)).fetchone()
        cid = r[0] if r else None
        if cid is None:
            cur.execute("INSERT INTO creators(firstName, lastName, fieldMode) VALUES (?,?,?)",
                        (fn, ln, fm))
            cid = cur.lastrowid
        cur.execute(
            "INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) "
            "VALUES (?,?,?,?)", (item_id, cid, ctype_id, idx))
        idx += 1
    for cid, ctype in others:
        cur.execute(
            "INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) "
            "VALUES (?,?,?,?)", (item_id, cid, ctype, idx))
        idx += 1
    z_touch(cur, item_id)


def z_tag_id(cur, name):
    r = cur.execute("SELECT tagID FROM tags WHERE name=?", (name,)).fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO tags(name) VALUES (?)", (name,))
    return cur.lastrowid


def z_set_manual_tags(cur, item_id, tags):
    """Reemplaza SOLO las etiquetas manuales (type=0); conserva automaticas.
    PK de itemTags = (itemID, tagID): si la tag ya existe como automatica se
    deja como esta (el item ya la lleva)."""
    cur.execute("DELETE FROM itemTags WHERE itemID=? AND type=0", (item_id,))
    for t in sorted(tags):
        tid = z_tag_id(cur, t)
        if not cur.execute("SELECT 1 FROM itemTags WHERE itemID=? AND tagID=?",
                           (item_id, tid)).fetchone():
            cur.execute("INSERT INTO itemTags(itemID, tagID, type) VALUES (?,?,0)",
                        (item_id, tid))
    z_touch(cur, item_id)


# ----------------------------------------------------------------------
# Nucleo de decision por par
# ----------------------------------------------------------------------

def plan_pair(plan, bid, cal, zot):
    zkey = cal["zkey"]
    iid = zot["itemID"]

    # --- tipo de item: manda el Item type de Calibre ---
    cal_itype = cal.get("cal_item_type", "")
    final_type = zot["typeName"]
    if cal_itype:
        mapped = TYPE_MAP.get(cal_itype)
        if mapped and mapped in TYPE_ID and mapped != zot["typeName"]:
            csl = {"Figure": "figure", "Musical Score": "musical_score",
                   "Pamphlet": "pamphlet", "Book Review": "review-book",
                   "Treaty": "treaty"}.get(cal_itype)
            plan.add(bid, zkey, "tipo", "calibre->zotero (cambio de tipo)",
                     zot["typeName"], mapped)
            plan.zot_writes.append(
                lambda c, i=iid, t=mapped, x=csl: z_change_type(c, i, t, x))
            final_type = mapped
        elif not mapped:
            plan.add(bid, zkey, "tipo", "reporte (sin mapeo de tipo)",
                     zot["typeName"], cal_itype)
    valid = VALID_FIELDS.get(final_type, set())
    prim_creator = PRIMARY_CREATOR.get(final_type)

    # --- titulo (Calibre manda; Zotero se ajusta) ---
    # comparación exacta: con norm() una corrección de tildes o mayúsculas en Calibre nunca llegaba a
    # Zotero (133 ítems desfasados el 2026-10-01; ver migraciones/titulos_zotero_2026-10-01)
    ct, zt = cal.get("title", ""), zot.get("title", "")
    if norm(ct) and " ".join(ct.split()) != " ".join(zt.split()):
        plan.add(bid, zkey, "titulo", "calibre->zotero", zt, ct)
        plan.zot_writes.append(lambda c, i=iid, v=ct: z_set_field(c, i, "title", v))

    # --- autores (semantico; superconjunto de Zotero se respeta) ---
    cal_names = [a for a in cal.get("authors", [])
                 if norm(a) not in ("unknown", "desconocido", "")]
    cal_persons = [parse_cal_author(a) for a in cal_names]
    cal_sets = {person_tokens(fn, ln) for fn, ln, _ in cal_persons}
    zot_creators = zot.get("creators", [])
    zot_sets = {person_tokens(fn, ln) for ln, fn, _ in zot_creators
                if norm(ln) not in ("unknown", "desconocido") or norm(fn)}
    zot_sets = {s for s in zot_sets if s}
    zdisp = "; ".join(f"{l}, {f}" if f else l for l, f, _ in zot_creators)
    if cal_sets and prim_creator:
        if not zot_sets:
            plan.add(bid, zkey, "autores", "calibre->zotero (Unknown/vacio)",
                     zdisp, " & ".join(cal_names))
            plan.zot_writes.append(
                lambda c, i=iid, p=cal_persons, t=prim_creator: z_set_creators(c, i, p, t))
        elif cal_sets == zot_sets:
            pass  # misma gente, cada sistema en su formato: correcto
        elif cal_sets < zot_sets:
            plan.add(bid, zkey, "autores", "reporte (Zotero mas completo)",
                     " & ".join(cal_names), zdisp)
        else:
            plan.add(bid, zkey, "autores", "calibre->zotero (conflicto)",
                     zdisp, " & ".join(cal_names))
            plan.zot_writes.append(
                lambda c, i=iid, p=cal_persons, t=prim_creator: z_set_creators(c, i, p, t))

    # --- fecha ---
    cal_year = year_of(cal.get("pubdate", ""))
    zot_year = year_of(zot.get("date", ""))
    if cal_year and cal_year != zot_year:
        val = cal.get("pubdate", "")[:10]
        multipart = f"{val} {val}"
        plan.add(bid, zkey, "fecha", "calibre->zotero", zot.get("date", ""), multipart)
        plan.zot_writes.append(lambda c, i=iid, v=multipart: z_set_field(c, i, "date", v))
    elif not cal_year and zot_year and DO_BACKFILL:
        plan.add(bid, zkey, "fecha", "zotero->calibre (relleno placeholder)",
                 cal.get("pubdate", ""), f"{zot_year}-01-01")
        plan.cal_writes.append(
            lambda c, b=bid, y=zot_year: c.execute(
                "UPDATE books SET pubdate=? WHERE id=?",
                (f"{y}-01-01 00:00:00+00:00", b)))

    # --- campos escalares: Calibre manda (solo si el campo cabe en el tipo) ---
    # Para articulos, la SERIE de Calibre es el nombre de la publicacion
    # (contrato RIS: T2={series} -> publicationTitle), no una serie editorial.
    series_target = "publicationTitle" if final_type in (
        "journalArticle", "magazineArticle", "newspaperArticle") else "series"
    for cfield, zfield in (("publisher", "publisher"), ("series", series_target),
                           ("pages", "numPages"), ("edition", "edition")):
        cv = str(cal.get(cfield, "") or "").strip()
        # Resolver PRIMERO el campo destino del tipo (publisher->institution
        # en report, etc.) y comparar contra ESE campo; si no, tras un cambio
        # de tipo se releeria el generico vacio y se re-escribiria siempre.
        target = zfield if zfield in valid else \
            TARGET_FIELD.get((final_type, zfield))
        zv = str(zot.get(target, "") or "").strip() if target else \
            str(zot.get(zfield, "") or "").strip()
        if cv and norm(cv) != norm(zv):
            if target:
                accion = "calibre->zotero" if zv else "calibre->zotero (vacio)"
                plan.add(bid, zkey, cfield, accion, zv, cv)
                plan.zot_writes.append(
                    lambda c, i=iid, f=target, v=cv: z_set_field(c, i, f, v))
            else:
                plan.add(bid, zkey, cfield,
                         f"reporte (campo no aplicable a {final_type})", zv, cv)

    # --- numero de serie ---
    if cal.get("series") and "seriesNumber" in valid:
        sidx = cal.get("series_index")
        cv = str(int(sidx)) if sidx == int(sidx) else str(sidx)
        zv = str(zot.get("seriesNumber", "") or "")
        if cv and cv != zv and cv != "0":
            plan.add(bid, zkey, "seriesNumber", "calibre->zotero", zv, cv)
            plan.zot_writes.append(
                lambda c, i=iid, v=cv: z_set_field(c, i, "seriesNumber", v))

    # --- ISBN (ambas direcciones, relleno) ---
    ci = re.sub(r"[^0-9Xx]", "", cal.get("isbn", "") or "")
    zi = re.sub(r"[^0-9Xx]", "", zot.get("ISBN", "") or "")
    if ci and not zi and "ISBN" in valid:
        plan.add(bid, zkey, "isbn", "calibre->zotero (vacio)", "", cal["isbn"])
        plan.zot_writes.append(
            lambda c, i=iid, v=cal["isbn"]: z_set_field(c, i, "ISBN", v))
    elif zi and not ci and DO_BACKFILL:
        plan.add(bid, zkey, "isbn", "zotero->calibre (relleno)", "", zot["ISBN"])
        plan.cal_writes.append(
            lambda c, b=bid, v=zot["ISBN"]: c.execute(
                "INSERT OR IGNORE INTO identifiers(book, type, val) VALUES (?,?,?)",
                (b, "isbn", v)))
    elif ci and zi and ci.lower() != zi.lower() and "ISBN" in valid:
        plan.add(bid, zkey, "isbn", "calibre->zotero (conflicto)",
                 zot["ISBN"], cal["isbn"])
        plan.zot_writes.append(
            lambda c, i=iid, v=cal["isbn"]: z_set_field(c, i, "ISBN", v))

    # --- idioma: CALIBRE MANDA SIEMPRE (Zotero quedo mal poblado) ---
    cb = lang_base(cal.get("language", ""))
    zraw = (zot.get("language", "") or "").strip()
    if cb:
        zb = lang_base(zraw)
        valid_iso = bool(re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?", zraw))
        if cb != zb:
            accion = "calibre->zotero (conflicto)" if zb else "calibre->zotero (vacio)"
            plan.add(bid, zkey, "idioma", accion, zraw, cb)
            plan.zot_writes.append(lambda c, i=iid, v=cb: z_set_field(c, i, "language", v))
        elif not valid_iso and zraw != cb:
            plan.add(bid, zkey, "idioma", "normalizar codigo ISO", zraw, cb)
            plan.zot_writes.append(lambda c, i=iid, v=cb: z_set_field(c, i, "language", v))

    # --- valoracion (estrellas) + tags ---
    ct_set = cal.get("tags", set())
    zt_set = zot.get("tags_manual", set())
    zot_star = next((t for t in sorted(zt_set) if STAR_RE.match(t)), "")
    stars_c = cal_stars(cal.get("rating", 0))
    star_tag = ""
    if stars_c:
        star_tag = "⭐" * stars_c
        if zot_star and zot_star != star_tag:
            plan.add(bid, zkey, "valoracion", "calibre->zotero (conflicto)",
                     zot_star, star_tag)
        elif not zot_star:
            plan.add(bid, zkey, "valoracion", "calibre->zotero (vacio)", "", star_tag)
    elif zot_star:
        star_tag = zot_star  # se conserva en Zotero
        if DO_BACKFILL:
            pts = min(10, 2 * len(zot_star))
            plan.add(bid, zkey, "valoracion", "zotero->calibre (relleno)",
                     "", f"{zot_star} ({pts}/10)")
            plan.cal_writes.append(
                lambda c, b=bid, r=pts: (
                    c.execute("INSERT OR IGNORE INTO ratings(rating) VALUES (?)", (r,)),
                    c.execute(
                        "INSERT OR REPLACE INTO books_ratings_link(book, rating) "
                        "SELECT ?, id FROM ratings WHERE rating=?", (b, r))))

    if ct_set or star_tag:
        personales = {t for t in zt_set if is_personal_tag(t)}
        destino = personales | ct_set
        if star_tag:
            destino.add(star_tag)
        if destino != zt_set:
            accion = "calibre->zotero" if zt_set else "calibre->zotero (vacio)"
            plan.add(bid, zkey, "tags", accion,
                     "; ".join(sorted(zt_set)), "; ".join(sorted(destino)))
            plan.zot_writes.append(
                lambda c, i=iid, t=frozenset(destino): z_set_manual_tags(c, i, t))

    # --- abstract: comments (sin HTML) -> abstractNote solo si vacio ---
    ca = strip_html(cal.get("comments", ""))
    if ca and not (zot.get("abstractNote") or "").strip():
        plan.add(bid, zkey, "abstract", "calibre->zotero (vacio)", "", ca[:120] + "...")
        plan.zot_writes.append(
            lambda c, i=iid, v=ca: z_set_field(c, i, "abstractNote", v))

    # --- Extra: actualizar SOLO la linea de ruta, preservando lineas CSL ---
    # ZMI (M2={path}) guarda la RUTA ABSOLUTA del fichero dentro de la
    # biblioteca: /.../biblioteca/Autor/Titulo (id)/Fichero.ext
    extra = zot.get("extra", "")
    if extra and cal.get("path") and cal.get("files"):
        base = os.path.dirname(CAL_DB)
        name = next((f[0] for f in cal["files"] if f[1] == "PDF"), cal["files"][0][0])
        ext = ".pdf" if any(f[1] == "PDF" for f in cal["files"]) \
            else "." + cal["files"][0][1].lower()
        actual = f"{base}/{cal['path']}/{name}{ext}"
        lines = extra.split("\n")
        for n, line in enumerate(lines):
            s = line.strip()
            if s.startswith(base + "/") and re.search(r"\(\d+\)/", s):
                if s != actual:
                    lines[n] = actual
                    newextra = "\n".join(lines)
                    plan.add(bid, zkey, "extra_path", "actualizar ruta", s, actual)
                    plan.zot_writes.append(
                        lambda c, i=iid, v=newextra: z_set_field(c, i, "extra", v))
                break

    # --- adjuntos: reparar rutas rotas ---
    if DO_ATTACH:
        base = os.path.dirname(CAL_DB)
        for att in zot.get("attachments", []):
            rel = att["path"][len("attachments:"):] \
                if att["path"].startswith("attachments:") else None
            if rel is None or os.path.exists(os.path.join(base, rel)):
                continue
            files = cal.get("files", [])
            if not files:
                plan.add(bid, zkey, "adjunto", "reporte (sin formatos en calibre)",
                         att["path"], "")
                continue
            ext = ".pdf" if any(f[1] == "PDF" for f in files) \
                else "." + files[0][1].lower()
            name = next((f[0] for f in files if f[1] == "PDF"), files[0][0])
            newrel = f"{cal['path']}/{name}{ext}"
            if os.path.exists(os.path.join(base, newrel)):
                plan.add(bid, zkey, "adjunto", "reparar ruta", att["path"],
                         "attachments:" + newrel)
                plan.zot_writes.append(
                    lambda c, a=att["itemID"], v="attachments:" + newrel: (
                        c.execute("UPDATE itemAttachments SET path=? WHERE itemID=?",
                                  (v, a)),
                        z_touch(c, a)))
            else:
                plan.add(bid, zkey, "adjunto", "reporte (fichero no hallado)",
                         att["path"], newrel)


def write_reports(plan, n_pairs, orphans):
    counts = {}
    for r in plan.rows:
        counts[r[3]] = counts.get(r[3], 0) + 1
    with open(REPORT_TSV, "w", encoding="utf-8") as f:
        f.write("book_id\tzotero_key\tcampo\taccion\tantes\tdespues\n")
        for r in plan.rows:
            f.write("\t".join(str(x).replace("\t", " ").replace("\n", " ")
                              for x in r) + "\n")
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Reporte de sincronizacion Calibre <-> Zotero\n\n")
        f.write(f"- Pares enlazados analizados: **{n_pairs}**\n")
        f.write(f"- Claves huerfanas (en Calibre, sin item en Zotero): **{len(orphans)}**\n")
        f.write(f"- Acciones planificadas: **{len(plan.rows)}**\n")
        f.write(f"- Modo: **{'APLICADO' if APPLY else 'SIMULACION'}**\n\n")
        f.write("| Accion | Cantidad |\n|---|---|\n")
        for a, n in sorted(counts.items(), key=lambda x: -x[1]):
            f.write(f"| {a} | {n} |\n")
        if orphans:
            f.write("\n## Claves huerfanas\n\n")
            for bid, key in orphans[:50]:
                f.write(f"- libro {bid}: `{key}`\n")
        f.write("\n> Detalle completo en el TSV. Los 'reporte (...)' no se aplican: "
                "son para revision manual.\n")
    return counts


def mirror_writes(cal_books, zot_items, pairs):
    """Escrituras de columnas espejo desde el estado Zotero dado."""
    writes, count = [], 0
    for bid, c, _ in pairs:
        z = zot_items.get(c["zkey"])
        if not z:
            continue
        for colnum, extract in MIRROR_COLS.items():
            val = (extract(z) or "").strip()
            if not val:
                continue
            count += 1
            writes.append((bid, colnum, val))
    return writes, count


def main():
    cal = sqlite3.connect(CAL_DB if APPLY else f"file:{CAL_DB}?mode=ro",
                          uri=not APPLY)
    zot = sqlite3.connect(ZOT_DB if APPLY else f"file:{ZOT_DB}?mode=ro",
                          uri=not APPLY)
    load_zotero_schema(zot)
    cal_books = read_calibre(cal)
    zot_items = read_zotero(zot)

    pairs, orphans = [], []
    for bid, data in sorted(cal_books.items()):
        if ONLY_IDS and bid not in ONLY_IDS:
            continue
        z = zot_items.get(data["zkey"])
        if z is None:
            orphans.append((bid, data["zkey"]))
        else:
            pairs.append((bid, data, z))
    if LIMIT:
        pairs = pairs[:LIMIT]

    plan = Plan()
    for bid, c, z in pairs:
        plan_pair(plan, bid, c, z)

    counts = write_reports(plan, len(pairs), orphans)

    mcount = 0
    if APPLY:
        zcur = zot.cursor()
        for w in plan.zot_writes:
            w(zcur)
        zot.commit()
        # espejo desde el estado Zotero FINAL (re-lectura tras aplicar)
        if DO_MIRROR:
            fresh = read_zotero(zot)
            writes, mcount = mirror_writes(cal_books, fresh, pairs)
        else:
            writes = []
        ccur = cal.cursor()
        for w in plan.cal_writes:
            w(ccur)
        for bid, colnum, val in writes:
            ccur.execute(
                f"INSERT INTO custom_column_{colnum}(book, value) VALUES (?,?) "
                "ON CONFLICT(book) DO UPDATE SET value=excluded.value",
                (bid, val))
        cal.commit()
        state = {c["zkey"]: {"title": z.get("title", ""), "sync": NOW_SQL}
                 for _, c, z in pairs}
        os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
        with open(STATE_JSON, "w", encoding="utf-8") as f:
            json.dump({"fecha": NOW_SQL, "pares": len(pairs), "items": state}, f)
    elif DO_MIRROR:
        _, mcount = mirror_writes(cal_books, zot_items, pairs)

    cal.close()
    zot.close()
    print(f"{len(pairs)}\t{len(plan.rows)}\t{len(plan.zot_writes)}\t"
          f"{len(plan.cal_writes) + mcount}\t{len(orphans)}\t{mcount}")


if __name__ == "__main__":
    main()
