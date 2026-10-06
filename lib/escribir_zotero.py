#!/usr/bin/env python3
"""lib/escribir_zotero.py — la puerta de escritura en zotero.sqlite: sus primitivas SQL (ola 2a, K2–K4).

Objetivo: que el SQL que modifica Zotero viva solo aquí (tests/test_puerta.py); no hay otra vía de
  escribir Zotero con la app cerrada. Cada primitiva marca el ítem tocado como no sincronizado
  (synced=0 y la fecha) para que la cuenta de zotero.org suba el cambio.
Método: `conexion_zotero` exige la puerta de Zotero abierta (PUERTA_ZOTERO=abierta para esa base: Zotero
  cerrado, LOCK_ZOTERO y respaldo verificado; lib/escribir.sh o `escribir.puerta()`); las `z_*` reciben
  el cursor de esa conexión. Las usan script_sincronizar_zotero y lib/adjuntos_zotero.py.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from escribir import exigir


def conexion_zotero(ruta) -> sqlite3.Connection:
    """Conexión de escritura a zotero.sqlite; exige la puerta de Zotero abierta para esa base."""
    exigir("zotero", ruta)
    return sqlite3.connect(ruta)


def ahora_sql() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


AHORA_SQL = ahora_sql()


def z_touch(cur, item_id, cuando: str | None = None):
    cur.execute("UPDATE items SET synced=0, dateModified=?, clientDateModified=? WHERE itemID=?",
                (cuando or AHORA_SQL, cuando or AHORA_SQL, item_id))


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
    if cur.execute("SELECT 1 FROM itemData WHERE itemID=? AND fieldID=?", (item_id, fid)).fetchone():
        cur.execute("UPDATE itemData SET valueID=? WHERE itemID=? AND fieldID=?", (vid, item_id, fid))
    else:
        cur.execute("INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)", (item_id, fid, vid))
    z_touch(cur, item_id)


def z_get_field(cur, item_id, field):
    r = cur.execute(
        "SELECT v.value FROM itemData d JOIN itemDataValues v ON v.valueID=d.valueID "
        "JOIN fields f ON f.fieldID=d.fieldID WHERE d.itemID=? AND f.fieldName=?", (item_id, field)).fetchone()
    return r[0] if r else ""


def z_change_type(cur, item_id, new_type, csl_type, esquema):
    """Cambia el tipo del ítem migrando campos y creadores sin perder datos (ver sincronizador.py).
    `esquema`: {"TYPE_ID", "VALID_FIELDS", "BASE_OF", "TARGET_FIELD", "VALID_CREATORS", "PRIMARY_CREATOR",
    "FIELD_NAME", "field_label"} del esquema de Zotero ya cargado."""
    e = esquema
    new_tid = e["TYPE_ID"][new_type]
    valid = e["VALID_FIELDS"].get(new_type, set())
    to_extra = []
    for fid, vid in cur.execute("SELECT fieldID, valueID FROM itemData WHERE itemID=?", (item_id,)).fetchall():
        fname = e["FIELD_NAME"][fid]
        if fname in valid or fname == "extra":
            continue
        val = cur.execute("SELECT value FROM itemDataValues WHERE valueID=?", (vid,)).fetchone()[0]
        base = e["BASE_OF"].get(fname, fname)
        target = e["TARGET_FIELD"].get((new_type, base), base if base in valid else None)
        cur.execute("DELETE FROM itemData WHERE itemID=? AND fieldID=?", (item_id, fid))
        if target and target in valid:
            tfid = z_field_id(cur, target)
            if not cur.execute("SELECT 1 FROM itemData WHERE itemID=? AND fieldID=?", (item_id, tfid)).fetchone():
                cur.execute("INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)", (item_id, tfid, vid))
                continue
        to_extra.append(f"{e['field_label'](fname)}: {val}")
    if csl_type:
        to_extra.append(f"Type: {csl_type}")
    if to_extra:
        extra = z_get_field(cur, item_id, "extra")
        lines = [l for l in extra.split("\n") if l.strip()] if extra else []
        for line in to_extra:
            if line not in lines:
                lines.append(line)
        z_set_field(cur, item_id, "extra", "\n".join(lines))
    vc = e["VALID_CREATORS"].get(new_type, set())
    prim = e["PRIMARY_CREATOR"].get(new_type)
    if prim:
        cur.execute("UPDATE itemCreators SET creatorTypeID=? WHERE itemID=? "
                    f"AND creatorTypeID NOT IN ({','.join(str(c) for c in vc)})", (prim, item_id))
    cur.execute("UPDATE items SET itemTypeID=? WHERE itemID=?", (new_tid, item_id))
    z_touch(cur, item_id)


def z_set_creators(cur, item_id, persons, ctype_id):
    """Reemplaza los creadores del rol primario conservando el resto."""
    others = cur.execute("SELECT creatorID, creatorTypeID FROM itemCreators WHERE itemID=? AND creatorTypeID!=? "
                         "ORDER BY orderIndex", (item_id, ctype_id)).fetchall()
    cur.execute("DELETE FROM itemCreators WHERE itemID=?", (item_id,))
    idx = 0
    for fn, ln, fm in persons:
        r = cur.execute("SELECT creatorID FROM creators WHERE firstName=? AND lastName=? AND fieldMode=?",
                        (fn, ln, fm)).fetchone()
        cid = r[0] if r else None
        if cid is None:
            cur.execute("INSERT INTO creators(firstName, lastName, fieldMode) VALUES (?,?,?)", (fn, ln, fm))
            cid = cur.lastrowid
        cur.execute("INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) VALUES (?,?,?,?)",
                    (item_id, cid, ctype_id, idx))
        idx += 1
    for cid, ctype in others:
        cur.execute("INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) VALUES (?,?,?,?)",
                    (item_id, cid, ctype, idx))
        idx += 1
    z_touch(cur, item_id)


def z_tag_id(cur, name):
    r = cur.execute("SELECT tagID FROM tags WHERE name=?", (name,)).fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO tags(name) VALUES (?)", (name,))
    return cur.lastrowid


def z_set_manual_tags(cur, item_id, tags):
    """Reemplaza SOLO las etiquetas manuales (type=0); conserva las automáticas."""
    cur.execute("DELETE FROM itemTags WHERE itemID=? AND type=0", (item_id,))
    for t in sorted(tags):
        tid = z_tag_id(cur, t)
        if not cur.execute("SELECT 1 FROM itemTags WHERE itemID=? AND tagID=?", (item_id, tid)).fetchone():
            cur.execute("INSERT INTO itemTags(itemID, tagID, type) VALUES (?,?,0)", (item_id, tid))
    z_touch(cur, item_id)


def z_set_attachment_path(cur, attachment_id, path):
    """Ruta de un adjunto enlazado (`attachments:<relativa a baseAttachmentPath>`)."""
    cur.execute("UPDATE itemAttachments SET path=? WHERE itemID=?", (path, attachment_id))
    z_touch(cur, attachment_id)


def z_rewrite_attachment_paths(cur, viejo: str, nuevo: str) -> int:
    """Toda ruta de adjunto igual a `viejo` pasa a `nuevo` (sin tocar la fecha, como las campañas)."""
    return cur.execute("UPDATE itemAttachments SET path = ? WHERE path = ?", (nuevo, viejo)).rowcount
