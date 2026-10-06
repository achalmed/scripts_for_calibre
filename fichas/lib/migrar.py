"""migrar.py — FD3: lleva las fichas anteriores al 2026-09-06 al formato único (fichas_formato_y_voz.md §7).

Dos formatos de origen:
  catalogacion  fichas de `script_catalogacion_biblioteca/fichas/` (ingesta 2026-09 y las antiguas «SALIDA PARA ZOTERO/CALIBRE»)
                → mismo archivo, con frontmatter `ficha_catalogacion`, sin H1, secciones Origen · Zotero · Calibre · Notas.
  hibrida       fichas de `escritura/<trabajo>/notes/fichas/` (una ficha por obra con resumen y citas mezcladas)
                → una ficha de FUENTE + una TEXTUAL por cita literal + una PARÁFRASIS por idea; la híbrida desaparece.
Nada se pierde: lo que no encaja en una sección va a «Observaciones». Se conserva el estado de verificación; un estado fuera de
contrato (`verificada-abstract`) pasa a `pendiente` con nota. Simula por defecto: devuelve el plan; `aplicar=True` escribe.
"""
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

from lib import ficha as F

config = F.config
sys.path.insert(0, str(config.PY_COMMON))
import biblioteca as bib  # noqa: E402

HOY = date.today().isoformat()
CATEGORIAS = {c.lower(): c for c in config.CATEGORIAS}
CATEGORIAS.update({"dato": "Dato/estadística", "definicion": "Concepto/definición", "definición": "Concepto/definición",
                   "cita de cierre": "Cita clave", "concepto": "Concepto/definición", "hallazgo": "Hallazgo", "limitacion": "Contraargumento/limitación"})
STOP = {"de", "la", "el", "los", "las", "y", "en", "del", "que", "a", "con", "por", "para", "se", "un", "una", "al", "lo", "su", "sus", "es", "como", "no"}


def slug(s, n=4, maxlen=44):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    w = [x for x in re.findall(r"[a-z0-9]+", s) if x not in STOP and len(x) > 2][:n]
    return "-".join(w)[:maxlen].strip("-") or "sin-tema"


def ascii_clave(c):
    """La clave del .bib tal cual (mayúsculas y guion bajo incluidos), sin tildes ni caracteres ajenos a un nombre de archivo."""
    return re.sub(r"[^A-Za-z0-9_.:]", "", unicodedata.normalize("NFKD", str(c or "")).encode("ascii", "ignore").decode()) or "sinclave"


# --- catalogación ----------------------------------------------------------
def _reescribir_ingesta(cuerpo):
    cuerpo = re.sub(r"^# Ficha de catalogación — (.+)$", lambda m: f"> Ficha de catalogación de «{m.group(1).strip()}».", cuerpo, count=1, flags=re.M)
    cuerpo = cuerpo.replace("`00_ingesta/lib/identificar.py`", "`scripts_for_fuentes/ingesta/lib/identificar.py`")
    cuerpo = cuerpo.replace("(formato del `prompt_para_zotero_1_catalogacion.md`)", "(formato de `prompts/01 fuentes/prompt_02_catalogar.md`)")
    # «> Ficha…» + «> Generada…» en un solo bloque de cita
    cuerpo = re.sub(r"^(> Ficha de catalogación de «[^\n]+»\.)\n\n> Generada", r"\1 Generada", cuerpo, count=1, flags=re.M)
    cuerpo = re.sub(r"^\*\*Origen:\*\*\s*(.+)$", r"## Origen\n\n\1", cuerpo, count=1, flags=re.M)
    return cuerpo.strip() + "\n"


