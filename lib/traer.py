# traer.py — los pasos 00 a 03 del Método Documental para UNA norma peruana, de la cita al libro de Calibre y su RIS
# para Zotero: lo que corre `main.py traer` y, por él, «Traer una norma nueva» de Inteligencia Legislativa (Qillqa).
#
# No es un escritor: orquesta las órdenes que ya existen y escribe por ellas (la puerta única, §2.5):
#   00 verificar   biblioteca.existe (resolutor, solo lectura)
#   01 localizar   fuentes/gobpe (ficha: sumilla, fecha, emisor) y fuentes/congreso (el PDF de las leyes) → descargar
#                  a entrada/ con hash y procedencia (fuentes_descargadas.tsv)
#   02 catalogar   ingesta/main.sh bib (la ficha y la fila de pendientes.tsv desde un .bib que se arma aquí) y
#                  ingesta/main.sh catalogar --aplicar --solo <el archivo> (Calibre cerrado, candado, respaldo)
#   03 Zotero      ingesta/lib/ris.py solo para ese libro (RIS_IDS); importarlo es de Zotero (Archivo › Importar) y
#                  cerrar el puente, de `lectura/main.sh --enlazar`
# Simula por omisión: `plan()` no descarga ni escribe nada y dice si la puerta está libre. `aplicar()` vuelve a
# verificar (por si otra persona la trajo mientras tanto) y sale con 75 sin descargar si Calibre está abierto.
from __future__ import annotations

import fcntl
import importlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import config
from lib import comun

sys.path.insert(0, str(config.PY_COMMON))
import biblioteca as bib  # noqa: E402

SALIDA_PUERTA = 75
# Las etiquetas que se proponen salen del vocabulario cerrado; «documento_oficial» no es de una norma.
TAGS_BASE = ["norma", "legislacion"]
TAGS_FUERA = {"documento_oficial"}
TIPOS_DEL_CONGRESO = {"ley", "decreto_legislativo", "decreto_ley", "decreto_de_urgencia"}


def _fuente(nombre):
    return importlib.import_module(f"fuentes.{nombre}.config"), importlib.import_module(f"fuentes.{nombre}.localizar")


def _db():
    return sqlite3.connect(f"file:{Path(config.BIBLIOTECA) / 'metadata.db'}?mode=ro", uri=True)


# ------------------------------------------------------------------ la puerta, vista desde fuera (no la abre)
def estado_puerta() -> dict:
    """¿Se podría escribir ahora? Calibre o Zotero abiertos, y el candado de Calibre (otra suite escribiendo)."""
    comm = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout.splitlines()
    abierta = lambda patron: any(re.match(patron, l.strip(), re.I) for l in comm)  # noqa: E731
    sys.path.insert(0, str(config.PY_COMMON))
    import candado  # noqa: E402
    ocupado = False
    ruta = candado.ruta("calibre")
    if ruta.exists():
        with open(ruta) as fd:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                ocupado = True
    calibre = abierta(r"^calibre")
    aviso = ("Calibre está abierto: ciérrelo para catalogar." if calibre else
             "Otra herramienta está escribiendo en la biblioteca; reintente en unos minutos." if ocupado else "")
    return {"libre": not (calibre or ocupado), "calibre_abierto": calibre, "candado_ocupado": ocupado,
            "zotero_abierto": abierta(r"^zotero"), "aviso": aviso}


# ------------------------------------------------------------------ lo que la biblioteca ya sabe (solo lectura)
def series_marco_legal() -> list[str]:
    with _db() as c:
        return [s for (s,) in c.execute("SELECT name FROM series WHERE name LIKE 'Marco legal%' ORDER BY name")]


