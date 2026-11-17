"""lectura_base/lib/adaptadores/yachay.py — el lector de Yachay ⇄ base de lectura, por la API de Yachay con token (§9.3.3).

El canal es el cliente de Yachay (`yachay/cliente.py`, de la fase 3b: solo biblioteca estándar, se carga por su ruta, el
token sale del llavero), nunca su base ni copias en archivos (decisión del autor del 2026-11-17). Este módulo no sabe de
HTTP: recibe un objeto con la forma del cliente y traduce.

- Traer: `cliente.cambios(desde)` → {cursor, mas, reiniciar, cambios: [{entidad, clave, accion, datos, …}]}. Los
  `resaltado` son filas de `lector_resaltados` (hoja del PDF de lectura, rects en fracciones como la base, texto o
  seleccion, intencion, nota, lugar, origen, origen_id); los `progreso`, de `lector_libros` (hoja). El cursor se guarda
  en `cursores` de la base («yachay»); `reiniciar` vuelve a 0. Lo que Yachay recibió de la base (su `origen_id` es el
  `uid` de una anotación) se reconoce como esa misma anotación.
- Enviar: las anotaciones de otros orígenes que Yachay no tiene, con `cliente.resaltar(...)`: su origen (el primero de
  la anotación: koreader, zotero u okular) y como `origen_id` el `uid` de la base, para que Yachay no duplique.

Límite (fase 3a): la hoja de Yachay es la del PDF de lectura; para un libro con PDF es la misma que la de KOReader y
Zotero; para un EPUB convertido no, y esos resaltados se unen solo por su texto.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from lectura_base.lib import base

ORIGEN = "yachay"
ORIGENES_YACHAY = ("koreader", "zotero", "okular")      # los que Yachay acepta como `origen` de un resaltado ajeno


def cargar_cliente():
    """El cliente de Yachay (`YACHAY_CLIENTE` o `<YACHAY_DIR|~/Documents/yachay>/yachay/cliente.py`) con su token del
    llavero, o None si aún no está (la fase 3b lo trae) o no hay token."""
    candidatos = [os.environ.get("YACHAY_CLIENTE") or ""]
    raiz = os.environ.get("YACHAY_DIR") or str(Path(os.environ.get("DOCS_ROOT") or Path.home() / "Documents") / "yachay")
    candidatos.append(str(Path(raiz) / "yachay" / "cliente.py"))
    for c in candidatos:
        if c and Path(c).is_file():
            s = importlib.util.spec_from_file_location("yachay_cliente", c)
            m = importlib.util.module_from_spec(s)
            s.loader.exec_module(m)
            try:
                return m.Cliente.del_llavero()
            except Exception:  # noqa: BLE001 — sin token en el llavero o sin red: no hay canal
                return None
    return None


def _rects(v) -> list:
    if isinstance(v, str):
        try:
            v = json.loads(v or "[]")
        except ValueError:
            v = []
    return [r for r in v or [] if isinstance(r, (list, tuple)) and len(r) == 5]


def de_resaltado(d: dict) -> dict:
    """Una fila de `lector_resaltados` como registro de la base."""
    return {"origen_id": str(d.get("id")), "calibre_id": d.get("calibre_id"), "hoja": d.get("hoja"),
            "pagina": str(d.get("lugar") or ""), "texto": d.get("texto") or d.get("seleccion") or "",
            "rects": _rects(d.get("rects")), "intencion": d.get("intencion") or "", "nota": d.get("nota") or "",
            "tipo": "resaltado", "creada": base.iso(d.get("creado_en"), local=False),
            "modificada": base.iso(d.get("actualizado_en") or d.get("creado_en"), local=False)}


def leer(cliente, desde: int | str = 0) -> tuple[base.Lectura, str]:
    """(lectura, cursor nuevo). Las bajas no se traen como ausencias por libro: Yachay da su último cambio de cada cosa, y
    una baja de un resaltado deja su presencia ausente (vía `bajas` de la lectura)."""
    lectura = base.Lectura(ORIGEN, alcance=None)
    cursor = str(desde or 0)
    bajas = []
    while True:
        r = cliente.cambios(desde=cursor)
        if r.get("reiniciar"):
            cursor = "0"
            lectura = base.Lectura(ORIGEN, alcance=None)
            bajas = []
            continue
        for c in r.get("cambios") or []:
            datos = c.get("datos") or {}
            if c.get("entidad") == "resaltado":
                if c.get("accion") == "baja":
                    bajas.append(str(c.get("clave") or datos.get("id")))
                elif datos:
                    reg = de_resaltado(datos)
                    if str(datos.get("origen_id") or "") and len(str(datos["origen_id"])) == 16:
                        reg["uid_base"] = str(datos["origen_id"])          # vino de la base: es esa anotación
                    lectura.anotaciones.append(reg)
            elif c.get("entidad") == "progreso" and datos.get("calibre_id") is not None:
                lectura.progreso.append({"calibre_id": datos["calibre_id"], "hoja": datos.get("hoja"),
                                         "ultima": base.iso(datos.get("abierto_en"), local=False)})
        cursor = str(r.get("cursor") or cursor)
        if not r.get("mas"):
            break
    lectura.bajas = bajas
    return lectura, cursor


def a_resaltado(a: dict) -> dict | None:
    """Una anotación de la base como cuerpo de `POST /lector/{calibre_id}/resaltados`; None si no se puede (sin libro u
    hoja, o solo de Yachay)."""
    origenes = [o["origen"] for o in a.get("origenes") or [] if not o.get("ausente")]
    origen = next((o for o in origenes if o in ORIGENES_YACHAY), None)
    if a.get("calibre_id") is None or not a.get("hoja") or origen is None or ORIGEN in origenes:
        return None
    return {"calibre_id": int(a["calibre_id"]), "hoja": int(a["hoja"]), "rects": a.get("rects") or [],
            "seleccion": a.get("texto") or "", "intencion": a.get("intencion") or "cita", "nota": a.get("nota") or "",
            "origen": origen, "origen_id": a["uid"]}