def _reescribir_antigua(cuerpo, d):
    """Formato «**ID Calibre** … ### SALIDA PARA ZOTERO … ### SALIDA PARA CALIBRE … ### TAGS … ### NOTAS ADICIONALES»."""
    partes = re.split(r"^### (.+?)\s*$", cuerpo, flags=re.M)
    pre, secs = partes[0], {}
    for i in range(1, len(partes), 2):
        secs[partes[i].strip()] = partes[i + 1].strip().strip("-").strip()
    limpiar = lambda s: re.sub(r"^\s*---\s*$", "", s, flags=re.M).strip()   # quita las reglas horizontales
    pre = limpiar(pre)
    tit = d["titulo"] if d else re.search(r"Title\s*\|\s*([^|]+)\|", cuerpo).group(1).strip() if re.search(r"Title\s*\|\s*([^|]+)\|", cuerpo) else "sin título"
    out = [f"> Ficha de catalogación de «{tit}». Formato anterior (prompt de catalogación, 2026-07), migrado al formato único el {HOY}.", "", "## Origen", ""]
    out.append(pre if pre else "(sin datos de origen)")
    if d:
        out += ["", f"Carpeta actual en Calibre: `{d['carpeta']}`"]
    out += ["", "## Zotero", ""]
    for k in ("TIPO DE ELEMENTO IDENTIFICADO", "SALIDA PARA ZOTERO"):
        if k in secs:
            out += [limpiar(secs.pop(k)), ""]
    out += ["## Calibre", ""]
    for k in ("SALIDA PARA CALIBRE", "TAGS"):
        if k in secs:
            out += [limpiar(secs.pop(k)), ""]
    out += ["## Notas", ""]
    resto = [f"{('**' + k + '.** ') if not k.startswith('NOTAS') else ''}{limpiar(v)}" for k, v in secs.items()]
    out += resto or ["(sin notas)"]
    return "\n".join(out).strip() + "\n"


def migrar_catalogacion(carpeta, aplicar=False):
    plan = []
    for p in sorted(Path(carpeta).glob("*.md")):
        meta, cuerpo = F.leer(p)
        if meta.get("tipo") == "ficha_catalogacion":
            continue                                   # ya migrada (o escrita por catalogar.py tras FD2)
        m = re.match(r"^(\d+)_", p.name)
        if not m:
            plan.append((p.name, "omitida: sin id en el nombre")); continue
        bid = int(m.group(1)); d = bib.datos(bid)
        if cuerpo.lstrip().startswith("# Ficha de catalogación"):
            nuevo = _reescribir_ingesta(cuerpo); fmt = "ingesta"
        elif "### SALIDA PARA ZOTERO" in cuerpo:
            nuevo = _reescribir_antigua(cuerpo, d); fmt = "antigua"
        else:
            plan.append((p.name, "omitida: formato no reconocido")); continue
        nmeta = {"tipo": "ficha_catalogacion", "calibre_id": bid, "zotero_key": (d or {}).get("zotero_key", ""), "clave_bibtex": "", "proyecto": "",
                 "verificacion": {"estado": "pendiente", "metodo": "", "fecha": ""}}
        if not d:
            nuevo = nuevo.rstrip() + f"\n\n**Aviso ({HOY}):** el id {bid} ya no existe en Calibre; ficha conservada como registro histórico.\n"
        plan.append((p.name, f"migrada ({fmt})" + ("" if d else ", id inexistente")))
        if aplicar:
            F.escribir(p, nmeta, nuevo)
    return plan


# --- híbridas (escritura) -------------------------------------------------
RE_H1 = re.compile(r"^# (.+?)\s+—\s+(.+)$", re.M)
RE_PAG = re.compile(r"\((?:pp?\.|p\.)\s*(\d+)(?:\s*[–-]\s*\d+)?\)")
RE_ART = re.compile(r"\((art\.\s*[^)]+)\)", re.I)
RE_USO = re.compile(r"\bUso:\s*(.+?)\.?\s*$")
RE_LOC = re.compile(r"Localización:\s*(.+?)(?=\s+Uso:|$)")
RE_ESSAY = re.compile(r"^(Art\.\s*\d+[^:]*|Principio\s*\d+[^:]*|Regla\s*\d+[^:]*|Cap[íi]tulo\s*[^:]+):\s*(.*)$", re.I)


def _bullets(texto):
    """Une las viñetas multilínea: cada elemento empieza por «- »."""
    items, cur = [], None
    for l in texto.splitlines():
        if l.startswith("- "):
            if cur is not None: items.append(cur)
            cur = l[2:].strip()
        elif cur is not None and l.strip():
            cur += " " + l.strip()
        elif cur is not None and not l.strip():
            items.append(cur); cur = None
    if cur is not None: items.append(cur)
    return items