def siguiente_indice(serie: str) -> int:
    with _db() as c:
        r = c.execute("SELECT max(b.series_index) FROM books b JOIN books_series_link l ON l.book = b.id "
                      "JOIN series s ON s.id = l.series WHERE s.name = ?", (serie,)).fetchone()
    return int((r[0] or 0) // 1) + 1


def libros_de_normas(normas: list[str]) -> list[dict]:
    """Los libros de Calibre con esos identificadores `norma:` (la ley que la nueva modifica o reglamenta)."""
    if not normas:
        return []
    with _db() as c:
        marcas = ",".join("?" * len(normas))
        filas = c.execute(f"SELECT i.val, b.id, b.title, (SELECT s.name FROM books_series_link l JOIN series s ON "
                          f"s.id = l.series WHERE l.book = b.id), (SELECT group_concat(t.name, ', ') FROM "
                          f"books_tags_link bt JOIN tags t ON t.id = bt.tag WHERE bt.book = b.id) FROM identifiers i "
                          f"JOIN books b ON b.id = i.book WHERE i.type = 'norma' AND i.val IN ({marcas})", normas).fetchall()
    return [{"norma": n, "calibre_id": i, "titulo": t, "serie": s or "", "tags": [x.strip() for x in (g or "").split(",") if x.strip()]}
            for n, i, t, s, g in filas]


def normas_por_nombre(texto: str) -> list[str]:
    """«Aprueban Reglamento de la Ley de Canon» no da el número: las normas de Calibre cuyo título es «… N.° X. Ley de
    Canon» (el nombre exacto tras el número). Solo nombres de ley de al menos dos palabras tras «Ley»."""
    nombres = {m.group(0).strip() for m in re.finditer(r"\bLey (?:Org[aá]nica |Marco |General )?(?:de|del|sobre) [^,.;]+", texto or "")}
    if not nombres:
        return []
    with _db() as c:
        out = []
        for n in nombres:
            for (val,) in c.execute("SELECT i.val FROM identifiers i JOIN books b ON b.id = i.book WHERE i.type = 'norma' "
                                    "AND b.title LIKE ? ESCAPE '\\'", (f"%. {n}",)):
                out.append(val)
    return out


def normas_citadas(texto: str, propia: str) -> list[str]:
    out = []
    for m in bib.RE_NORMA.finditer(bib.norm_ligera(texto or "")):
        n = re.sub(r"\s+", "_", m.group(1).strip()) + "_" + m.group(2)
        if n != propia and n not in out:
            out.append(n)
    return out


# ------------------------------------------------------------------ el plan (simulación)
def plan(cita: str, serie: str = "", tags: str = "", titulo: str = "", fecha: str = "", emisor: str = "") -> dict:
    """Pasos 00 a 03 sin escribir nada. Los argumentos no vacíos reemplazan lo que propone la fuente."""
    cfg_g, gobpe = _fuente("gobpe")
    par = gobpe.partir(cita)
    if not par:
        return {"estado": "no-reconocida", "cita": cita,
                "mensaje": "No reconozco la norma: escriba su tipo y su número (Ley 28077, D.S. 005-2002-EF)."}
    tipo, num = par
    norma = f"{tipo}_{num}"
    # 00 — ¿ya está?
    v = bib.existe(norma=norma)
    pasos = [{"paso": "00", "nombre": "Verificar si ya existe", "resultado": v["resultado"],
              "detalle": "; ".join(f"{b['metodo']}: {b['resultados']}" for b in v.get("busquedas", []))}]
    if v["resultado"] == "existe":
        c = v["candidatos"][0]
        return {"estado": "existe", "cita": cita, "norma": norma, "calibre_id": c["calibre_id"],
                "titulo": c.get("titulo", ""), "pasos": pasos,
                "mensaje": f"Ya está en la biblioteca (libro {c['calibre_id']}): súmela a la colección desde la búsqueda."}
    # 01 — localizar: la ficha en gob.pe y el PDF oficial (el del Congreso para las leyes)
    ficha = gobpe.localizar(cita, cfg_g)
    pdf, origen = "", ""
    if tipo in TIPOS_DEL_CONGRESO:
        cfg_c, congreso = _fuente("congreso")
        r = congreso.localizar(f"{gobpe.ROTULO.get(tipo, tipo)} {num}", cfg_c)
        pdf, origen = r.get("url", ""), r.get("fuente", "")
    if not pdf and ficha.get("url"):
        pdf, origen = ficha["url"], "gob.pe"
    pasos.append({"paso": "01", "nombre": "Localizar en la fuente oficial", "resultado": "localizada" if pdf else "no-localizada",
                  "detalle": f"{origen}: {pdf}" if pdf else (ficha.get("error") or "ninguna fuente oficial la tiene")})
    if not pdf:
        return {"estado": "no-localizada", "cita": cita, "norma": norma, "pasos": pasos,
                "mensaje": ficha.get("error") or "No la encontré en el Congreso ni en gob.pe."}
    # 02 — los metadatos que tendrá en Calibre
    citadas = normas_citadas(ficha.get("sumilla", ""), norma) or normas_por_nombre(ficha.get("sumilla", ""))
    relacionadas = libros_de_normas(citadas)
    serie = serie or next((r["serie"] for r in relacionadas if r["serie"].startswith("Marco legal")), "")
    propuestas = list(TAGS_BASE) + [t for r in relacionadas for t in r["tags"]]
    tags_l = [t.strip() for t in tags.split(",") if t.strip()] if tags else list(dict.fromkeys(t for t in propuestas if t not in TAGS_FUERA))
    rotulo = ficha.get("rotulo") or f"{gobpe.ROTULO.get(tipo, tipo)} N.° {num.upper() if '-' in num else num}"
    meta = {"titulo": titulo or ficha.get("titulo") or rotulo, "autores": emisor or ficha.get("emisor") or "",
            "fecha": fecha or ficha.get("fecha", ""), "norma": norma, "url": pdf, "origen": origen,
            "pagina": ficha.get("pagina", ""), "editorial": "Diario Oficial El Peruano", "item_type": "Statute",
            "clasificador": "Normativa", "serie": serie, "serie_indice": siguiente_indice(serie) if serie else None,
            "tags": tags_l, "idioma": "spa", "relacionadas": relacionadas}
    pasos.append({"paso": "02", "nombre": "Catalogar en Calibre", "resultado": "por-aplicar",
                  "detalle": f"«{meta['titulo']}» · {meta['autores']} · {meta['fecha']} · {serie or 'sin serie'}"})
    pasos.append({"paso": "03", "nombre": "Pasar a Zotero", "resultado": "por-aplicar",
                  "detalle": "un .ris de este libro (tipo statute, con su número y su fecha) para importar en Zotero"})
    return {"estado": "por-traer", "cita": cita, "norma": norma, "metadatos": meta, "pasos": pasos,
            "series": series_marco_legal(), "puerta": estado_puerta(),
            "ordenes": ordenes(norma, meta)}


def _bib(norma: str, meta: dict) -> str:
    limpio = lambda s: re.sub(r"[{}\"\n]", "", str(s or ""))  # noqa: E731
    campos = {"title": meta["titulo"], "emisor": meta["autores"], "date": meta["fecha"],
              "year": (meta["fecha"] or "")[:4], "url": meta["url"], "note": f"Traída por main.py traer desde {meta['origen']}"
              f"{' (ficha: ' + meta['pagina'] + ')' if meta.get('pagina') else ''}"}
    cuerpo = "".join(f"  {k} = {{{limpio(v)}}},\n" for k, v in campos.items() if v)
    return f"@legislation{{{norma},\n{cuerpo}}}\n"


def ordenes(norma: str, meta: dict) -> list[str]:
    """Las órdenes que correrá `aplicar`, tal cual (para mostrarlas antes de confirmar)."""
    arch = f"entrada/{norma}.pdf"
    return [f"main.py descargar (desde {meta['origen']}) → {arch}",
            f"ingesta/main.sh bib {norma}.bib --serie \"{meta['serie']}\" --indice {meta['serie_indice'] or ''} "
            f"--tags \"{', '.join(meta['tags'])}\" --archivo {norma}={arch}",
            f"ingesta/main.sh catalogar --aplicar --solo '{norma}\\.pdf$'   (Calibre cerrado, candado, respaldo)",
            "RIS_IDS=<id> ingesta/lib/ris.py → ingesta/salida_ris/traer_<id>.ris"]


# ------------------------------------------------------------------ aplicar
def _correr(*args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args], cwd=config.RAIZ, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def aplicar(cita: str, **cambios) -> tuple[int, dict]:
    p = plan(cita, **cambios)
    if p["estado"] != "por-traer":
        return 0 if p["estado"] == "existe" else 1, p
    if not p["puerta"]["libre"]:
        return SALIDA_PUERTA, {**p, "estado": "puerta-cerrada", "mensaje": p["puerta"]["aviso"]}
    norma, meta = p["norma"], p["metadatos"]
    # 01 — descargar con hash y procedencia
    config.ENTRADA.mkdir(exist_ok=True)
    try:
        ruta, sha, n = comun.descargar(meta["url"], config.ENTRADA, norma)
    except Exception as exc:
        return 1, {**p, "estado": "fallo", "mensaje": f"No se pudo descargar: {type(exc).__name__}: {str(exc)[:120]}"}
    comun.anotar({"sha256": sha, "fuente": "gobpe" if meta["origen"] == "gob.pe" else "congreso", "tipo": norma.rsplit("_", 1)[0],
                  "referencia": cita, "titulo": meta["titulo"], "url": meta["url"], "origen": meta["origen"],
                  "archivo": ruta.name, "bytes": n, "estado": "descargado"})
    ya = bib.existe(archivo=str(ruta))
    if ya["candidatos"]:   # el mismo archivo ya está, con otro identificador: no se duplica
        c = ya["candidatos"][0]
        ruta.unlink(missing_ok=True)
        return 0, {**p, "estado": "existe", "calibre_id": c["calibre_id"], "titulo": c.get("titulo", ""),
                   "mensaje": f"El mismo PDF ya está en la biblioteca (libro {c['calibre_id']})."}
    # 02 — la ficha desde un .bib (en la caché, fuera del repo) y la catalogación por la puerta
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "biblioteca" / "traer"
    cache.mkdir(parents=True, exist_ok=True)
    bibf = cache / f"{norma}.bib"
    bibf.write_text(_bib(norma, meta), encoding="utf-8")
    args = ["bash", "ingesta/main.sh", "bib", bibf, "--tags", ", ".join(meta["tags"]), "--archivo", f"{norma}={ruta}"]
    if meta["serie"]:
        args += ["--serie", meta["serie"], "--indice", str(meta["serie_indice"])]
    r = _correr(*args)
    if r.returncode:
        return 1, {**p, "estado": "fallo", "mensaje": "La ficha no se pudo preparar.", "salida": (r.stdout + r.stderr)[-1500:]}
    r = _correr("bash", "ingesta/main.sh", "catalogar", "--aplicar", "--solo", rf"{re.escape(norma)}\.pdf$")
    salida = r.stdout + r.stderr
    if r.returncode == SALIDA_PUERTA:
        return SALIDA_PUERTA, {**p, "estado": "puerta-cerrada", "mensaje": "Calibre se abrió o la biblioteca está ocupada: no se catalogó; reintente.",
                               "salida": salida[-1500:]}
    m = re.search(r"\[✓\] id=(\d+)|\[=\] ya en Calibre \(id (\d+)\)", salida)
    if r.returncode or not m:
        return 1, {**p, "estado": "fallo", "mensaje": "La catalogación no terminó.", "salida": salida[-1500:]}
    cid = int(m.group(1) or m.group(2))
    # 03 — el RIS de este libro
    ris = config.RAIZ / "ingesta" / "salida_ris" / f"traer_{cid}_{norma}.ris"
    ris.parent.mkdir(exist_ok=True)
    rr = _correr(sys.executable, "ingesta/lib/ris.py", config.LEDGER_INGESTA, ris, env={"RIS_IDS": str(cid), "PY_COMMON": str(config.PY_COMMON)})
    pasos = [x if x["paso"] in ("00", "01") else {**x, "resultado": "hecho"} for x in p["pasos"]]
    return 0, {**p, "estado": "catalogada", "calibre_id": cid, "pasos": pasos, "ris": str(ris) if ris.exists() else "",
               "salida": (salida + rr.stdout + rr.stderr)[-1500:],
               "siguiente": ["Abra Zotero y use Archivo › Importar con el .ris (enlazar a los archivos en su ubicación).",
                             "Después, con Calibre cerrado: lectura/main.sh --enlazar --aplicar (escribe la clave de Zotero en Calibre).",
                             "El original queda en entrada/ hasta ingesta/main.sh archivar --aplicar."]}


def imprimir(r: dict) -> None:
    print(f"traer «{r.get('cita', '')}» — {r['estado']}\n" + "─" * 62)
    for x in r.get("pasos", []):
        print(f"  {x['paso']} {x['nombre']:<32} {x['resultado']:<14} {x['detalle'][:90]}")
    if r.get("metadatos"):
        m = r["metadatos"]
        print(f"\n  Título   {m['titulo']}\n  Emisor   {m['autores']}\n  Fecha    {m['fecha']}\n  Serie    {m['serie'] or '—'}"
              f" [{m['serie_indice'] or ''}]\n  Etiquetas {', '.join(m['tags'])}\n  PDF      {m['url']}")
    if r.get("puerta") and not r["puerta"]["libre"]:
        print(f"\n  ✗ {r['puerta']['aviso']}")
    if r.get("mensaje"):
        print(f"\n  {r['mensaje']}")
    for s in r.get("siguiente", []):
        print(f"  · {s}")
    if r["estado"] == "por-traer":
        print("\n  Simulación: nada se descargó ni se escribió. Con --aplicar se trae (Calibre cerrado).")


def json_de(r: dict) -> str:
    return json.dumps(r, ensure_ascii=False, indent=2, default=str)
