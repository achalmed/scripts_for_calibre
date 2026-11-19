"""lectura_base/lib/sincronizar.py — la ida: leer cada herramienta (solo lectura) y conciliar con la base.

El orden importa poco (la conciliación une el mismo pasaje venga primero de donde venga), pero se fija para que el
informe sea estable: KOReader, Zotero, Okular, Yachay. Yachay se lee por su cliente desde el cursor que la base guarda
(«yachay» en `cursores`); sin cliente, se avisa y se sigue con los demás. Las fichas de obra de Yachay (§9.13) llegan en
la misma lectura de Yachay, con su propio cursor («yachay-fichas-obra»).
"""
from __future__ import annotations

from pathlib import Path

from lectura_base.lib import base
from lectura_base.lib.biblioteca import Resolutor

CONSUMIDOR_YACHAY = "yachay-entrada"
CONSUMIDOR_FICHAS = "yachay-fichas-obra"


def leer(origenes: tuple[str, ...] = base.ORIGENES, resolutor: Resolutor | None = None, ruta: Path | None = None,
         cliente=None, recortar_okular: bool = True) -> tuple[list[base.Lectura], dict]:
    """(lecturas, extra) de los orígenes pedidos; `extra["cursor_yachay"]` y `extra["cursor_fichas"]` son los cursores nuevos
    de Yachay (resaltados y progreso; fichas de obra), si se leyeron."""
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
                                         avisos=["Yachay: sin canal (falta el cliente o el token en el llavero; con el Python del sistema, el token se lee con secret-tool, del paquete libsecret-tools)"]))
        else:
            try:
                lectura, cursor = yachay.leer(cliente, base.leer_cursor(CONSUMIDOR_YACHAY, ruta))
                extra["cursor_yachay"] = cursor
            except Exception as e:  # noqa: BLE001 — Yachay caído o sin permiso: los demás orígenes siguen
                lectura = base.Lectura("yachay", alcance=None, avisos=[f"Yachay: no respondió ({e})"])
            if "cursor_yachay" in extra:
                try:
                    fichas, cursor = yachay.leer_fichas(cliente, base.leer_cursor(CONSUMIDOR_FICHAS, ruta))
                    lectura.fichas_obra, lectura.bajas_fichas = fichas.fichas_obra, fichas.bajas_fichas
                    extra["cursor_fichas"] = cursor
                except Exception as e:  # noqa: BLE001 — sin las fichas de obra, lo demás de Yachay entra igual
                    lectura.avisos.append(f"Yachay: no dio las fichas de obra ({e})")
            lecturas.append(lectura)
    return lecturas, extra


def sincronizar(origenes: tuple[str, ...] = base.ORIGENES, aplicar: bool = False, ruta: Path | None = None,
                resolutor: Resolutor | None = None, cliente=None, recortar_okular: bool = True) -> list[base.Plan]:
    lecturas, extra = leer(origenes, resolutor, ruta, cliente, recortar_okular)
    planes = base.importar(lecturas, aplicar=aplicar, ruta=ruta)
    if aplicar and "cursor_yachay" in extra:
        base.guardar_cursor(CONSUMIDOR_YACHAY, extra["cursor_yachay"], ruta)
    if aplicar and "cursor_fichas" in extra:
        base.guardar_cursor(CONSUMIDOR_FICHAS, extra["cursor_fichas"], ruta)
    return planes
