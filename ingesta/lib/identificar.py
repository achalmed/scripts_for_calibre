#!/usr/bin/env python3
# identificar.py — identifica y clasifica documentos de la zona de entrada (solo lectura).
# Por archivo: sha256, páginas, ¿tiene texto? (si no → marcar OCR), título/autor/fecha/tipo
# por PDF-info + primera página + heurísticas de documento legal/estadístico peruano,
# y ficha dual (Zotero+Calibre) con el formato del prompt_para_zotero_1_catalogacion.
# Salida: pendientes.tsv (columnas de resumen_catalogacion.tsv sin `id`) + fichas/<sha8>_<slug>.md
import csv, hashlib, json, os, re, subprocess, sys, unicodedata
from datetime import date
import importlib.util
from pathlib import Path

# La carpeta de los informes es WRITING_DIR de core/env.py (normativa 5.2; ola 0).
_d = Path(__file__).resolve()
while _d != _d.parent and not (_d / "core" / "env.py").is_file(): _d = _d.parent
_s = importlib.util.spec_from_file_location("core_env", _d / "core" / "env.py"); env = importlib.util.module_from_spec(_s); _s.loader.exec_module(env)
_WRITING = re.escape(env.WRITING_DIR.name)
_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # rutas del ledger relativas a DOCS_ROOT (F5)
_s = importlib.util.spec_from_file_location("rutas", _R); R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)

cfg = json.loads(sys.argv[1]); archivos = sys.argv[2:]
FICHAS = Path(cfg["FICHAS_DIR"]); PEND = Path(cfg["PENDIENTES"]); LEDGER = Path(cfg["LEDGER"])
TAGS_CARPETA = json.loads(cfg["TAGS_POR_CARPETA_JSON"])
INST_CARPETA = json.loads(cfg.get("INSTITUCION_POR_CARPETA_JSON") or "{}")
SIGLAS = json.loads(cfg.get("SIGLAS_JSON") or "{}")
DESCONOCIDO = cfg.get("AUTOR_DESCONOCIDO") or "Unknown"
try: PAQUETES = json.loads(cfg.get("PAQUETES_JSON") or "[]")
except json.JSONDecodeError: PAQUETES = []
PREF_ML, PREF_CIL, PREF_INF = cfg.get("SERIE_MARCO_LEGAL_PREFIJO") or "Marco legal", cfg.get("SERIE_CIL_PREFIJO") or "CIL", cfg.get("SERIE_INFORME_PREFIJO") or "Informe"

def humano(s):
    """'03_congreso' → 'Congreso'; 'diagnostico-educacion-ayacucho' → 'Diagnostico educacion ayacucho'."""
    s = re.sub(r"^\d+[_-]", "", s).replace("_", " ").replace("-", " ").strip()
    return s[:1].upper() + s[1:]

def serie_de(carpeta, nombre):
    """Serie de Calibre = carpeta de origen (pedido 2026-09-06). Devuelve (serie, indice)."""
    c = carpeta.replace("\\", "/")
    m = re.search(r"marco_legal/(\d{2})_([^/]+)", c)
    if m:
        top = f"{m.group(1)}_{m.group(2)}"
        orden = [k for k in MANIFIESTO if k.split("/")[0] == top]
        clave = next((k for k in orden if k.endswith("/" + nombre)), None)
        idx = orden.index(clave) + 1 if clave else 90 + sum(1 for k in orden)  # sin fila en el manifiesto → al final
        return f"{PREF_ML} {m.group(1)} - {humano(m.group(2))}", idx
    m = re.search(r"02_investigacion/(?:informes/)?(20\d{2}-\d{2}-\d{2})-([^/]+)", c)
    if m: return f"{PREF_CIL} {m.group(1)} - {humano(m.group(2))}", 0
    m = re.search(rf"{_WRITING}/reports/([^/]+)/01_fuentes", c)
    if m: return f"{PREF_INF} {m.group(1)} - Fuentes", 0
    # `(?:peru/)?`: el acervo de datafw perdió el nivel de país el 2026-09-25 (se aplanó
    # a data/raw/<institución>/). Con `peru/` obligatorio, todo documento de datafw
    # catalogado desde entonces salía SIN serie. Se acepta la forma vieja por los
    # orígenes ya registrados en el ledger.
    m = re.search(r"data/raw/(?:peru/)?([^/]+)/([^/]+)/([^/]+)/(\d{4})", c)   # mef/presupuesto/aprobado/2024 → serie por carpeta, índice = año
    if m: return f"datafw {m.group(1)} - {humano(m.group(2))} {m.group(3)}", int(m.group(4))
    m = re.search(r"data/raw/(?:peru/)?([^/]+)/", c)                        # inei/criminalidad_i_sem_2025 → «datafw inei», correlativo
    if m: return f"datafw {m.group(1)}", 0
    return "", 0

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def slug(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    # al último guion completo: ni palabra partida ni guion final (M5, 2026-09-15; antes 157 fichas acababan en «-»)
    return s[:60].rsplit("-", 1)[0] if len(s) > 60 else s

def pdfinfo(p):
    r = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, errors="replace"); d = {}
    for lin in r.stdout.splitlines():
        if ":" in lin: k, v = lin.split(":", 1); d[k.strip()] = v.strip()
    return d

