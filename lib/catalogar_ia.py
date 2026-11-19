#!/usr/bin/env python3
"""lib/catalogar_ia.py — catalogar con un chat: el prompt del paso 02 con la portada del documento, y la respuesta pegada,
comprobada sin IA y guardada en su registro tras revisarla; sin llamar a ningún modelo.

Objetivo: lo que `identificar` adivina mal (el título de una revista por título, la OIT por autor) o lo que la catalogación
  de un libro ya en Calibre dejó con confianza baja se corrige con el prompt del Método Documental
  (`prompts/skills/fuentes-documentales/references/paso-02-catalogar.md`) desde Biblioteca Studio: Método › Entrada (una
  fila de `ingesta/pendientes.tsv`) o Método › Catalogar (una fila de `catalogacion/resumen_catalogacion.tsv`).
Método: `prompt` lee el prompt del disco, rellena su «4 Entrada» (el archivo, su carpeta, `pdfinfo` y el texto de las
  primeras hojas, la ficha heurística que hay que corregir y los vocabularios cerrados de Calibre: clasificador, item_type
  y las etiquetas más usadas), lo traduce para un chat externo (`ayuda_ia.para_ia_externa`) y pide de vuelta un solo
  bloque ```yaml `tipo: catalogacion`. `leer` comprueba lo pegado sin IA: tipo de Zotero, clasificador e item_type dentro
  de su enumeración, autores en `Nombre, Apellidos` con ` & ` y sin «Desconocido», fecha que no esté en el futuro, serie
  e índice juntos, etiquetas solo de las que ya existen en Calibre (una nueva se quita y se propone en la nota), y las
  grafías de autor parecidas a una que ya existe. `guardar` reescribe solo esa fila del registro (simula por defecto).
Fundamento: decisiones §9.5 (los prompts en los studios: copiar, pegar, comprobar, aceptar) y §9.15 (esta herramienta);
  el paso 02 del Método Documental.
Límite: no es una puerta: Calibre y Zotero se leen en solo lectura y nada se escribe en ellos. Lo guardado lo aplica
  después la suite de siempre («Catalogar en Calibre» o «Aplicar la catalogación», F5 simula y Ctrl+Intro aplica).

    python3 lib/catalogar_ia.py prompt entrada <ruta del archivo>        # el prompt, a la salida estándar
    python3 lib/catalogar_ia.py prompt catalogar <calibre_id>
    python3 lib/catalogar_ia.py leer catalogar 9894 respuesta.md          # comprueba (o «-» para la entrada estándar)
    python3 lib/catalogar_ia.py guardar catalogar 9894 respuesta.md [--aplicar]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROMPT = "skills/fuentes-documentales/references/paso-02-catalogar.md"
HOJAS = 3                  # las primeras hojas del PDF: portada, página legal y algo del índice
MAX_TEXTO = 9000           # caracteres del texto de la portada que van en el prompt
MAX_ETIQUETAS = 160        # las más usadas de Calibre, como vocabulario en el prompt
REGISTROS = {
    "entrada": {"ruta": "ingesta/pendientes.tsv", "nombre": "pendientes.tsv de la ingesta"},
    "catalogar": {"ruta": "catalogacion/resumen_catalogacion.tsv", "nombre": "resumen_catalogacion.tsv"},
}
CAMPOS = ("autores", "titulo", "tipo_zotero", "clasificador", "item_type", "editorial", "fecha", "identificador", "idioma",
          "tags", "serie", "serie_index", "confianza", "nota")
ROTULOS = {"autores": "Autores", "titulo": "Título", "tipo_zotero": "Tipo de Zotero", "clasificador": "Clasificador",
           "item_type": "Item type", "editorial": "Editorial", "fecha": "Fecha", "identificador": "Identificadores",
           "idioma": "Idioma", "tags": "Etiquetas", "serie": "Serie", "serie_index": "Índice de serie", "confianza": "Confianza",
           "nota": "Nota"}
TIPOS_ZOTERO = ("Artwork", "Audio Recording", "Bill", "Blog Post", "Book", "Book Section", "Case", "Computer Program",
                "Conference Paper", "Dataset", "Dictionary Entry", "Document", "Email", "Encyclopedia Article", "Film",
                "Forum Post", "Hearing", "Instant Message", "Interview", "Journal Article", "Letter", "Magazine Article",
                "Manuscript", "Map", "Newspaper Article", "Patent", "Podcast", "Preprint", "Presentation", "Radio Broadcast",
                "Report", "Standard", "Statute", "Thesis", "TV Broadcast", "Video Recording", "Webpage")
ANONIMOS = {"desconocido", "varios autores", "varios", "anonimo", "anónimo", "s/a", "sin autor"}
CONFIANZAS = ("alta", "media", "baja")
RE_FECHA = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
RE_CLAVE_BIB = re.compile(r"^[a-z]+\d{4}[a-z]+$")

FORMATO_DE_VUELTA = """## Formato de vuelta para Biblioteca Studio (manda sobre el «7 Formato de salida» del prompt)
Devuelve un solo bloque de código `yaml` con estas claves, y nada más dentro del bloque. Fuera de él, si quieres, la
justificación en dos o tres líneas. Biblioteca Studio lo comprueba sin IA y lo muestra como cambio sugerido: la persona lo
acepta o lo descarta.

