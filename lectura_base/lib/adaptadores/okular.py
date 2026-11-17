"""lectura_base/lib/adaptadores/okular.py — Okular ⇄ base de lectura.

Okular guarda lo que se anota en un PDF sin guardarlo en el archivo en `~/.local/share/okular/docdata/<tamaño>.<nombre>.xml`
(`OKULAR_DOCDATA`): `<documentInfo url="…">`, y en `<pageList><page number="N">` (N desde 0) su `<annotationList>`.
Cada `<annotation type="…">` lleva un `<base>` (author, contents = la nota, color #AARRGGBB o #RRGGBB, uniqueName,
creationDate, modifyDate) con su `<boundary l t r b>` en fracciones de la hoja (origen arriba), y un resaltado (type 4)
sus `<quad>` en `<hl type=…>` (0 resaltar, 1 ondulado, 2 subrayar, 3 tachar). Una nota (type 1) es una nota suelta.
Okular no guarda el texto resaltado: se recorta del PDF con `pdftotext` en el rectángulo de cada quad.

Lee: los docdata cuyo `url` es un libro de la biblioteca (`(<id>)/` en la ruta), su última hoja (`<current viewport>`).
Escribe (solo si el autor lo aprueba, `ESCRIBE` en `exportar.py`; §9.7): suma resaltados al docdata de un libro con
Okular cerrado, con respaldo y escritura atómica; si el docdata no existe, lo crea con el nombre que Okular espera.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from lectura_base.lib import base
from lectura_base.lib.biblioteca import Resolutor, id_de_ruta, medidas

ORIGEN = "okular"
SUBTIPOS = {"0": "resaltado", "1": "subrayado", "2": "subrayado", "3": "tachado"}
_VIEWPORT = re.compile(r"^(\d+);")


def carpeta_docdata() -> Path:
    if os.environ.get("OKULAR_DOCDATA"):
        return Path(os.environ["OKULAR_DOCDATA"]).expanduser()
    datos = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return datos / "okular" / "docdata"


def recortar(pdf: Path, hoja: int, rect: list, hojas: list) -> str:
    """El texto del PDF dentro de un rectángulo [hoja, x, y, ancho, alto] en fracciones (pdftotext a 72 ppp = puntos)."""
    if not (0 < hoja <= len(hojas)):
        return ""
    w, h = hojas[hoja - 1]
    args = ["pdftotext", "-q", "-enc", "UTF-8", "-r", "72", "-f", str(hoja), "-l", str(hoja),
            "-x", str(int(rect[1] * w)), "-y", str(int(rect[2] * h)), "-W", str(max(1, int(rect[3] * w + 1))),
            "-H", str(max(1, int(rect[4] * h + 1))), str(pdf), "-"]
    try:
        r = subprocess.run(args, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.decode("utf-8", "replace").replace("\f", "").strip()


def _quads(nodo) -> list[list[float]]:
    salida = []
    for q in nodo.iter("quad"):
        xs = [float(q.get(k, 0)) for k in ("ax", "bx", "cx", "dx")]
        ys = [float(q.get(k, 0)) for k in ("ay", "by", "cy", "dy")]
        salida.append([min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)])
    return salida


def anotaciones_de(raiz: ET.Element, calibre_id, pdf: Path | None, hojas: list, recortar_texto: bool = True) -> list[dict]:
    salida = []
    for pagina in raiz.iter("page"):
        hoja = int(pagina.get("number", "0")) + 1
        for a in pagina.iter("annotation"):
            tipo = a.get("type", "")
            b = a.find("base")
            if b is None or tipo not in ("1", "4"):
                continue
            uid = b.get("uniqueName") or ""
            nota = (b.get("contents") or "").strip()
            rects = []
            if tipo == "4":
                hl = a.find("hl")
                cajas = _quads(hl) if hl is not None else []
                rects = [[hoja, *c] for c in cajas if c[2] > 0 and c[3] > 0]
                subtipo = SUBTIPOS.get(hl.get("type", "0") if hl is not None else "0", "resaltado")
            else:
                subtipo = "nota"
            if not rects:
                caja = b.find("boundary")
                if caja is not None:
                    l, t, r, bo = (float(caja.get(k, 0)) for k in ("l", "t", "r", "b"))
                    if r > l and bo > t:
                        rects = [[hoja, l, t, r - l, bo - t]]
            texto = ""
            if tipo == "4" and pdf is not None and recortar_texto:
                texto = " ".join(t for t in (recortar(pdf, hoja, r, hojas) for r in rects) if t)
            if not texto and not nota:
                continue
            salida.append({"origen_id": uid or f"{calibre_id}:{hoja}:{len(salida)}", "calibre_id": calibre_id, "hoja": hoja,
                           "texto": texto, "rects": rects, "color": b.get("color") or "", "tipo": subtipo, "nota": nota,
                           "creada": base.iso(b.get("creationDate")), "modificada": base.iso(b.get("modifyDate") or b.get("creationDate"))})
    return salida


def leer(resolutor: Resolutor | None = None, carpeta: Path | None = None, recortar_texto: bool = True) -> base.Lectura:
    resolutor = resolutor or Resolutor()
    lectura = base.Lectura(ORIGEN)
    carpeta = Path(carpeta or carpeta_docdata())
    if not carpeta.is_dir():
        lectura.avisos.append("Okular: no está su carpeta docdata")
        lectura.alcance = None
        return lectura
    for xml in sorted(carpeta.glob("*.xml")):
        try:
            cabeza = xml.read_bytes()[:2048].decode("utf-8", "replace")
        except OSError:
            continue
        m = re.search(r'<documentInfo url="([^"]*)"', cabeza)
        if not m:
            continue
        url = m.group(1).replace("&amp;", "&").replace("&quot;", '"').replace("&apos;", "'")
        calibre_id = id_de_ruta(url)
        if calibre_id is None or not url.lower().endswith(".pdf"):
            continue
        try:
            raiz = ET.parse(xml).getroot()
        except ET.ParseError as e:
            lectura.avisos.append(f"Okular: {xml.name} no se pudo leer ({e})")
            continue
        pdf = Path(url) if Path(url).is_file() else resolutor.pdf(calibre_id)
        hojas = medidas(pdf) if pdf else []
        lectura.anotaciones += anotaciones_de(raiz, calibre_id, pdf, hojas, recortar_texto)
        lectura.alcance.add(base.clave_libro(calibre_id))
        actual = raiz.find("./generalInfo/history/current")
        vista = _VIEWPORT.match(actual.get("viewport", "")) if actual is not None else None
        if vista:
            lectura.progreso.append({"calibre_id": calibre_id, "hoja": int(vista.group(1)) + 1, "hojas": len(hojas) or None,
                                     "fraccion": (int(vista.group(1)) + 1) / len(hojas) if hojas else None,
                                     "ultima": base.iso(xml.stat().st_mtime)})
        lectura.libros.setdefault(calibre_id, resolutor.ficha(calibre_id))
    return lectura


# ------------------------------------------------------------------------------------------------------------- escribir
def abierto() -> bool:
    r = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
    return any(l.strip() == "okular" for l in r.splitlines())


def nombre_docdata(pdf: Path) -> str:
    """El nombre con que Okular busca el docdata de un archivo: «<tamaño en bytes>.<nombre del archivo>.xml»."""
    return f"{pdf.stat().st_size}.{pdf.name}.xml"


def _color_okular(hex_: str) -> str:
    return (hex_ or "#ffff00").lower()


def elemento(a: dict) -> ET.Element | None:
    rects = [r for r in a.get("rects") or [] if int(r[0]) == a.get("hoja")]
    if not a.get("hoja") or not rects:
        return None
    ahora = datetime.now().replace(microsecond=0).isoformat()
    nodo = ET.Element("annotation", type="4", _hoja=str(int(a["hoja"]) - 1))
    l = min(r[1] for r in rects); t = min(r[2] for r in rects)
    r_ = max(r[1] + r[3] for r in rects); b_ = max(r[2] + r[4] for r in rects)
    b = ET.SubElement(nodo, "base", creationDate=ahora, modifyDate=ahora, uniqueName=f"okular-{a['uid']}",
                      author="Biblioteca Studio", color=_color_okular(a.get("color")), contents=a.get("nota") or "", flags="0")
    ET.SubElement(b, "boundary", l=f"{l:.6f}", t=f"{t:.6f}", r=f"{r_:.6f}", b=f"{b_:.6f}")
    hl = ET.SubElement(nodo, "hl", type={"subrayado": "2", "tachado": "3"}.get(a.get("tipo"), "0"))
    for r in rects:
        x0, y0, x1, y1 = r[1], r[2], r[1] + r[3], r[2] + r[4]
        ET.SubElement(hl, "quad", ax=f"{x0:.6f}", ay=f"{y0:.6f}", bx=f"{x1:.6f}", by=f"{y0:.6f}", cx=f"{x1:.6f}", cy=f"{y1:.6f}",
                      dx=f"{x0:.6f}", dy=f"{y1:.6f}", feather="1")
    return nodo


def anadir(pdf: Path, nuevas: list[ET.Element], carpeta: Path, respaldos: Path) -> list[str]:
    """Suma los resaltados al docdata del PDF (lo crea si no existe) con Okular cerrado; devuelve sus `uniqueName`."""
    if abierto():
        raise RuntimeError("Okular está abierto: ciérralo antes de escribir en sus anotaciones")
    xml = carpeta / nombre_docdata(pdf)
    if xml.is_file():
        respaldos.mkdir(parents=True, exist_ok=True)
        copia = respaldos / f"{xml.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(xml, copia)
        if copia.read_bytes() != xml.read_bytes():
            raise RuntimeError(f"el respaldo de {xml.name} no coincide con el original")
        arbol = ET.parse(xml)
        raiz = arbol.getroot()
    else:
        raiz = ET.Element("documentInfo", url=str(pdf))
        arbol = ET.ElementTree(raiz)
    lista_paginas = raiz.find("pageList")
    if lista_paginas is None:
        lista_paginas = ET.Element("pageList")
        raiz.insert(0, lista_paginas)
    ids = []
    for nodo in nuevas:
        numero = nodo.attrib.pop("_hoja")          # el número de página de Okular (desde 0)
        pagina = next((p for p in lista_paginas.findall("page") if p.get("number") == numero), None)
        if pagina is None:
            pagina = ET.SubElement(lista_paginas, "page", number=numero)
        lista = pagina.find("annotationList")
        if lista is None:
            lista = ET.SubElement(pagina, "annotationList")
        lista.append(nodo)
        ids.append(nodo.find("base").get("uniqueName"))
    ET.indent(arbol, space=" ")
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = xml.with_suffix(".xml.tmp")
    with open(tmp, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE documentInfo>\n')
        arbol.write(f, encoding="utf-8", xml_declaration=False)
    ET.parse(tmp)                              # se vuelve a leer antes de reemplazar
    os.replace(tmp, xml)
    return ids
