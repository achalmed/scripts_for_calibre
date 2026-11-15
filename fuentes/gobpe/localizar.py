# localizar.py — de la CITA de una norma a su ficha y su PDF en gob.pe (contrato de las fuentes: {url, fuente} o
# {error}; esta además devuelve sumilla, fecha y emisor, que `main.py traer` usa para catalogar).
#
# Solo lectura: una consulta al buscador por cita (con pausa); no descarga el PDF (eso es `descargar`).
import html
import json
import re
import sys
import unicodedata
import urllib.parse

from lib.comun import red
import config as _config_raiz

sys.path.insert(0, str(_config_raiz.PY_COMMON))
import biblioteca as bib  # noqa: E402  norma_id: la grafía de la ingesta

ROTULO = {"ley": "Ley", "decreto_legislativo": "Decreto Legislativo", "decreto_supremo": "Decreto Supremo",
          "decreto_de_urgencia": "Decreto de Urgencia", "decreto_ley": "Decreto Ley",
          "resolucion_ministerial": "Resolución Ministerial", "resolucion_suprema": "Resolución Suprema",
          "resolucion_legislativa": "Resolución Legislativa"}
# Quién da la norma cuando la página es de otra institución (una ley la da el Congreso aunque la suba el MEF).
EMISOR_POR_TIPO = {"ley": "Congreso de la República", "decreto_ley": "Congreso de la República",
                   "resolucion_legislativa": "Congreso de la República"}
MESES = {m: i for i, m in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "setiembre", "octubre", "noviembre", "diciembre"), 1)}
MESES["septiembre"] = 9


def _plano(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def fecha_iso(texto):
    """« 7 de enero de 2002» → «2002-01-07»; lo que no se entiende, vacío."""
    m = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", _plano(texto))
    if not m or m.group(2) not in MESES:
        return ""
    return f"{m.group(3)}-{MESES[m.group(2)]:02d}-{int(m.group(1)):02d}"


def sumilla_en_frase(s):
    """La sumilla tal como la da gob.pe, sin el punto final; si viene EN MAYÚSCULAS, en frase."""
    s = re.sub(r"\bN\s*[º°o]\.?\s*(?=\d)", "N.° ", _texto(s)).rstrip(". ")   # «Ley Nº 27506» → «Ley N.° 27506», la grafía de la biblioteca
    if s and s.upper() == s:
        s = s[:1] + s[1:].lower()
    return s[:1].upper() + s[1:]


def partir(cita):
    """«D.S. 005-2002-EF» → ('decreto_supremo', '005-2002-ef'); None si no es una norma."""
    t = _plano(cita)
    for abrev, largo in ((r"\bd\.\s*s\.", "decreto supremo "), (r"\bd\.\s*leg\.", "decreto legislativo "),
                         (r"\bd\.\s*u\.", "decreto de urgencia "), (r"\bd\.\s*l\.", "decreto ley "),
                         (r"\br\.\s*m\.", "resolucion ministerial "), (r"\br\.\s*s\.", "resolucion suprema "),
                         (r"^\s*ds\b", "decreto supremo "), (r"^\s*du\b", "decreto de urgencia ")):
        t = re.sub(abrev, largo, t)
    n = bib.norma_id(t)
    if not n:
        return None
    tipo, num = n.rsplit("_", 1)
    return tipo, num


def elegir(resultados, tipo, num):
    """El resultado cuyo número es exactamente el pedido y cuyo rótulo es el tipo pedido; si hay varios, el de la
    institución que da la sigla del número (EF → MEF)."""
    rot = _plano(ROTULO.get(tipo, tipo.replace("_", " ")))
    sufijo = num.rsplit("-", 1)[-1] if "-" in num and not num.rsplit("-", 1)[-1].isdigit() else ""
    buenos = []
    for it in resultados:
        nombre = _plano(it.get("name_with_parent"))
        enlace = _texto(it.get("url"))
        if nombre != _plano(num) or not _plano(enlace).startswith(rot):
            continue
        if not it.get("action_url", "").lower().endswith(".pdf"):
            continue
        buenos.append(it)
    if sufijo:   # la sigla de la institución contiene la del número: «EF» en «MEF», «PCM» en «PCM»
        buenos.sort(key=lambda it: _plano(sufijo) not in _plano(_texto(it.get("content_sub_title_card")).split(" - ")[0]))
    return buenos[0] if buenos else None


def localizar(cita, cfg):
    par = partir(cita)
    if not par:
        return {"cita": cita, "error": "cita no reconocida: escriba el tipo y el número (Ley 28077, D.S. 005-2002-EF)"}
    tipo, num = par
    rotulo = ROTULO.get(tipo, tipo.replace("_", " ").capitalize())
    numero = num.upper() if "-" in num else num
    term = urllib.parse.quote(f"{rotulo} {numero}")
    try:
        datos = red.obtener(cfg.BUSQUEDA.format(term=term), user_agent=cfg.USER_AGENT, timeout=cfg.TIMEOUT,
                            reintentos=1, pausa=cfg.PAUSA)
        resultados = json.loads(datos.decode("utf-8", "replace"))["data"]["attributes"]["results"]
    except Exception as exc:
        return {"cita": cita, "tipo": tipo, "numero": numero, "error": f"gob.pe no respondió ({type(exc).__name__})"}
    it = elegir(resultados, tipo, num)
    if not it:
        return {"cita": cita, "tipo": tipo, "numero": numero, "error": f"gob.pe no tiene «{rotulo} N.° {numero}»"}
    institucion = _texto(it.get("content_sub_title_card"))
    sumilla = sumilla_en_frase(it.get("content"))
    pagina = re.search(r'href="([^"]+)"', it.get("url", ""))
    return {"cita": cita, "tipo": tipo, "numero": numero, "norma": f"{tipo}_{num}", "url": it["action_url"],
            "fuente": "gob.pe", "rotulo": f"{rotulo} N.° {numero}",
            "titulo": f"{rotulo} N.° {numero}. {sumilla}" if sumilla else f"{rotulo} N.° {numero}",
            "sumilla": sumilla, "fecha": fecha_iso(it.get("publication")),
            "emisor": EMISOR_POR_TIPO.get(tipo) or institucion.split(" - ", 1)[-1],
            "pagina": cfg.BASE + pagina.group(1) if pagina else ""}
