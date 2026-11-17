"""lectura_base/lib/adaptadores/koreader.py — KOReader ⇄ base de lectura.

Lee (siempre en solo lectura):
- los `metadata.<ext>.lua` de `hashdocsettings/` y `docsettings/` de la carpeta de KOReader (la viva; su respaldo
  `KOREADER_RESPALDO_DIR` solo si la viva no está): los resaltados (`annotations` con `drawer`; sin él son marcadores de
  página y no se traen), el progreso (`percent_finished`, `summary.status`, `last_page`);
- `statistics.sqlite3` (`mode=ro`): cada página con su hora y su duración → sesiones (una pausa de más de
  `PAUSA` segundos abre otra) y el tiempo total del libro.

El libro se reconoce por la carpeta `(<id>)/` de su `doc_path` o por el MD5 parcial (el nombre del `.sdr` central o
`partial_md5_checksum`, contra `#ko_md5` de Calibre). En un PDF la hoja es `page` y los rectángulos salen de `pboxes`
(puntos) entre las medidas de la hoja; en un EPUB `page` es un xpointer: no hay hoja del PDF, se queda el capítulo.

Escribe (solo si el autor lo aprueba, `ESCRIBE` en `exportar.py`; §9.7): suma a un sidecar de un PDF, con KOReader
cerrado, los resaltados de otros orígenes que tengan hoja y rectángulos, con respaldo del archivo y escritura atómica.
El archivo se reescribe con `lua.escribir`, que deja idéntico byte a byte lo que lee (probado sobre los sidecars reales).
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from lectura_base.lib import base, lua
from lectura_base.lib import texto as tx
from lectura_base.lib.biblioteca import Resolutor, medidas

ORIGEN = "koreader"
PAUSA = 600
DRAWERS = {"lighten": "resaltado", "underscore": "subrayado", "strikeout": "tachado", "invert": "resaltado"}
_SIDECAR = re.compile(r"^metadata\.(\w+)\.lua$")


def carpeta_koreader() -> Path | None:
    """La carpeta viva de KOReader: `KOREADER_DIR`, o la de `KOREADER_STATS` (…/settings/statistics.sqlite3), o
    `~/.config/koreader`; si no existe, el respaldo en texto (`KOREADER_RESPALDO_DIR`)."""
    candidatos = []
    if os.environ.get("KOREADER_DIR"):
        candidatos.append(Path(os.environ["KOREADER_DIR"]).expanduser())
    if os.environ.get("KOREADER_STATS"):
        candidatos.append(Path(os.environ["KOREADER_STATS"]).expanduser().parent.parent)
    candidatos.append(Path.home() / ".config" / "koreader")
    if os.environ.get("KOREADER_RESPALDO_DIR"):
        candidatos.append(Path(os.environ["KOREADER_RESPALDO_DIR"]).expanduser())
    for c in candidatos:
        if c.is_dir():
            return c
    return None


def ruta_estadisticas(carpeta: Path | None) -> Path | None:
    if os.environ.get("KOREADER_STATS"):
        p = Path(os.environ["KOREADER_STATS"]).expanduser()
        return p if p.is_file() else None
    if carpeta is None:
        return None
    p = carpeta / "settings" / "statistics.sqlite3"
    return p if p.is_file() else None


def sidecars(carpeta: Path) -> list[Path]:
    return sorted(p for p in carpeta.glob("*docsettings/*/*.sdr/metadata.*.lua") if _SIDECAR.match(p.name))


def _md5_del_sidecar(p: Path, datos: dict) -> str:
    md5 = str(datos.get("partial_md5_checksum") or "")
    if not md5 and re.fullmatch(r"[0-9a-f]{32}\.sdr", p.parent.name):
        md5 = p.parent.name[:-4]
    return md5


def _rects(a: dict, hoja: int | None, hojas: list) -> list:
    if not hoja or not (0 < hoja <= len(hojas)):
        return []
    w, h = hojas[hoja - 1]
    cajas = a.get("pboxes") or {}
    salida = []
    for b in (cajas.values() if isinstance(cajas, dict) else cajas):
        if isinstance(b, dict) and w and h:
            salida.append([hoja, float(b.get("x", 0)) / w, float(b.get("y", 0)) / h, float(b.get("w", 0)) / w, float(b.get("h", 0)) / h])
    return [r for r in salida if 0 <= r[1] <= 1 and 0 <= r[2] <= 1 and r[3] > 0 and r[4] > 0]


def anotaciones_de(datos: dict, md5: str, calibre_id, es_pdf: bool, hojas: list) -> list[dict]:
    lista = datos.get("annotations") or datos.get("highlight") or {}
    entradas = lista.values() if isinstance(lista, dict) else lista
    salida, usados = [], {}
    for a in entradas:
        if not isinstance(a, dict) or not a.get("drawer"):
            continue
        texto, nota = str(a.get("text") or ""), str(a.get("note") or "")
        if not texto.strip() and not nota.strip():
            continue
        cuando = str(a.get("datetime") or "")
        clave = f"{md5}:{cuando}"
        usados[clave] = usados.get(clave, 0) + 1
        if usados[clave] > 1:
            clave += f":{usados[clave]}"
        hoja = a.get("page") if es_pdf and isinstance(a.get("page"), int) else None
        salida.append({"origen_id": clave, "calibre_id": calibre_id, "md5": md5, "hoja": hoja,
                       "pagina": str(a.get("pageref") or ""), "capitulo": str(a.get("chapter") or ""),
                       "texto": texto, "rects": _rects(a, hoja, hojas), "color": a.get("color") or "",
                       "tipo": DRAWERS.get(str(a.get("drawer")), "resaltado"), "nota": nota,
                       "creada": base.iso(cuando), "modificada": base.iso(a.get("datetime_updated") or cuando)})
    return salida


def _fraccion(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:                       # nan
        return None
    return f / 100.0 if f > 1.0 else f


def sesiones_de(ruta_stats: Path) -> tuple[list[dict], dict[str, dict]]:
    """(sesiones, {md5: {segundos, paginas, titulo, primera, ultima}}) de statistics.sqlite3, en solo lectura."""
    c = sqlite3.connect(ruta_stats.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        libros = {i: (md5, titulo, t or 0, p or 0) for i, md5, titulo, t, p in
                  c.execute("SELECT id, md5, title, total_read_time, pages FROM book")}
        filas = c.execute("SELECT id_book, page, start_time, duration FROM page_stat_data ORDER BY id_book, start_time").fetchall()
    finally:
        c.close()
    sesiones, actual = [], None
    for id_book, pagina, inicio, dur in filas:
        if id_book not in libros or not inicio:
            continue
        md5 = libros[id_book][0] or ""
        if actual is None or actual["_libro"] != id_book or inicio - actual["fin"] > PAUSA:
            if actual is not None:
                sesiones.append(actual)
            actual = {"_libro": id_book, "origen_id": f"{md5}:{inicio}", "md5": md5, "inicio": inicio, "fin": inicio,
                      "segundos": 0, "_paginas": set(), "desde": pagina, "hasta": pagina}
        actual["fin"] = max(actual["fin"], inicio + (dur or 0))
        actual["segundos"] += dur or 0
        actual["_paginas"].add(pagina)
        actual["desde"], actual["hasta"] = min(actual["desde"], pagina), max(actual["hasta"], pagina)
    if actual is not None:
        sesiones.append(actual)
    for s in sesiones:
        s["paginas"] = len(s.pop("_paginas"))
        s.pop("_libro")
    totales = {}
    for i, (md5, titulo, t, p) in libros.items():
        propias = [s for s in sesiones if s["md5"] == md5]
        totales[md5] = {"segundos": int(t), "paginas": int(p), "titulo": titulo or "",
                        "primera": base.iso(min((s["inicio"] for s in propias), default=None)),
                        "ultima": base.iso(max((s["fin"] for s in propias), default=None))}
    return sesiones, totales


def leer(resolutor: Resolutor | None = None, carpeta: Path | None = None, ruta_stats: Path | None = None) -> base.Lectura:
    resolutor = resolutor or Resolutor()
    lectura = base.Lectura(ORIGEN)
    carpeta = carpeta or carpeta_koreader()
    if carpeta is None:
        lectura.avisos.append("KOReader: no está su carpeta (KOREADER_DIR, ~/.config/koreader)")
        lectura.alcance = None
        return lectura
    md5_a_id: dict[str, int] = {}
    progreso: dict[str, dict] = {}
    for p in sidecars(carpeta):
        try:
            datos = lua.leer(p.read_bytes())
        except (OSError, ValueError, IndexError) as e:
            lectura.avisos.append(f"KOReader: no se pudo leer {p.parent.name}/{p.name} ({e})")
            continue
        if not isinstance(datos, dict):
            continue
        md5 = _md5_del_sidecar(p, datos)
        doc = str(datos.get("doc_path") or "")
        calibre_id = resolutor.id_de(doc, md5)
        if calibre_id is not None and md5:
            md5_a_id[md5] = calibre_id
        es_pdf = _SIDECAR.match(p.name).group(1).lower() == "pdf"
        hojas = []
        if es_pdf:
            hojas = medidas(doc) if doc and Path(doc).is_file() else medidas(resolutor.pdf(calibre_id) or "")
        lectura.anotaciones += anotaciones_de(datos, md5, calibre_id, es_pdf, hojas)
        lectura.alcance.add(base.clave_libro(calibre_id, md5))
        resumen = datos.get("summary") if isinstance(datos.get("summary"), dict) else {}
        estadisticas = datos.get("stats") if isinstance(datos.get("stats"), dict) else {}
        fraccion = _fraccion(datos.get("percent_finished"))
        hojas_total = datos.get("doc_pages") or estadisticas.get("pages")
        hoja = datos.get("last_page") if isinstance(datos.get("last_page"), int) else None
        if fraccion is not None or resumen.get("status"):
            progreso[base.clave_libro(calibre_id, md5)] = {
                "calibre_id": calibre_id, "md5": md5, "hoja": hoja,
                "hojas": int(hojas_total) if isinstance(hojas_total, (int, float)) and hojas_total == hojas_total else None,
                "fraccion": fraccion, "estado": str(resumen.get("status") or "").lower(),
                "ultima": base.iso(resumen.get("modified")) if resumen.get("modified") else ""}
        if calibre_id is not None:
            lectura.libros[calibre_id] = {**resolutor.ficha(calibre_id), "md5": md5 or resolutor.ficha(calibre_id).get("md5", "")}
    ruta_stats = ruta_stats or ruta_estadisticas(carpeta)
    if ruta_stats is not None:
        try:
            sesiones, totales = sesiones_de(ruta_stats)
        except sqlite3.DatabaseError as e:
            sesiones, totales = [], {}
            lectura.avisos.append(f"KOReader: no se pudo leer statistics.sqlite3 ({e})")
        for s in sesiones:
            s["calibre_id"] = md5_a_id.get(s["md5"]) or resolutor.id_de(md5=s["md5"])
        lectura.sesiones = sesiones
        for md5, t in totales.items():
            calibre_id = md5_a_id.get(md5) or resolutor.id_de(md5=md5)
            clave = base.clave_libro(calibre_id, md5)
            g = progreso.setdefault(clave, {"calibre_id": calibre_id, "md5": md5})
            g.update(segundos=t["segundos"], primera=t["primera"], ultima=max(g.get("ultima") or "", t["ultima"] or ""))
            if not g.get("hojas") and t["paginas"]:
                g["hojas"] = t["paginas"]
    lectura.progreso = list(progreso.values())
    return lectura


# ------------------------------------------------------------------------------------------------------------- escribir
def abierto() -> bool:
    """¿Corre KOReader? (el lanzador de escritorio es `luajit` con `reader.lua`, o el binario `koreader`)."""
    r = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    return any(re.search(r"(^|/)koreader(\s|$)|reader\.lua", linea) for linea in r.splitlines())


def sidecar_de(carpeta: Path, md5: str) -> Path | None:
    p = carpeta / "hashdocsettings" / md5[:2] / f"{md5}.sdr" / "metadata.pdf.lua"
    return p if md5 and p.is_file() else None


def entrada(a: dict, hojas: list) -> dict | None:
    """Un resaltado de la base como lo guarda KOReader en un PDF (None si no tiene hoja o rectángulos)."""
    rects = a.get("rects") or []
    hoja = a.get("hoja")
    if not hoja or not rects or not (0 < hoja <= len(hojas)):
        return None
    w, h = hojas[hoja - 1]
    cajas = {i: {"x": r[1] * w, "y": r[2] * h, "w": r[3] * w, "h": r[4] * h} for i, r in enumerate(rects, 1) if int(r[0]) == hoja}
    if not cajas:
        return None
    primera, ultima = cajas[min(cajas)], cajas[max(cajas)]
    cuando = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e = {"chapter": a.get("capitulo") or "", "color": tx.nombre_de_color(a.get("color") or ""), "datetime": cuando,
         "drawer": {"subrayado": "underscore", "tachado": "strikeout"}.get(a.get("tipo"), "lighten"), "page": hoja,
         "pageno": hoja, "pboxes": cajas, "text": a.get("texto") or "",
         "pos0": {"page": hoja, "rotation": 0, "x": primera["x"], "y": primera["y"] + primera["h"] / 2, "zoom": 1},
         "pos1": {"page": hoja, "rotation": 0, "x": ultima["x"] + ultima["w"], "y": ultima["y"] + ultima["h"] / 2, "zoom": 1}}
    if a.get("nota"):
        e["note"] = a["nota"]
    return e


def anadir(sidecar: Path, nuevas: list[dict], respaldos: Path) -> list[str]:
    """Suma las entradas al sidecar (respaldo, escritura atómica) y devuelve sus `origen_id`. KOReader tiene que estar
    cerrado: al cerrar un libro reescribe su sidecar con lo que tiene en memoria."""
    if abierto():
        raise RuntimeError("KOReader está abierto: ciérralo antes de escribir en sus anotaciones")
    original = sidecar.read_bytes()
    datos = lua.leer(original)
    lista = datos.get("annotations")
    if not isinstance(lista, (dict, list)):
        lista = {}
    entradas = list(lista.values()) if isinstance(lista, dict) else list(lista)
    md5 = _md5_del_sidecar(sidecar, datos)
    ids = []
    ocupadas = {str(e.get("datetime")) for e in entradas if isinstance(e, dict)}
    momento = datetime.now().replace(microsecond=0)
    for e in nuevas:
        e = dict(e)
        while momento.strftime("%Y-%m-%d %H:%M:%S") in ocupadas:     # la fecha es el nombre del resaltado en KOReader
            momento += timedelta(seconds=1)
        e["datetime"] = momento.strftime("%Y-%m-%d %H:%M:%S")
        ocupadas.add(e["datetime"])
        entradas.append(e)
        ids.append(f"{md5}:{e['datetime']}")
    entradas.sort(key=lambda e: (e.get("page") if isinstance(e.get("page"), int) else 0,
                                 (e.get("pos0") or {}).get("y", 0), (e.get("pos0") or {}).get("x", 0)))
    datos["annotations"] = {i: e for i, e in enumerate(entradas, 1)}
    if isinstance(datos.get("stats"), dict) and "highlights" in datos["stats"]:
        datos["stats"]["highlights"] = sum(1 for e in entradas if e.get("drawer"))
        datos["stats"]["notes"] = sum(1 for e in entradas if e.get("note"))
    primera = original.split(b"\n", 1)[0][3:].decode("utf-8", "replace")
    nuevo = lua.escribir(datos, primera)
    respaldos.mkdir(parents=True, exist_ok=True)
    copia = respaldos / f"{md5}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.lua"
    shutil.copy2(sidecar, copia)
    if copia.read_bytes() != original:
        raise RuntimeError(f"el respaldo de {sidecar.name} no coincide con el original")
    tmp = sidecar.with_suffix(".lua.tmp")
    tmp.write_bytes(nuevo)
    lua.leer(tmp.read_bytes())                 # lo que se escribió se vuelve a leer antes de reemplazar
    os.replace(tmp, sidecar)
    return ids
