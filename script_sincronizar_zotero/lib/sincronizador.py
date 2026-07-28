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
  - Formato por sistema, nunca homogenizar: Calibre "Nombre, Apellido"
    (separador interno '|'), Zotero firstName/lastName separados.
  - Campo Extra de Zotero: se edita linea a linea; solo se actualiza la
    linea de ruta {path}, las lineas "CSL Variable: Value" se preservan.
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
import sys
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

# Columnas espejo zotero_* de Calibre (colnum -> extractor sobre el estado
# Zotero final). Formato Zotero preservado (autores "Apellido, Nombre; ...").
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
    """True para etiquetas personales de Zotero que el sync NUNCA borra:
    valoraciones/emoji (⭐, ★, cualquier simbolo Unicode alto) y hashtags
    (#Apuntes...). Las variantes ortograficas obsoletas de vocabulario
    (Ciencias sociales, economía_ambiental, programming_R, el typo
    'ecuacione s_lineales') NO son personales: se reemplazan por la version
    limpia de Calibre para no reintroducir duplicados ya fusionados."""
    t = t.strip()
    return t.startswith("#") or any(ord(c) >= 0x2000 for c in t)


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

    Sin separador -> institucion (fieldMode=1, todo en lastName).
    """
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


class Plan:
    """Acumula acciones; cada accion es una fila del reporte."""

    def __init__(self):
        self.rows = []          # (book_id, zkey, campo, accion, antes, despues)
        self.zot_writes = []    # callables sobre cursor zotero
        self.cal_writes = []    # callables sobre cursor calibre
        self.touched_items = set()

    def add(self, bid, zkey, campo, accion, antes, despues):
        self.rows.append((bid, zkey, campo, accion,
                          str(antes or "")[:200], str(despues or "")[:200]))


def read_calibre(con):
    """Estado Calibre por book id (solo libros con #zotero_key)."""
    books = {}
    for bid, key in con.execute(
            f"SELECT book, TRIM(value) FROM custom_column_{COL_ZKEY} WHERE TRIM(COALESCE(value,''))<>''"):
        books[bid] = {"zkey": key}
    q = f"({','.join(str(b) for b in books)})"
    for bid, title, pubdate, sidx, path in con.execute(
            f"SELECT id, title, pubdate, series_index, path FROM books WHERE id IN {q}"):
        b = books[bid]
        b.update(title=title, pubdate=pubdate or "", series_index=sidx, path=path)
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
            (f"SELECT book, text FROM comments WHERE book IN {q}", "comments")):
        for bid, v in con.execute(sql):
            if bid in books:
                books[bid][field] = v
    langs = dict(con.execute("SELECT id, lang_code FROM languages"))
    for bid, lid in con.execute(f"SELECT book, lang_code FROM books_languages_link WHERE book IN {q}"):
        if bid in books:
            books[bid]["language"] = langs.get(lid, "")
    for bid, tags in con.execute(
            f"SELECT l.book, GROUP_CONCAT(t.name, '###') FROM books_tags_link l "
            f"JOIN tags t ON t.id=l.tag WHERE l.book IN {q} GROUP BY l.book"):
        books[bid]["tags"] = set((tags or "").split("###")) - {""}
    # formatos (para reparar rutas de adjuntos): preferir PDF
    for bid, name, fmt in con.execute(
            f"SELECT book, name, format FROM data WHERE book IN {q} ORDER BY book, format='PDF' DESC"):
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
            "SELECT ic.itemID, c.lastName, c.firstName, c.fieldMode FROM itemCreators ic "
            "JOIN creators c ON c.creatorID=ic.creatorID ORDER BY ic.itemID, ic.orderIndex"):
        if iid in by_id:
            by_id[iid].setdefault("creators", []).append((ln or "", fn or "", fm))
    for iid, tag, ttype in con.execute(
            "SELECT it.itemID, t.name, it.type FROM itemTags it JOIN tags t ON t.tagID=it.tagID"):
        if iid in by_id:
            k = "tags_manual" if ttype == 0 else "tags_auto"
            by_id[iid].setdefault(k, set()).add(tag)
    for iid, key, dadd, dmod in con.execute(
            "SELECT itemID, key, dateAdded, dateModified FROM items"):
        if iid in by_id:
            by_id[iid]["dateAdded"] = dadd
            by_id[iid]["dateModified"] = dmod
    # adjuntos enlazados hijos (para reparar rutas)
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
    return cur.execute("SELECT fieldID FROM fields WHERE fieldName=?", (name,)).fetchone()[0]