```yaml
tipo: catalogacion
autores: "Nombre, Apellidos & Nombre, Apellidos"   # corporativos completos y sin invertir; anónimo real = Unknown
titulo: "Título en frase, en el idioma del documento"
tipo_zotero: Report                  # uno de los tipos de Zotero (Book, Book Section, Journal Article, Report, Thesis…)
clasificador: Informe técnico        # solo de la lista «clasificador» de la entrada
item_type: Report                    # solo de la lista «item_type» de la entrada (vacío si ninguno encaja)
editorial: ""
fecha: 2024                          # año del documento (o AAAA-MM-DD); nunca la fecha de descarga
identificador: "isbn:…, doi:…, url:…"   # solo los que estén en el documento, limpios
idioma: Spanish                      # nombre completo en inglés, como Calibre
tags: [disciplina, asignatura, metodo]   # de 2 a 4, solo del vocabulario de la entrada; una nueva, en «nota»
serie: ""                            # serie e índice juntos, o los dos vacíos
serie_index: ""
confianza: alta                      # alta · media · baja
verificar: []                        # los datos que no salen del documento: «campo: qué falta»
nota: ""                             # breve: qué baja la confianza, etiqueta nueva propuesta, edición…
```

- Nada inventado: lo que no esté en el texto de la entrada va vacío y en `verificar`, y la confianza baja.
- Las comillas dobles, en los valores con dos puntos, comas o el signo &."""


# --- entorno, prompt y módulos cargados por su ruta ----------------------------------------------------------------------

def _cargar(nombre: str, ruta: Path):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


def _ayuda():
    return _cargar("biblioteca_ayuda_ia", RAIZ / "lib" / "ayuda_ia.py")


def _rutas():
    return _cargar("biblioteca_rutas", RAIZ / "lib" / "rutas.py")


def _env():
    return _ayuda()._env()


def _db() -> Path:
    lib = os.environ.get("BIBLIOTECA") or os.environ.get("QIR_BIBLIOTECA")
    if lib:
        return Path(lib) / "metadata.db"
    return Path(os.environ.get("CALIBRE_DB") or _env().CALIBRE_DB)


def _leer_db():
    db = _db()
    if not db.is_file():
        return None
    return sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def vocabularios() -> dict:
    """Los vocabularios cerrados de Calibre, en solo lectura (las columnas se resuelven por etiqueta, nunca por número):
    {clasificador, item_type, etiquetas (las más usadas primero), autores, leido: bool}."""
    v = {"clasificador": [], "item_type": [], "etiquetas": [], "autores": [], "leido": False}
    con = _leer_db()
    if con is None:
        return v
    try:
        for etiqueta in ("clasificador", "item_type"):
            r = con.execute("select display from custom_columns where label=?", (etiqueta,)).fetchone()
            if r:
                try:
                    v[etiqueta] = list(json.loads(r[0]).get("enum_values") or [])
                except ValueError:
                    pass
        v["etiquetas"] = [t for (t,) in con.execute(
            "select t.name from tags t left join books_tags_link l on l.tag=t.id group by t.id order by count(l.book) desc, t.name")]
        v["autores"] = [a.replace("|", ",") for (a,) in con.execute("select name from authors")]
        v["leido"] = True
    except sqlite3.Error:
        pass
    finally:
        con.close()
    return v


# --- el registro (pendientes.tsv o resumen_catalogacion.tsv) -------------------------------------------------------------

def _ruta_registro(registro: str, repo: Path | None = None) -> Path:
    if registro not in REGISTROS:
        raise ValueError(f"Registro desconocido: {registro} (entrada o catalogar).")
    return Path(repo or RAIZ) / REGISTROS[registro]["ruta"]


def _leer_tsv(ruta: Path) -> tuple[list[str], list[dict]]:
    if not ruta.is_file():
        raise LookupError(f"No existe {ruta.name}: no hay fila que catalogar.")
    with open(ruta, encoding="utf-8", newline="") as fh:
        lector = csv.DictReader(fh, delimiter="\t")
        return list(lector.fieldnames or []), [dict(r) for r in lector]


def _coincide(registro: str, fila: dict, clave: str, repo: Path) -> bool:
    if registro == "catalogar":
        return str(fila.get("id", "")).strip() == str(clave).strip()
    if re.fullmatch(r"[0-9a-f]{64}", clave or ""):
        return fila.get("sha256") == clave
    destino = _rutas().resolver(fila.get("origen", ""), repo / "entrada")
    try:
        return destino is not None and Path(destino).resolve() == Path(clave).resolve()
    except OSError:
        return False


def fila(registro: str, clave: str, repo: Path | None = None) -> dict:
    """La fila del registro: en Entrada, por la ruta del archivo (o su SHA-256); en Catalogar, por el id de Calibre."""
    repo = Path(repo or RAIZ)
    _cols, filas = _leer_tsv(_ruta_registro(registro, repo))
    for f in filas:
        if _coincide(registro, f, clave, repo):
            return f
    if registro == "entrada":
        raise LookupError("Ese archivo aún no está identificado: corre «Identificar» (Entrada) y vuelve a intentarlo.")
    raise LookupError(f"El libro {clave} no tiene fila en resumen_catalogacion.tsv.")


def archivo_de(registro: str, f: dict, clave: str, repo: Path | None = None) -> Path | None:
    repo = Path(repo or RAIZ)
    if registro == "entrada":
        r = _rutas().resolver(f.get("origen", ""), repo / "entrada")
        return Path(r) if r else None
    try:
        bib = _cargar("biblioteca_core", Path(os.environ.get("PY_COMMON") or _env().PY_COMMON) / "biblioteca.py")
        d = bib.datos(int(clave)) or {}
        return Path(d["ruta"]) if d.get("ruta") else None
    except Exception:  # noqa: BLE001 — sin la biblioteca, el prompt va sin el texto
        return None


def _zotero_key(clave: str) -> str:
    con = _leer_db()
    if con is None:
        return ""
    try:
        col = con.execute("select id from custom_columns where label='zotero_key'").fetchone()
        if not col:
            return ""
        r = con.execute(f"select value from custom_column_{int(col[0])} where book=?", (int(clave),)).fetchone()
        return r[0] if r and r[0] else ""
    except (sqlite3.Error, ValueError):
        return ""
    finally:
        con.close()


# --- el texto del documento ----------------------------------------------------------------------------------------------

def texto_portada(archivo: Path | None, hojas: int = HOJAS, maximo: int = MAX_TEXTO) -> tuple[str, str]:
    """(pdfinfo, texto de las primeras hojas) de un PDF; vacíos si no lo es o no hay herramientas."""
    if archivo is None or not archivo.is_file() or archivo.suffix.lower() != ".pdf":
        return "", ""
    info = texto = ""
    try:
        r = subprocess.run(["pdfinfo", str(archivo)], capture_output=True, text=True, timeout=30)
        info = "\n".join(ln for ln in r.stdout.splitlines()
                         if ln.split(":", 1)[0] in ("Title", "Author", "Subject", "Keywords", "Creator", "Producer", "CreationDate", "Pages"))
        for n in (hojas, hojas * 2):     # una portada que es una imagen: unas hojas más, hasta dar con texto
            r = subprocess.run(["pdftotext", "-f", "1", "-l", str(n), "-layout", str(archivo), "-"],
                               capture_output=True, text=True, timeout=60)
            if len(r.stdout.strip()) > 400:
                break
        texto = re.sub(r"[ \t]+\n", "\n", r.stdout)
        texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if len(texto) > maximo:
        texto = texto[:maximo].rsplit("\n", 1)[0] + "\n[… cortado]"
    return info, texto


# --- el prompt -----------------------------------------------------------------------------------------------------------

def prompt(registro: str, clave: str, repo: Path | None = None) -> dict:
    """El prompt del paso 02 para una fila, traducido, con su «4 Entrada» rellena.
    → {prompt, fuente, archivo, titulo, conTexto, largo, aviso, problemas}."""
    repo = Path(repo or RAIZ)
    a = _ayuda()
    f = fila(registro, clave, repo)
    archivo = archivo_de(registro, f, clave, repo)
    info, texto = texto_portada(archivo)
    v = vocabularios()
    texto_prompt = a.leer_prompt(PROMPT)
    fuente = a._fuente(PROMPT, texto_prompt)
    nombre = archivo.name if archivo else (f.get("origen") or "")
    carpeta = ""
    if registro == "entrada":
        partes = Path(f.get("origen", "")).parts
        carpeta = partes[-2] if len(partes) > 1 else "entrada/ (sin subcarpeta)"
    ficha = "\n".join(f"{c}: {f.get(c, '')}" for c in CAMPOS if c in f)
    if registro == "entrada":
        veredicto = "no existe: la ingesta comprobó por su huella (SHA-256) que el archivo no está en Calibre"
        camino = f"Archivo en la zona de entrada: {nombre}"
    else:
        veredicto = f"el libro ya está en Calibre (id {clave}): se corrige su catalogación"
        camino = f"Libro {clave} de Calibre; su archivo: {nombre or 'sin archivo'}"
    clave_bib = Path(nombre).stem if RE_CLAVE_BIB.match(Path(nombre).stem or "") else ""
    entrada = [
        f"Veredicto del paso 00: {veredicto}.",
        camino + ".",
        f"Carpeta de origen (serie): {carpeta or '—'}.",
        "Metadatos del PDF (pdfinfo; el Author del PDF no es el autor):\n" + (info or "(sin pdfinfo)"),
        "Texto de las primeras hojas:\n" + (texto or "(sin texto: ¿escaneado sin OCR? Márcalo «OCR pendiente» y baja la confianza)"),
        "Ficha heurística que hay que corregir:\n" + ficha,
        "Proyecto y clave_bibtex: " + (f"el nombre del archivo es la clave de cita {clave_bib} de un trabajo de escritura" if clave_bib else "ninguno") + ".",
        "Uso: catalogación desde Biblioteca Studio.",
        "Vocabulario «clasificador» (enumeración de Calibre): " + (", ".join(v["clasificador"]) or "(no se pudo leer)") + ".",
        "Vocabulario «item_type» (enumeración de Calibre): " + (", ".join(v["item_type"]) or "(no se pudo leer)") + ".",
        f"Vocabulario de etiquetas (las {MAX_ETIQUETAS} más usadas de Calibre; solo estas): "
        + (", ".join(v["etiquetas"][:MAX_ETIQUETAS]) or "(no se pudo leer)") + ".",
    ]
    bloques = [f"# {fuente['titulo']}",
               f"(Versión {fuente['version'] or '—'} de este prompt. Su sección «4 Entrada» la trae el bloque «entrada» de abajo: "
               "no hace falta abrir nada más ni correr ningún comando; los pasos 7 y 8 de aplicar los hace Biblioteca Studio.)",
               a.para_ia_externa(texto_prompt).strip(),
               "<entrada>\n" + "\n\n".join(entrada) + "\n</entrada>",
               FORMATO_DE_VUELTA]
    salida = "\n\n".join(bloques)
    largo = len(salida) > a.LARGO
    return {"prompt": salida, "fuente": fuente, "archivo": str(archivo or ""), "titulo": f.get("titulo", "") or nombre,
            "conTexto": bool(texto), "largo": largo,
            "aviso": "El prompt es largo para un chat externo: puede cortarse." if largo else
                     ("" if texto else "El documento no tiene texto extraíble: el chat solo verá el nombre y la ficha heurística."),
            "problemas": a.problemas_externos(salida)}


# --- lo pegado -----------------------------------------------------------------------------------------------------------

def _bloque(pegado: str) -> str:
    t = (pegado or "").replace("\r\n", "\n")
    for m in re.finditer(r"```[ \t]*(?:yaml|yml)?[ \t]*\n(.*?)\n[ \t]*```", t, re.S | re.I):
        if re.search(r"^\s*tipo\s*:\s*[\"']?catalogacion", m.group(1), re.M):
            return m.group(1)
    m = re.search(r"^tipo\s*:\s*[\"']?catalogacion.*", t, re.M | re.S)
    return m.group(0) if m else ""


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return ", ".join(_texto(x) for x in valor if _texto(x))
    if isinstance(valor, (dt.date, dt.datetime)):
        return valor.isoformat()[:10]
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\s+", " ", str(valor)).strip()


def _apellidos(nombre: str) -> set[str]:
    partes = nombre.split(",", 1)
    return {t for t in _plano(partes[1] if len(partes) > 1 else partes[0]).split() if len(t) > 3}


def _nombres(nombre: str) -> set[str]:
    partes = nombre.split(",", 1)
    return {t for t in _plano(partes[0]).split() if len(t) > 1} if len(partes) > 1 else set()


def _parecidos(autor: str, existentes: list[str]) -> list[str]:
    """Grafías de Calibre que serían la misma persona: igual sin tildes, o los mismos apellidos y algún nombre en común."""
    plano = _plano(autor)
    iguales = [e for e in existentes if _plano(e) == plano]
    if iguales:
        return iguales[:3]
    ap, no = _apellidos(autor), _nombres(autor)
    if not ap:
        return []
    return [e for e in existentes if ap <= _apellidos(e) and (not no or no & _nombres(e))][:3]


def leer(registro: str, clave: str, pegado: str, repo: Path | None = None, hoy: dt.date | None = None) -> dict:
    """Lo pegado, comprobado sin IA contra la fila y los vocabularios de Calibre.
    → {ok, campos (los que se guardarían), cambios [{campo, rotulo, antes, despues}], problemas [], avisos [], verificar []}."""
    import yaml
    repo = Path(repo or RAIZ)
    hoy = hoy or dt.date.today()
    f = fila(registro, clave, repo)
    cols, _ = _leer_tsv(_ruta_registro(registro, repo))
    problemas: list[str] = []
    avisos: list[str] = []
    bloque = _bloque(pegado)
    if not bloque:
        return {"ok": False, "campos": {}, "cambios": [], "verificar": [], "avisos": [],
                "problemas": ["No hay un bloque ```yaml con «tipo: catalogacion»: pide al chat el formato de vuelta del prompt."]}
    try:
        d = yaml.safe_load(bloque)
    except yaml.YAMLError as e:
        return {"ok": False, "campos": {}, "cambios": [], "verificar": [], "avisos": [],
                "problemas": [f"El bloque YAML no se puede leer: {str(e).splitlines()[0]}. Suele ser un valor con dos puntos sin comillas."]}
    if not isinstance(d, dict):
        return {"ok": False, "campos": {}, "cambios": [], "verificar": [], "avisos": [], "problemas": ["El bloque YAML no es un mapa de campos."]}
    v = vocabularios()
    campos = {}
    for c in CAMPOS:
        if c not in d:
            continue
        valor = d[c]
        if c == "autores" and isinstance(valor, (list, tuple)):
            campos[c] = " & ".join(_texto(x) for x in valor if _texto(x))
        else:
            campos[c] = _texto(valor)
    verificar = [_texto(x) for x in (d.get("verificar") or []) if _texto(x)] if isinstance(d.get("verificar"), list) else \
                ([_texto(d.get("verificar"))] if _texto(d.get("verificar")) else [])

    # obligatorios y enumeraciones
    if not campos.get("titulo"):
        problemas.append("Falta el título.")
    elif campos["titulo"].isupper() and len(campos["titulo"]) > 12:
        avisos.append("El título está en mayúsculas: va en frase.")
    if not campos.get("autores"):
        problemas.append("Faltan los autores (anónimo real: Unknown).")
    else:
        for a in (x.strip() for x in campos["autores"].split("&")):
            if _plano(a) in ANONIMOS:
                problemas.append(f"«{a}» no es un autor: el anónimo real es Unknown.")
    tz = campos.get("tipo_zotero", "")
    if tz and tz not in TIPOS_ZOTERO:
        casi = next((t for t in TIPOS_ZOTERO if t.lower() == tz.lower()), "")
        if casi:
            campos["tipo_zotero"] = casi
        else:
            problemas.append(f"«{tz}» no es un tipo de Zotero.")
    for c in ("clasificador", "item_type"):
        valor = campos.get(c, "")
        if valor and v[c] and valor not in v[c]:
            casi = next((x for x in v[c] if _plano(x) == _plano(valor)), "")
            if casi:
                campos[c] = casi
            else:
                problemas.append(f"«{valor}» no está en la enumeración de {c} de Calibre.")
    if not v["leido"]:
        avisos.append("No se pudo leer la biblioteca de Calibre: el clasificador, item_type, las etiquetas y los autores no se cotejaron.")
    fecha = campos.get("fecha", "")
    if fecha:
        if not RE_FECHA.match(fecha):
            problemas.append(f"La fecha «{fecha}» no es AAAA ni AAAA-MM-DD.")
        elif int(fecha[:4]) > hoy.year:
            problemas.append(f"La fecha {fecha} está en el futuro.")
    conf = campos.get("confianza", "").lower()
    if conf and conf not in CONFIANZAS:
        problemas.append(f"La confianza «{campos['confianza']}» no es alta, media ni baja.")
    elif conf:
        campos["confianza"] = conf
    if (conf == "alta") and (verificar or "[VERIFICAR]" in " ".join(campos.values())):
        avisos.append("Confianza alta con datos por verificar: revísalos antes de aplicar.")

    # serie e índice, juntos
    if "serie" in cols or "serie_index" in cols:
        serie, indice = campos.get("serie", f.get("serie", "")), campos.get("serie_index", f.get("serie_index", ""))
        if bool(serie) != bool(indice):
            problemas.append("Serie e índice van juntos: los dos o ninguno.")

    # etiquetas: solo del vocabulario; las nuevas se quitan y se proponen en la nota
    if "tags" in campos:
        etiquetas = [t.strip() for t in campos["tags"].split(",") if t.strip()]
        if v["leido"]:
            conocidas = set(v["etiquetas"])
            nuevas = [t for t in etiquetas if t not in conocidas]
            if nuevas:
                etiquetas = [t for t in etiquetas if t in conocidas]
                avisos.append("Etiquetas que no existen en Calibre, quitadas y propuestas en la nota: " + ", ".join(nuevas) + ".")
                campos["nota"] = "; ".join(x for x in (campos.get("nota", ""), "etiquetas propuestas: " + ", ".join(nuevas)) if x)
        if not etiquetas and f.get("tags"):
            avisos.append("Ninguna etiqueta propuesta existe en Calibre: se conservan las de la fila.")
            etiquetas = [t.strip() for t in f["tags"].split(",") if t.strip()]
        elif not 2 <= len(etiquetas) <= 4:
            avisos.append(f"Quedan {len(etiquetas)} etiquetas: el método pide de 2 a 4.")
        campos["tags"] = ", ".join(etiquetas)

    # grafías de autor parecidas a una existente
    if v["leido"] and campos.get("autores"):
        existentes = set(v["autores"])
        for a in (x.strip() for x in campos["autores"].split("&")):
            if not a or a in existentes or _plano(a) in ANONIMOS or a == "Unknown":
                continue
            parecidos = _parecidos(a, v["autores"])
            if parecidos:
                avisos.append(f"«{a}» no está en Calibre, pero sí " + ", ".join(f"«{p}»" for p in parecidos) + ": si es la misma persona, usa esa grafía.")

    # lo que el registro no puede guardar
    sin_columna = [c for c in campos if c not in cols]
    if sin_columna:
        avisos.append(f"{REGISTROS[registro]['nombre']} no tiene columna para " + ", ".join(ROTULOS[c].lower() for c in sin_columna)
                      + ": no se guarda" + ("n." if len(sin_columna) > 1 else "."))
        for c in sin_columna:
            campos.pop(c)

    # la nota dice de dónde salió; los datos por verificar van en ella
    marca = f"revisada con un chat y por el autor el {hoy.isoformat()}"
    extra = ("por verificar: " + "; ".join(verificar)) if verificar else ""
    nota = campos.get("nota", f.get("nota", ""))
    campos["nota"] = "; ".join(x for x in (nota, extra, marca) if x)

    # título o autores de un libro que ya tiene ítem en Zotero
    if registro == "catalogar" and any(campos.get(c) and campos[c] != f.get(c, "") for c in ("titulo", "autores")) and _zotero_key(clave):
        avisos.append("El libro ya tiene ítem en Zotero: cambiar título o autores en Calibre mueve su carpeta; "
                      "va con una campaña que reescriba Zotero en la misma operación (CLAUDE.md).")

    cambios = [{"campo": c, "rotulo": ROTULOS[c], "antes": f.get(c, ""), "despues": campos[c]}
               for c in CAMPOS if c in campos and campos[c] != f.get(c, "")]
    if not cambios:
        avisos.append("Lo pegado no cambia nada de la fila.")
    return {"ok": not problemas, "campos": campos, "cambios": cambios, "problemas": problemas, "avisos": avisos, "verificar": verificar}


# --- guardar -------------------------------------------------------------------------------------------------------------

def guardar(registro: str, clave: str, pegado: str, aplicar: bool = False, repo: Path | None = None,
            hoy: dt.date | None = None) -> dict:
    """Reescribe solo la fila del registro con lo comprobado (simula si no `aplicar`); con problemas, no escribe.
    → lo de `leer` + {escrito, ruta}."""
    repo = Path(repo or RAIZ)
    r = leer(registro, clave, pegado, repo, hoy)
    r.update({"escrito": False, "ruta": str(_ruta_registro(registro, repo))})
    if not r["ok"] or not r["cambios"] or not aplicar:
        return r
    ruta = _ruta_registro(registro, repo)
    cols, filas = _leer_tsv(ruta)
    hecho = 0
    for f in filas:
        if _coincide(registro, f, clave, repo):
            f.update({c: v.replace("\t", " ").replace("\n", " ") for c, v in r["campos"].items()})
            hecho += 1
            break
    if not hecho:
        raise LookupError("La fila ya no está en el registro: vuelve a leerlo (F6).")
    buf = io.StringIO()
    if registro == "entrada":            # como lo escribe `identificar` (csv.DictWriter), con el fin de línea del archivo
        w = csv.DictWriter(buf, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for f in filas:
            w.writerow({k: f.get(k, "") for k in cols})
    else:                                # la catalogación lo lee en Bash, por tabuladores: sin comillas
        buf.write("\t".join(cols) + "\n")
        for f in filas:
            buf.write("\t".join((f.get(k) or "") for k in cols) + "\n")
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(buf.getvalue(), encoding="utf-8", newline="")
    os.replace(temporal, ruta)
    r["escrito"] = True
    return r


# --- CLI -----------------------------------------------------------------------------------------------------------------

def _pegado(origen: str) -> str:
    return sys.stdin.read() if origen == "-" else Path(origen).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="catalogar_ia.py", description="Catalogar con un chat: el prompt del paso 02 y la respuesta, comprobada sin IA.")
    sub = p.add_subparsers(dest="orden", required=True)
    for orden in ("prompt", "leer", "guardar"):
        s = sub.add_parser(orden)
        s.add_argument("registro", choices=tuple(REGISTROS))
        s.add_argument("clave", help="entrada: la ruta del archivo (o su SHA-256); catalogar: el id de Calibre")
        if orden != "prompt":
            s.add_argument("respuesta", help="el archivo con lo que respondió el chat, o «-» para la entrada estándar")
        if orden == "guardar":
            s.add_argument("--aplicar", action="store_true", help="escribe la fila (sin él, simula)")
        s.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.orden == "prompt":
            r = prompt(a.registro, a.clave)
            if not a.json:
                print(r["prompt"])
                if r["aviso"]:
                    print(f"[AVISO] {r['aviso']}", file=sys.stderr)
                return 0
        elif a.orden == "leer":
            r = leer(a.registro, a.clave, _pegado(a.respuesta))
        else:
            r = guardar(a.registro, a.clave, _pegado(a.respuesta), aplicar=a.aplicar)
    except (LookupError, ValueError, OSError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok", True) else 4
    for c in r["cambios"]:
        print(f"{c['rotulo']}: «{c['antes']}» → «{c['despues']}»")
    for x in r["problemas"]:
        print(f"[PROBLEMA] {x}")
    for x in r["avisos"]:
        print(f"[AVISO] {x}")
    if a.orden == "guardar":
        print("Escrito en " + r["ruta"] if r["escrito"] else ("No se escribe: hay problemas." if r["problemas"] else "Simulación: --aplicar escribe la fila."))
    return 0 if r["ok"] else 4


if __name__ == "__main__":
    sys.exit(main())
