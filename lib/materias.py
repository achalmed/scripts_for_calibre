#!/usr/bin/env python3
"""lib/materias.py — de qué trata cada obra según los catálogos abiertos, con caché (decisiones §9.20).

Objetivo: que el mapa de la biblioteca (§9.19) diga de qué trata un libro aunque nadie lo haya leído. Los conceptos
  del mapa salen de las sesiones guiadas de Ñawinchay, así que solo existen donde ya se estudió; las materias de los
  catálogos existen para toda obra publicada, y llenan el resto del mapa sin leer una página.
Método: SOLO LEE el índice compartido (`lib/indice.py`, que ya resolvió el `doi` y el `isbn` de cada libro en solo
  lectura) y consulta una vez por obra, según lo que tenga:
  · DOI → `api.openalex.org/works/doi:<doi>` (CC0): sus `topics` con score ≥ 0,05 —con su jerarquía materia >
    subcampo > campo > dominio— y sus `keywords`. Los `concepts` heredados no se usan: traen ruido («Perspective
    (graphical)» en un artículo de política monetaria).
  · ISBN → `openlibrary.org/isbn/<isbn>.json` y, si lo tiene, su `work` (ahí suelen estar las materias de verdad).
    Son materias de catálogo bibliotecario: irregulares, en varios idiomas y con nombres de autor colados como
    materia, así que se filtran los que parecen personas y se toman las primeras `TOPE_OL`.
  Una obra con DOI y con ISBN se consulta en las dos, y cada fuente guarda lo suyo por separado.
  La caché vive en `$XDG_STATE_HOME/biblioteca/materias.json` (junto al índice y a la de `verificar_ids`, fuera del
  repo y de las bases): lo hallado se vuelve a mirar a los 180 días, lo no hallado a los 30, y un error de red no se
  guarda, para que una caída no se tome por «no está».
Límite: NO ESCRIBE EN NINGUNA BASE — ni en `metadata.db` ni en `zotero.sqlite`, ni por la puerta: esto no es una
  catalogación, es una caché de consulta. El vocabulario cerrado de etiquetas de Calibre es del autor y no se toca:
  las materias viven aparte y en el idioma en que las publica cada catálogo. Sin `--aplicar` no se toca la red.

    python3 lib/materias.py estado                                   # qué hay y qué falta, por fuente (no consulta)
    python3 lib/materias.py traer [--fuente openalex|openlibrary] [--limite N] [--ids 1,2] [--forzar] [--aplicar] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import difflib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

AGENTE = "biblioteca-studio/3 (materias)"
OPENALEX = "https://api.openalex.org/works/doi:"
CAMPOS_OA = "id,title,topics,keywords"
OPENLIBRARY = "https://openlibrary.org"
FUENTES = ("openalex", "openlibrary", "openalex_titulo")
CLAVE = {"openalex": "doi", "openlibrary": "isbn", "openalex_titulo": "titulo"}
EXACTAS = ("openalex", "openlibrary")  # por identificador: lo que `traer` consulta si no se le pide otra cosa
INCIERTAS = ("openalex_titulo",)      # se busca por el título, así que puede dar con otra obra: ver `COINCIDE`
COINCIDE = 0.87                       # parecido mínimo del título; 0,75 basta si además coincide un apellido
COINCIDE_CON_AUTOR = 0.75
CANDIDATOS = 5
VIGENCIA = {"hallado": 180, "no_hallado": 30}
SCORE_MINIMO = 0.05          # por debajo, OpenAlex está adivinando: el tercer topic de una obra venía con 0,0002
TOPE_OL = 12                 # una obra de Open Library llegaba a 63 materias y se comía el recuento de su tema
PAUSA = 0.12                 # cortesía con dos APIs públicas y gratuitas
RATE_LIMIT = 429
# OpenAlex da 1 000 peticiones al día por IP sin clave («free daily budget shared by everyone on your network's IP
# address»), y se reponen a medianoche UTC. Al llegar al tope contesta 429 con `Retry-After`: seguir pidiendo no
# adelanta nada y molesta a una sede gratuita, así que `traer` para en seco y lo dice.
ESPERA: dict = {"segundos": 0}
# «Bueno, Gustavo, 1924-» es un autor que el catálogo guarda como materia. Se reconoce por la coma y el año del
# encabezado, no por tener coma: «Economics, Mathematical» es una materia de verdad y se queda.
PERSONA = re.compile(r",\s*\d{4}\s*-|,\s*\d{4}\s*$")
# Encabezados de catálogo que no dicen nada del tema: «filosofia» salía como «General · Fiction - General · Philosophy».
GENERICAS = {"general", "nonfiction", "non-fiction", "fiction", "fiction - general", "general & literary fiction",
             "miscellanea", "textbooks", "collections", "readers", "general works", "other", "varia"}


# «Spanish: Adult Nonfiction» clasifica al lector y al idioma, no a la obra.
PUBLICO = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]+:\s*(adult|juvenile|young adult|children)\b", re.I)


def util(nombre: str) -> bool:
    """Si la materia dice algo del tema: ni un autor, ni un encabezado genérico de catálogo, ni una marca de público."""
    limpio = (nombre or "").strip().rstrip(".")
    return (bool(limpio) and limpio.lower() not in GENERICAS
            and not PERSONA.search(limpio) and not PUBLICO.match(limpio))


def ruta_cache() -> Path:
    estado = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return estado / "biblioteca" / "materias.json"


def leer_cache(ruta: Path | None = None) -> dict:
    """La caché, con las entradas del formato anterior (una sola fuente por libro) traídas a este sin consultar nada."""
    ruta = ruta or ruta_cache()
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"libros": {}}
    if not isinstance(d, dict) or not isinstance(d.get("libros"), dict):
        return {"libros": {}}
    for b, v in d["libros"].items():
        if isinstance(v, dict) and "estado" in v:          # formato del 2026-11-24 por la mañana: era solo OpenAlex
            d["libros"][b] = {"openalex": v}
    return d


def guardar_cache(cache: dict, ruta: Path | None = None) -> Path:
    ruta = ruta or ruta_cache()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(ruta)
    return ruta


def vigente(entrada: dict | None, hoy: date | None = None) -> bool:
    if not entrada or entrada.get("estado") not in VIGENCIA:
        return False
    try:
        cuando = date.fromisoformat(str(entrada.get("fecha"))[:10])
    except ValueError:
        return False
    return (hoy or date.today()) - cuando <= timedelta(days=VIGENCIA[entrada["estado"]])


def _pedir(url: str, timeout: int = 25):
    """(código HTTP, JSON o None). Un fallo de red da (0, None): nunca se toma por «no está en el catálogo».

    Un 429 (presupuesto agotado) guarda en `ESPERA` lo que la sede pide aguardar, para que `traer` pare en seco."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace") or "null")
    except urllib.error.HTTPError as e:
        if e.code == RATE_LIMIT:
            try:
                ESPERA["segundos"] = int(e.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                ESPERA["segundos"] = 0
        return e.code, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None


# ------------------------------------------------------------------ OpenAlex (por DOI)
def materias_openalex(obra: dict) -> list[dict]:
    salida = []
    for t in obra.get("topics") or []:
        try:
            score = float(t.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score < SCORE_MINIMO or not t.get("display_name"):
            continue
        salida.append({"nombre": t["display_name"], "score": round(score, 4), "tipo": "materia",
                       "subcampo": (t.get("subfield") or {}).get("display_name", ""),
                       "campo": (t.get("field") or {}).get("display_name", ""),
                       "dominio": (t.get("domain") or {}).get("display_name", "")})
    for k in obra.get("keywords") or []:
        if k.get("display_name"):
            salida.append({"nombre": k["display_name"], "score": round(float(k.get("score") or 0), 4),
                           "tipo": "palabra", "subcampo": "", "campo": "", "dominio": ""})
    return salida


def consultar_openalex(doi: str, pedir=_pedir) -> dict:
    hoy = date.today().isoformat()
    codigo, d = pedir(OPENALEX + urllib.parse.quote(doi.strip().lower(), safe="/") + "?select=" + CAMPOS_OA)
    if codigo == 200 and isinstance(d, dict):
        return {"estado": "hallado", "fecha": hoy, "ref": str(d.get("id") or ""),
                "titulo": str(d.get("title") or ""), "materias": materias_openalex(d)}
    if codigo in (403, 404):
        return {"estado": "no_hallado", "fecha": hoy, "materias": []}
    return {"estado": "error", "fecha": hoy, "codigo": codigo, "materias": []}


# ------------------------------------------------------------------ Open Library (por ISBN)
def _nombres_ol(valores) -> list[str]:
    """Los `subjects` de Open Library, sin los que son personas y sin repetir, hasta `TOPE_OL`."""
    fuera, vistos = [], set()
    for s in valores or []:
        nombre = (s.get("name") if isinstance(s, dict) else str(s or "")).strip().rstrip(".")
        clave = nombre.lower()
        if clave in vistos or not util(nombre):
            continue
        vistos.add(clave)
        fuera.append(nombre)
        if len(fuera) >= TOPE_OL:
            break
    return fuera


def consultar_openlibrary(isbn: str, pedir=_pedir) -> dict:
    """La edición y, si la tiene, su obra: las materias de catálogo suelen estar en la obra, no en la edición."""
    hoy = date.today().isoformat()
    limpio = re.sub(r"[^0-9Xx]", "", isbn or "")
    codigo, ed = pedir(f"{OPENLIBRARY}/isbn/{urllib.parse.quote(limpio)}.json")
    if codigo in (403, 404):
        return {"estado": "no_hallado", "fecha": hoy, "materias": []}
    if codigo != 200 or not isinstance(ed, dict):
        return {"estado": "error", "fecha": hoy, "codigo": codigo, "materias": []}
    crudas = list(ed.get("subjects") or [])
    ref = str(ed.get("key") or "")
    for w in (ed.get("works") or [])[:1]:
        c2, obra = pedir(f"{OPENLIBRARY}{w.get('key', '')}.json")
        if c2 == 200 and isinstance(obra, dict):
            ref = str(obra.get("key") or ref)
            crudas += [s for s in (obra.get("subjects") or [])]
    nombres = _nombres_ol(crudas)
    return {"estado": "hallado" if nombres else "no_hallado", "fecha": hoy, "ref": ref,
            "titulo": str(ed.get("title") or ""),
            "materias": [{"nombre": n, "score": 0.0, "tipo": "materia", "subcampo": "", "campo": "", "dominio": ""}
                         for n in nombres]}


# ------------------------------------------------------------------ OpenAlex (por título y autor)
def _plano(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9ñ ]+", " ", t).split())


def _apellidos(autores) -> set[str]:
    """Los apellidos de «Apellido, Nombre» o «Nombre Apellido», en plano, para cotejar con los de OpenAlex."""
    fuera = set()
    for a in autores or []:
        partes = [p for p in re.split(r"[,;&]| y ", str(a)) if p.strip()]
        for p in partes[:1] if "," in str(a) else partes:
            palabras = _plano(p).split()
            if palabras:
                fuera.add(palabras[-1] if "," not in str(a) else palabras[0])
    return {x for x in fuera if len(x) > 2}


def coincide(titulo: str, autores, obra: dict) -> float:
    """Cuánto se parecen, de 0 a 1, el libro de la biblioteca y una obra de OpenAlex. 0 si no llega al umbral.

    El título manda; un apellido en común rebaja el listón, porque las traducciones cambian el título y los
    subtítulos se pierden («Economía internacional» por «International Economics: Theory and Policy»)."""
    mio, suyo = _plano(titulo), _plano(obra.get("title") or "")
    if not mio or not suyo:
        return 0.0
    parecido = difflib.SequenceMatcher(None, mio, suyo).ratio()
    suyos = set()
    for a in obra.get("authorships") or []:
        # un nombre que al quitarle lo que no es latino se queda vacío (ideogramas, cirílico) no da apellido
        palabras = _plano((a.get("author") or {}).get("display_name", "")).split()
        if palabras:
            suyos.add(palabras[-1])
    hay_autor = bool(_apellidos(autores) & {x for x in suyos if len(x) > 2})
    umbral = COINCIDE_CON_AUTOR if hay_autor else COINCIDE
    return round(parecido, 4) if parecido >= umbral else 0.0


def consultar_openalex_titulo(titulo: str, autores=(), pedir=_pedir) -> dict:
    """La obra de OpenAlex que mejor case con el título (y el autor) del libro. Sin coincidencia, `no_hallado`."""
    hoy = date.today().isoformat()
    busca = _plano(titulo)[:180]
    if len(busca) < 8:                      # un título de dos palabras encuentra cualquier cosa
        return {"estado": "no_hallado", "fecha": hoy, "materias": []}
    url = (f"https://api.openalex.org/works?filter=title.search:{urllib.parse.quote(busca)}"
           f"&select={CAMPOS_OA},authorships&per-page={CANDIDATOS}")
    codigo, d = pedir(url)
    if codigo in (403, 404):
        return {"estado": "no_hallado", "fecha": hoy, "materias": []}
    if codigo != 200 or not isinstance(d, dict):
        return {"estado": "error", "fecha": hoy, "codigo": codigo, "materias": []}
    mejor, suyo = None, 0.0
    for obra in d.get("results") or []:
        r = coincide(titulo, autores, obra)
        if r > suyo:
            mejor, suyo = obra, r
    if mejor is None:
        return {"estado": "no_hallado", "fecha": hoy, "materias": []}
    return {"estado": "hallado", "fecha": hoy, "ref": str(mejor.get("id") or ""), "titulo": str(mejor.get("title") or ""),
            "parecido": suyo, "incierta": True, "materias": materias_openalex(mejor)}


CONSULTA = {"openalex": consultar_openalex, "openlibrary": consultar_openlibrary,
            "openalex_titulo": consultar_openalex_titulo}


# ------------------------------------------------------------------ el índice y la cola
def _indice() -> dict:
    raiz = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(raiz / "lib"))
    import indice as mod                                  # noqa: PLC0415
    try:
        return json.loads(mod.ruta_indice().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"libros": {}}


def pendientes(indice: dict, cache: dict, fuentes=FUENTES, ids: list[str] | None = None,
               forzar: bool = False) -> list[tuple[str, str, str]]:
    """[(calibre_id, fuente, clave)] de lo que falta consultar: el DOI en OpenAlex, el ISBN en Open Library y, para lo
    que no tiene ninguno de los dos ni materias ya, el título en OpenAlex (la vía incierta)."""
    con_materias = por_libro(cache)
    fuera = []
    for b, v in sorted(indice.get("libros", {}).items(), key=lambda x: int(x[0])):
        if ids is not None and b not in ids:
            continue
        for fuente in fuentes:
            clave = str(v.get(CLAVE[fuente]) or "").strip()
            if not clave or (not forzar and vigente((cache["libros"].get(b) or {}).get(fuente))):
                continue
            if fuente in INCIERTAS:
                # la vía incierta es el último recurso: solo si no hay identificador que consultar ni materias ya
                tiene_id = any(str(v.get(CLAVE[f]) or "").strip() for f in EXACTAS)
                if tiene_id or int(b) in con_materias:
                    continue
            fuera.append((b, fuente, clave))
    return fuera


def estado(indice: dict | None = None, cache: dict | None = None) -> dict:
    indice, cache = indice if indice is not None else _indice(), cache if cache is not None else leer_cache()
    libros = indice.get("libros", {})
    r = {"libros": len(libros), "fuentes": {}, "con_materias": len(por_libro(cache)),
         "pendientes": len(pendientes(indice, cache))}
    for fuente in FUENTES:
        tienen = [b for b, v in libros.items() if str(v.get(CLAVE[fuente]) or "").strip()]
        hallados = [b for b in tienen if ((cache["libros"].get(b) or {}).get(fuente) or {}).get("estado") == "hallado"]
        r["fuentes"][fuente] = {"con_clave": len(tienen), "hallados": len(hallados),
                                "consultados": len([b for b in tienen if fuente in (cache["libros"].get(b) or {})])}
    return r


def traer(aplicar: bool = False, fuentes=EXACTAS, limite: int | None = None, ids: list[str] | None = None,
          forzar: bool = False, consulta=None, pausa: float = PAUSA) -> dict:
    """Consulta los catálogos por lo pendiente y guarda la caché. Sin `aplicar`, dice qué consultaría y no toca la red."""
    consulta = consulta or CONSULTA
    indice, cache = _indice(), leer_cache()
    faltan = pendientes(indice, cache, fuentes=fuentes, ids=ids, forzar=forzar)
    if limite:
        faltan = faltan[:limite]
    r = {"consultados": 0, "hallados": 0, "no_hallados": 0, "errores": 0, "materias": 0,
         "pendientes": len(faltan), "aplicado": bool(aplicar), "cache": str(ruta_cache()),
         "por_fuente": {f: 0 for f in fuentes}}
    if not aplicar:
        r["ejemplos"] = [f"{b} · {fuente} · {clave}" for b, fuente, clave in faltan[:5]]
        return r
    ESPERA["segundos"] = 0
    for n, (b, fuente, clave) in enumerate(faltan):
        if fuente in INCIERTAS:
            d = consulta[fuente](clave, (indice["libros"].get(b) or {}).get("autores") or ())
        else:
            d = consulta[fuente](clave)
        r["consultados"] += 1
        if d.get("codigo") == RATE_LIMIT:
            # el presupuesto del día se acabó: lo consultado queda guardado y el resto se retoma cuando se reponga
            r["sin_presupuesto"] = True
            r["espera"] = ESPERA["segundos"]
            r["errores"] += 1
            break
        if d["estado"] == "error":
            r["errores"] += 1                     # no se guarda: se reintenta la próxima vez
        else:
            cache["libros"].setdefault(b, {})[fuente] = dict(d, clave=clave)
            r["hallados" if d["estado"] == "hallado" else "no_hallados"] += 1
            r["materias"] += len(d["materias"])
            r["por_fuente"][fuente] += len(d["materias"])
        if pausa and n + 1 < len(faltan):
            time.sleep(pausa)
    guardar_cache(cache)
    return r


def por_libro(cache: dict | None = None) -> dict[int, list[str]]:
    """{calibre_id: [materias]} de lo que hay en la caché, de todas las fuentes, para el mapa (§9.19)."""
    cache = cache if cache is not None else leer_cache()
    salida: dict[int, list[str]] = {}
    for b, v in cache.get("libros", {}).items():
        nombres: list[str] = []
        for fuente in FUENTES:
            for m in ((v.get(fuente) or {}).get("materias") or []):
                # `util` también aquí: lo guardado antes de afinar el filtro no hace falta volver a consultarlo
                if m.get("tipo") == "materia" and m.get("nombre") not in nombres and util(m.get("nombre", "")):
                    nombres.append(m["nombre"])
        if nombres:
            try:
                salida[int(b)] = nombres
            except (TypeError, ValueError):
                continue
    return salida


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="De qué trata cada obra según OpenAlex y Open Library (no escribe en ninguna base).")
    sub = p.add_subparsers(dest="orden")
    sub.add_parser("estado", help="qué hay y qué falta, por fuente (no consulta)")
    t = sub.add_parser("traer", help="consulta los catálogos por lo pendiente")
    t.add_argument("--aplicar", action="store_true", help="consulta de verdad y guarda la caché (sin esto, simula)")
    t.add_argument("--fuente", choices=FUENTES, help="solo esta fuente")
    t.add_argument("--limite", type=int, help="solo los primeros N pendientes")
    t.add_argument("--ids", help="solo estos calibre_id, separados por comas")
    t.add_argument("--forzar", action="store_true", help="vuelve a consultar aunque la caché esté vigente")
    p.add_argument("--json", action="store_true", help="la salida en JSON")
    a = p.parse_args(argv)
    if (a.orden or "estado") == "estado":
        r = estado()
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            print(f"{r['libros']} libros · {r['con_materias']} con materias · {r['pendientes']} por consultar")
            for f, d in r["fuentes"].items():
                print(f"   {f:<13} {d['con_clave']:>5} con {CLAVE[f]} · {d['consultados']:>5} consultados · {d['hallados']:>5} hallados")
        return 0
    r = traer(aplicar=a.aplicar, fuentes=(a.fuente,) if a.fuente else EXACTAS, limite=a.limite,
              ids=(a.ids or "").split(",") if a.ids else None, forzar=a.forzar)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    elif not a.aplicar:
        print(f"simulación: consultaría {r['pendientes']} veces (sin --aplicar no se toca la red)")
        for e in r.get("ejemplos", []):
            print("   ", e)
    else:
        print(f"{r['consultados']} consultados · {r['hallados']} hallados · {r['no_hallados']} sin materias · "
              f"{r['errores']} con error (se reintentan) · {r['materias']} materias en {r['cache']}")
        if r.get("sin_presupuesto"):
            horas = (r.get("espera") or 0) / 3600
            print(f"   se acabó el presupuesto del día de la sede (429); quedan {r['pendientes'] - r['consultados']} "
                  f"por consultar. Vuelva a correrlo en {horas:.0f} h, cuando se reponga.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
