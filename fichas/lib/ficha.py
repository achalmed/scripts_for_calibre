"""ficha.py — leer, escribir y validar fichas con el frontmatter único (fichas_formato_y_voz.md §1–§3).

Una ficha es: frontmatter YAML entre `---` + cuerpo Markdown. Aquí no se interpreta el cuerpo salvo para
localizar secciones `## Nombre`. Al escribir, las claves salen SIEMPRE en el orden de config.CLAVES y los valores
vacíos se escriben vacíos (`zotero_key:`), como exige la norma.
"""
import importlib.util
import re
from datetime import date
from pathlib import Path

import yaml


def _config():
    """Carga el config.py de ESTA suite por ruta, para que otra suite (lecturas) pueda importar esta lib sin choques."""
    ruta = Path(__file__).resolve().parents[1] / "config.py"
    spec = importlib.util.spec_from_file_location("fichas_config", ruta)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


config = _config()


def leer(path):
    """(meta, cuerpo). meta = {} si no hay frontmatter."""
    t = Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", t, re.S)
    if not m:
        return {}, t
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"frontmatter ilegible: {e}")
    return meta, m.group(2)


def _y(v):
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.search(r"[:#\[\]{}&*!|>'\"%@`]|^\s|\s$|^-", s) or s.lower() in ("true", "false", "null", "yes", "no"):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def frontmatter(meta):
    """Serializa en el orden fijo; omite las claves que el tipo no lleva; deja vacíos los valores vacíos."""
    tipo = meta.get("tipo", "")
    omite = config.OMITE.get(tipo, set())
    out = ["---"]
    for k in config.CLAVES:
        if k in omite:
            continue
        if k == "verificacion":
            v = meta.get("verificacion") or {}
            out.append("verificacion:")
            for kk in config.CLAVES_VERIFICACION:
                val = v.get(kk, "") if isinstance(v, dict) else ""
                out.append(f"  {kk}: {_y(val)}".rstrip())
            continue
        out.append(f"{k}: {_y(meta.get(k, ''))}".rstrip())
    out.append("---")
    return "\n".join(out) + "\n"


def escribir(path, meta, cuerpo):
    cuerpo = cuerpo.lstrip("\n")
    Path(path).write_text(frontmatter(meta) + ("\n" + cuerpo if cuerpo else ""), encoding="utf-8")


def secciones(cuerpo):
    """{nombre: texto} de las secciones `## Nombre` del cuerpo (nombre sin numeración ni espacios extremos)."""
    out, actual, buf = {}, None, []
    for l in cuerpo.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", l)
        if m:
            if actual is not None:
                out[actual] = "\n".join(buf).strip()
            actual, buf = re.sub(r"^\d+[.)]\s*", "", m.group(1)).strip(), []
        elif actual is not None:
            buf.append(l)
    if actual is not None:
        out[actual] = "\n".join(buf).strip()
    return out


def literal(cuerpo, tipo):
    """Cadena literal a cotejar: el contenido de la sección que fija config.SECCION_LITERAL, sin comillas envolventes."""
    sec = config.SECCION_LITERAL.get(tipo)
    if not sec:
        return ""
    s = secciones(cuerpo).get(sec, "")
    # se toma el primer párrafo o cita en bloque; se quitan comillas envolventes y marcas de bloque
    s = "\n".join(l.lstrip("> ").rstrip() for l in s.splitlines())
    s = re.split(r"\n\s*\n", s.strip())[0] if s.strip() else ""
    s = s.strip()
    s = re.sub(r"^[“\"«‘']+", "", s); s = re.sub(r"[”\"»’']+\s*(\([^)]*\))?\.?$", "", s)
    return s.strip()


def enlaces(texto):
    """Destinos de los enlaces Markdown `[x](y.md)` (nunca wikilinks)."""
    return re.findall(r"\[[^\]]*\]\(([^)\s]+\.md)\)", texto or "")


