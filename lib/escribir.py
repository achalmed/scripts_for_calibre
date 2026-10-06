#!/usr/bin/env python3
"""lib/escribir.py — la única puerta de escritura de scripts_for_calibre, lado Python (ola 2a, K2).

Objetivo: que ningún otro archivo del repo escriba en metadata.db ni en zotero.sqlite (normativa 9.1,
  RQ-PRE-06; lo comprueba tests/test_puerta.py).
Método:
  - Calibre se escribe con su API (`set_campos`, dentro de `calibre-debug`) o con `calibredb`
    (`calibredb_escribe` de lib/escribir.sh), nunca por SQL: el SQL directo choca con los disparadores
    de Calibre (title_sort) y deja los OPF rancios;
  - Zotero se escribe por SQL (no hay otra vía con la app cerrada) con las primitivas `z_*` de aquí, que
    marcan cada ítem tocado como no sincronizado para que la cuenta lo suba;
  - toda escritura exige la puerta abierta: PUERTA_CALIBRE / PUERTA_ZOTERO = «abierta», que pone
    lib/escribir.sh tras comprobar la app cerrada, tomar el candado y respaldar verificado, o el gestor
    `puerta()` de aquí para las herramientas que son solo Python.
Uso como CLI (lo llama lib/escribir.sh):
    escribir.py respaldar BASE CARPETA PREFIJO N   → respaldo verificado y rotado; imprime su ruta
    escribir.py integridad BASE…                   → PRAGMA integrity_check (solo lectura) = ok en todas
    calibre-debug -e escribir.py aplicar-plan BIBLIOTECA PLAN.json   → {campo: {libro: valor}} por la API
Límite: la API de Calibre solo existe dentro de `calibre-debug`; fuera, `set_campos` no se puede llamar.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LIB = Path(__file__).resolve().parent
CORE = LIB.parent.parent / "core"
ABIERTA = "abierta"


class PuertaCerrada(RuntimeError):
    """Se intentó escribir sin abrir la puerta."""


def exigir(base: str, ruta: str | os.PathLike | None = None) -> None:
    """Falla si la puerta de `base` («calibre» o «zotero») no está abierta para `ruta`."""
    if os.environ.get(f"PUERTA_{base.upper()}") != ABIERTA:
        raise PuertaCerrada(f"la puerta de {base} está cerrada: ábrela con lib/escribir.sh o escribir.puerta()")
    if ruta is not None:
        esperado = os.environ.get("PUERTA_BIBLIOTECA" if base == "calibre" else "PUERTA_ZOTERO_DB", "")
        if not esperado or os.path.realpath(esperado) != os.path.realpath(ruta):
            raise PuertaCerrada(f"la puerta de {base} se abrió para «{esperado}», no para «{ruta}»")


# ------------------------------------------------------------------ respaldo e integridad
def _ro(ruta) -> sqlite3.Connection:
    return sqlite3.connect(Path(ruta).resolve().as_uri() + "?mode=ro", uri=True)


def integridad(*bases) -> bool:
    ok = True
    for b in bases:
        c = _ro(b)
        r = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        if r != "ok":
            print(f"integridad de {b}: {r}", file=sys.stderr)
            ok = False
    return ok


def respaldar(base, carpeta, prefijo: str, conservar: int = 3) -> Path:
    """Copia consistente (API de respaldo de SQLite desde una conexión de solo lectura) a un temporal,
    `quick_check` = ok, renombrado atómico y, solo entonces, rotación a los `conservar` más recientes."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{prefijo}_", suffix=".tmp", dir=carpeta)
    os.close(fd)
    try:
        src, dst = _ro(base), sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        c = _ro(tmp)
        bien = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        c.close()
        if not bien:
            raise RuntimeError(f"PRAGMA quick_check no dio «ok» en la copia de {base}")
        final = carpeta / f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{Path(base).suffix or '.db'}"
        os.replace(tmp, final)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    viejos = sorted(carpeta.glob(f"{prefijo}_*"), key=lambda p: p.stat().st_mtime, reverse=True)[conservar:]
    for v in viejos:
        v.unlink(missing_ok=True)
    return final


def _app_abierta(patron: str) -> bool:
    """Mismo criterio que core/shell-lib/detectar_apps.sh: el nombre del binario (`ps -eo comm`)."""
    import re
    salida = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
    return any(re.match(patron, l.strip(), re.I) for l in salida.splitlines())


