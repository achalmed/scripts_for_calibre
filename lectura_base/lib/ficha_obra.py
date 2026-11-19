"""lectura_base/lib/ficha_obra.py — la ficha de obra de la persona sobre un libro (la de Yachay, decisiones §9.13): leerla de
la base y llevarla de vuelta a Yachay por su cliente, con `version_base`.

Objetivo: que lo que la persona responde de una obra en Biblioteca Studio (las seis preguntas, los temas y el signo) llegue a
  su ficha de obra de Yachay sin pisar lo que escribió allí después, y que la base muestre la versión nueva.
Método: `plan` (solo lee la base) arma la ficha entera que viajaría: la que la base tiene, con las respuestas nuevas encima
  (el PUT de Yachay reemplaza la ficha entera), la `version_base` (la de la base, o la que la persona elige tras un
  conflicto con `sobre`), qué preguntas cambian y si se pedirá darla por leída. `llevar` simula por omisión (devuelve el
  plan); con `aplicar`, `cliente.guardar_ficha_obra` (PUT `/lectura/{calibre_id}/ficha`): un 409 `lectura_modificada` no
  escribe nada, ni en Yachay ni en la base, y devuelve la versión actual para que la persona elija (llevar la suya sobre
  esa versión o quedarse con la de Yachay, que trae la sincronía); lo aceptado se guarda en la base (por su único
  escritor, tras su respaldo) y, si se pidió, `cliente.dar_por_leida` (422 `ficha_incompleta`: se dice qué falta).
Límite: escribe solo en Yachay (por su API, con el token de la persona) y en la base de lectura; nunca en Calibre, Zotero ni
  en las fichas de un escrito (esas las escribe `lib/fichar.py`). Lo de las palabras propias lo mide Yachay y vuelve en su
  revisión; aquí no se juzga.
"""
from __future__ import annotations

from pathlib import Path

from lectura_base.lib import base

ORIGEN = "yachay"
DE_TITULO = {v: k for k, v in base.TITULOS_OBRA.items()}
EXTRA = ("temas", "signo")
ROTULOS = {**base.TITULOS_OBRA, "temas": "Temas", "signo": "Signo"}


class SinCanal(RuntimeError):
    """No hay cliente de Yachay o no hay token en el llavero."""


def respuestas_de(datos: dict) -> dict:
    """Las respuestas pedidas, por la clave de Yachay (`pregunta` … `uso`, `temas`, `signo`) o por el título de la norma de
    fichas («Pregunta» … «Uso que le daré»); lo demás se ignora. Un signo fuera del vocabulario es un error."""
    salida = {}
    for k, v in (datos or {}).items():
        clave = DE_TITULO.get(str(k), str(k))
        if clave in base.CAMPOS_OBRA:
            salida[clave] = str(v or "").strip()
        elif clave in EXTRA:
            salida[clave] = v
    if "signo" in salida:
        signo = str(salida["signo"] or "")
        if signo not in base.SIGNOS:
            raise ValueError(f"El signo es uno de: {', '.join(s for s in base.SIGNOS if s)} (o vacío).")
        salida["signo"] = signo
    if "temas" in salida:
        salida["temas"] = base.ficha_limpia({"temas": salida["temas"]})["temas"]
    return salida


def plan(calibre_id: int, datos: dict, sobre: int | None = None, leida: bool = False, ruta: Path | None = None) -> dict:
    """Lo que se enviaría a Yachay (solo lee la base): {calibre_id, ficha, version_base, cambian, nueva, leida, faltan,
    actual}. `sobre` es la versión de Yachay sobre la que la persona eligió llevar la suya tras un conflicto."""
    respuestas = respuestas_de(datos)
    if not respuestas:
        raise ValueError("Nada que llevar: escribe al menos una de las seis respuestas, los temas o el signo.")
    actual = base.ficha_obra(int(calibre_id), ORIGEN, ruta)
    previa = (actual or {}).get("ficha") or base.ficha_limpia({})
    ficha = base.ficha_limpia({**previa, **respuestas})
    cambian = [ROTULOS[k] for k in (*base.CAMPOS_OBRA, *EXTRA) if ficha[k] != previa.get(k, [] if k == "temas" else "")]
    version = int(sobre) if sobre is not None else int((actual or {}).get("version") or 0)
    faltan = [base.TITULOS_OBRA[k] for k in base.CAMPOS_OBRA if not ficha[k]]
    return {"calibre_id": int(calibre_id), "ficha": ficha, "version_base": version, "cambian": cambian, "nueva": actual is None,
            "leida": bool(leida), "faltan": faltan, "actual": actual, "origen_id": (actual or {}).get("origen_id") or ""}


def _registro(p: dict, respuesta: dict) -> dict:
    """La respuesta de Yachay (su vista de la lectura: `ficha`, `version`, `leida_en`) como registro de la base."""
    previa = p.get("actual") or {}
    leida_en = respuesta.get("leida_en") or ""
    return {"origen_id": p.get("origen_id") or "", "calibre_id": p["calibre_id"], "ficha": respuesta.get("ficha") or p["ficha"],
            "version": int(respuesta.get("version") or 0), "leida": bool(leida_en), "leida_en": base.iso(leida_en, local=False),
            "creada": previa.get("creada") or base.ahora(), "modificada": base.ahora()}