def _locator_slug(loc):
    s = unicodedata.normalize("NFKD", loc).encode("ascii", "ignore").decode().lower()
    nums = re.findall(r"\d+[a-z]?|(?<=lit\.\s)[a-z]\b", s)
    lit = re.search(r"lit\.\s*([a-z])", s)
    partes = re.findall(r"\d+", s)[:2]
    return "s" + "-".join(partes) + (lit.group(1) if lit else "") if partes else "s0"


def _parsear_bullet(b, es_textual):
    """→ dict(categoria, texto, cita, pagina, locator, uso, localizacion, nota)."""
    r = {"categoria": "", "cita": "", "texto": "", "pagina": "", "locator": "", "uso": "", "localizacion": "", "nota": ""}
    m = RE_USO.search(b)
    if m: r["uso"] = m.group(1).strip().rstrip("."); b = b[:m.start()].strip()
    m = RE_LOC.search(b)
    if m: r["localizacion"] = m.group(1).strip().rstrip("."); b = (b[:m.start()] + b[m.end():]).strip()
    m = RE_ESSAY.match(b)
    if m:
        r["locator"], b = m.group(1).strip(), m.group(2).strip()
    else:
        m = re.match(r"^([^«“\"]{2,45}?)(?:\s*\(([^)]{1,40})\))?:\s*(.+)$", b)
        if m and m.group(1).strip().lower() not in ("uso",):
            etiqueta = m.group(1).strip(); nota = m.group(2) or ""
            r["categoria"] = CATEGORIAS.get(etiqueta.lower(), "")
            if not r["categoria"]:
                r["nota"] = f"rótulo original: «{etiqueta}»"
            if nota: r["nota"] = (r["nota"] + "; " if r["nota"] else "") + f"nota original: {nota}"
            b = m.group(3).strip()
    m = RE_PAG.search(b)
    if m: r["pagina"] = m.group(1); b = (b[:m.start()] + b[m.end():]).strip()
    m = RE_ART.search(b)
    if m: r["locator"] = r["locator"] or m.group(1); b = (b[:m.start()] + b[m.end():]).strip()
    q = re.search(r"[«“\"](.+?)[»”\"]", b)
    if q and es_textual:
        r["cita"] = q.group(1).strip(); resto = (b[:q.start()] + b[q.end():]).strip(" .;:")
        if resto: r["nota"] = (r["nota"] + "; " if r["nota"] else "") + resto
    else:
        r["texto"] = b.strip().rstrip(".") + "."
        if q: r["cita"] = q.group(1).strip()
    if not r["categoria"]:
        r["categoria"] = "Cita clave" if es_textual else "Idea principal"
    return r


def _pagina_codigo(r):
    if r["pagina"]:
        return f"p{int(r['pagina']):03d}", r["pagina"]
    if r["locator"]:
        return _locator_slug(r["locator"]), r["locator"]
    return "s0", ""