def texto_primeras(p, n=2):
    r = subprocess.run(["pdftotext", "-l", str(n), "-layout", str(p), "-"], capture_output=True, text=True, errors="replace")
    return r.stdout

RE_NORMA = re.compile(r"\b(LEY|DECRETO LEGISLATIVO|DECRETO SUPREMO|DECRETO DE URGENCIA|DECRETO LEY|RESOLUCI[ÓO]N (?:MINISTERIAL|SUPREMA|LEGISLATIVA))\s*N[°º.o]*\s*([\d-]+)", re.I)
INSTITUCIONES = ["Instituto Nacional de Estadística e Informática", "Banco Central de Reserva del Perú", "Instituto Nacional Penitenciario", "Ministerio de Economía y Finanzas",
                 "Superintendencia Nacional de Aduanas y de Administración Tributaria", "Autoridad Nacional del Servicio Civil", "Ministerio de la Producción", "Contraloría General de la República",
                 "Defensoría del Pueblo", "Congreso de la República", "Presidencia del Consejo de Ministros", "Banco Mundial", "Banco Interamericano de Desarrollo", "CEPAL", "OIT", "Tribunal Constitucional"]

MANIFIESTO = {}
_m = Path(cfg.get("MANIFIESTO_MARCO_LEGAL") or (Path(cfg["CIL_DIR"]) / "02_investigacion" / "marco_legal" / "00_manifiesto" / "manifiesto.tsv"))
if _m.exists():
    for r in csv.DictReader(open(_m, encoding="utf-8"), delimiter="\t"):
        MANIFIESTO[f"{r['carpeta']}/{r['archivo']}"] = r
TIPO_ARCHIVO = {"ley": "Ley", "dleg": "Decreto Legislativo", "dley": "Decreto Ley", "du": "Decreto de Urgencia", "ds": "Decreto Supremo", "rm": "Resolución Ministerial", "tuo": "Texto Único Ordenado"}
RE_ARCHIVO = re.compile(r"^(ley|dleg|dley|du|ds|rm)_(\d{3,5}(?:_\d{4})?)_(.+)$|^(tuo)_()(.+)$")

def limpio(s):
    s = "".join(ch for ch in (s or "") if ch.isprintable()); return re.sub(r"\s+", " ", s).strip()

SUFIJOS_SIGLA = {"jus", "in", "ef", "pcm", "ed", "minedu", "sa", "tr", "minam", "vivienda", "minem", "em", "produce", "de", "mimp", "midis", "mtc", "ag", "osce", "oece", "ceplan", "pcm"}
def titulo_desde_archivo(nombre):
    m = RE_ARCHIVO.match(Path(nombre).stem.lower())
    if not m: return None, None
    g = m.groups(); tipo, num, resto = (g[0], g[1], g[2]) if g[0] else (g[3], g[4], g[5]); num = (num or "").replace("_", "-")
    if tipo == "tuo":   # tuo_ley_27444_ds_004_2019_jus → Texto Único Ordenado de la Ley N.° 27444 (D.S. 004-2019-JUS)
        mm = re.match(r"^(ley|dleg)_(\d+)_?(.*)$", f"{num}_{resto}".lstrip("_")) or re.match(r"^(ley|dleg)_(\d+)_?(.*)$", resto)
        if mm:
            base = f"{TIPO_ARCHIVO[mm.group(1)]} N.° {mm.group(2)}"; art = "del" if mm.group(1) == "dleg" else "de la"
            return f"Texto Único Ordenado {art} {base}. {titulo_de_tokens(mm.group(3).split('_'))}".rstrip(". "), base
        return f"Texto Único Ordenado. {titulo_de_tokens(resto.split('_'))}", ""   # tuo_ley_organica_poder_judicial_ds_017_93_jus
    partes = resto.split("_")
    if tipo in ("ds", "rm", "rs", "rd", "du") and partes and partes[0].isalpha() and len(partes[0]) <= 8 and partes[0] in SUFIJOS_SIGLA:
        num = f"{num}-{partes[0].upper()}"; partes = partes[1:]          # ds_040_2014_pcm → D.S. N.° 040-2014-PCM
    return f"{TIPO_ARCHIVO[tipo]} N.° {num}. {titulo_de_tokens(partes)}".rstrip(". "), f"{TIPO_ARCHIVO[tipo]} N.° {num}"