def z_value_id(cur, value):
    r = cur.execute("SELECT valueID FROM itemDataValues WHERE value=?", (value,)).fetchone()
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


def z_creator_id(cur, fn, ln, fm):
    r = cur.execute(
        "SELECT creatorID FROM creators WHERE firstName=? AND lastName=? AND fieldMode=?",
        (fn, ln, fm)).fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO creators(firstName, lastName, fieldMode) VALUES (?,?,?)",
                (fn, ln, fm))
    return cur.lastrowid


def z_set_creators(cur, item_id, persons):
    """Reemplaza los creadores de tipo AUTHOR conservando el resto.

    persons: [(first, last, fieldMode)] en orden. Editores, traductores y
    demas roles se preservan y quedan despues de los autores. Asi el sync
    nunca borra co-creadores que Calibre no representa.
    """
    at = cur.execute(
        "SELECT creatorTypeID FROM creatorTypes WHERE creatorType='author'").fetchone()[0]
    others = cur.execute(
        "SELECT creatorID, creatorTypeID FROM itemCreators "
        "WHERE itemID=? AND creatorTypeID!=? ORDER BY orderIndex",
        (item_id, at)).fetchall()
    cur.execute("DELETE FROM itemCreators WHERE itemID=?", (item_id,))
    idx = 0
    for fn, ln, fm in persons:
        cid = z_creator_id(cur, fn, ln, fm)
        cur.execute(
            "INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) "
            "VALUES (?,?,?,?)", (item_id, cid, at, idx))
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

    La PK de itemTags es (itemID, tagID) — 'type' no es parte de la clave.
    Si la etiqueta ya esta en el item como automatica (type=1) se deja como
    esta (el item ya la lleva); un INSERT type=0 chocaria en silencio.
    """
    cur.execute("DELETE FROM itemTags WHERE itemID=? AND type=0", (item_id,))
    for t in sorted(tags):
        tid = z_tag_id(cur, t)
        exists = cur.execute(
            "SELECT 1 FROM itemTags WHERE itemID=? AND tagID=?", (item_id, tid)).fetchone()
        if not exists:
            cur.execute("INSERT INTO itemTags(itemID, tagID, type) VALUES (?,?,0)",
                        (item_id, tid))
    z_touch(cur, item_id)


# ----------------------------------------------------------------------
# Nucleo de decision por par
# ----------------------------------------------------------------------

def plan_pair(plan, bid, cal, zot):
    zkey = cal["zkey"]
    iid = zot["itemID"]

    # Guarda de tipo: el contrato ZMI crea items 'book' y todos los campos
    # que escribimos (publisher, series, numPages, edition, ISBN...) existen
    # para 'book'. Un item de otro tipo tendria campos invalidos: no se toca,
    # solo se reporta para revision manual.
    if zot.get("typeName") != "book":
        plan.add(bid, zkey, "item", "reporte (tipo Zotero != book, revision manual)",
                 zot.get("typeName", ""), cal.get("title", ""))
        return

    # --- titulo (Calibre manda; Zotero se ajusta) ---
    ct, zt = cal.get("title", ""), zot.get("title", "")
    if norm(ct) and norm(ct) != norm(zt):
        plan.add(bid, zkey, "titulo", "calibre->zotero", zt, ct)
        plan.zot_writes.append(lambda c, i=iid, v=ct: z_set_field(c, i, "title", v))
    elif not norm(zt) and norm(ct):
        plan.add(bid, zkey, "titulo", "calibre->zotero (vacio)", "", ct)
        plan.zot_writes.append(lambda c, i=iid, v=ct: z_set_field(c, i, "title", v))

    # --- autores (semantico; superconjunto de Zotero se respeta) ---
    cal_names = [a for a in cal.get("authors", []) if norm(a) not in ("unknown", "desconocido", "")]
    cal_persons = [parse_cal_author(a) for a in cal_names]
    cal_sets = {person_tokens(fn, ln) for fn, ln, _ in cal_persons}
    zot_creators = zot.get("creators", [])
    zot_sets = {person_tokens(fn, ln) for ln, fn, _ in zot_creators
                if norm(ln) not in ("unknown", "desconocido") or norm(fn)}
    zot_sets = {s for s in zot_sets if s}
    if cal_sets:
        if not zot_sets:
            plan.add(bid, zkey, "autores", "calibre->zotero (Unknown/vacio)",
                     "; ".join(f"{l}, {f}" if f else l for l, f, _ in zot_creators),
                     " & ".join(cal_names))
            plan.zot_writes.append(lambda c, i=iid, p=cal_persons: z_set_creators(c, i, p))
        elif cal_sets == zot_sets:
            pass  # misma gente, cada sistema en su formato: correcto
        elif cal_sets < zot_sets:
            plan.add(bid, zkey, "autores", "reporte (Zotero mas completo)",
                     " & ".join(cal_names),
                     "; ".join(f"{l}, {f}" if f else l for l, f, _ in zot_creators))
        else:
            plan.add(bid, zkey, "autores", "calibre->zotero (conflicto)",
                     "; ".join(f"{l}, {f}" if f else l for l, f, _ in zot_creators),
                     " & ".join(cal_names))
            plan.zot_writes.append(lambda c, i=iid, p=cal_persons: z_set_creators(c, i, p))

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
                "UPDATE books SET pubdate=? WHERE id=?", (f"{y}-01-01 00:00:00+00:00", b)))

    # --- campos escalares: Calibre manda ---
    for cfield, zfield in (("publisher", "publisher"), ("series", "series"),
                           ("pages", "numPages"), ("edition", "edition")):
        cv = str(cal.get(cfield, "") or "").strip()
        zv = str(zot.get(zfield, "") or "").strip()
        if cv and norm(cv) != norm(zv):
            accion = "calibre->zotero" if zv else "calibre->zotero (vacio)"
            plan.add(bid, zkey, cfield, accion, zv, cv)
            plan.zot_writes.append(
                lambda c, i=iid, f=zfield, v=cv: z_set_field(c, i, f, v))

    # --- numero de serie ---
    if cal.get("series"):
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
    if ci and not zi:
        plan.add(bid, zkey, "isbn", "calibre->zotero (vacio)", "", cal["isbn"])
        plan.zot_writes.append(
            lambda c, i=iid, v=cal["isbn"]: z_set_field(c, i, "ISBN", v))
    elif zi and not ci and DO_BACKFILL:
        plan.add(bid, zkey, "isbn", "zotero->calibre (relleno)", "", zot["ISBN"])
        plan.cal_writes.append(
            lambda c, b=bid, v=zot["ISBN"]: c.execute(
                "INSERT OR IGNORE INTO identifiers(book, type, val) VALUES (?,?,?)",
                (b, "isbn", v)))
    elif ci and zi and ci.lower() != zi.lower():
        plan.add(bid, zkey, "isbn", "calibre->zotero (conflicto)", zot["ISBN"], cal["isbn"])
        plan.zot_writes.append(
            lambda c, i=iid, v=cal["isbn"]: z_set_field(c, i, "ISBN", v))

    # --- idioma ---
    # Se comparan por base ISO 639-1. Solo se AUTOAPLICA la normalizacion de
    # formato (spa->es, English->en) o el relleno de un Zotero vacio. Un
    # desacuerdo REAL de idioma (Zotero 'en' vs Calibre 'es') no se voltea
    # solo: se reporta, porque ninguno de los dos lados es autoridad fiable.
    cb = lang_base(cal.get("language", ""))
    zraw = (zot.get("language", "") or "").strip()
    zb = lang_base(zraw)
    if cb:
        valid_iso = bool(re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?", zraw))
        if cb != zb:
            if zb:
                plan.add(bid, zkey, "idioma", "reporte (conflicto de idioma)", zraw, cb)
            else:
                plan.add(bid, zkey, "idioma", "calibre->zotero (vacio)", zraw, cb)
                plan.zot_writes.append(lambda c, i=iid, v=cb: z_set_field(c, i, "language", v))
        elif not valid_iso and zraw != cb:
            plan.add(bid, zkey, "idioma", "normalizar codigo ISO", zraw, cb)
            plan.zot_writes.append(lambda c, i=iid, v=cb: z_set_field(c, i, "language", v))

    # --- tags: Calibre manda SOLO sobre el vocabulario controlado ---
    # Las etiquetas personales de Zotero fuera del vocabulario de Calibre
    # (valoraciones ⭐, emojis, tags libres) se PRESERVAN siempre. El destino
    # es: (personales de Zotero) union (tags de Calibre).
    ct_set = cal.get("tags", set())
    zt_set = zot.get("tags_manual", set())
    if ct_set:
        personales = {t for t in zt_set if is_personal_tag(t)}
        destino = personales | ct_set
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

    # (No se compara el tipo: todos los items enlazados son 'book' por
    # diseno ZMI; el Item type interno de Calibre sirve a otro proposito.)

    # --- Extra: actualizar SOLO la linea de ruta, preservando lineas CSL ---
    extra = zot.get("extra", "")
    if extra and cal.get("path"):
        lines = extra.split("\n")
        for n, line in enumerate(lines):
            if re.fullmatch(r"[^:\n]{1,300}\(\d+\)", line.strip()):
                if line.strip() != cal["path"]:
                    old = line.strip()
                    lines[n] = cal["path"]
                    newextra = "\n".join(lines)
                    plan.add(bid, zkey, "extra_path", "actualizar ruta", old, cal["path"])
                    plan.zot_writes.append(
                        lambda c, i=iid, v=newextra: z_set_field(c, i, "extra", v))
                break

    # --- adjuntos: reparar rutas rotas ---
    if DO_ATTACH:
        base = os.path.dirname(CAL_DB)
        for att in zot.get("attachments", []):
            rel = att["path"][len("attachments:"):] if att["path"].startswith("attachments:") else None
            if rel is None or os.path.exists(os.path.join(base, rel)):
                continue
            files = cal.get("files", [])
            if not files:
                plan.add(bid, zkey, "adjunto", "reporte (sin formatos en calibre)",
                         att["path"], "")
                continue
            ext = ".pdf" if any(f[1] == "PDF" for f in files) else "." + files[0][1].lower()
            name = next((f[0] for f in files if f[1] == "PDF"), files[0][0])
            newrel = f"{cal['path']}/{name}{ext}"
            if os.path.exists(os.path.join(base, newrel)):
                plan.add(bid, zkey, "adjunto", "reparar ruta", att["path"],
                         "attachments:" + newrel)
                plan.zot_writes.append(
                    lambda c, a=att["itemID"], v="attachments:" + newrel: (
                        c.execute("UPDATE itemAttachments SET path=? WHERE itemID=?", (v, a)),
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
            f.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in r) + "\n")
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


def main():
    cal = sqlite3.connect(CAL_DB if APPLY else f"file:{CAL_DB}?mode=ro",
                          uri=not APPLY)
    zot = sqlite3.connect(ZOT_DB if APPLY else f"file:{ZOT_DB}?mode=ro",
                          uri=not APPLY)
    cal_books = read_calibre(cal)
    # item type de Calibre (col 39) para el informe de tipos
    q = f"({','.join(str(b) for b in cal_books)})"
    for bid, v in cal.execute(
            f"SELECT l.book, c.value FROM books_custom_column_39_link l "
            f"JOIN custom_column_39 c ON c.id=l.value WHERE l.book IN {q}"):
        cal_books[bid]["cal_item_type"] = v
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

    # --- columnas espejo (Zotero -> Calibre), estado final tras aplicar ---
    mirror_count = 0
    if DO_MIRROR:
        for bid, c, z in pairs:
            for colnum, extract in MIRROR_COLS.items():
                val = (extract(z) or "").strip()
                if not val:
                    continue
                mirror_count += 1
                plan.cal_writes.append(
                    lambda cur, b=bid, n=colnum, v=val: cur.execute(
                        f"INSERT INTO custom_column_{n}(book, value) VALUES (?,?) "
                        "ON CONFLICT(book) DO UPDATE SET value=excluded.value",
                        (b, v)))

    counts = write_reports(plan, len(pairs), orphans)

    if APPLY:
        zcur = zot.cursor()
        for w in plan.zot_writes:
            w(zcur)
        zot.commit()
        ccur = cal.cursor()
        for w in plan.cal_writes:
            w(ccur)
        cal.commit()
        state = {c["zkey"]: {"title": z.get("title", ""),
                             "sync": NOW_SQL} for _, c, z in pairs}
        os.makedirs(os.path.dirname(STATE_JSON), exist_ok=True)
        with open(STATE_JSON, "w", encoding="utf-8") as f:
            json.dump({"fecha": NOW_SQL, "pares": len(pairs), "items": state}, f)

    cal.close()
    zot.close()
    # linea resumen para main.sh
    print(f"{len(pairs)}\t{len(plan.rows)}\t{len(plan.zot_writes)}\t"
          f"{len(plan.cal_writes)}\t{len(orphans)}\t{mirror_count}")


if __name__ == "__main__":
    main()
