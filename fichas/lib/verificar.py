"""verificar.py — cotejo mecánico de una ficha contra el texto del libro en Calibre (METODO_DOCUMENTAL.md §4).

verificada_script = la cadena literal existe en la página declarada (más el desfase indicado), carácter por carácter
tras normalizar solo espacios, guiones de corte de línea, comillas tipográficas y elipsis. Hallada en otra página o
no hallada = observada, con el detalle. Una paráfrasis coteja su «Origen literal»; una síntesis solo comprueba que
todas sus fichas de entrada estén verificadas.
"""
import re
import sys
import unicodedata
from pathlib import Path

from lib import ficha as F

config = F.config
sys.path.insert(0, str(config.PY_COMMON))
import biblioteca as bib  # noqa: E402

_TRANS = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "­": "", " ": " ",
                        "–": "-", "—": "-", "‐": "-"})


def normalizar(s):
    s = unicodedata.normalize("NFKC", s or "").translate(_TRANS)
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)          # pala-\nbra → palabra
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([,.;:)\]!?])", r"\1", s)               # «palabra ,» → «palabra,» (pdftotext -layout)
    return s.strip()


def fragmentos(cita):
    """Divide la cita por sus marcas de elipsis; cada fragmento debe aparecer en orden."""
    s = cita
    for m in config.MARCAS_ELIPSIS:
        s = s.replace(m, "\x00")
    fr = [normalizar(f) for f in s.split("\x00")]
    fr = [f.strip(" .,;:") for f in fr if f.strip(" .,;:")]
    return [f for f in fr if len(f) >= config.MIN_FRAGMENTO] or fr


def en_pagina(frs, pagina):
    p = normalizar(pagina); pos = 0
    for f in frs:
        i = p.find(f, pos)
        if i < 0:
            return False
        pos = i + len(f)
    return True


def _pagina_num(v):
    if v is None:
        return None
    m = re.match(r"^\s*p?0*(\d+)", str(v))
    return int(m.group(1)) if m else None


def cotejar(meta, cuerpo, desfase=None, tol=None):
    """dict(estado, metodo, detalle, pagina_pdf). No escribe nada."""
    tipo = meta.get("tipo")
    tol = config.TOLERANCIA_PAGINAS if tol is None else tol
    desfase = config.DESFASE_DEFECTO if desfase is None else desfase
    if tipo == "ficha_sintesis":
        return _cotejar_sintesis(meta, cuerpo)
    if tipo not in config.SECCION_LITERAL:
        return {"estado": None, "metodo": "", "detalle": f"el tipo {tipo} no se coteja contra el PDF", "pagina_pdf": None}
    cita = F.literal(cuerpo, tipo)
    if not cita or cita.startswith("(") and cita.endswith(")"):
        # sin cadena literal (una paráfrasis sin «Origen literal» registrado) no hay nada que cotejar: sigue pendiente
        return {"estado": "pendiente", "metodo": "", "detalle": f"sin texto literal en «{config.SECCION_LITERAL[tipo]}»: no se puede cotejar", "pagina_pdf": None}
    cid = meta.get("calibre_id")
    if cid in (None, ""):
        # sin libro en Calibre no hay cotejo posible: la ficha no se toca (conserva lo que el autor haya verificado a mano)
        return {"estado": None, "metodo": "", "detalle": "calibre_id vacío: sin PDF contra el que cotejar (pasos 00–03 pendientes)", "pagina_pdf": None}
    pags = bib.texto(cid)
    if not pags:
        return {"estado": "observada", "metodo": config.METODO_SCRIPT, "detalle": f"el ítem {cid} no tiene texto extraíble (¿escaneado sin OCR?)", "pagina_pdf": None}
    r = _cotejar_en(meta, cita, pags, desfase, tol)
    if r["estado"] == "observada" and "no hallada" in r["detalle"]:
        # segunda pasada en orden de lectura: en documentos a dos columnas -layout entrelaza las columnas y rompe la cadena
        r2 = _cotejar_en(meta, cita, bib.texto(cid, layout=False), desfase, tol)
        if r2["estado"] == "verificada_script":
            r2["detalle"] += " (orden de lectura, documento a columnas)"; return r2
    return r


