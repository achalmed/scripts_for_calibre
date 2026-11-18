#!/usr/bin/env python3
"""lib/escribir_zotero.py — la puerta de escritura en zotero.sqlite: sus primitivas SQL (ola 2a, K2–K4).

Objetivo: que el SQL que modifica Zotero viva solo aquí (tests/test_puerta.py); no hay otra vía de
  escribir Zotero con la app cerrada. Cada primitiva marca el ítem tocado como no sincronizado
  (synced=0 y la fecha) para que la cuenta de zotero.org suba el cambio.
Método: `conexion_zotero` exige la puerta de Zotero abierta (PUERTA_ZOTERO=abierta para esa base: Zotero
  cerrado, LOCK_ZOTERO y respaldo verificado; lib/escribir.sh o `escribir.puerta()`); las `z_*` reciben
  el cursor de esa conexión. Las usan sincronizar-zotero y lib/adjuntos_zotero.py.
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


def z_del_field(cur, item_id, field) -> bool:
    """Quita un campo del ítem (deja el valor en itemDataValues: Zotero lo limpia solo). True si había algo que quitar."""
    fid = z_field_id(cur, field)
    if not cur.execute("SELECT 1 FROM itemData WHERE itemID=? AND fieldID=?", (item_id, fid)).fetchone():
        return False
    cur.execute("DELETE FROM itemData WHERE itemID=? AND fieldID=?", (item_id, fid))
    z_touch(cur, item_id)
    return True


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


_ALFABETO_CLAVE = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"      # el de Zotero.Utilities.generateObjectKey


def z_nueva_clave(cur, libreria: int) -> str:
    """Una clave de ocho caracteres que no use ningún ítem de esa biblioteca."""
    import secrets
    while True:
        clave = "".join(secrets.choice(_ALFABETO_CLAVE) for _ in range(8))
        if not cur.execute("SELECT 1 FROM items WHERE libraryID=? AND key=?", (libreria, clave)).fetchone():
            return clave


def z_anadir_anotacion(cur, adjunto_id: int, libreria: int, datos: dict) -> str:
    """Una anotación nueva en un adjunto PDF (la base de lectura, decisiones §9.6): un ítem de tipo «annotation» y su fila
    de `itemAnnotations`, sin sincronizar, para que la cuenta la suba. `datos`: tipo (1 resaltado, 2 nota, 5 subrayado),
    texto, comentario, color (#rrggbb), etiqueta (la página impresa), orden (sortIndex) y posicion (JSON de Zotero).
    Devuelve la clave del ítem."""
    tipo = cur.execute("SELECT itemTypeID FROM itemTypes WHERE typeName='annotation'").fetchone()[0]
    clave = z_nueva_clave(cur, libreria)
    cur.execute("INSERT INTO items(itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced) "
                "VALUES (?,?,?,?,?,?,0,0)", (tipo, AHORA_SQL, AHORA_SQL, AHORA_SQL, libreria, clave))
    cur.execute("INSERT INTO itemAnnotations(itemID, parentItemID, type, authorName, text, comment, color, pageLabel, sortIndex, "
                "position, isExternal) VALUES (?,?,?,NULL,?,?,?,?,?,?,0)",
                (cur.lastrowid, adjunto_id, int(datos["tipo"]), datos.get("texto") or None, datos.get("comentario") or None,
                 datos.get("color") or "#ffd400", datos.get("etiqueta") or "", datos["orden"], datos["posicion"]))
    return clave


# ------------------------------------------------------------------ obras nuevas (lib/ingresar.py; decisiones §9.10)
# Una obra que entra a la biblioteca por su DOI o ISBN (Método Documental, paso 03) nace en Zotero con la app cerrada: el
# ítem con sus campos válidos para su tipo, sus creadores, su clave de cita (la de Better BibTeX, fijada en `citationKey`),
# sus etiquetas, su colección y, si tiene PDF en Calibre, el adjunto enlazado a ese archivo. Todo sin sincronizar
# (`synced=0`, `version=0`) para que la cuenta lo suba, como lo nuevo que crea Zotero.

def _normalizado(t: str | None):
    """Lo que Zotero guarda en las columnas `…Normalized`: minúsculas sin tildes, solo si el texto no es ASCII."""
    import unicodedata
    if not t or t.isascii():
        return None
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def z_campos_validos(cur, tipo: str) -> set[str]:
    return {r[0] for r in cur.execute("SELECT f.fieldName FROM itemTypeFields itf JOIN itemTypes t ON t.itemTypeID=itf.itemTypeID "
                                      "JOIN fields f ON f.fieldID=itf.fieldID WHERE t.typeName=?", (tipo,))}


def z_creador(cur, nombre: str, apellido: str, modo: int) -> int:
    """El creador (nombre, apellido, modo: 0 persona, 1 un solo campo, como una institución), reutilizado si ya existe."""
    nombre = "" if modo == 1 else (nombre or "")
    r = cur.execute("SELECT creatorID FROM creators WHERE firstName=? AND lastName=? AND fieldMode=?", (nombre, apellido, modo)).fetchone()
    if r:
        return r[0]
    cur.execute("INSERT INTO creators(firstName, lastName, fieldMode, firstNameNormalized, lastNameNormalized) VALUES (?,?,?,?,?)",
                (nombre, apellido, modo, _normalizado(nombre), _normalizado(apellido)))
    return cur.lastrowid


def z_nuevo_item(cur, libreria: int, tipo: str, campos: dict, creadores: list[dict]) -> tuple[int, str]:
    """Un ítem nuevo de tipo `tipo` (journalArticle, book…) con `campos` {fieldName: valor} (solo los válidos para el tipo;
    uno que no lo sea es un error, no se pierde en silencio) y `creadores` [{nombre, apellido, modo, rol}]. Devuelve
    (itemID, clave del ítem)."""
    fila = cur.execute("SELECT itemTypeID FROM itemTypes WHERE typeName=?", (tipo,)).fetchone()
    if not fila:
        raise ValueError(f"Zotero no tiene el tipo «{tipo}»")
    validos = z_campos_validos(cur, tipo)
    ajenos = [k for k, v in campos.items() if v not in (None, "") and k not in validos]
    if ajenos:
        raise ValueError(f"{tipo} no lleva los campos {', '.join(ajenos)}")
    clave = z_nueva_clave(cur, libreria)
    cur.execute("INSERT INTO items(itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced) "
                "VALUES (?,?,?,?,?,?,0,0)", (fila[0], AHORA_SQL, AHORA_SQL, AHORA_SQL, libreria, clave))
    item = cur.lastrowid
    for campo, valor in campos.items():
        if valor not in (None, ""):
            cur.execute("INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)",
                        (item, z_field_id(cur, campo), z_value_id(cur, str(valor))))
    roles = dict(cur.execute("SELECT creatorType, creatorTypeID FROM creatorTypes").fetchall())
    for i, c in enumerate(creadores):
        cid = z_creador(cur, c.get("nombre") or "", c["apellido"], int(c.get("modo") or 0))
        cur.execute("INSERT INTO itemCreators(itemID, creatorID, creatorTypeID, orderIndex) VALUES (?,?,?,?)",
                    (item, cid, roles[c.get("rol") or "author"], i))
    return item, clave


def z_etiquetar(cur, item_id: int, etiquetas) -> None:
    """Añade etiquetas manuales (type=0) sin quitar las que ya tenga."""
    for t in etiquetas:
        tid = cur.execute("SELECT tagID FROM tags WHERE name=?", (t,)).fetchone()
        if tid:
            tid = tid[0]
        else:
            cur.execute("INSERT INTO tags(name, nameNormalized) VALUES (?,?)", (t, _normalizado(t)))
            tid = cur.lastrowid
        cur.execute("INSERT OR IGNORE INTO itemTags(itemID, tagID, type) VALUES (?,?,0)", (item_id, tid))
    z_touch(cur, item_id)


def z_coleccion(cur, libreria: int, nombre: str) -> int:
    """La colección de primer nivel `nombre` (la crea si falta, sin sincronizar)."""
    r = cur.execute("SELECT collectionID FROM collections WHERE libraryID=? AND collectionName=? AND parentCollectionID IS NULL",
                    (libreria, nombre)).fetchone()
    if r:
        return r[0]
    clave = z_nueva_clave(cur, libreria)
    while cur.execute("SELECT 1 FROM collections WHERE libraryID=? AND key=?", (libreria, clave)).fetchone():
        clave = z_nueva_clave(cur, libreria)
    cur.execute("INSERT INTO collections(collectionName, parentCollectionID, clientDateModified, libraryID, key, version, synced) "
                "VALUES (?,NULL,?,?,?,0,0)", (nombre, AHORA_SQL, libreria, clave))
    return cur.lastrowid


def z_en_coleccion(cur, coleccion_id: int, item_id: int) -> None:
    n = cur.execute("SELECT COALESCE(MAX(orderIndex), -1) + 1 FROM collectionItems WHERE collectionID=?", (coleccion_id,)).fetchone()[0]
    cur.execute("INSERT OR IGNORE INTO collectionItems(collectionID, itemID, orderIndex) VALUES (?,?,?)", (coleccion_id, item_id, n))
    cur.execute("UPDATE collections SET synced=0, clientDateModified=? WHERE collectionID=?", (AHORA_SQL, coleccion_id))


def z_adjunto_enlazado(cur, libreria: int, padre_id: int, ruta: str, titulo: str, tipo_contenido: str = "application/pdf") -> int:
    """Un adjunto enlazado (linkMode 2) al archivo de Calibre: `ruta` = `attachments:<relativa a la biblioteca>`, como los
    demás (Zotero lo resuelve con su baseAttachmentPath)."""
    tipo = cur.execute("SELECT itemTypeID FROM itemTypes WHERE typeName='attachment'").fetchone()[0]
    clave = z_nueva_clave(cur, libreria)
    cur.execute("INSERT INTO items(itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced) "
                "VALUES (?,?,?,?,?,?,0,0)", (tipo, AHORA_SQL, AHORA_SQL, AHORA_SQL, libreria, clave))
    item = cur.lastrowid
    cur.execute("INSERT INTO itemAttachments(itemID, parentItemID, linkMode, contentType, charsetID, path, syncState) "
                "VALUES (?,?,2,?,NULL,?,0)", (item, padre_id, tipo_contenido, ruta))
    cur.execute("INSERT INTO itemData(itemID, fieldID, valueID) VALUES (?,?,?)", (item, z_field_id(cur, "title"), z_value_id(cur, titulo)))
    return item


# ------------------------------------------------------------------ adjuntos con el linkMode cambiado (decisiones §2.14)
# zotero.org no deja cambiar el linkMode de un adjunto que ya subió («Cannot change attachment linkMode»): un adjunto
# guardado (imported_file) que luego se volvió enlazado (linked_file) por SQL bloquea la sincronización. Lo que hace
# Zotero al «convertir en archivo enlazado» es lo mismo que aquí: un adjunto nuevo, con clave nueva, y el viejo borrado
# con su entrada en `syncDeleteLog` para que la cuenta borre también la copia del servidor.

_MODOS = {0: "imported_file", 1: "imported_url", 2: "linked_file", 3: "linked_url", 4: "embedded_image"}


def z_conflictos_linkmode(cur) -> list[dict]:
    """Adjuntos sin sincronizar que ya existen en el servidor (`version` > 0) y cuyo linkMode local no es el que el
    servidor conoce (`syncCache`), o de los que no queda copia en `syncCache`."""
    filas = cur.execute(
        "SELECT i.itemID, i.key, ia.linkMode, ia.path, json_extract(sc.data, '$.data.linkMode') "
        "FROM itemAttachments ia JOIN items i USING(itemID) "
        "LEFT JOIN syncCache sc ON sc.libraryID = i.libraryID AND sc.key = i.key AND sc.syncObjectTypeID = "
        "(SELECT syncObjectTypeID FROM syncObjectTypes WHERE name = 'item') "
        "WHERE i.synced = 0 AND i.version > 0 ORDER BY i.itemID").fetchall()
    return [{"id": r[0], "clave": r[1], "local": _MODOS.get(r[2], str(r[2])), "ruta": r[3] or "",
             "servidor": r[4] or "(sin copia)"}
            for r in filas if r[4] is None or r[4] != _MODOS.get(r[2])]


def z_borrar_item(cur, item_id: int) -> None:
    """Borra un ítem como lo hace Zotero (sin papelera): su clave a `syncDeleteLog` y sus filas de toda tabla que lo
    nombre por `itemID`. La conexión de la puerta no activa las claves foráneas: las cascadas se hacen aquí."""
    libreria, clave = cur.execute("SELECT libraryID, key FROM items WHERE itemID=?", (item_id,)).fetchone()
    tipo = cur.execute("SELECT syncObjectTypeID FROM syncObjectTypes WHERE name='item'").fetchone()[0]
    cur.execute("INSERT OR IGNORE INTO syncDeleteLog(syncObjectTypeID, libraryID, key, dateDeleted) VALUES (?,?,?,?)",
                (tipo, libreria, clave, AHORA_SQL))
    tablas = [n for (n,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name <> 'items'").fetchall()
              if "itemID" in {c[1] for c in cur.execute(f'PRAGMA table_info("{n}")').fetchall()}]
    for t in tablas:
        cur.execute(f'DELETE FROM "{t}" WHERE itemID=?', (item_id,))
    cur.execute("DELETE FROM items WHERE itemID=?", (item_id,))


def z_rehacer_adjunto(cur, adjunto_id: int) -> tuple[int, str]:
    """El adjunto `adjunto_id` renace enlazado (linkMode 2) con clave nueva, la misma ruta, título y tipo de contenido;
    sus anotaciones pasan al nuevo y el viejo se borra con su entrada en `syncDeleteLog`. Devuelve (itemID, clave)."""
    libreria, padre, ruta, tipo_contenido = cur.execute(
        "SELECT i.libraryID, ia.parentItemID, ia.path, ia.contentType FROM itemAttachments ia JOIN items i USING(itemID) "
        "WHERE ia.itemID=?", (adjunto_id,)).fetchone()
    titulo = z_get_field(cur, adjunto_id, "title") or ""
    nuevo = z_adjunto_enlazado(cur, libreria, padre, ruta, titulo, tipo_contenido or "application/pdf")
    for (anot,) in cur.execute("SELECT itemID FROM itemAnnotations WHERE parentItemID=?", (adjunto_id,)).fetchall():
        cur.execute("UPDATE itemAnnotations SET parentItemID=? WHERE itemID=?", (nuevo, anot))
        z_touch(cur, anot)
    z_borrar_item(cur, adjunto_id)
    return nuevo, cur.execute("SELECT key FROM items WHERE itemID=?", (nuevo,)).fetchone()[0]
