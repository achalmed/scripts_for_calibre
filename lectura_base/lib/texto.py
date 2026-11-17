"""lectura_base/lib/texto.py — lo que hace comparables dos subrayados que vienen de herramientas distintas (sin dependencias).

Un mismo pasaje llega distinto de cada lector: KOReader parte las líneas y deja el guion de corte, Zotero guarda el texto
de su capa, Okular no guarda texto (se recorta de la hoja), Yachay lo limpia contra el texto de la hoja. Aquí se reduce
todo a una forma normal (minúsculas, sin tildes ni signos, sin cortes de palabra) y se mide el parecido; la huella de una
anotación sale de esa forma normal, del libro y de la hoja.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

_CORTE = re.compile(r"(\w)[-­]\s*\n\s*(\w)")       # «comuni-\ndades» → «comunidades»
_NO_PALABRA = re.compile(r"[^0-9a-zñ]+")


def limpiar(texto: str) -> str:
    """El texto como se muestra: sin cortes de palabra al final de línea y con los espacios juntos."""
    t = _CORTE.sub(r"\1\2", str(texto or "")).replace("­", "")
    return re.sub(r"\s+", " ", t).strip()


def normal(texto: str) -> str:
    """La forma normal con que se compara: minúsculas, sin tildes (la ñ se queda), solo letras y números."""
    t = limpiar(texto).lower().replace("ñ", "\0")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).replace("\0", "ñ")
    return _NO_PALABRA.sub(" ", t).strip()


def parecido(a: str, b: str) -> float:
    """0 a 1: cuánto se parecen dos textos ya normalizados. Uno dentro del otro cuenta por la proporción de largo (un
    subrayado que tomó una palabra más sigue siendo el mismo)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    corto, largo = sorted((a, b), key=len)
    if corto in largo:
        return len(corto) / len(largo)
    sin_a, sin_b = a.replace(" ", ""), b.replace(" ", "")      # una capa de OCR sin espacios («preguntaquehabíamos»)
    if sin_a == sin_b:
        return 0.99
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def huella(libro: str, hoja: int | None, texto_normal: str, nota: str = "", rects: list | None = None) -> str:
    """La huella de una anotación: el libro, la hoja y el comienzo de su texto normal (si no tiene texto, como una nota
    suelta, su nota y su primer rectángulo redondeado)."""
    if texto_normal:
        cuerpo = texto_normal[:160]
    else:
        r = (rects or [[0, 0, 0, 0, 0]])[0]
        cuerpo = "nota:" + normal(nota)[:120] + ":" + ",".join(f"{float(v):.2f}" for v in r[1:3])
    return hashlib.sha1(f"{libro}|{hoja or ''}|{cuerpo}".encode("utf-8")).hexdigest()[:20]


def solape(r1: list, r2: list) -> float:
    """El solape (intersección sobre unión) de dos listas de rectángulos [[hoja, x, y, ancho, alto], …] en la misma hoja."""
    def area(r):
        return max(0.0, r[3]) * max(0.0, r[4])

    inter = 0.0
    for a in r1 or []:
        for b in r2 or []:
            if int(a[0]) != int(b[0]):
                continue
            w = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            h = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
            if w > 0 and h > 0:
                inter += w * h
    total = sum(area(r) for r in r1 or []) + sum(area(r) for r in r2 or []) - inter
    return inter / total if total > 0 else 0.0


COLORES = {"yellow": "#E9C46A", "red": "#E07A7A", "orange": "#F0A35E", "green": "#7FBF7F", "olive": "#A9B665",
           "cyan": "#6CC4D1", "blue": "#7EA6E0", "purple": "#B08AD8", "gray": "#A0A0A0", "grey": "#A0A0A0"}


# la paleta de Zotero, con el nombre de KOReader que le corresponde (para llevar un resaltado de Zotero a KOReader)
ZOTERO = {"yellow:z": "#FFD400", "red:z": "#FF6666", "green:z": "#5FB236", "blue:z": "#2EA8E5", "purple:z": "#A28AE5",
          "purple:zm": "#E56EEE", "orange:z": "#F19837", "gray:z": "#AAAAAA"}


def color(c: str) -> str:
    """#RRGGBB de un color de KOReader («yellow»), de Zotero («#ffd400») o de Okular («#ffff00»); vacío si no hay."""
    c = (c or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{8}", c):        # Okular guarda #AARRGGBB
        c = "#" + c[3:]
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", c):
        return c.upper()
    return COLORES.get(c.lower(), "")


def nombre_de_color(hex_: str) -> str:
    """El nombre de KOReader más cercano a un #RRGGBB (KOReader solo entiende sus nombres)."""
    hex_ = color(hex_)
    if not hex_:
        return "yellow"

    def rgb(h):
        return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

    r = rgb(hex_)
    candidatos = [(n, h) for n, h in COLORES.items() if n != "grey"] + list(ZOTERO.items())
    return min(candidatos, key=lambda nh: sum((a - b) ** 2 for a, b in zip(r, rgb(nh[1]))))[0].split(":")[0]