def migrar_hibrida(carpeta, proyecto, aplicar=False):
    carpeta = Path(carpeta); plan = []; creados = []
    fichas = [p for p in sorted(carpeta.glob("*.md")) if not p.name.startswith("00-")]
    mapa = {}                                   # nombre viejo → clave (para reescribir «Enlaces»)
    lecturas = {}
    for p in fichas:
        meta, cuerpo = F.leer(p)
        if meta.get("tipo") in config.TIPOS or "clave_bibtex" not in meta:
            continue
        mapa[p.name] = ascii_clave(meta["clave_bibtex"]); lecturas[p] = (meta, cuerpo)
    for p, (meta, cuerpo) in lecturas.items():
        clave = mapa[p.name]                    # solo para nombres de archivo (ascii); el frontmatter conserva la clave del .bib
        clave_bib = str(meta["clave_bibtex"])
        m = RE_H1.search(cuerpo)
        autor_anio, titulo = (m.group(1).strip(), m.group(2).strip()) if m else ("", p.stem)
        anio = re.search(r"\((\d{4})\)", autor_anio); anio = anio.group(1) if anio else ""
        autor = re.sub(r"\s*\(\d{4}\)\s*$", "", autor_anio)
        secs = F.secciones(cuerpo)
        pub = ""
        mm = re.search(r"^\*(.+?)\*\s*(.*)$", cuerpo[cuerpo.find("\n", cuerpo.find("# ")):].strip().split("\n\n")[0], re.M) if m else None
        if mm: pub = (mm.group(1) + " " + mm.group(2)).strip()
        v = meta.get("verificacion") or {}
        est, met, fec = v.get("estado", "pendiente"), str(v.get("metodo", "") or ""), str(v.get("fecha", "") or "")
        nota_estado = ""
        if est not in config.ESTADOS:
            nota_estado = f"estado anterior «{est}» fuera de contrato → pendiente"; est = "pendiente"
        # — citas: subsecciones dentro de «Citas»
        citas_txt = secs.get("Citas", "")
        bloques = re.split(r"^### (.+?)\s*$", citas_txt, flags=re.M)
        derivadas = []; usados = set()
        for i in range(1, len(bloques), 2):
            rot = bloques[i].lower(); es_textual = "textual" in rot
            for b in _bullets(bloques[i + 1]):
                r = _parsear_bullet(b, es_textual)
                cod, pag = _pagina_codigo(r)
                tipo = "ficha_textual" if (es_textual and r["cita"]) else "ficha_parafrasis"
                tema = slug(r["cita"] or r["texto"]); base = f"{clave}-{cod}-{'textual' if tipo == 'ficha_textual' else 'parafrasis'}-{tema}"
                nombre, k = base + ".md", 2
                while nombre in usados: nombre = f"{base}-{k}.md"; k += 1
                usados.add(nombre)
                fm = {"tipo": tipo, "calibre_id": "", "zotero_key": "", "clave_bibtex": clave_bib, "proyecto": proyecto, "pagina": pag or "s0",
                      "categoria": r["categoria"], "uso": r["uso"]}
                obs = [x for x in (r["nota"], r["localizacion"] and f"Localización original: {r['localizacion']}", nota_estado,
                                   "" if pag else "Sin página en la ficha original (cita del resumen o del registro)",
                                   "Fuente aún no catalogada en Calibre: pendiente de los pasos 00–03 del Método Documental") if x]
                if tipo == "ficha_textual":
                    fm["verificacion"] = {"estado": est, "metodo": met, "fecha": fec}
                    cita_apa = f"({autor or clave}, {anio or 's. f.'}, {'p. ' + pag if r['pagina'] else (pag or 'sin página')})"
                    body = (f"## Cita exacta\n\n“{r['cita']}” {cita_apa}\n\n## Localización para el cotejo\n\n"
                            f"{r['localizacion'] or ('Página ' + pag if r['pagina'] else (pag or 'no registrada'))}. Fuente aún no catalogada en Calibre: cotejo pendiente de los pasos 00–03.\n\n"
                            f"## Análisis\n\n{r['texto'] or '(pendiente)'}\n\n## Encadenamiento\n\n- Proviene de: [{clave}-fuente]({clave}-fuente.md)\n"
                            f"- Alimenta a: {('sección ' + r['uso']) if r['uso'] else '(sin asignar)'}\n\n## Observaciones\n\n" + ("\n".join(f"- {o}" for o in obs) or "(ninguna)") + "\n")
                else:
                    fm["verificacion"] = {"estado": "pendiente", "metodo": f"derivada de una ficha {est} ({fec}); sin origen literal registrado" if est != "pendiente" else "", "fecha": fec if est != "pendiente" else ""}
                    body = (f"## Paráfrasis\n\n{r['texto'] or r['cita']}\n\n## Origen literal\n\n" + (f"“{r['cita']}”" if r["cita"] and r["texto"] else "(no registrado en la ficha original; cotejar contra el PDF)") +
                            f"\n\n## Control de fidelidad\n\n(pendiente)\n\n## Encadenamiento\n\n- Proviene de: [{clave}-fuente]({clave}-fuente.md)\n- Alimenta a: {('sección ' + r['uso']) if r['uso'] else '(sin asignar)'}\n"
                            + ("\n## Observaciones\n\n" + "\n".join(f"- {o}" for o in obs) + "\n" if obs else ""))
                derivadas.append((nombre, fm, body, tipo, r["categoria"], pag, r["uso"]))
        # — ficha de fuente
        ex = bib.existe(titulo=titulo) if titulo else {"resultado": "no-existe", "candidatos": []}
        rel = [f"[{mapa[Path(x).name][0:0] + mapa.get(Path(x).name, Path(x).stem)}-fuente]({mapa.get(Path(x).name, Path(x).stem)}-fuente.md)" for x in F.enlaces(secs.get("Enlaces", ""))]
        extras = {k: v for k, v in meta.items() if k not in ("clave_bibtex", "verificacion")}
        otras = {k: v for k, v in secs.items() if k not in ("Resumen", "Citas", "Observaciones", "Preguntas", "Palabras por buscar", "Nuevas citas", "Enlaces")}
        obs_f = [secs.get("Observaciones", "").strip()]
        if secs.get("Preguntas"): obs_f.append("Preguntas:\n" + secs["Preguntas"].strip())
        if secs.get("Palabras por buscar"): obs_f.append("Palabras por buscar: " + secs["Palabras por buscar"].strip())
        for k, vv in otras.items(): obs_f.append(f"{k}:\n{vv.strip()}")
        if extras: obs_f.append("Metadatos de la ficha anterior: " + "; ".join(f"{k}: {vv}" for k, vv in extras.items()))
        if rel: obs_f.append("Relacionadas: " + " · ".join(rel))
        obs_f.append(f"Migrada el {HOY} desde `{p.name}` (formato híbrido); verificación anterior: {v.get('estado', '')} ({met}).")
        fm_f = {"tipo": "ficha_fuente", "calibre_id": (ex["candidatos"][0]["calibre_id"] if ex["candidatos"] else ""), "zotero_key": "", "clave_bibtex": clave_bib, "proyecto": proyecto, "uso": "",
                "verificacion": {"estado": "pendiente", "metodo": f"existencia en Calibre: {ex['resultado'].replace('-', ' ')} (resolutor, {HOY})", "fecha": HOY}}
        body_f = (f"## Datos de verificación de existencia\n\n- Obra: {autor_anio + ' — ' if autor_anio else ''}{titulo}\n" + (f"- Publicación: {pub}\n" if pub else "") +
                  f"- Calibre: {ex['resultado'].replace('-', ' ')} (búsqueda por título, {HOY})" + ("" if ex["candidatos"] else "; pendiente de los pasos 00–03 del Método Documental (localizar, catalogar, Zotero)") + "\n\n"
                  f"## Resumen\n\n{secs.get('Resumen', '').strip() or '(sin resumen)'}\n\n## Fichas derivadas\n\n" +
                  ("\n".join(f"- [{n[:-3]}]({n}) · {t.replace('ficha-', '')} · {c} · {('p. ' + pg) if pg.isdigit() else pg or 'sin página'} · uso {u or '—'}" for n, _, _, t, c, pg, u in derivadas) or "(ninguna)") +
                  "\n\n## Apunte de estudio\n\n(ninguno)\n\n## Observaciones\n\n" + "\n\n".join(x for x in obs_f if x) +
                  "\n\n## Nuevas fuentes detectadas\n\n" + (secs.get("Nuevas citas", "").strip() or "(ninguna)") + "\n")
        plan.append((p.name, f"→ {clave}-fuente.md + {sum(1 for d in derivadas if d[3] == 'ficha_textual')} textuales + {sum(1 for d in derivadas if d[3] == 'ficha_parafrasis')} paráfrasis"))
        if aplicar:
            F.escribir(carpeta / f"{clave}-fuente.md", fm_f, body_f)
            for n, fm, body, *_ in derivadas:
                F.escribir(carpeta / n, fm, body)
            p.unlink()
        creados += [f"{clave}-fuente.md"] + [d[0] for d in derivadas]
    return plan, creados