def llevar(p: dict, cliente=None, aplicar: bool = False, ruta: Path | None = None) -> dict:
    """Simula sin `aplicar` (devuelve el plan con `escrita: False`). Con `aplicar`, el PUT con `version_base`:
    - 409 `lectura_modificada` → {"codigo": "lectura_modificada", "version", "actual", "mensaje"}; nada se escribe.
    - aceptado → la base guarda lo que Yachay respondió; con `leida`, se pide darla por leída (422 → `leida_error` y
      `faltan`, sin deshacer lo guardado). {"escrita": True, "version", "aviso", "revision", "leida_en", …}."""
    salida = {**p, "escrita": False}
    if not aplicar:
        return salida
    if cliente is None:
        raise SinCanal("Yachay: sin canal (falta el cliente o el token en el llavero)")
    obra = {"calibre_id": p["calibre_id"], "ficha": p["ficha"], "version": p["version_base"]}
    try:
        r = cliente.guardar_ficha_obra(obra)
    except Exception as e:  # noqa: BLE001 — el cliente lanza Conflicto (409) o ErrorYachay; se distinguen por su estado
        if getattr(e, "estado", None) == 409:
            actual = getattr(e, "actual", None) or {}
            return {**salida, "codigo": getattr(e, "codigo", "") or "lectura_modificada", "mensaje": getattr(e, "mensaje", str(e)),
                    "version": getattr(e, "version", None) or actual.get("version"),
                    "actual": {"ficha": base.ficha_limpia(actual.get("ficha")), "version": actual.get("version"),
                               "leida_en": actual.get("leida_en") or ""}}
        raise
    r = r or {}
    salida.update(escrita=True, version=r.get("version"), aviso=r.get("aviso") or "", revision=r.get("revision") or {},
                  leida_en=r.get("leida_en") or "")
    if p.get("leida") and not r.get("leida_en"):
        try:
            r2 = cliente.dar_por_leida(p["calibre_id"]) or {}
            r = {**r, **{k: r2[k] for k in ("ficha", "version", "leida_en") if k in r2}}
            salida.update(version=r.get("version"), leida_en=r.get("leida_en") or "")
        except Exception as e:  # noqa: BLE001 — 422 ficha_incompleta: la ficha quedó guardada, solo no está leída
            detalle = getattr(e, "detalle", None)
            detalle = detalle if isinstance(detalle, dict) else {}
            faltan = [base.TITULOS_OBRA.get(k, k) for k in detalle.get("faltan") or []]
            salida.update(leida_error=getattr(e, "mensaje", str(e)), faltan=faltan or salida["faltan"])
    salida["base"] = base.guardar_ficha_obra(_registro(p, r), ORIGEN, aplicar=True, ruta=ruta).resumen()["fichas_obra"]
    return salida


def texto(r: dict) -> list[str]:
    """Lo que dice la CLI (y la consola de la ventana) de un plan o de su resultado."""
    lineas = []
    if r.get("codigo") == "lectura_modificada":
        lineas.append(f"✗ Tu ficha de obra cambió en Yachay (ahora va en la versión {r.get('version')}): no se envió nada.")
        actual = (r.get("actual") or {}).get("ficha") or {}
        for k in base.CAMPOS_OBRA:
            if actual.get(k) != r["ficha"].get(k):
                lineas.append(f"    {base.TITULOS_OBRA[k]}: en Yachay «{(actual.get(k) or '')[:70]}» · la tuya «{(r['ficha'].get(k) or '')[:70]}»")
        lineas.append(f"    Para llevar la tuya sobre esa versión: --sobre {r.get('version')} --aplicar. Para quedarte con la de "
                      "Yachay: main.py sincronizar --origen yachay --aplicar.")
        return lineas
    if r.get("escrita"):
        lineas.append(f"✓ Ficha de obra del libro {r['calibre_id']} llevada a Yachay (versión {r.get('version')}) y guardada en la base.")
        if r.get("aviso"):
            lineas.append(f"    ! {r['aviso']}")
        if r.get("leida_en"):
            lineas.append("    La obra quedó leída en Yachay.")
        if r.get("leida_error"):
            lineas.append(f"    ! No se dio por leída: {r['leida_error']}")
        return lineas
    sobre = "nueva en Yachay" if r["nueva"] and not r["version_base"] else f"sobre la versión {r['version_base']}"
    lineas.append(f"[simulación] La ficha de obra del libro {r['calibre_id']} iría a Yachay ({sobre}); cambian: "
                  f"{', '.join(r['cambian']) or 'nada'}.")
    if r["faltan"]:
        lineas.append(f"    Faltan: {', '.join(r['faltan'])} (Yachay la guarda, pero no la da por leída sin las seis).")
    if r["leida"]:
        lineas.append("    Después se pediría darla por leída.")
    lineas.append("--aplicar la envía por la API de Yachay con tu token (un 409 no pisa nada).")
    return lineas