def _cotejar_en(meta, cita, pags, desfase, tol):
    decl_txt = meta.get("pagina")
    frs = fragmentos(cita)
    decl = _pagina_num(decl_txt)
    if decl is None:
        # localizador de sección (`s1-1`: artículo 1.1 de una ley; `s0`: cita del resumen): no hay página que confirmar, pero la
        # cadena literal sí debe existir en el documento
        for i, p in enumerate(pags, 1):
            if en_pagina(frs, p):
                return {"estado": "verificada_script", "metodo": config.METODO_SCRIPT, "detalle": f"localizador {decl_txt}; hallada en la página {i} del PDF", "pagina_pdf": i}
        malos = [f for f in frs if not any(normalizar(p).find(f) >= 0 for p in pags)]
        return {"estado": "observada", "metodo": config.METODO_SCRIPT, "detalle": f"localizador {decl_txt}: no hallada en el documento; sin coincidencia: " + " | ".join(f"«{m[:60]}»" for m in malos[:3]), "pagina_pdf": None}
    obj = decl + desfase
    if 1 <= obj <= len(pags) and en_pagina(frs, pags[obj - 1]):
        return {"estado": "verificada_script", "metodo": config.METODO_SCRIPT,
                "detalle": f"p. {decl}" + (f" (PDF {obj}, desfase {desfase:+d})" if desfase else ""), "pagina_pdf": obj}
    for d in range(1, tol + 1):
        for cand in (obj - d, obj + d):
            if 1 <= cand <= len(pags) and en_pagina(frs, pags[cand - 1]):
                return {"estado": "observada", "metodo": config.METODO_SCRIPT,
                        "detalle": f"hallada en la página {cand} del PDF, no en la declarada {decl}{f' (+{desfase})' if desfase else ''}: corrige `pagina` o usa --desfase", "pagina_pdf": cand}
    for i, p in enumerate(pags, 1):
        if en_pagina(frs, p):
            # los artículos paginan de forma impresa (167–177): si la página del PDF donde está la cita lleva impreso el
            # número declarado (cabecera o pie), la página declarada es correcta y el desfase es solo del PDF
            if re.search(rf"(?<!\d){decl}(?!\d)", p):
                return {"estado": "verificada_script", "metodo": config.METODO_SCRIPT,
                        "detalle": f"p. {decl} (PDF {i}; paginación impresa confirmada en la página)", "pagina_pdf": i}
            return {"estado": "observada", "metodo": config.METODO_SCRIPT,
                    "detalle": f"hallada en la página {i} del PDF, lejos de la declarada {decl}", "pagina_pdf": i}
    # diagnóstico: ¿qué fragmento falla?
    malos = [f for f in frs if not any(normalizar(p).find(f) >= 0 for p in pags)]
    return {"estado": "observada", "metodo": config.METODO_SCRIPT,
            "detalle": "no hallada en el documento; fragmento(s) sin coincidencia: " + " | ".join(f"«{m[:60]}»" for m in malos[:3]), "pagina_pdf": None}


def _cotejar_sintesis(meta, cuerpo):
    secs = F.secciones(cuerpo)
    destinos = F.enlaces(secs.get("Fichas de entrada", ""))
    if not destinos:
        return {"estado": "observada", "metodo": "cadena de fichas", "detalle": "sin fichas de entrada enlazadas", "pagina_pdf": None}
    base = Path(meta.get("_ruta", ".")).parent
    malas = []
    for d in destinos:
        q = base / d
        if not q.exists():
            malas.append(f"{d} (no existe)"); continue
        m, _ = F.leer(q)
        est = (m.get("verificacion") or {}).get("estado")
        if not str(est).startswith("verificada"):
            malas.append(f"{d} ({est})")
    if malas:
        return {"estado": "pendiente", "metodo": "cadena de fichas", "detalle": "fichas de entrada sin verificar: " + ", ".join(malas), "pagina_pdf": None}
    return {"estado": "verificada_script", "metodo": "cadena de fichas", "detalle": f"{len(destinos)} fichas de entrada verificadas", "pagina_pdf": None}
