"""manifiesto.py — leer, generar, verificar y resolver el `fuentes.yml` de un proyecto (FD4).

Formato:
    proyecto: delegacion-facultades-2026   # el id del proyecto (NORMATIVA §1.1), nunca una ruta
    generado: 2026-09-07
    fuentes:
      - origen: normas/ley_30057_ley_del_servicio_civil.pdf   # nombre con que el proyecto conocía el archivo (relativo al manifiesto)
        calibre_id: 10024
        zotero_key: ""
        clave_bibtex: ""
        titulo: Ley N.° 30057. Ley del servicio civil
        autores: Autoridad Nacional del Servicio Civil
        serie: Marco legal 04 - Administracion publica [3]
        anexo: ""            # ruta dentro de data/ del libro cuando la entrada es un adjunto
        sha256: ""           # huella del original, si el ledger de ingesta la conoce
        uso: ""              # sección del trabajo que la usa (paso 09); se conserva al regenerar
        nota: ""
Una entrada por archivo que el proyecto usaba; varios orígenes pueden apuntar al mismo libro (copias).
"""
import csv
import os
import re
import sys
from datetime import date
from pathlib import Path

import importlib.util

import yaml


def _config():
    """Carga el config.py de ESTA suite por ruta: otras suites (fichas, ingesta) importan esta lib con su propio `config`."""
    ruta = Path(__file__).resolve().parents[1] / "config.py"
    spec = importlib.util.spec_from_file_location("manifiesto_config", ruta)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


config = _config()
sys.path.insert(0, str(config.PY_COMMON))
import biblioteca as bib  # noqa: E402

_spec_r = importlib.util.spec_from_file_location("fuentes_rutas", Path(__file__).resolve().parents[2] / "lib" / "rutas.py")
_R = importlib.util.module_from_spec(_spec_r); _spec_r.loader.exec_module(_R)   # rutas del ledger (ola 2, F5)

RE_ID = re.compile(r"/biblioteca/[^/]+/[^/]+ \((\d+)\)/(.*)$")


# --- ubicación -------------------------------------------------------------
def raiz_de(path):
    """Carpeta que lleva el manifiesto del archivo `path`.

    Se aplica la primera regla de `config.REGLAS_RAIZ` que case; si ninguna lo
    hace, la carpeta del archivo.

    Con una excepción (P5, 2026-09-08): si la raíz que sale de la regla tiene
    dentro una carpeta `fuentes/`, el manifiesto va ahí. Es el rol canónico de
    las fuentes de un proyecto de `03 writing`, y así un documento archivado
    desde `referencias/` no deja el `fuentes.yml` suelto en la raíz mientras el
    resto de las fuentes viven en `fuentes/`.
    """
    s = str(Path(path).resolve() if not Path(path).is_symlink() else Path(path).absolute())
    # Las reglas se prueban PRIMERO contra la ruta tal como se dio y después
    # contra la resuelta. `02 analysis/data` es un enlace simbólico al disco
    # externo desde el 2026-09-20: resuelta, la ruta ya no contiene
    # `/02 analysis/data/raw/`, ninguna regla casaba y el manifiesto caía en la
    # carpeta del archivo —un `fuentes.yml` suelto por documento en vez de su
    # entrada en `data/raw/fuentes.yml`— (2026-09-29, primer documento de datafw
    # archivado desde el enlace). Las reglas describen el proyecto como lo
    # conoce la gente, no dónde están los bytes.
    raiz = None
    for cand in dict.fromkeys((str(Path(path).absolute()), s)):
        for rx in config.REGLAS_RAIZ:
            m = rx.match(cand)
            if m:
                raiz = Path(m.group(1))
                break
        if raiz is not None:
            break
    if raiz is None:
        raiz = Path(path).absolute().parent
    sub = raiz / "fuentes"
    return sub if sub.is_dir() else raiz


def base_de(raiz):
    """Carpeta contra la que se escribe el `origen` relativo de cada entrada.

    Es la raíz del PROYECTO, no la del manifiesto: cuando `raiz_de` aplicó la
    excepción P5 (el manifiesto vive en `<proyecto>/fuentes/`), un archivo de
    `<proyecto>/referencias/x.pdf` se registra como `referencias/x.pdf` —que es
    como quedaron las entradas anteriores a P7— y no revienta con un
    `relative_to` fuera de subruta (fallo del 2026-09-11 al archivar las siete
    fuentes de la tesis de referencia). Si la propia `raiz` es la que dicta una
    regla (`reports/<slug>/fuentes`), la base es ella misma.
    """
    r = Path(raiz).absolute()
    if r.name == "fuentes":
        for rx in config.REGLAS_RAIZ:
            m = rx.match(str(r) + "/")
            if m:
                return r if Path(m.group(1)) == r else r.parent
    return r