def validar(path, meta, cuerpo):
    """Lista de problemas (vacía = cumple). Comprueba frontmatter, nombre, categoría, estado y secciones."""
    p, prob = Path(path), []
    if not meta:
        return ["sin frontmatter"]
    tipo = meta.get("tipo")
    if tipo not in config.TIPOS:
        prob.append(f"tipo inválido: {tipo!r}")
        return prob
    omite = config.OMITE[tipo]
    esperadas = [k for k in config.CLAVES if k not in omite]
    presentes = [k for k in meta if k in config.CLAVES]
    faltan = [k for k in esperadas if k not in meta]
    if faltan:
        prob.append("faltan claves: " + ", ".join(faltan))
    if presentes != [k for k in esperadas if k in meta]:
        prob.append("claves fuera del orden normativo")
    sobran = [k for k in meta if k not in config.CLAVES]
    if sobran:
        prob.append("claves ajenas al frontmatter único: " + ", ".join(sobran))
    v = meta.get("verificacion")
    if not isinstance(v, dict):
        prob.append("verificacion debe ser un bloque con estado, metodo y fecha")
    else:
        if v.get("estado") not in config.ESTADOS:
            prob.append(f"estado inválido: {v.get('estado')!r}")
        if v.get("fecha") not in (None, "") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(v.get("fecha"))):
            prob.append("fecha de verificación no es ISO")
    if "categoria" not in omite and meta.get("categoria") not in config.CATEGORIAS:
        prob.append(f"categoría fuera de los once rótulos: {meta.get('categoria')!r}")
    if not re.match(config.PATRON_NOMBRE[tipo], p.name):
        prob.append(f"nombre de archivo no sigue el patrón de {tipo}")
    if meta.get("calibre_id") in (None, "") and tipo not in ("apunte", "ficha_sintesis"):  # la síntesis reúne varias obras: no tiene un único calibre_id
        # vacío con nota de pendiente (pasos 00–03) es un aviso, no una falta: la norma lo admite mientras la fuente no entra a Calibre
        pendiente = re.search(r"pasos?\s*00\s*[–-]\s*03|no existe en Calibre|no catalogada", cuerpo, re.I)
        prob.append(("aviso: " if pendiente else "") + "calibre_id vacío (la fuente debe estar en la biblioteca; si no, anótalo en Observaciones)")
    if "pagina" not in omite and meta.get("pagina") in (None, ""):
        prob.append("pagina vacía")
    secs = secciones(cuerpo)
    faltan_sec = [s for s in config.SECCIONES[tipo] if s not in secs]
    if faltan_sec:
        prob.append("faltan secciones: " + ", ".join(faltan_sec))
    if re.search(r"\[\[[^\]]+\]\]", cuerpo):
        prob.append("usa wikilinks; deben ser enlaces Markdown [nombre](nombre.md)")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", cuerpo):
        prob.append("contiene emojis")
    if re.search(r"^# ", cuerpo, re.M):
        prob.append("título de nivel 1 dentro de la ficha (el título es el nombre del archivo)")
    if re.search(r"\b(\w+)\s+&\s+(\w+)\b", cuerpo) and tipo != "ficha_catalogacion":
        prob.append("autores unidos con «&»; debe ser «y»")
    return prob


def es_ficha(path):
    try:
        meta, _ = leer(path)
    except Exception:
        return False
    return isinstance(meta, dict) and meta.get("tipo") in config.TIPOS


def fichas_en(rutas):
    """Expande archivos y carpetas (recursivo) a la lista de fichas con frontmatter reconocido."""
    out = []
    for r in rutas:
        p = Path(r).expanduser()
        if p.is_dir():
            out += [q for q in sorted(p.rglob("*.md")) if es_ficha(q)]
        elif p.is_file():
            out.append(p)
    return out


def marcar(meta, estado, metodo, detalle=""):
    meta["verificacion"] = {"estado": estado, "metodo": (metodo + (f"; {detalle}" if detalle else "")).strip(), "fecha": date.today().isoformat()}
    return meta
