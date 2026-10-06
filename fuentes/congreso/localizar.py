# localizar.py — de la CITA de una norma a la URL de su PDF oficial.
#
# Portado de CIL/…/scripts_for_fuentes/manifiestos/marco_legal/localizar_normas.py (2026-09-06). La lógica de
# descubrimiento es la misma —probar los patrones del Congreso en orden y, si
# fallan, buscar en gob.pe validando que el título traiga el número exacto—,
# pero la comprobación de que la URL sirve un PDF de verdad no se reimplementa:
# se apoya en la maquinaria compartida (`lib.comun` → `core/py-common/red.py`).
#
# Es la PRIMERA fuente documental del sistema. Las siguientes —tesis, artículos,
# libros— traen su propio `localizar()` con el mismo contrato: recibe una
# referencia, devuelve {url, fuente} o un error explicando qué se intentó.

import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from lib.comun import red

# Cómo se escribe cada tipo en las citas reales, normalizado a la clave de PATRONES.
_TIPOS = {
    "ley": "ley",
    "decreto legislativo": "decreto legislativo", "d. leg.": "decreto legislativo",
    "dleg": "decreto legislativo", "decreto leg": "decreto legislativo",
    "decreto ley": "decreto ley", "d.l.": "decreto ley",
    "decreto de urgencia": "decreto de urgencia", "du": "decreto de urgencia",
}
_RE_CITA = re.compile(
    r"^\s*(?P<tipo>ley|decreto\s+legislativo|d\.?\s*leg\.?|decreto\s+ley|d\.?l\.?|"
    r"decreto\s+de\s+urgencia|du)\s*(?:n\.?[°º]?\s*)?(?P<num>[\d\-]+)", re.I)


def clave(texto):
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.lower()).strip()


def slug(texto):
    return re.sub(r"[^a-z0-9]+", "_", clave(texto)).strip("_")


def parsear_cita(texto):
    """«Ley N.° 31143» → ('ley', '31143'). Devuelve None si no reconoce la cita."""
    m = _RE_CITA.match(clave(texto))
    if not m:
        return None
    bruto = re.sub(r"\s+", " ", m.group("tipo")).strip().rstrip(".")
    tipo = _TIPOS.get(bruto) or _TIPOS.get(bruto.replace(" ", "")) 
    if tipo is None:
        for k, v in _TIPOS.items():
            if bruto.startswith(k.rstrip(".")):
                tipo = v
                break
    return (tipo, m.group("num").replace("-", "_")) if tipo else None


def sirve_pdf(url, cfg):
    """¿La URL devuelve un PDF de verdad?

    Un 200 no basta: los portales del Estado responden 200 con una página de
    error HTML. Se pide el primer trozo y se comprueban los bytes mágicos, que
    es el mismo criterio que `red.validar_magia` (core/py-common) aplica tras descargar.
    """
    try:
        datos = red.obtener(url, user_agent=cfg.USER_AGENT, timeout=cfg.TIMEOUT,
                            reintentos=0, pausa=cfg.PAUSA, rango=(0, 3))
        return datos[:4] == b"%PDF"
    except Exception:
        return False


def candidatos(tipo, numero, cfg):
    """URLs a probar, en orden de preferencia, con la fuente que representan."""
    for patron, fuente in cfg.PATRONES.get(tipo, []):
        if "{p}" in patron:
            for periodo in cfg.PERIODOS:
                yield cfg.BASE + patron.format(p=periodo, n=numero, n5=numero), fuente
        else:
            n5 = f"{int(numero):05d}" if numero.isdigit() else numero
            yield cfg.BASE + patron.format(n=numero, n5=n5), fuente


def buscar_en_gobpe(tipo, numero, cfg):
    """Último recurso: la búsqueda de gob.pe, que es ruidosa.

    Solo se acepta un resultado si su TÍTULO contiene el número exacto de la
    norma; sin ese filtro devuelve normas parecidas y se cita la que no es.
    """
    term = urllib.parse.quote(f"{tipo} {numero}")
    try:
        datos = red.obtener(cfg.GOBPE_BUSQUEDA.format(term=term),
                            user_agent=cfg.USER_AGENT, timeout=cfg.TIMEOUT,
                            reintentos=1, pausa=cfg.PAUSA)
        d = json.loads(datos.decode("utf-8", "replace"))
        for it in d["data"]["attributes"]["results"][:10]:
            titulo = re.sub("<[^>]+>", "", it.get("title", ""))
            m = re.search(r'href="([^"]+)"', it.get("url", ""))
            if not (m and re.search(rf"\b{re.escape(numero)}\b", titulo)):
                continue
            html = red.obtener("https://www.gob.pe" + m.group(1),
                               user_agent=cfg.USER_AGENT, timeout=cfg.TIMEOUT,
                               reintentos=1, pausa=cfg.PAUSA)
            pdf = re.search(cfg.GOBPE_CDN, html.decode("utf-8", "replace"))
            if pdf:
                return pdf.group(0), "cdn.www.gob.pe"
    except Exception:
        pass
    return None, None


def localizar(cita, cfg):
    """Devuelve {cita, tipo, numero, url, fuente, intentos} o None si no aparece."""
    par = parsear_cita(cita)
    if not par:
        return {"cita": cita, "error": "cita no reconocida (¿tipo de norma no soportado?)"}
    tipo, numero = par
    intentos = 0
    for url, fuente in candidatos(tipo, numero, cfg):
        intentos += 1
        if sirve_pdf(url, cfg):
            return {"cita": cita, "tipo": tipo, "numero": numero,
                    "url": url, "fuente": fuente, "intentos": intentos}
    url, fuente = buscar_en_gobpe(tipo, numero, cfg)
    if url:
        return {"cita": cita, "tipo": tipo, "numero": numero,
                "url": url, "fuente": fuente, "intentos": intentos + 1}
    return {"cita": cita, "tipo": tipo, "numero": numero,
            "error": f"no localizada tras {intentos} candidatos + gob.pe"}