def origen_de(raiz, path):
    """`origen` relativo de `path` para el manifiesto de `raiz` (ver `base_de`)."""
    return str(Path(path).absolute().relative_to(base_de(raiz)))


def id_proyecto(raiz):
    """El `id` del proyecto dueño del manifiesto (§1.1): el nombre de su carpeta, no una ruta.
    El manifiesto vive en `<proyecto>/fuentes/` (P5) o `<proyecto>/01_fuentes/`: se sube un nivel."""
    r = Path(raiz).absolute()
    return r.parent.name if r.name in ("fuentes", "01_fuentes") else r.name


def rel_docs(p):
    try:
        return str(Path(p).absolute().relative_to(config.DOCS))
    except ValueError:
        return str(p)


# --- lectura y escritura ---------------------------------------------------
# Analizador C de libyaml si está compilado. Sobre un manifiesto de 142 KB la
# diferencia con el de Python puro es de un orden de magnitud.
try:
    _Loader = yaml.CSafeLoader
except AttributeError:                                   # pragma: no cover
    _Loader = yaml.SafeLoader

_CACHE = {}


def cargar(raiz, recargar=False):
    """Manifiesto de `raiz`, EN CACHÉ por (ruta, mtime, tamaño).

    `ruta()` consulta el manifiesto una vez por documento buscado. Sin caché,
    una corrida que resuelve doscientos documentos volvía a analizar el YAML
    doscientas veces: minutos de CPU en el analizador, no en el trabajo. La
    clave incluye mtime y tamaño, así que una edición del manifiesto se recoge
    sola y no hace falta acordarse de invalidar nada.
    """
    f = Path(raiz) / config.NOMBRE
    if not f.exists():
        return {"proyecto": rel_docs(raiz), "generado": "", "fuentes": []}
    st = f.stat()
    clave = (str(f), st.st_mtime_ns, st.st_size)
    if recargar or clave not in _CACHE:
        d = yaml.load(f.read_text(encoding="utf-8"), Loader=_Loader) or {}
        d.setdefault("fuentes", [])
        _CACHE.clear()                      # un manifiesto por raíz; no crece
        _CACHE[clave] = d
    return _CACHE[clave]