def _respaldo_calibre(db, carpeta, conservar: int) -> str:
    """El respaldo verificado de core (`backup_metadata_db`), el mismo que usa lib/escribir.sh."""
    r = subprocess.run(["bash", "-c", 'source "$1"; backup_metadata_db "$2" "$3" "$4"', "_",
                        str(CORE / "shell-lib" / "backup_rotado.sh"), str(db), str(carpeta), str(conservar)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"sin respaldo verificado de {db}: {r.stderr.strip()}")
    return r.stdout.strip().removeprefix("── Backup: ")


@contextmanager
def puerta(suite: str, calibre: str | os.PathLike | None = None, zotero: str | os.PathLike | None = None,
           respaldos: str | os.PathLike | None = None):
    """La puerta para herramientas que son solo Python: app cerrada, candado y respaldo verificado de cada
    base pedida (`calibre` = carpeta de la biblioteca; `zotero` = zotero.sqlite). Ocupado: `Ocupado` (75)."""
    sys.path.insert(0, str(CORE / "py-common"))
    from candado import candado  # noqa: E402  (core/py-common/candado.py)
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    raiz = Path(respaldos or os.environ.get("PUERTA_RESPALDOS") or estado / "biblioteca" / "respaldos") / suite
    antes = {k: os.environ.get(k) for k in ("PUERTA_CALIBRE", "PUERTA_BIBLIOTECA", "PUERTA_ZOTERO", "PUERTA_ZOTERO_DB")}
    pilas = []
    try:
        if calibre is not None:
            if _app_abierta(r"^calibre"):
                raise PuertaCerrada("Calibre está abierto: ciérralo antes de escribir en la biblioteca")
            cm = candado("calibre"); cm.__enter__(); pilas.append(cm)
            r = _respaldo_calibre(Path(calibre) / "metadata.db", raiz / "calibre",
                                  int(os.environ.get("PUERTA_CONSERVAR_CALIBRE", 5)))
            print(f"── Backup: {r}")
            os.environ.update(PUERTA_CALIBRE=ABIERTA, PUERTA_BIBLIOTECA=str(calibre))
        if zotero is not None:
            if _app_abierta(r"^zotero"):
                raise PuertaCerrada("Zotero está abierto: ciérralo antes de escribir en zotero.sqlite")
            cm = candado("zotero"); cm.__enter__(); pilas.append(cm)
            r = respaldar(zotero, raiz / "zotero", "zotero", int(os.environ.get("PUERTA_CONSERVAR_ZOTERO", 3)))
            print(f"── Backup: {r}")
            os.environ.update(PUERTA_ZOTERO=ABIERTA, PUERTA_ZOTERO_DB=str(zotero))
        yield
    finally:
        for k, v in antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for cm in reversed(pilas):
            cm.__exit__(None, None, None)


# ------------------------------------------------------------------ Calibre (API, dentro de calibre-debug)
def set_campos(api, cambios: dict) -> int:
    """{campo: {libro: valor}} → `api.set_field` por campo; devuelve cuántos valores pidió escribir."""
    exigir("calibre", api.backend.library_path)
    n = 0
    for campo, valores in cambios.items():
        if valores:
            api.set_field(campo, valores)
            n += len(valores)
    return n


def _fecha(v):
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-":
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return v


def aplicar_plan(biblioteca, plan_json) -> int:
    """Un plan {campo: {libro: valor}} escrito por otra herramienta (p. ej. sincronizar_zotero), por la API.
    `identifiers` se fusiona con los que el libro ya tiene (nunca borra); `pubdate` admite texto ISO."""
    from calibre.library import db as calibre_db
    plan = json.loads(Path(plan_json).read_text(encoding="utf-8"))
    api = calibre_db(str(biblioteca)).new_api
    cambios = {}
    for campo, valores in plan.items():
        v = {int(b): x for b, x in valores.items()}
        if campo == "identifiers":
            v = {b: {**(api.field_for("identifiers", b) or {}), **x} for b, x in v.items()}
        elif campo == "pubdate":
            v = {b: _fecha(x) for b, x in v.items()}
        cambios[campo] = v
    return set_campos(api, cambios)


# ------------------------------------------------------------------ Zotero (SQL, con la app cerrada)
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


# ------------------------------------------------------------------ CLI
def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    orden, args = argv[0], argv[1:]
    if orden == "respaldar":
        base, carpeta, prefijo, n = args
        print(respaldar(base, carpeta, prefijo, int(n)))
        return 0
    if orden == "integridad":
        return 0 if integridad(*args) else 1
    if orden == "aplicar-plan":
        biblioteca, plan = args
        n = aplicar_plan(biblioteca, plan)
        print(f"── Calibre: {n} valores enviados a la API (solo se escriben los que cambian)")
        return 0
    print(f"orden desconocida: {orden}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except PuertaCerrada as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