TIPOS_DOC = {"rd": "Resolución Directoral N.°", "constitucion": "Constitución", "codigo": "Código", "directiva": "Directiva N.°", "pta": "PTA N.°", "reglamento": "Reglamento", "manual": "Manual", "convenio": "Convenio",
             "pacto": "Pacto", "convencion": "Convención", "sentencia": "Sentencia", "tuo": "TUO", "acuerdo": "Acuerdo", "guia": "Guía", "protocolo": "Protocolo", "resolucion": "Resolución"}
GRAFIA = {"dl": "D.L.", "minjus": "MINJUS", "osce": "OSCE", "oece": "OECE", "spley": "SPLEY", "pedn": "PEDN", "pei": "PEI", "poi": "POI", "pen": "PEN", "uncac": "UNCAC", "dga": "DGA", "om": "OM", "in": "IN", "dleg": "D.Leg.", "ds": "D.S.", "rm": "R.M.", "rs": "R.S.", "du": "D.U.", "tuo": "TUO", "cr": "CR", "dgp": "DGP", "jus": "JUS", "ef": "EF", "pcm": "PCM", "sbs": "SBS", "pnp": "PNP",
          "air": "AIR", "oit": "OIT", "cite": "CITE", "onu": "ONU", "oea": "OEA", "tc": "TC", "jne": "JNE", "inei": "INEI", "bcrp": "BCRP", "mef": "MEF", "pbi": "PBI", "dini": "DINI", "sacs": "SACS",
          "renteseg": "RENTESEG", "fogasa": "FOGASA", "bfh": "BFH", "ceplan": "CEPLAN", "enla": "ENLA", "endes": "ENDES", "escale": "ESCALE", "mclcp": "MCLCP", "per": "PER", "gore": "GORE",
          "ppto": "presupuesto", "peru": "Perú", "elperuano": "(El Peruano)", "politica": "política", "edicion": "edición", "ejecucion": "ejecución", "codigos": "códigos", "organica": "orgánica",
          "gestion": "gestión", "modernizacion": "modernización", "administracion": "administración", "tecnica": "técnica", "redaccion": "redacción", "evaluacion": "evaluación", "inversion": "inversión",
          "informacion": "información", "regulacion": "regulación", "planificacion": "planificación", "publica": "pública", "publico": "público", "economica": "económica", "economico": "económico",
          "estadistico": "estadístico", "estadistica": "estadística", "sindicacion": "sindicación", "negociacion": "negociación", "penal": "penal", "civil": "civil", "ninos": "niños"}
def titulo_de_tokens(partes):
    """['directiva','02','2023','dgp','cr','gestion','documental'] → 'Directiva N.° 02-2023-DGP/CR. Gestión documental'."""
    toks = [t for t in partes if t and not re.fullmatch(r"v\d{3}|(bajado-)?\d{4}-\d{2}-\d{2}|cubre-.+-a-.+", t)]   # memoria_2025_v001_2026-09-04 y memoria_2025_v001_cubre-…_bajado-2026-09-04 (datafw §7.34) → sin versión, cobertura ni fecha de descarga
    if not toks: return ""
    out = []; i = 0
    if toks[0].lower() in TIPOS_DOC:
        out.append(TIPOS_DOC[toks[0].lower()]); i = 1
        # número + año + siglas del emisor
        if i < len(toks) and re.fullmatch(r"\d{1,4}[a-z]?", toks[i]):
            num = toks[i]; i += 1
            if i < len(toks) and re.fullmatch(r"(19|20)\d{2}", toks[i]): num += "-" + toks[i]; i += 1
            sig = []
            while i < len(toks) and toks[i].lower() in GRAFIA and len(toks[i]) <= 4 and toks[i].isalpha(): sig.append(GRAFIA[toks[i].lower()]); i += 1
            out[-1] = out[-1] + " " + num + ("-" + "/".join(sig) if sig else "")
            out[-1] += "."
    resto = [GRAFIA.get(t.lower(), t) for t in toks[i:]]
    frase = " ".join(resto).replace("_", " ").strip()
    frase = re.sub(r"\b(\d{2,3}) ((?:19|20)\d{2})\b", r"\1-\2", frase)          # 004 2019 → 004-2019
    frase = re.sub(r"\b(ppto|presupuesto)(20\d{2})\b", r"presupuesto \2", frase)
    if frase and (not out or out[-1].endswith(".")): frase = frase[:1].upper() + frase[1:]   # «Reglamento del congreso», «Directiva N.° 02-2023. Gestión…»
    t = (" ".join(out) + " " + frase).strip()
    return t[:1].upper() + t[1:]

