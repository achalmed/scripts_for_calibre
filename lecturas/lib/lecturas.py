"""lib/lecturas.py — lógica de la suite `lecturas`: clave derivada, búsqueda de pasajes, bloque entre marcas y escritura de la ficha.
Orquestación en main.py; valores en config.py (FS3, 2026-09-07)."""
import re
import unicodedata
from datetime import date

import config


def _ficha():
    """lib/ficha.py de la suite fichas, cargado por ruta: así `lib` sigue siendo el paquete de esta suite."""
    import importlib.util
    ruta = config.SUITE_FICHAS / "lib" / "ficha.py"
    s = importlib.util.spec_from_file_location("ficha_de_fichas", ruta); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


F = _ficha()


def na(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


CORPORATIVO = re.compile(r"\b(ministerio|banco|presidencia|comision|instituto|organismo|autoridad|congreso|fondo|corporacion|universidad|centro|consejo|caf|bid|inei|bcrp|mef|ocde|oecd|cepal|onu|oit|fmi|pnud|unesco)\b")
_usadas = set()


def clave_de(d):
    """<apellido><año><palabra>: apellido = parte tras «|» en Calibre; sin «|», último token salvo nombre corporativo.
    Es un valor por defecto: el `lecturas.yml` debe fijar `clave_bibtex` (la de Better BibTeX) en cuanto exista."""
    aut = d["autores_calibre"][0] if d["autores_calibre"] else ""
    if "|" in aut:
        ap = aut.split("|")[-1].strip().split()[0] if aut.split("|")[-1].strip() else aut.split("|")[0]
    else:
        toks = aut.split()
        ap = toks[0] if (not toks or CORPORATIVO.search(na(aut))) else toks[-1]
    pal = next((w for w in re.findall(r"[a-z]{4,}", na(d["titulo"])) if w not in ("para", "sobre", "desde", "entre", "como", "obras", "hacia", "tomo")), "obra")
    anio = d["pubdate"][:4]
    if not anio or anio < "1000":                 # Calibre guarda 0101-01-01 cuando no hay fecha
        anio = "sf"
    base = re.sub(r"[^a-z0-9]", "", na(ap or "anon")) + anio + pal
    clave, i = base, 0
    while clave in _usadas:                       # dos ítems con la misma clave derivada (varios tomos): sufijo b, c, …
        i += 1; clave = base + "abcdefghijklmnopqrstuvwxyz"[i]
    _usadas.add(clave)
    return clave


def pasajes(pags, patrones, mx):
    out, total = [], 0
    for pat in patrones:
        rx = re.compile(pat, re.I); hits = 0
        for i, p in enumerate(pags, 1):
            for m in rx.finditer(na(p)):
                a, b = max(0, m.start() - config.CONTEXTO_ANTES), min(len(p), m.end() + config.CONTEXTO_DESPUES)
                frag = re.sub(r"\s+", " ", p[a:b]).strip()
                out.append((i, pat, frag)); hits += 1; total += 1
                if hits >= mx:
                    break
            if hits >= mx:
                break
        if not hits:
            out.append((None, pat, ""))
    return out, total


def bloque(d, etiqueta, ps):
    l = [config.MARCA_INICIO, "", f"## Pasajes candidatos ({date.today().isoformat()})", "",
         f"Ítem {d['calibre_id']}: *{d['titulo']}* · {'; '.join(d['autores'])} · {d['pubdate'][:4]}. Página = índice del PDF desde 1, no la impresa.", ""]
    if etiqueta:
        l += [f"Conceptos guía: {etiqueta}", ""]
    for i, pat, frag in ps:
        l.append(f"- «{pat}»: sin coincidencias" if i is None else f"- p. {i} «{pat}»: . . . {frag} . . .")
    l += ["", config.MARCA_FIN]
    return "\n".join(l)


def escribir_item(destino, d, clave, proyecto, etiqueta, ps, aplicar):
    p = destino / f"{clave}{config.SUFIJO_ARCHIVO}"
    nuevo = bloque(d, etiqueta, ps)
    if p.exists():
        meta, cuerpo = F.leer(p)
        if config.MARCA_INICIO in cuerpo and config.MARCA_FIN in cuerpo:
            cuerpo = re.sub(re.escape(config.MARCA_INICIO) + r".*?" + re.escape(config.MARCA_FIN), lambda _: nuevo, cuerpo, flags=re.S)
        else:
            cuerpo = cuerpo.rstrip() + "\n\n" + nuevo + "\n"
        accion = "actualizado"
    else:
        meta = {"tipo": "lectura", "calibre_id": d["calibre_id"], "zotero_key": d["zotero_key"], "clave_bibtex": clave, "proyecto": proyecto, "uso": "",
                "verificacion": {"estado": "pendiente", "metodo": "", "fecha": ""}}
        cuerpo = "\n".join(f"## {s}\n\n" for s in config.SECCIONES) + "\n" + nuevo + "\n"
        accion = "creado"
    if aplicar:
        destino.mkdir(parents=True, exist_ok=True); F.escribir(p, meta, cuerpo)
    return p, accion
