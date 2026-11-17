"""lectura_base/lib/sincronizar.py — la ida: leer cada herramienta (solo lectura) y conciliar con la base.

El orden importa poco (la conciliación une el mismo pasaje venga primero de donde venga), pero se fija para que el
informe sea estable: KOReader, Zotero, Okular, Yachay. Yachay se lee por su cliente desde el cursor que la base guarda
(«yachay» en `cursores`); sin cliente, se avisa y se sigue con los demás.
"""
from __future__ import annotations

from pathlib import Path

from lectura_base.lib import base
from lectura_base.lib.biblioteca import Resolutor

CONSUMIDOR_YACHAY = "yachay-entrada"


def leer(origenes: tuple[str, ...] = base.ORIGENES, resolutor: Resolutor | None = None, ruta: Path | None = None,
         cliente=None, recortar_okular: bool = True) -> tuple[list[base.Lectura], dict]:
    """(lecturas, extra) de los orígenes pedidos; `extra["cursor_yachay"]` es el cursor nuevo de Yachay, si se leyó."""
    resolutor = resolutor or Resolutor()
    lecturas, extra = [], {}
    if "koreader" in origenes:
        from lectura_base.lib.adaptadores import koreader
        lecturas.append(koreader.leer(resolutor))
    if "zotero" in origenes:
        from lectura_base.lib.adaptadores import zotero
        lecturas.append(zotero.leer(resolutor))
    if "okular" in origenes:
        from lectura_base.lib.adaptadores import okular
        lecturas.append(okular.leer(resolutor, recortar_texto=recortar_okular))
    if "yachay" in origenes:
        from lectura_base.lib.adaptadores import yachay
        cliente = cliente if cliente is not None else yachay.cargar_cliente()
        if cliente is None:
            lecturas.append(base.Lectura("yachay", alcance=None,
                                         avisos=["Yachay: sin canal todavía (el cliente con token es de la fase 3b)"]))
        else:
            try:
                lectura, cursor = yachay.leer(cliente, base.leer_cursor(CONSUMIDOR_YACHAY, ruta))
                lecturas.append(lectura)
                extra["cursor_yachay"] = cursor
            except Exception as e:  # noqa: BLE001 — Yachay caído o sin permiso: los demás orígenes siguen
                lecturas.append(base.Lectura("yachay", alcance=None, avisos=[f"Yachay: no respondió ({e})"]))
    return lecturas, extra


def sincronizar(origenes: tuple[str, ...] = base.ORIGENES, aplicar: bool = False, ruta: Path | None = None,
                resolutor: Resolutor | None = None, cliente=None, recortar_okular: bool = True) -> list[base.Plan]:
    lecturas, extra = leer(origenes, resolutor, ruta, cliente, recortar_okular)
    planes = base.importar(lecturas, aplicar=aplicar, ruta=ruta)
    if aplicar and "cursor_yachay" in extra:
        base.guardar_cursor(CONSUMIDOR_YACHAY, extra["cursor_yachay"], ruta)
    return planes