ACRONIMOS = {v for v in GRAFIA.values() if v.isupper()} | {"PL", "EM", "SP", "AIR", "TC", "ONU", "OEA", "OIT", "PBI", "INEI", "BCRP", "MEF", "PCM", "UNSCH", "ENAHO", "ENDES", "ENLA", "ENAPRES", "SIAF", "SNIP", "CAS", "PNP", "FFAA"}
def sentencia(t):
    """Títulos EN MAYÚSCULAS (o con palabras sueltas en mayúscula) del PDF → frase; se conservan siglas conocidas y tokens con dígitos."""
    if len(t) > 12 and sum(1 for x in t.split() if x.isupper() and x.isalpha()) >= max(2, len(t.split()) // 2):
        w = [x if (x in ACRONIMOS or any(ch.isdigit() for ch in x)) else x.lower() for x in t.split()]
        t = " ".join(w); t = t[:1].upper() + t[1:]
    return t

def autor_valido(a):
    a = limpio(a); return a if (len(a) > 6 and " " in a and not re.search(r"@|\.(exe|pdf)|^[a-z]+\d*$", a, re.I)) else ""


FAM_TXT = {"presupuesto": "Presupuesto del sector público", "equilibrio": "Equilibrio financiero del presupuesto del sector público", "endeudamiento": "Endeudamiento del sector público"}
def presupuesto_mef(nombre, carpeta, txt):
    """Leyes, proyectos de ley y exposiciones de motivos del presupuesto (data/raw/peru/mef/presupuesto/<aprobado|proyecto>/<año>)."""
    m = re.search(r"mef/presupuesto/(aprobado|proyecto)/(\d{4})", carpeta)
    if not m: return None
    etapa, anio = m.group(1), int(m.group(2)); n = nombre.lower()
    fam = "equilibrio" if "equilibrio" in n else ("endeudamiento" if "endeudamiento" in n else "presupuesto")
    orden = {"presupuesto": 0, "equilibrio": 1, "endeudamiento": 2}[fam]
    mn = re.search(r"ley_?n?_?(\d{5})", n) or RE_NORMA.search(txt[:3000] if txt else "")
    num = mn.group(1) if mn and mn.re is not RE_NORMA else (mn.group(2) if mn else "")
    if n.startswith("em_"):
        return dict(titulo=f"Exposición de motivos del proyecto de Ley de {FAM_TXT[fam].lower()} para el año fiscal {anio}", tipo="Document", clasif="Documento oficial", item="document",
                    editorial="Ministerio de Economía y Finanzas", fecha=str(anio - 1), ident="", idx=anio + (orden * 2 + 1) / 10, tags="presupuesto_publico, politica_fiscal")
    if n.startswith("pl_"):
        return dict(titulo=f"Proyecto de Ley de {FAM_TXT[fam].lower()} para el año fiscal {anio}", tipo="Document", clasif="Documento oficial", item="document",
                    editorial="Ministerio de Economía y Finanzas", fecha=str(anio - 1), ident="", idx=anio + (orden * 2) / 10, tags="presupuesto_publico, politica_fiscal")
    if n.startswith("ley"):
        return dict(titulo=f"Ley N.° {num}. {FAM_TXT[fam]} para el año fiscal {anio}" if num else f"Ley de {FAM_TXT[fam].lower()} para el año fiscal {anio}", tipo="Statute", clasif="Normativa", item="statute",
                    editorial="Diario Oficial El Peruano", fecha=str(anio - 1), ident=f"norma:ley_{num}" if num else "", idx=anio + orden / 10, tags="presupuesto_publico, politica_fiscal, legislacion")
    return None

def clasificar(nombre, info, txt, carpeta):
    t = txt[:6000]; tn = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    m = RE_NORMA.search(tn) or RE_NORMA.search(nombre.replace("_", " "))
    _SIGLAS_VIEJAS = {"inei": "Instituto Nacional de Estadística e Informática", "bcrp": "Banco Central de Reserva del Perú", "mef": "Ministerio de Economía y Finanzas", "servir": "Autoridad Nacional del Servicio Civil",
              "contraloria": "Contraloría General de la República", "defensoria": "Defensoría del Pueblo", "ceplan": "Centro Nacional de Planeamiento Estratégico", "inpe": "Instituto Nacional Penitenciario",
              "sunat": "Superintendencia Nacional de Aduanas y de Administración Tributaria", "produce": "Ministerio de la Producción", "congreso": "Congreso de la República", "pcm": "Presidencia del Consejo de Ministros"}
    sigla = (re.match(r"^[a-z]+", Path(nombre).stem.lower()) or re.match(r"", "")).group(0)   # endes2024_… → endes
    segs = carpeta.replace("\\", "/").split("/")
    top = segs[segs.index("marco_legal") + 1] if "marco_legal" in segs and segs.index("marco_legal") + 1 < len(segs) else ""
    stem = Path(nombre).stem.lower()
    # decretos supremos / resoluciones: el sector va en el sufijo (ds_004_2019_jus, rm_151_2021_pcm)
    SUFIJOS = {"jus": "Ministerio de Justicia y Derechos Humanos", "in": "Ministerio del Interior", "ef": "Ministerio de Economía y Finanzas", "pcm": "Presidencia del Consejo de Ministros",
               "ed": "Ministerio de Educación", "minedu": "Ministerio de Educación", "sa": "Ministerio de Salud", "tr": "Ministerio de Trabajo y Promoción del Empleo", "minam": "Ministerio del Ambiente",
               "vivienda": "Ministerio de Vivienda, Construcción y Saneamiento", "minem": "Ministerio de Energía y Minas", "em": "Ministerio de Energía y Minas", "produce": "Ministerio de la Producción",
               "de": "Ministerio de Defensa", "mimp": "Ministerio de la Mujer y Poblaciones Vulnerables", "midis": "Ministerio de Desarrollo e Inclusión Social", "mtc": "Ministerio de Transportes y Comunicaciones"}
    msuf = re.search(r"(?:^|_)(ds|rm|rs|rd|du)_\d+_\d{2,4}_([a-z]+)", stem)
    inst_suf = SUFIJOS.get(msuf.group(2)) if msuf else None
    toks = stem.split("_")
    inst_tok = next((SIGLAS[t] for t in toks[1:] if t in SIGLAS and t not in TIPOS_DOC and t not in ("per", "gore", "exp")), None)   # …_minjus_… → MINJUS
    mraw = re.search(r"data/raw/peru/([a-z_]+)/", carpeta)
    # la sigla del nombre de archivo manda; luego el sufijo sectorial; luego la carpeta (marco legal o raíz datafw); el texto, último recurso
    inst = (SIGLAS.get(sigla) if sigla not in TIPOS_DOC else None) or inst_suf or inst_tok or INST_CARPETA.get(top) or (SIGLAS.get(mraw.group(1)) if mraw else None) or next((i for i in INSTITUCIONES if i.lower() in t[:1500].lower()), None)
    tipo, clasif, item, conf = "Report", "Informe", "report", "media"
    if m and (re.search(r"\b(art[ií]culo|decreta|promulg|el presidente de la rep[uú]blica|congreso)\b", t, re.I) or "marco_legal" in carpeta):
        tipo, clasif, item, conf = "Statute", "Normativa", "statute", "alta"
    elif re.search(r"\b(oficio|proyecto de ley|dictamen|exposici[oó]n de motivos)\b", t, re.I):
        tipo, clasif, item, conf = "Document", "Documento oficial", "document", "alta"
    elif re.search(r"informe t[eé]cnico|bolet[ií]n|estad[ií]stic|encuesta", t, re.I):
        tipo, clasif, item, conf = "Report", "Informe técnico", "report", "alta" if inst else "media"
    elif re.search(r"\bISBN\b|cap[ií]tulo 1|índice general|prólogo", t, re.I):
        tipo, clasif, item, conf = "Book", "Libro", "book", "media"
    t_arch, norma_arch = titulo_desde_archivo(nombre)
    if norma_arch and not m:
        tipo, clasif, item, conf = "Statute", "Normativa", "statute", "alta"
    titulo = limpio(info.get("Title") or "")
    generico = re.search(r"diario oficial|el peruano|normas_legales|\.indd|^n[º°]\s|untitled|microsoft word|\.pdf$|\.docx$|export html|javascript|word document|presentaci[oó]n de powerpoint|^portada|^info_|^iso \d|^slide|^diapositiva|^documento\d*$|^t[ií]tulo", titulo, re.I) or len(titulo) < 8 or "_" in titulo
    if t_arch:
        titulo = t_arch
    elif generico or len(titulo) < 30 or re.fullmatch(r"[A-ZÁÉÍÓÚ][a-záéíóú]+( [A-ZÁÉÍÓÚ][a-záéíóú]+){1,3}", titulo):
        # informes: nombre de archivo 'sigla_descripcion_aaaa' → «SIGLA — Descripcion aaaa» (mejor que el Title del PDF)
        partes = Path(nombre).stem.split("_")
        if len(partes) >= 2 and len(partes[0]) <= 14:
            # título en frase desde la descripción del archivo (sin la sigla: la institución ya es el autor)
            desc = partes[1:] if (partes[0].lower() in SIGLAS and partes[0].lower() not in TIPOS_DOC) else partes
            titulo = titulo_de_tokens(desc)
            inst = inst or {"inei": "Instituto Nacional de Estadística e Informática", "bcrp": "Banco Central de Reserva del Perú", "mef": "Ministerio de Economía y Finanzas", "servir": "Autoridad Nacional del Servicio Civil", "contraloria": "Contraloría General de la República", "defensoria": "Defensoría del Pueblo", "ceplan": "Centro Nacional de Planeamiento Estratégico", "inpe": "Instituto Nacional Penitenciario"}.get(partes[0].lower())
        elif generico:
            pass
    if generico and not t_arch and titulo == limpio(info.get("Title") or ""):
        lineas = [limpio(l) for l in t.splitlines() if len(limpio(l)) > 12 and not re.search(r"firmado|fecha:|fau \d|p[aá]gina|www\.|el peruano|lima, ", l, re.I)]
        titulo = (f"{m.group(1).title()} N.° {m.group(2)}" if m else (lineas[0] if lineas else Path(nombre).stem.replace("_", " ")))[:180]
    man = MANIFIESTO.get(f"{carpeta.split('marco_legal/')[-1]}/{nombre}") if "marco_legal" in carpeta else None
    # documentos oficiales: el autor es la institución, nunca el Author del PDF (cuentas de usuario, digitadores)
    oficial = clasif in ("Normativa", "Documento oficial", "Informe técnico", "Informe") or "marco_legal" in carpeta
    autor = inst or ("Congreso de la República" if clasif == "Normativa" else ("" if oficial else autor_valido(info.get("Author"))) or DESCONOCIDO)
    if man and man.get("fuente"): inst = inst or None
    fecha = ""
    # año: primero el del nombre de archivo (ds_004_2019_jus, informe_2026_t1), luego CreationDate, luego el texto
    anios = re.findall(r"(?:^|_)(19[89]\d|20[0-3]\d)(?:_|$|-)", Path(nombre).stem) + re.findall(r"\b(20[0-3]\d|19[89]\d)\b", (info.get("CreationDate") or "") + " " + t[:3000])
    fecha = next((a for a in anios if int(a) <= date.today().year + 1), "")   # «PEN 2036», «Perú 2050» no son años de publicación
    tags = TAGS_CARPETA.get(carpeta.split("/")[0], TAGS_CARPETA.get(carpeta.split("/")[-1], "documento_oficial"))
    ident = f"norma:{m.group(1).lower().replace(' ', '_')}_{m.group(2)}" if m else ""
    if norma_arch: ident = "norma:" + norma_arch.lower().replace("n.° ", "").replace(" ", "_")   # el archivo manda (el texto cita otras normas)
    nota_man = limpio(man["nota"]) if man else ""
    serie, serie_idx = serie_de(carpeta, nombre)
    pm = presupuesto_mef(nombre, carpeta, t)
    if pm:
        return dict(autores="Ministerio de Economía y Finanzas", titulo=pm["titulo"], tipo_zotero=pm["tipo"], clasificador=pm["clasif"], item_type=pm["item"], editorial=pm["editorial"], fecha=pm["fecha"],
                    identificador=pm["ident"], idioma="Spanish", tags=pm["tags"], confianza="alta", norma=pm["ident"].replace("norma:ley_", "Ley N.° ") if pm["ident"] else "", nota_manifiesto="", serie=serie, serie_index=pm["idx"])
    if autor != DESCONOCIDO and conf == "media" and (inst or clasif == "Normativa"): conf = "alta"   # institución conocida + carpeta conocida
    return dict(autores=autor, titulo=sentencia(limpio(titulo)), tipo_zotero=tipo, clasificador=clasif, item_type=item, editorial=inst or (("Diario Oficial El Peruano") if clasif == "Normativa" else ""), fecha=fecha,
                identificador=ident, idioma="Spanish", tags=tags, confianza=conf, norma=(norma_arch or (m.group(0) if m else "")), nota_manifiesto=nota_man, serie=serie, serie_index=serie_idx)

def ficha_md(f, p, sha, info, tiene_texto, carpeta):
    z = f["tipo_zotero"]
    # Frontmatter único (prompts/00 metodo/fichas_formato_y_voz.md §1): calibre_id lo rellena catalogar.py al copiar la
    # ficha a catalogacion/fichas; zotero_key la rellena el paso 03. Sin H1: el título es el archivo.
    return f"""---
tipo: ficha_catalogacion
calibre_id:
zotero_key:
clave_bibtex:
proyecto:
verificacion:
  estado: pendiente
  metodo:
  fecha:
---

> Ficha de catalogación de «{f['titulo']}». Generada por `scripts_for_fuentes/ingesta/lib/identificar.py` el {date.today()} (formato de `prompts/skills/fuentes-documentales/references/paso-02-catalogar.md`). Confianza: **{f['confianza']}**. Revisar antes de aplicar si es media/baja.

## Origen

`{R.a_texto(carpeta)}/{p.name}` · SHA-256 `{sha[:16]}…` · {info.get('Pages','?')} págs · {'con texto' if tiene_texto else 'SIN TEXTO → OCR (datafw/pipeline/documentos)'}

## Zotero
| Campo | Valor |
|---|---|
| Item Type | {z} |
| Title | {f['titulo']} |
| Author | {f['autores']} |
| Date | {f['fecha']} |
| Publisher / Institution | {f['editorial']} |
| Language | es |
| Extra | {('Number: ' + f['norma']) if f['norma'] else ''} |
| Tags | {f['tags']} |

## Calibre
| Campo | Valor |
|---|---|
| Title | {f['titulo']} |
| Authors | {f['autores']} |
| Publisher | {f['editorial']} |
| Pubdate | {f['fecha']} |
| Languages | spa |
| Identifiers | {f['identificador']} |
| Series | {f.get('serie','')} [{f.get('serie_index','')}] |
| Tags | {f['tags']} |
| #clasificador | {f['clasificador']} |
| #item_type | {f['item_type']} |

## Notas
- Heurística: {'norma legal (número detectado: ' + f['norma'] + ')' if f['norma'] else 'sin número de norma detectado'}; institución: {f['editorial'] or 'no detectada'}.
"""

hechos = set(); led_por_sha = {}; led_origenes = set()
if LEDGER.exists():
    for r in csv.DictReader(open(LEDGER, encoding="utf-8"), delimiter="\t"): hechos.add(r["sha256"]); led_por_sha.setdefault(r["sha256"], r); led_origenes.add(r["origen"])
filas = []
if PEND.exists():
    for r in csv.DictReader(open(PEND, encoding="utf-8"), delimiter="\t"): filas.append(r)
ya = {(r["sha256"], r["origen"]) for r in filas}   # la misma huella puede entrar desde otra ruta (copia)
nuevos = 0
for a in archivos:
    p = Path(a)
    if p.is_symlink() or not p.is_file(): continue
    if any(str(p).startswith(pk["raiz"]) for pk in PAQUETES) and re.match(r"^anexo", p.name, re.I):
        print(f"  [adj ] anexo de un paquete: lo coloca 'main.sh paquetes' en la carpeta data/ del documento principal ← {p.parent.name}/{p.name}"); continue
    mv = re.match(r"^(.*?)(_ocr_buscable|_ocr|_texto|_escaneado)$", p.stem)
    if mv and (p.with_name(mv.group(1) + p.suffix).exists() or any(q != p and q.stem == mv.group(1) + suf for q in p.parent.iterdir() for suf in ("_escaneado", "_texto", "_ocr", "_ocr_buscable"))):
        print(f"  [fmt ] variante de {mv.group(1)}: la trata 'main.sh ocr' (formato/enlace), no se cataloga aparte ← {p.name}"); continue
    sha = sha256(p)
    try: origen_rel = str(p.relative_to(cfg["CIL_DIR"]))
    except ValueError: origen_rel = R.a_texto(p)   # fuera de la entrada: relativo a DOCS_ROOT (F5)
    if (sha, origen_rel) in ya: continue
    if sha in hechos:
        if origen_rel in led_origenes: continue
        o = led_por_sha[sha]   # el mismo archivo ya está en Calibre desde otra ruta: fila «copia» para que catalogar la registre y archivar la enlace
        filas.append(dict(sha256=sha, origen=origen_rel, autores=o["autores"], titulo=o["titulo"], tipo_zotero=o["tipo_zotero"], clasificador=o["clasificador"], item_type="", editorial=o["editorial"],
                          fecha=o["fecha_doc"], identificador="", idioma="Spanish", tags=o["tags"], confianza="alta", nota=f"copia del libro {o['calibre_id']} (misma huella); se enlaza", ficha="", serie="", serie_index=""))
        print(f"  [copia] ya en Calibre (id {o['calibre_id']}): {origen_rel[-70:]}"); nuevos += 1; continue
    # El documento puede venir de una raíz externa (datafw): entonces el origen se guarda relativo a DOCS_ROOT
    # (absoluto antes de F5) y la carpeta es su ruta legible, no relativa al CIL.
    try:
        carpeta = str(p.parent.relative_to(cfg["CIL_DIR"])); origen = str(p.relative_to(cfg["CIL_DIR"]))
    except ValueError:
        carpeta = str(p.parent); origen = R.a_texto(p)
    info = pdfinfo(p) if p.suffix.lower() == ".pdf" else {}
    txt = texto_primeras(p) if p.suffix.lower() == ".pdf" else ""
    tiene_texto = len(txt.strip()) > 200
    f = clasificar(p.name, info, txt, carpeta)
    fila = dict(sha256=sha, origen=origen, autores=f["autores"], titulo=f["titulo"], tipo_zotero=f["tipo_zotero"], clasificador=f["clasificador"],
                item_type=f["item_type"], editorial=f["editorial"], fecha=f["fecha"], identificador=f["identificador"], idioma=f["idioma"], tags=f["tags"], confianza=f["confianza"], serie=f["serie"], serie_index=f["serie_index"],
                nota=limpio(("OCR pendiente; " if not tiene_texto else "") + (f["norma"] or "") + ("; " + f["nota_manifiesto"][:120] if f.get("nota_manifiesto") else "")), ficha=f"{sha[:8]}_{slug(f['titulo'])}.md")
    (FICHAS / fila["ficha"]).write_text(ficha_md(f, p, sha, info, tiene_texto, carpeta), encoding="utf-8")
    if fila["serie"] and not fila["serie_index"]:
        fila["serie_index"] = 1 + sum(1 for r in filas if r.get("serie") == fila["serie"])
    filas.append(fila); nuevos += 1
    print(f"  [{f['confianza']:5s}] {f['clasificador']:18s} {f['titulo'][:70]} ← {carpeta}/{p.name}")
cols = ["sha256", "origen", "autores", "titulo", "tipo_zotero", "clasificador", "item_type", "editorial", "fecha", "identificador", "idioma", "tags", "confianza", "nota", "ficha", "serie", "serie_index"]
filas = [r for r in filas if (r["sha256"], r["origen"]) not in {(x["sha256"], x["origen"]) for x in (csv.DictReader(open(LEDGER, encoding="utf-8"), delimiter="\t") if LEDGER.exists() else [])}]
with open(PEND, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t"); w.writeheader(); [w.writerow({k: r.get(k, "") for k in cols}) for r in filas]
print(f"[identificar] {nuevos} nuevos · {len(filas)} pendientes en {PEND.name} · fichas en {FICHAS.name}/")