def guardar(raiz, data):
    _CACHE.clear()          # lo que se acaba de escribir manda sobre lo cacheado
    f = Path(raiz) / config.NOMBRE
    if not data.get("proyecto") or "/" in str(data["proyecto"]):      # NORMATIVA §1.1: el id, no la ruta (M5, 2026-09-15)
        data["proyecto"] = id_proyecto(raiz)
    data["generado"] = date.today().isoformat()
    ordenadas = []
    for e in sorted(data["fuentes"], key=lambda e: str(e.get("origen", ""))):
        ordenadas.append({k: ("" if e.get(k) is None else e.get(k)) for k in config.CLAVES_ENTRADA})
    data["fuentes"] = ordenadas
    cab = ("# fuentes.yml — manifiesto de fuentes documentales del proyecto (Método Documental, paso 09; FD4).\n"
           "# Generado por ~/Documents/scripts_for_fuentes/manifiesto/main.py generar; se conservan clave_bibtex, uso y nota.\n"
           "# No lleva rutas físicas: la ruta la da `manifiesto/main.py ruta <carpeta> <origen|calibre_id>` (resolutor de Calibre).\n")
    f.write_text(cab + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    return f


# --- descubrimiento --------------------------------------------------------
def id_de_ruta_biblioteca(p):
    """(calibre_id, anexo) a partir de una ruta dentro de la biblioteca; (None, '') si no lo es."""
    m = RE_ID.search(str(p))
    if not m:
        return None, ""
    resto = m.group(2)
    return int(m.group(1)), (resto[5:] if resto.startswith("data/") else "")


def enlaces_biblioteca(raiz):
    """Enlaces simbólicos bajo `raiz` que resuelven dentro de la biblioteca: [(enlace, destino_real, id, anexo)]."""
    out = []
    for p in sorted(Path(raiz).rglob("*")):
        if not p.is_symlink():
            continue
        real = Path(os.path.realpath(p))
        bid, anexo = id_de_ruta_biblioteca(real)
        if bid:
            out.append((p, real, bid, anexo))
    return out


def filas_ledger(raiz):
    """Filas del ledger de ingesta cuyo origen cae bajo `raiz`."""
    if not config.LEDGER_INGESTA.exists():
        return []
    raiz = Path(raiz).absolute(); base = base_de(raiz); out = []
    with open(config.LEDGER_INGESTA, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            o = r.get("origen", "")
            p = _R.resolver(o, config.CIL_DIR)   # relativo a DOCS_ROOT, a la entrada o absoluto (F5)
            if p is None:
                continue
            try:
                rel = p.absolute().relative_to(base)
            except ValueError:
                continue
            if r.get("calibre_id", "").isdigit():
                out.append((str(rel), int(r["calibre_id"]), r.get("sha256", ""), r.get("zotero_key", "")))
    return out


def _entrada(origen, bid, anexo="", sha="", previa=None):
    d = bib.datos(bid) or {}
    e = {"origen": origen, "calibre_id": bid, "zotero_key": d.get("zotero_key", ""), "clave_bibtex": "",
         "titulo": d.get("titulo", "(id inexistente en Calibre)"), "autores": "; ".join(d.get("autores", [])),
         "serie": (f"{d['serie']} [{int(d['serie_index']) if float(d['serie_index'] or 0).is_integer() else d['serie_index']}]" if d.get("serie") else ""),
         "anexo": anexo, "sha256": sha, "uso": "", "nota": ""}
    if previa:
        for k in config.CLAVES_MANUALES:
            if previa.get(k):
                e[k] = previa[k]
        if previa.get("sha256") and not sha:
            e["sha256"] = previa["sha256"]
        if previa.get("anexo") and not anexo:
            e["anexo"] = previa["anexo"]
    return e


def generar(raiz, aplicar=False):
    """Manifiesto = entradas previas ∪ enlaces hacia la biblioteca ∪ filas del ledger bajo la raíz. Devuelve (data, resumen)."""
    raiz = Path(raiz).absolute(); data = cargar(raiz)
    previas = {e.get("origen"): e for e in data["fuentes"]}
    nuevas = {}
    for enlace, real, bid, anexo in enlaces_biblioteca(raiz):
        o = origen_de(raiz, enlace); nuevas[o] = (bid, anexo, "")
    for rel, bid, sha, _zk in filas_ledger(raiz):
        if rel in nuevas:
            nuevas[rel] = (nuevas[rel][0], nuevas[rel][1], sha)
        else:
            nuevas[rel] = (bid, "", sha)
    conservadas = 0
    for o, e in previas.items():
        if not e.get("calibre_id"):
            continue
        if o not in nuevas:
            nuevas[o] = (int(e["calibre_id"]), e.get("anexo", ""), e.get("sha256", ""))
        elif not bib.datos(nuevas[o][0]) and bib.datos(int(e["calibre_id"])):
            # Nunca se cambia un id que EXISTE en Calibre por uno que no existe.
            # Cuando dos libros se fusionan, el ledger conserva el id muerto y el
            # manifiesto ya se había corregido a mano hacia el superviviente
            # (tracking_sdg7_2025: ledger 10261, borrado; manifiesto 10260, vivo).
            # Regenerar dando prioridad ciega al ledger deshacía esa corrección
            # (2026-09-29). No se decide aquí qué libro es el bueno: solo se
            # impide la regresión de uno válido a uno inexistente.
            nuevas[o] = (int(e["calibre_id"]), nuevas[o][1] or e.get("anexo", ""), nuevas[o][2] or e.get("sha256", ""))
            conservadas += 1
    entradas = [_entrada(o, bid, anexo, sha, previas.get(o)) for o, (bid, anexo, sha) in nuevas.items()]
    data["fuentes"] = entradas
    res = {"entradas": len(entradas), "desde_enlaces": len(enlaces_biblioteca(raiz)), "desde_ledger": len(filas_ledger(raiz)), "previas": len(previas),
           "sin_libro": sum(1 for e in entradas if e["titulo"].startswith("(id inexistente")), "anexos": sum(1 for e in entradas if e["anexo"]),
           "conservadas": conservadas}
    if aplicar and entradas:
        guardar(raiz, data)
    return data, res


def generar_desde_bib(raiz, bib_path, asignar=None, aplicar=False):
    """Manifiesto de un trabajo de 03 writing: una entrada por clave del .bib, localizada en Calibre por DOI, URL o título
    (o fijada a mano con asignar={clave: id}). Conserva las entradas previas. Devuelve (data, resumen)."""
    import re
    raiz = Path(raiz).absolute(); data = cargar(raiz)
    previas = {e.get("origen"): e for e in data["fuentes"]}
    asignar = asignar or {}
    texto = Path(bib_path).expanduser().read_text(encoding="utf-8")
    entradas, sin = [], []
    for kind, key, body in re.findall(r"@(\w+)\{([^,]+),(.*?)\n\}", texto, re.S):
        key = key.strip(); f = {k.lower(): v for k, v in re.findall(r"(\w+)\s*=\s*[{\"](.+?)[}\"],?\n", body + "\n")}
        titulo = re.sub(r"[{}]", "", f.get("title", ""))
        bid = asignar.get(key)
        if not bid:
            r = bib.existe(titulo=titulo or None, doi=f.get("doi"))
            bid = r["candidatos"][0]["calibre_id"] if r["candidatos"] else None
        if not bid and previas.get(key, {}).get("calibre_id"):
            bid = previas[key]["calibre_id"]
        if not bid:
            sin.append(key); continue
        e = _entrada(key, int(bid), previa=previas.get(key)); e["clave_bibtex"] = key
        entradas.append(e)
    for o, e in previas.items():
        if o not in {x["origen"] for x in entradas} and e.get("calibre_id"):
            entradas.append(e)
    data["fuentes"] = entradas
    res = {"entradas": len(entradas), "sin_libro": sin}
    if aplicar and entradas:
        guardar(raiz, data)
    return data, res


def agregar(raiz, origen, bid, anexo="", sha="", nota=""):
    """Añade o actualiza una entrada (la usan ingesta/archivar, paquetes y ocr)."""
    raiz = Path(raiz).absolute(); data = cargar(raiz)
    previas = {e.get("origen"): e for e in data["fuentes"]}
    e = _entrada(origen, bid, anexo, sha, previas.get(origen))
    if nota:
        e["nota"] = nota
    previas[origen] = e
    data["fuentes"] = list(previas.values())
    return guardar(raiz, data)


# --- uso -------------------------------------------------------------------
def verificar(raiz):
    """Problemas del manifiesto: ids inexistentes, archivos ausentes, anexos ausentes, orígenes duplicados."""
    data = cargar(Path(raiz)); prob = []; vistos = set()
    if not (Path(raiz) / config.NOMBRE).exists():
        return [f"sin {config.NOMBRE}"], data
    for e in data["fuentes"]:
        o = e.get("origen", "")
        if o in vistos:
            prob.append(f"origen duplicado: {o}")
        vistos.add(o)
        bid = e.get("calibre_id")
        d = bib.datos(bid) if bid else None
        if not d:
            prob.append(f"{o}: calibre_id {bid} no existe en Calibre"); continue
        if e.get("anexo"):
            if not (Path(d["carpeta"]) / "data" / e["anexo"]).exists():
                prob.append(f"{o}: anexo data/{e['anexo']} ausente en el libro {bid}")
        elif not d["ruta"] or not Path(d["ruta"]).exists():
            prob.append(f"{o}: el libro {bid} no tiene archivo")
    return prob, data


def ruta(raiz, clave):
    """Ruta física de una entrada por `origen` (o su nombre de archivo) o por calibre_id."""
    data = cargar(Path(raiz))
    for e in data["fuentes"]:
        o = str(e.get("origen", ""))
        if clave in (o, Path(o).name) or (str(clave).isdigit() and int(clave) == e.get("calibre_id") and not e.get("anexo")):
            d = bib.datos(e["calibre_id"])
            if not d:
                return None
            return Path(d["carpeta"]) / "data" / e["anexo"] if e.get("anexo") else (Path(d["ruta"]) if d["ruta"] else None)
    if str(clave).isdigit():
        return bib.ruta(int(clave))
    return None


def quitar_enlaces(raiz, aplicar=False):
    """Borra los enlaces hacia la biblioteca que el manifiesto ya cubre. Devuelve (borrados, sin_cubrir)."""
    raiz = Path(raiz).absolute(); data = cargar(raiz)
    cubiertos = {e.get("origen"): e for e in data["fuentes"]}
    borrados, sin = [], []
    for enlace, real, bid, anexo in enlaces_biblioteca(raiz):
        o = origen_de(raiz, enlace); e = cubiertos.get(o)
        if e and int(e.get("calibre_id") or 0) == bid and (e.get("anexo") or "") == anexo:
            if aplicar:
                enlace.unlink()
            borrados.append(o)
        else:
            sin.append(o)
    return borrados, sin


def manifiestos_en(raices=None):
    out = []
    for r in (raices or config.RAICES_VIGILADAS):
        if Path(r).is_dir():
            out += sorted(p.parent for p in Path(r).rglob(config.NOMBRE) if "/.git/" not in str(p))
    return out
