"""lectura_base/lib/adaptadores/zotero.py — Zotero ⇄ base de lectura.

Lee de una copia consistente de `zotero.sqlite` (la API de respaldo de SQLite en solo lectura; si Zotero la tiene
bloqueada, una copia del archivo a la caché), nunca de la base viva:
- `itemAnnotations` de los adjuntos PDF enlazados a la biblioteca (su ruta lleva `(<calibre_id>)/`), fuera de la
  papelera: resaltado (1), nota (2), subrayado (5) y texto (6); imagen y tinta no traen texto y no se traen. Los
  `rects` de Zotero son [x1, y1, x2, y2] en puntos con el origen abajo: se pasan a fracciones con el origen arriba.
- el tiempo de Ethereal Style (las notas `readingTime`, como `lectura/lib/sync_zotero_lectura.py`) y la última hoja
  del lector de Zotero (`syncedSettings.lastPageIndex_u_<adjunto>`), como progreso de origen «zotero».

Escribe por la puerta (`lib/escribir_zotero.z_anadir_anotacion`, con Zotero cerrado, el candado y el respaldo
verificado; `exportar.py`): los resaltados de otros orígenes con hoja y rectángulos, en el adjunto PDF del libro.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path

from lectura_base.lib import base
from lectura_base.lib.biblioteca import Resolutor, id_de_ruta, medidas

ORIGEN = "zotero"
TIPOS = {1: "resaltado", 2: "nota", 5: "subrayado", 6: "nota"}
TIPO_DE = {"resaltado": 1, "subrayado": 5, "nota": 2, "tachado": 5}


def ruta_zotero() -> Path:
    if os.environ.get("ZOTERO_DB"):
        return Path(os.environ["ZOTERO_DB"])
    return Path(os.environ.get("ZOTERO_DIR") or Path.home() / "Zotero") / "zotero.sqlite"


@contextmanager
def copia(ruta: Path):
    """Una conexión a una copia de la base de Zotero (en memoria; si está bloqueada, del archivo a la caché)."""
    m = base.memoria()
    tmp = None
    try:
        try:
            o = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)
            o.backup(m)
            o.close()
        except sqlite3.OperationalError:
            cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "biblioteca-studio"
            cache.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix="zotero_", suffix=".sqlite", dir=cache)
            os.close(fd)
            shutil.copyfile(ruta, tmp)
            o = sqlite3.connect(Path(tmp).resolve().as_uri() + "?mode=ro", uri=True)
            o.backup(m)
            o.close()
        yield m
    finally:
        m.close()
        if tmp:
            Path(tmp).unlink(missing_ok=True)


def archivo_del_adjunto(ruta_zotero_: str, biblioteca: Path) -> Path | None:
    """`attachments:<relativa>` (relativa a la biblioteca, que es la baseAttachmentPath) o una ruta absoluta."""
    r = str(ruta_zotero_ or "")
    if r.startswith("attachments:"):
        return biblioteca / r[len("attachments:"):]
    return Path(r) if r.startswith("/") else None


def a_fracciones(pos: dict, hojas: list) -> tuple[int | None, list]:
    indice = pos.get("pageIndex")
    hoja = int(indice) + 1 if isinstance(indice, int) else None
    rects = []
    if hoja and 0 < hoja <= len(hojas):
        w, h = hojas[hoja - 1]
        for r in pos.get("rects") or []:
            if len(r) == 4 and w and h:
                x1, y1, x2, y2 = (float(v) for v in r)
                rects.append([hoja, x1 / w, (h - y2) / h, (x2 - x1) / w, (y2 - y1) / h])
    return hoja, rects


def a_posicion(hoja: int, rects: list, hojas: list) -> dict | None:
    """Los rectángulos de la base como `position` de Zotero ({pageIndex, rects: [[x1, y1, x2, y2]]} en puntos, origen abajo)."""
    if not hoja or not (0 < hoja <= len(hojas)):
        return None
    w, h = hojas[hoja - 1]
    salida = [[round(r[1] * w, 3), round(h - (r[2] + r[4]) * h, 3), round((r[1] + r[3]) * w, 3), round(h - r[2] * h, 3)]
              for r in rects if int(r[0]) == hoja]
    return {"pageIndex": hoja - 1, "rects": salida} if salida else None


def orden(hoja: int, pos: dict, hojas: list) -> str:
    """El `sortIndex` de Zotero: «hoja|carácter|distancia desde arriba» (00005|000000|00123); el carácter no se sabe."""
    w, h = hojas[hoja - 1]
    arriba = min((h - r[3] for r in pos["rects"]), default=0)
    return f"{hoja - 1:05d}|000000|{max(0, int(arriba)):05d}"


def leer(resolutor: Resolutor | None = None, ruta: Path | None = None) -> base.Lectura:
    resolutor = resolutor or Resolutor()
    lectura = base.Lectura(ORIGEN)
    ruta = Path(ruta or ruta_zotero())
    if not ruta.is_file():
        lectura.avisos.append("Zotero: no está zotero.sqlite")
        lectura.alcance = None
        return lectura
    with copia(ruta) as c:
        try:
            adjuntos = c.execute("SELECT a.itemID, a.path, i.key, p.key FROM itemAttachments a JOIN items i ON i.itemID = a.itemID "
                                 "LEFT JOIN items p ON p.itemID = a.parentItemID WHERE lower(a.path) LIKE '%.pdf' AND a.path LIKE '%(%)/%' "
                                 "AND a.itemID NOT IN (SELECT itemID FROM deletedItems)").fetchall()
            filas = c.execute("SELECT n.itemID, i.key, n.parentItemID, n.type, n.text, n.comment, n.color, n.pageLabel, n.position, "
                              "i.dateAdded, i.dateModified FROM itemAnnotations n JOIN items i ON i.itemID = n.itemID "
                              "WHERE n.itemID NOT IN (SELECT itemID FROM deletedItems) ORDER BY n.parentItemID, n.sortIndex").fetchall()
        except sqlite3.DatabaseError as e:
            lectura.avisos.append(f"Zotero: no se pudo leer sus anotaciones ({e})")
            lectura.alcance = None
            return lectura
        por_adjunto, libro_de_padre = {}, {}
        for item_id, path, _clave, clave_padre in adjuntos:
            calibre_id = id_de_ruta(path)
            if calibre_id is None:
                continue
            por_adjunto[item_id] = (calibre_id, archivo_del_adjunto(path, resolutor.biblioteca))
            lectura.alcance.add(base.clave_libro(calibre_id))
            if clave_padre:
                libro_de_padre[clave_padre] = calibre_id
        for item_id, clave, padre, tipo, texto, comentario, color, etiqueta, posicion, alta, modif in filas:
            if padre not in por_adjunto or int(tipo or 0) not in TIPOS:
                continue
            calibre_id, archivo = por_adjunto[padre]
            try:
                pos = json.loads(posicion or "{}")
            except ValueError:
                pos = {}
            hoja, rects = a_fracciones(pos, medidas(archivo) if archivo else [])
            if not (texto or "").strip() and not (comentario or "").strip():
                continue
            lectura.anotaciones.append({"origen_id": clave, "calibre_id": calibre_id, "hoja": hoja, "pagina": etiqueta or "",
                                        "texto": texto or "", "rects": rects, "color": color or "", "tipo": TIPOS[int(tipo)],
                                        "nota": comentario or "", "creada": base.iso(alta, local=False),
                                        "modificada": base.iso(modif, local=False)})
            lectura.libros.setdefault(calibre_id, resolutor.ficha(calibre_id))
        lectura.progreso = _progreso(c, libro_de_padre)
    return lectura


def _progreso(c, libro_de_padre: dict) -> list[dict]:
    """El tiempo de Ethereal Style y la última hoja del lector de Zotero, por libro."""
    import re
    salida: dict[int, dict] = {}
    try:
        notas = c.execute("SELECT n.note, i.dateModified FROM itemNotes n JOIN items i ON i.itemID = n.itemID "
                          "WHERE n.note LIKE '%\"readingTime\"%'").fetchall()
    except sqlite3.DatabaseError:
        notas = []
    for nota, fecha in notas:
        m = re.search(r'znv1"[^>]*>\s*([A-Z0-9]{8})', nota or "")
        if not m or m.group(1) not in libro_de_padre:
            continue
        ini, fin = nota.find("{"), nota.rfind("}")
        try:
            rt = json.loads(nota[ini:fin + 1]).get("readingTime", {})
            seg = sum(int(v) for v in (rt.get("data") or {}).values())
        except (ValueError, TypeError):
            continue
        b = libro_de_padre[m.group(1)]
        g = salida.setdefault(b, {"calibre_id": b})
        if seg >= g.get("segundos", 0):
            g.update(segundos=seg, ultima=base.iso(fecha, local=False))
    try:
        hojas = c.execute("SELECT ip.key, ss.value FROM syncedSettings ss JOIN items ia ON ia.key = substr(ss.setting, 17) "
                          "AND ia.libraryID = ss.libraryID JOIN itemAttachments att ON att.itemID = ia.itemID "
                          "JOIN items ip ON ip.itemID = att.parentItemID WHERE ss.setting LIKE 'lastPageIndex_u_%'").fetchall()
    except sqlite3.DatabaseError:
        hojas = []
    for clave, valor in hojas:
        if clave not in libro_de_padre:
            continue
        try:
            hoja = int(json.loads(valor)) + 1 if isinstance(valor, str) else int(valor) + 1
        except (ValueError, TypeError):
            continue
        b = libro_de_padre[clave]
        g = salida.setdefault(b, {"calibre_id": b})
        g["hoja"] = max(hoja, g.get("hoja") or 0)
    return list(salida.values())


def adjuntos_pdf(c, biblioteca: Path) -> dict[int, dict]:
    """{calibre_id: {item_id, library_id, archivo}} de los adjuntos PDF enlazados a la biblioteca (de una conexión ya abierta)."""
    salida = {}
    for item_id, libreria, path in c.execute(
            "SELECT a.itemID, i.libraryID, a.path FROM itemAttachments a JOIN items i ON i.itemID = a.itemID "
            "WHERE lower(a.path) LIKE '%.pdf' AND a.path LIKE '%(%)/%' AND a.itemID NOT IN (SELECT itemID FROM deletedItems) "
            "ORDER BY a.itemID"):
        b = id_de_ruta(path)
        if b is not None and b not in salida:
            salida[b] = {"item_id": item_id, "library_id": libreria, "archivo": archivo_del_adjunto(path, biblioteca)}
    return salida


def anotacion_de_zotero(a: dict, hojas: list) -> dict | None:
    """Un resaltado de la base como fila de Zotero (sin clave ni ids), o None si no tiene posición."""
    pos = a_posicion(a.get("hoja"), a.get("rects") or [], hojas)
    if pos is None:
        return None
    return {"tipo": TIPO_DE.get(a.get("tipo"), 1), "texto": a.get("texto") or "", "comentario": a.get("nota") or "",
            "color": (a.get("color") or "#ffd400").lower(), "etiqueta": a.get("pagina") or str(a["hoja"]),
            "orden": orden(a["hoja"], pos, hojas), "posicion": json.dumps(pos, separators=(",", ":"))}
