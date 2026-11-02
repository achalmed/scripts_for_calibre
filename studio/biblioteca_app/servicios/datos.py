"""biblioteca_app/servicios/datos.py — lo que cada vista lista, leído tal cual de donde ya vive (sin Qt, se prueba solo):
el índice de libros (`lib/indice.py`, el JSON), los ledgers (`fuentes_descargadas.tsv`, `ingesta/pendientes.tsv`,
`ingesta/ingesta.tsv`, `catalogacion/resumen_catalogacion.tsv`), las fichas canónicas (`catalogacion/fichas/*.md`, su
frontmatter), los manifiestos (`fuentes.yml` de las raíces vigiladas) y las comprobaciones de coherencia que salen de
cruzarlos. Nada se escribe; las bases no se abren (el índice las leyó en solo lectura).

Las rutas salen de `core/env.py` (buscado subiendo carpetas; respeta las variables del entorno, así las pruebas y las
capturas apuntan a una biblioteca de muestra) y los textos de los ledgers se resuelven con `lib/rutas.py`.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
_TITULO_FICHA = re.compile(r"Ficha de catalogación de «(.+?)»")
_OMITIR = {".git", "node_modules", "_site", "_freeze", ".quarto", "__pycache__", ".venv", "site_libs"}


def _modulo(nombre: str, ruta: Path):
    s = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def cargar_env():
    """`core/env.py` del espacio de trabajo (subiendo desde este repo); fuera de él, lo mínimo desde el entorno."""
    d = REPO
    while d != d.parent and not (d / "core" / "env.py").is_file():
        d = d.parent
    if (d / "core" / "env.py").is_file():
        return _modulo("core_env", d / "core" / "env.py")
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    docs = Path(os.environ.get("DOCS_ROOT") or REPO.parent)
    biblioteca = Path(os.environ.get("BIBLIOTECA_DIR") or docs / "biblioteca")
    return SimpleNamespace(DOCS_ROOT=docs, BIBLIOTECA_DIR=biblioteca, CALIBRE_DB=Path(os.environ.get("CALIBRE_DB") or biblioteca / "metadata.db"),
                           ZOTERO_DB=Path(os.environ.get("ZOTERO_DB") or Path.home() / "Zotero/zotero.sqlite"),
                           LOCK_CALIBRE=Path(os.environ.get("LOCK_CALIBRE") or estado / "biblioteca/calibre.lock"),
                           LOCK_ZOTERO=Path(os.environ.get("LOCK_ZOTERO") or estado / "biblioteca/zotero.lock"),
                           CORE_PYTHON=Path(os.environ.get("CORE_PYTHON") or "python3"),
                           WRITING_DIR=Path(os.environ.get("WRITING_DIR") or docs / "escritura"),
                           DATAFW_DIR=Path(os.environ.get("DATAFW_DIR") or docs / "datafw"),
                           RESPALDOS_DIR=Path(os.environ.get("RESPALDOS_DIR") or ""))


def _rutas():
    return _modulo("biblioteca_rutas", REPO / "lib" / "rutas.py")


def ruta_indice() -> Path:
    return _modulo("biblioteca_indice", REPO / "lib" / "indice.py").ruta_indice()


# ------------------------------------------------------------------------------------------------ el índice
def leer_indice(ruta: Path | None = None) -> dict:
    """El JSON de `lib/indice.py`; sin él, un índice vacío (la ventana lo dice y ofrece regenerarlo)."""
    ruta = ruta or ruta_indice()
    try:
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        d.setdefault("libros", {})
        return d
    except (OSError, ValueError):
        return {"libros": {}, "biblioteca": "", "generado": "", "notas": ""}


def libros(indice: dict) -> list[dict]:
    """Una entrada por libro con su `calibre_id` como texto, en el orden del índice."""
    return [{"id": b, **d} for b, d in indice.get("libros", {}).items()]


def antiguedad_indice(indice: dict) -> str:
    """«hace n h» del campo `generado` del índice; vacío si no hay índice."""
    g = indice.get("generado") or ""
    try:
        t = time.mktime(time.strptime(g[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return ""
    s = time.time() - t
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    return f"hace {int(s // 86400)} d"


# ---------------------------------------------------------------------------------------------- los ledgers
def leer_tsv(ruta: Path) -> list[dict]:
    try:
        with open(ruta, encoding="utf-8", newline="") as f:
            return [dict(fila) for fila in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)]
    except OSError:
        return []


def descargas(repo: Path = REPO) -> list[dict]:
    """`fuentes_descargadas.tsv`: una fila por descarga, la más reciente primero."""
    filas = leer_tsv(repo / "fuentes_descargadas.tsv")
    return sorted(filas, key=lambda f: f.get("fecha", ""), reverse=True)


def entrada(repo: Path = REPO, docs: Path | None = None) -> list[dict]:
    """Los archivos de la zona de entrada (`entrada/`) y las filas de `ingesta/pendientes.tsv`, cruzados con
    `ingesta/ingesta.tsv`: cada uno con su paso (recibido · identificado · catalogado · sin archivo)."""
    rutas = _rutas()
    docs = Path(docs) if docs else rutas.docs_root()
    zona = repo / "entrada"
    pendientes = {}
    for f in leer_tsv(repo / "ingesta" / "pendientes.tsv"):
        r = rutas.resolver(f.get("origen", ""), zona, docs)
        if r is not None:
            pendientes.setdefault(str(r), f)
    ingeridos = {}
    for f in leer_tsv(repo / "ingesta" / "ingesta.tsv"):
        r = rutas.resolver(f.get("origen", ""), zona, docs)
        if r is not None:
            ingeridos[str(r)] = f
    salida = []
    vistos = set()
    archivos = []
    if zona.is_dir():
        for p in sorted(zona.rglob("*")):
            if p.is_file() and not p.name.startswith(".") and p.name != "fuentes.yml" and not any(x in _OMITIR for x in p.parts):
                archivos.append(p)
    for p in archivos:
        clave = str(p)
        vistos.add(clave)
        salida.append(_fila_entrada(p, pendientes.get(clave), ingeridos.get(clave), existe=True, zona=zona, docs=docs))
    for clave, f in pendientes.items():
        if clave in vistos:
            continue
        p = Path(clave)
        salida.append(_fila_entrada(p, f, ingeridos.get(clave), existe=p.is_file(), zona=zona, docs=docs))
    return salida


def _fila_entrada(p: Path, pendiente: dict | None, ingerido: dict | None, existe: bool, zona: Path, docs: Path) -> dict:
    if ingerido and ingerido.get("calibre_id"):
        paso, nivel = "catalogado", "positivo"
    elif not existe:
        paso, nivel = "sin archivo", "inactivo"
    elif pendiente:
        paso, nivel = "identificado", "activo"
    else:
        paso, nivel = "recibido", "neutro"
    try:
        origen = str(p.relative_to(zona))
    except ValueError:
        try:
            origen = str(p.relative_to(docs))
        except ValueError:
            origen = str(p)
    try:
        bytes_ = p.stat().st_size if existe else 0
    except OSError:
        bytes_ = 0
    return {"archivo": p.name, "paso": paso, "nivel": nivel, "titulo": (pendiente or {}).get("titulo", "") or (ingerido or {}).get("titulo", ""),
            "confianza": (pendiente or {}).get("confianza", ""), "calibre_id": (ingerido or {}).get("calibre_id", ""),
            "origen": origen, "ruta": str(p), "bytes": bytes_, "existe": existe,
            "ficha": (pendiente or {}).get("ficha", ""), "autores": (pendiente or {}).get("autores", "") or (ingerido or {}).get("autores", ""),
            "identificador": (pendiente or {}).get("identificador", ""), "tipo": (pendiente or {}).get("tipo_zotero", "") or (ingerido or {}).get("tipo_zotero", ""),
            "estado_ledger": (ingerido or {}).get("estado", "")}


def ids_con_ficha(repo: Path = REPO) -> set[str]:
    """Los `calibre_id` que tienen ficha canónica, por el prefijo del nombre (`<id>_<slug>.md`)."""
    return {p.name.split("_", 1)[0] for p in (repo / "catalogacion" / "fichas").glob("*.md") if p.name.split("_", 1)[0].isdigit()}


def catalogacion(repo: Path = REPO) -> list[dict]:
    """`catalogacion/resumen_catalogacion.tsv`: una fila por libro catalogado, con si tiene ficha canónica."""
    con_ficha = ids_con_ficha(repo)
    filas = []
    for f in leer_tsv(repo / "catalogacion" / "resumen_catalogacion.tsv"):
        f = dict(f)
        f["ficha"] = "sí" if f.get("id", "") in con_ficha else "no"
        f["nivel"] = "positivo" if f["ficha"] == "sí" else "neutro"
        filas.append(f)
    return filas


def leer_ficha(ruta: Path) -> dict:
    """El frontmatter y el título de una ficha canónica (solo las primeras líneas)."""
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError:
        return {}
    m = _FRONTMATTER.match(texto)
    datos: dict = {}
    if m:
        bloque = None
        for linea in m.group(1).splitlines():
            if not linea.strip():
                continue
            if not linea.startswith(" ") and ":" in linea:
                clave, _, valor = linea.partition(":")
                bloque = clave.strip() if valor.strip() == "" else None
                datos[clave.strip()] = valor.strip()
            elif bloque and ":" in linea:
                clave, _, valor = linea.strip().partition(":")
                datos[f"{bloque}.{clave.strip()}"] = valor.strip()
    t = _TITULO_FICHA.search(texto)
    datos["titulo"] = t.group(1) if t else ruta.stem
    return datos


def fichas(repo: Path = REPO) -> list[dict]:
    """Las fichas canónicas de `catalogacion/fichas/`, con su `calibre_id`, proyecto y estado de verificación."""
    carpeta = repo / "catalogacion" / "fichas"
    filas = []
    for p in sorted(carpeta.glob("*.md")):
        d = leer_ficha(p)
        estado = d.get("verificacion.estado", "") or "pendiente"
        nivel = {"verificada": "positivo", "observada": "activo", "pendiente": "neutro"}.get(estado, "")
        filas.append({"ficha": p.name, "calibre_id": d.get("calibre_id", ""), "titulo": d.get("titulo", p.stem),
                      "proyecto": d.get("proyecto", ""), "verificacion": estado, "nivel": nivel, "zotero_key": d.get("zotero_key", ""),
                      "clave": d.get("clave_bibtex", ""), "ruta": str(p)})
    return filas


def raices_vigiladas(env, repo: Path = REPO) -> list[Path]:
    """Las mismas raíces que recorre `manifiesto/main.py todo` (`config.RAICES_VIGILADAS`)."""
    return [repo / "entrada", Path(env.DATAFW_DIR) / "data" / "raw", Path(env.WRITING_DIR)]


def manifiestos(env, repo: Path = REPO) -> list[dict]:
    """Los proyectos con `fuentes.yml` en las raíces vigiladas: entradas, cuántas sin libro, cuándo se generó."""
    try:
        import yaml
    except ImportError:         # pragma: no cover
        yaml = None
    docs = Path(env.DOCS_ROOT)
    filas = []
    for raiz in raices_vigiladas(env, repo):
        if not raiz.is_dir():
            continue
        for p in sorted(raiz.rglob("fuentes.yml")):
            if any(x in _OMITIR for x in p.parts):
                continue
            entradas, sin_libro, generado, proyecto = 0, 0, "", p.parent.name
            if yaml is not None:
                try:
                    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                    lista = d.get("fuentes") or []
                    entradas = len(lista)
                    sin_libro = sum(1 for e in lista if not (e or {}).get("calibre_id"))
                    generado = str(d.get("generado") or "")
                    proyecto = str(d.get("proyecto") or proyecto)
                except (OSError, ValueError, AttributeError):
                    pass
            try:
                carpeta = str(p.parent.relative_to(docs))
            except ValueError:
                carpeta = str(p.parent)
            filas.append({"proyecto": proyecto, "carpeta": carpeta, "entradas": entradas, "sin_libro": sin_libro, "generado": generado,
                          "ruta": str(p), "nivel": "negativo" if sin_libro else "positivo"})
    return filas


# ------------------------------------------------------------------------------------------ la coherencia
def notas_sin_enlazar(indice: dict) -> list[dict]:
    """Los libros sin «apuntes» cuya nota de lectura ya existe (lo mismo que `lib/enlazar_notas.pendientes`)."""
    return [{"id": b, **d} for b, d in indice.get("libros", {}).items()
            if not d.get("apuntes") and d.get("nota") and Path(d["nota"]).is_file()]


def coherencia(indice: dict, fichas_: list[dict], catalogacion_: list[dict]) -> list[dict]:
    """Las comprobaciones de coherencia, calculadas sin correr nada: nombre, recuento, nivel, la operación que lo
    resuelve y los primeros afectados."""
    lista = libros(indice)
    ids = set(indice.get("libros", {}))
    con_ficha = {f["calibre_id"] for f in fichas_}

    def comp(nombre, afectados, operacion, nivel_si_hay="negativo", titulo=lambda d: d.get("titulo", "")):
        n = len(afectados)
        return {"comprobacion": nombre, "cuantos": n, "resultado": "en orden" if n == 0 else f"{n}",
                "nivel": "positivo" if n == 0 else nivel_si_hay, "operacion": operacion,
                "afectados": [titulo(d) for d in afectados[:25]]}

    salida = [
        comp("Libros sin clave de Zotero", [d for d in lista if not d.get("zotero_key")], "enlazar_zotero"),
        comp("Libros sin clave para citar", [d for d in lista if d.get("zotero_key") and not d.get("clave")], "zotero_calibre"),
        comp("Libros sin archivo", [d for d in lista if not d.get("formatos")], "indice"),
        comp("Notas de lectura sin enlazar", notas_sin_enlazar(indice), "notas"),
        comp("Libros sin ficha canónica", [d for d in lista if not d.get("fichas")], "catalogacion", "neutro"),
        comp("Fichas sin libro en el índice", [f for f in fichas_ if f.get("calibre_id") and f["calibre_id"] not in ids], "indice",
             titulo=lambda f: f.get("ficha", "")),
        comp("Filas de catalogación sin ficha", [f for f in catalogacion_ if f.get("ficha") != "sí"], "catalogacion", "neutro",
             titulo=lambda f: f.get("titulo", "")),
    ]
    g = antiguedad_indice(indice)
    salida.append({"comprobacion": "Índice de libros", "cuantos": 0 if ids else 1,
                   "resultado": f"{len(ids)} libros · generado {g}" if ids else "no hay índice", "nivel": "positivo" if ids else "negativo",
                   "operacion": "indice", "afectados": []})
    return salida
