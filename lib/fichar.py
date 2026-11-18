#!/usr/bin/env python3
"""lib/fichar.py — crear y corregir las fichas de un escrito (textual, paráfrasis, síntesis y fuente) en su carpeta
`fuentes/fichas/`, con la norma única de fichas y la huella del archivo, como Yachay.

Objetivo: fichar desde Biblioteca Studio (la ficha de un libro, con su PDF al lado) y desde LaTeX Studio (Citas › Fichas)
  lo mismo que en Yachay: una ficha nueva con su nombre normativo, o la corrección de una que ya existe sin pisar lo que
  otro cambió (decisiones §9.4).
Método: el frontmatter y las secciones salen del lector y escritor único (`fichas/lib/ficha.py`, `fichas/config.py`);
  la forma de Yachay (`yachay/estudios/fuentes_escritura.py`): el literal entre comillas tipográficas (§4), la localización
  y el encadenamiento con la ficha de fuente, que lista la nueva entre sus «Fichas derivadas» (y nace si falta), y la
  huella sha256 del archivo entero: una corrección trae la huella con que se abrió y, si en disco es otra, `Cambiada`
  (lo que Yachay responde con 409). El cotejo contra el PDF es el de `fichas/lib/verificar.py` (la suite `fichas`): una
  textual o paráfrasis nueva o con otro literal se coteja al guardar; lo que verificó el autor no baja con el mismo literal.
Fundamento: `prompts/00 metodo/fichas_formato_y_voz.md` (§1 frontmatter, §2 nombres y secciones, §3 los once rótulos, §4
  la voz); `prompts/00 metodo/METODO_DOCUMENTAL.md` (paso 05, fichar; la verificación).
Límite: solo escribe en `<proyecto>/fuentes/fichas/` y solo con `aplicar`; nunca toca Calibre ni Zotero ni el texto del
  escrito. Lo que necesita de la biblioteca (la clave, el `calibre_id`) lo trae quien llama (`lib/consulta.py`).
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.util
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = Path("fuentes") / "fichas"
FIRMA = "Ficha hecha en Biblioteca Studio"
TIPOS = {"textual": "ficha_textual", "parafrasis": "ficha_parafrasis", "sintesis": "ficha_sintesis", "fuente": "ficha_fuente",
         "obra": "ficha_obra"}
DE_TIPO = {v: k for k, v in TIPOS.items()}
# Las secciones que arma la herramienta (la persona no las escribe): la localización, el encadenamiento, la existencia y
# las derivadas de la ficha de fuente.
AUTOMATICAS = {"Localización para el cotejo", "Encadenamiento", "Datos de verificación de existencia", "Fichas derivadas"}
# El literal de cada tipo (lo que se coteja y va entre comillas tipográficas, §4).
LITERAL = {"ficha_textual": "Cita exacta", "ficha_parafrasis": "Origen literal"}
VACIAS = {"del", "las", "los", "una", "uno", "que", "por", "para", "con", "como", "sus", "entre", "sobre", "este", "esta",
          "esto", "the", "and", "pero", "sin", "más", "mas", "cuando", "donde", "desde", "hasta", "también", "tambien", "ser",
          "son", "fue", "han", "hay", "muy", "cada"}


def _modulo(nombre: str, ruta: Path):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


F = _modulo("fichas_ficha", RAIZ / "fichas" / "lib" / "ficha.py")
config = F.config


def _verificador():
    """`fichas/lib/verificar.py`, que hace `from lib import ficha`: se carga por su ruta bajo un paquete `lib` propio (el de
    la suite `fichas`) y después se devuelve el `lib` de antes (en Biblioteca Studio, `lib` es el paquete de este repo)."""
    if "fichas_verificar" in sys.modules:
        return sys.modules["fichas_verificar"]
    import types
    previas = {k: v for k, v in sys.modules.items() if k == "lib" or k.startswith("lib.")}
    for k in previas:
        del sys.modules[k]
    paquete = types.ModuleType("lib")
    paquete.__path__ = [str(RAIZ / "fichas" / "lib")]
    paquete.ficha = F
    sys.modules.update({"lib": paquete, "lib.ficha": F})
    try:
        spec = importlib.util.spec_from_file_location("lib.verificar", RAIZ / "fichas" / "lib" / "verificar.py")
        V = importlib.util.module_from_spec(spec)
        sys.modules["lib.verificar"] = V
        spec.loader.exec_module(V)
        sys.modules["fichas_verificar"] = V
    finally:
        for k in [k for k in sys.modules if k == "lib" or k.startswith("lib.")]:
            del sys.modules[k]
        sys.modules.update(previas)
    return sys.modules["fichas_verificar"]


class Cambiada(RuntimeError):
    """La ficha cambió en disco desde que se abrió: no se pisa (Yachay responde 409 `ficha_cambiada`)."""

    def __init__(self, actual: dict):
        super().__init__("Esta ficha cambió fuera de aquí desde que la abrió: vuelva a abrirla.")
        self.actual = actual


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _llano(t) -> str:
    return " ".join(str(t or "").split())


def _ascii(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def clave_literal(t: str) -> str:
    """El literal sin tildes, signos ni mayúsculas: dos escrituras de la misma cita dan lo mismo."""
    return re.sub(r"[^a-z0-9]+", " ", _ascii(t)).strip()


def nombre_clave(clave: str) -> str:
    """La clave como la admite el nombre de una ficha (`[A-Za-z0-9_.:]+`)."""
    return re.sub(r"[^A-Za-z0-9_.:]", "_", clave or "") or "obra"


def lugar_de(pagina) -> tuple[str, int | str]:
    """(lugar del nombre, valor de `pagina`): «12» o «p. 12» → (`p012`, 12); «art. 5» → (`s5`, «art. 5»); «3.2» → (`s3-2`,
    «3.2»). §2: NNN con tres dígitos o, si la obra no pagina, la sección."""
    t = _llano(pagina)
    m = re.match(r"^(?:pp?\.?\s*)?0*(\d+)$", t, re.I)
    if m and int(m.group(1)) > 0:
        return f"p{int(m.group(1)):03d}", int(m.group(1))
    m = re.match(r"^(?:art|secc?|cap|§|num|inc|fund|disp)\.?\s*(\d+(?:\s*[.-]\s*\d+)*)\s*([a-z])?$", t, re.I)
    if m:
        return "s" + "-".join(re.split(r"\s*[.-]\s*", m.group(1))) + (m.group(2) or "").lower(), t
    m = re.match(r"^s?(\d+(?:[.-]\d+)*)$", t)
    if m:
        return "s" + "-".join(re.split(r"[.-]", m.group(1))), t
    raise ValueError("Escriba la página («12») o el lugar («art. 5», «3.2»): toda ficha lleva dónde está el pasaje.")


def tema_de(texto: str) -> str:
    """De una a tres palabras con guion, sin las vacías (§2): «La escala urbana importa» → `escala-urbana-importa`."""
    palabras = [w for w in re.sub(r"[^a-z0-9]+", " ", _ascii(texto)).split() if w.isdigit() or (len(w) > 2 and w not in VACIAS)]
    return "-".join(palabras[:3]) or "ficha"


def _cita(t: str) -> str:
    """§4: el literal entre comillas dobles tipográficas, en una línea; las dobles de dentro pasan a simples."""
    t = _llano(t)
    if len(t) >= 2 and t[0] in "“\"«" and t[-1] in "”\"»":
        t = t[1:-1].strip()
    t = t.replace("“", "‘").replace("”", "’").replace('"', "’").replace("«", "‘").replace("»", "’")
    return f"“{t}”"


def _sin_comillas(t: str) -> str:
    t = _llano(t)
    if len(t) >= 2 and t[0] in "“\"«" and t[-1] in "”\"»":
        t = t[1:-1].strip()
    return t


def _escribir(ruta: Path, texto: str) -> None:
    tmp = ruta.with_name(f".{ruta.name}.guardando")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ruta)


def carpeta(proyecto: Path) -> Path:
    return Path(proyecto) / CARPETA


def _ruta(proyecto: Path, archivo: str) -> Path:
    nombre = Path(str(archivo or "")).name
    if not re.match(r"^[A-Za-z0-9_.:-]+\.md$", nombre) or nombre.startswith("."):
        raise LookupError("Esa ficha no existe.")
    p = carpeta(proyecto) / nombre
    if not p.is_file():
        raise LookupError("Esa ficha no existe.")
    return p


def editables(tipo: str) -> list[str]:
    """Las secciones de un tipo que escribe la persona (las demás las arma la herramienta)."""
    return [s for s in config.SECCIONES.get(tipo, []) if s not in AUTOMATICAS]


NOMBRES = {"textual": "Textual", "parafrasis": "Paráfrasis", "sintesis": "Síntesis", "fuente": "Fuente", "obra": "De obra"}
# Lo que pregunta cada sección de la ficha de obra (C3.1): se responde con palabras propias, sin mirar ni copiar.
GUIAS_OBRA = {"Pregunta": "¿Qué pregunta responde la obra?", "Método": "¿Cómo la responde: diseño, técnica, enfoque?",
              "Datos": "¿Con qué datos o fuentes, de dónde y de cuándo?", "Hallazgo": "¿Qué encuentra o sostiene, en una o dos oraciones?",
              "Límites": "¿Qué no puede afirmar, por su diseño o sus datos?", "Uso que le daré": "¿Para qué parte de mi trabajo me sirve?"}
POR_QUE = {
    "obra": ("Escribir con palabras propias lo que la obra pregunta, hace y encuentra fija más que subrayar o releer.",
             "Fiorella y Mayer (2016); Chi y Wylie (2014); Keshav (2007)"),
    "origen": ("La IA no responde por lo que escribe: su ficha se coteja en la página antes de citarla.",
               "COPE (2023); Jergas y Baethge (2015)"),
    "registro": ("Lo que propuso la IA queda registrado y el escrito lo declara.",
                 "COPE (2023); ICMJE (2025); Penabad-Camacho et al. (2024, Calibre 3110)"),
}
# Una ficha de obra que repite ocho palabras seguidas de la obra la está copiando (Roig, 2015: la paráfrasis demasiado
# cercana también es plagio).
COPIA_PALABRAS = 8
HERRAMIENTA_IA = "Un chat de IA externo, con el prompt de Biblioteca Studio"


def formulario() -> dict:
    """Lo que una ventana necesita para pintar el formulario de una ficha sin saber de la norma: los tipos (con sus
    secciones editables, si llevan página y categoría, y cuál es el literal) y los once rótulos."""
    tipos = []
    for corto, tipo in TIPOS.items():
        omite = config.OMITE[tipo]
        porque = POR_QUE.get(corto)
        tipos.append({"clave": corto, "nombre": NOMBRES[corto], "secciones": editables(tipo), "literal": LITERAL.get(tipo, ""),
                      "pagina": "pagina" not in omite, "categoria": "categoria" not in omite, "libro": tipo != "ficha_sintesis",
                      "guias": GUIAS_OBRA if corto == "obra" else {}, "porque": porque[0] if porque else "",
                      "fuente": porque[1] if porque else ""})
    return {"tipos": tipos, "categorias": list(config.CATEGORIAS),
            "origen": {"porque": POR_QUE["origen"][0], "fuente": POR_QUE["origen"][1]}}


# --- leer ---------------------------------------------------------------------------------------------------------------

def leer(proyecto: Path, archivo: str) -> dict:
    """La ficha para editarla: su frontmatter, sus secciones editables con su texto, su huella y lo que la norma le
    objeta (`problemas`, de `ficha.validar`)."""
    p = _ruta(proyecto, archivo)
    texto = p.read_text(encoding="utf-8")
    try:
        meta, cuerpo = F.leer(p)
    except ValueError as e:
        return {"archivo": p.name, "ruta": str(p), "huella": huella(texto), "error": str(e), "tipo": "", "secciones": []}
    tipo = str(meta.get("tipo") or "")
    secs = F.secciones(cuerpo)
    v = meta.get("verificacion") if isinstance(meta.get("verificacion"), dict) else {}
    lista = [{"titulo": s, "texto": _sin_comillas(secs.get(s, "")) if s == LITERAL.get(tipo) else secs.get(s, ""),
              "literal": s == LITERAL.get(tipo)} for s in editables(tipo)]
    clave = meta.get("clave_bibtex")
    return {"archivo": p.name, "ruta": str(p), "huella": huella(texto), "error": "" if tipo in DE_TIPO else
            "Esta ficha no es textual, de paráfrasis, de síntesis ni de fuente: se corrige a mano.",
            "tipo": DE_TIPO.get(tipo, tipo), "calibre_id": meta.get("calibre_id") or "",
            "clave": "" if isinstance(clave, list) else str(clave or ""), "pagina": str(meta.get("pagina") or ""),
            "categoria": str(meta.get("categoria") or ""), "uso": str(meta.get("uso") or ""),
            "verificacion": {k: str(v.get(k) or "") for k in config.CLAVES_VERIFICACION},
            "origen": F.origen_de(meta, cuerpo), "citable": F.citable(meta, cuerpo)[0], "motivo": F.citable(meta, cuerpo)[1],
            "secciones": lista, "problemas": F.validar(p, meta, cuerpo)}


# --- escribir -----------------------------------------------------------------------------------------------------------

def _unir_derivadas(texto: str, nombre: str) -> str:
    """Una ficha de fuente conserva lo suyo y suma a «Fichas derivadas» el enlace que le falte."""
    if f"]({nombre})" in texto:
        return texto
    nuevo = f"- [{nombre[:-3]}]({nombre})\n"
    m = re.search(r"^## Fichas derivadas[^\n]*\n(.*?)(?=^## |\Z)", texto, re.S | re.M)
    if not m:
        return texto.rstrip("\n") + f"\n\n## Fichas derivadas\n{nuevo}"
    bloque = m.group(1).rstrip("\n")
    bloque = "" if bloque.strip().lower() in ("ninguna.", "ninguna", "sin fichas derivadas.") else bloque
    return texto[: m.start(1)] + (bloque + "\n" if bloque else "") + nuevo + ("\n" if texto[m.end(1):] else "") + texto[m.end(1):]


def _texto_fuente(entrada: dict, proyecto: str, derivada: str, referencia: str = "") -> str:
    meta = {"tipo": "ficha_fuente", "calibre_id": entrada.get("calibre_id") or "", "zotero_key": entrada.get("zotero_key") or "",
            "clave_bibtex": entrada["clave"], "proyecto": proyecto, "uso": entrada.get("uso") or "",
            "verificacion": {"estado": "pendiente", "metodo": "", "fecha": ""}}
    existencia = ((referencia + " ") if referencia else "") + (f"Calibre {entrada['calibre_id']}." if entrada.get("calibre_id")
                                                                else "La fuente no existe en Calibre: queda pendiente de los pasos 00–03.")
    secs = {"Datos de verificación de existencia": existencia, "Resumen": "Sin resumen: lo escribe quien lee la obra (paso 04).",
            "Fichas derivadas": f"- [{derivada[:-3]}]({derivada})" if derivada else "Ninguna.",
            "Apunte de estudio": "No hay apunte de estudio.", "Observaciones": f"{FIRMA}.", "Nuevas fuentes detectadas": "Ninguna registrada."}
    return F.frontmatter(meta) + "\n" + "\n\n".join(f"## {t}\n{v}" for t, v in secs.items()) + "\n"


def _componer(meta: dict, secs: dict[str, str], tipo: str) -> str:
    orden = config.SECCIONES[tipo]
    titulos = [t for t in orden if t in secs] + [t for t in secs if t not in orden]
    return F.frontmatter(meta) + "\n" + "\n\n".join(f"## {t}\n{secs[t].strip()}" for t in titulos) + "\n"


def _limpiar(datos: dict) -> dict:
    clase = str(datos.get("tipo") or "textual").replace("ficha_", "")
    tipo = TIPOS.get(clase)
    if tipo is None:
        raise ValueError("Una ficha de aquí es textual, de paráfrasis, de síntesis o de fuente.")
    secs = {str(k): str(v or "").strip() for k, v in (datos.get("secciones") or {}).items()}
    # los atajos de la API de Yachay: cita, parafrasis, analisis, observaciones
    for corto, sec in (("cita", LITERAL.get(tipo, "")), ("parafrasis", "Paráfrasis"), ("analisis", "Análisis" if tipo == "ficha_textual" else "Control de fidelidad"),
                       ("observaciones", "Observaciones")):
        if sec and datos.get(corto) not in (None, "") and not secs.get(sec):
            secs[sec] = str(datos[corto]).strip()
    categoria = str(datos.get("categoria") or ("Cita clave" if tipo == "ficha_textual" else "Idea principal"))
    if tipo in ("ficha_textual", "ficha_parafrasis", "ficha_sintesis") and categoria not in config.CATEGORIAS:
        raise ValueError("La categoría es uno de los once rótulos de la norma de fichas (§3).")
    if tipo == "ficha_textual" and not _sin_comillas(secs.get("Cita exacta", "")):
        raise ValueError("Una ficha textual lleva la cita exacta, tal cual está en la fuente.")
    if tipo == "ficha_parafrasis":
        if not secs.get("Paráfrasis"):
            raise ValueError("Una ficha de paráfrasis lleva la paráfrasis.")
        if len(secs["Paráfrasis"].split()) > 120:
            raise ValueError("La paráfrasis va en 120 palabras o menos (norma de fichas, §5).")
    if tipo == "ficha_sintesis" and not secs.get("Párrafo de síntesis"):
        raise ValueError("Una ficha de síntesis lleva su párrafo de síntesis.")
    if tipo == "ficha_obra":
        faltan = [s for s in GUIAS_OBRA if not secs.get(s)]
        if faltan:
            raise ValueError("La ficha de obra responde las seis preguntas con palabras propias; falta: " + ", ".join(faltan) + ".")
    for s in list(secs):
        if s in AUTOMATICAS:
            del secs[s]
    return {**datos, "tipo": tipo, "categoria": categoria, "secciones": secs, "uso": _llano(datos.get("uso")),
            "tema": _llano(datos.get("tema")), "origen": _origen(datos.get("origen"))}


def _origen(o) -> dict | None:
    """El bloque `origen` pedido (None si no se pidió): autor persona o llm, la herramienta y la fecha (hoy si falta)."""
    if not isinstance(o, dict) or not o.get("autor"):
        return None
    autor = str(o["autor"]).strip().lower()
    if autor not in config.AUTORES:
        raise ValueError("El origen de una ficha es «persona» o «llm».")
    herramienta = _llano(o.get("herramienta")) or (HERRAMIENTA_IA if autor == "llm" else "Biblioteca Studio")
    return {"autor": autor, "herramienta": herramienta, "fecha": str(o.get("fecha") or date.today().isoformat())[:10]}


def copiado(texto: str, hojas: list[str], n: int = COPIA_PALABRAS) -> list[str]:
    """Los pasajes de `texto` que repiten `n` palabras seguidas de la obra (sus `hojas`), sin tildes ni signos."""
    palabras = clave_literal(texto).split()
    if len(palabras) < n or not hojas:
        return []
    obra = " " + clave_literal(" ".join(hojas)) + " "
    salida, i = [], 0
    while i <= len(palabras) - n:
        trozo = " ".join(palabras[i:i + n])
        if f" {trozo} " in obra:
            j = i + n
            while j < len(palabras) and f" {' '.join(palabras[i:j + 1])} " in obra:
                j += 1
            salida.append(" ".join(palabras[i:j]))
            i = j
        else:
            i += 1
    return salida


def _hojas(calibre_id) -> list[str]:
    """El texto de las hojas del PDF del libro por el resolutor único ([] sin texto o sin libro)."""
    if not str(calibre_id or "").isdigit():
        return []
    try:
        d = Path(__file__).resolve()
        while d != d.parent and not (d / "core" / "py-common" / "biblioteca.py").is_file():
            d = d.parent
        sys.path.insert(0, str(d / "core" / "py-common"))
        import biblioteca as bib  # noqa: E402
        return bib.texto(int(calibre_id)) or []
    except Exception:  # noqa: BLE001 — sin el texto del libro no se puede comprobar: se dice
        return []


def _verificar(meta: dict, cuerpo: str, ruta: Path) -> dict | None:
    """El cotejo de la suite `fichas` (None si el tipo no se coteja o no hay libro)."""
    try:
        V = _verificador()
        r = V.cotejar({**meta, "_ruta": str(ruta)}, cuerpo)
    except Exception as e:  # noqa: BLE001 — sin el texto del libro se dice, no se cae
        return {"estado": "pendiente", "metodo": "", "fecha": "", "detalle": f"no se pudo cotejar: {e}"}
    if r.get("estado") is None:
        return None
    return {"estado": r["estado"], "metodo": r["metodo"] + (f"; {r['detalle']}" if r["estado"] != "verificada_script" and r.get("detalle") else ""),
            "fecha": date.today().isoformat() if r["estado"] != "pendiente" else "", "detalle": r.get("detalle", ""),
            "pagina_pdf": r.get("pagina_pdf")}


def guardar(proyecto: Path, datos: dict, entrada: dict | None, archivo: str | None = None, huella_base: str | None = None,
            aplicar: bool = False, referencia: str = "") -> dict:
    """Crea (`archivo` None) o corrige una ficha. `entrada` es la fuente del proyecto a la que pertenece ({clave,
    calibre_id, zotero_key}; None en una síntesis). Sin `aplicar` no escribe: devuelve lo que escribiría (`texto`, `diff`,
    `archivo`, `verificacion`, `problemas`). Corregir exige la huella con que se abrió (`Cambiada` si en disco es otra);
    una página o un tipo nuevos cambian el nombre y los enlaces de las otras fichas se corrigen."""
    proyecto = Path(proyecto)
    if archivo:
        p0 = _ruta(proyecto, archivo)
        if huella(p0.read_text(encoding="utf-8")) != huella_base:
            raise Cambiada(leer(proyecto, p0.name))
    datos = _limpiar(datos)
    tipo = datos["tipo"]
    if tipo != "ficha_sintesis" and not (entrada and entrada.get("clave")):
        raise ValueError("La ficha es de una obra del escrito: falta su clave (añada el libro a las fuentes).")
    car = carpeta(proyecto)
    previa_meta: dict = {}
    previas: dict[str, str] = {}
    texto_previo = ""
    p_vieja = None
    if archivo:
        p_vieja = _ruta(proyecto, archivo)
        texto_previo = p_vieja.read_text(encoding="utf-8")
        if huella(texto_previo) != huella_base:
            raise Cambiada(leer(proyecto, p_vieja.name))
        previa_meta, cuerpo_previo = F.leer(p_vieja)
        previas = F.secciones(cuerpo_previo)
        if previa_meta.get("tipo") not in DE_TIPO:
            raise ValueError("Esa ficha no tiene el frontmatter único de un tipo que se edite aquí: se corrige a mano.")
        clave_previa = previa_meta.get("clave_bibtex")
        if entrada and clave_previa and not isinstance(clave_previa, list) and str(clave_previa) != entrada["clave"]:
            raise ValueError("Una ficha no cambia de obra: haga otra ficha de la obra nueva.")
    # el lugar y el nombre
    if tipo in ("ficha_textual", "ficha_parafrasis"):
        lugar, pagina = lugar_de(datos.get("pagina"))
    else:
        lugar, pagina = "", ""
    literal_sec = LITERAL.get(tipo, "")
    literal = _sin_comillas(datos["secciones"].get(literal_sec, "")) if literal_sec else ""
    literal_previo = _sin_comillas(previas.get(literal_sec, "")) if literal_sec else ""
    cita_cambio = clave_literal(literal) != clave_literal(literal_previo)
    tema = tema_de(datos.get("tema") or literal or datos["secciones"].get("Paráfrasis", "") or datos["secciones"].get("Párrafo de síntesis", ""))
    clave = (entrada or {}).get("clave", "")
    if tipo == "ficha_fuente":
        base = f"{nombre_clave(clave)}-fuente"
    elif tipo == "ficha_obra":
        base = f"{nombre_clave(clave)}-obra"
    elif tipo == "ficha_sintesis":
        base = f"sintesis-{tema}"
    else:
        base = f"{nombre_clave(clave)}-{lugar}-{DE_TIPO[tipo]}-{tema}"
    prefijo = base if tipo in ("ficha_fuente", "ficha_obra") else (f"{nombre_clave(clave)}-{lugar}-{DE_TIPO[tipo]}-" if lugar else None)
    if p_vieja is not None and (p_vieja.stem == base or (prefijo and p_vieja.name.startswith(prefijo)) or tipo == "ficha_sintesis"
                                and previa_meta.get("tipo") == tipo):
        destino = p_vieja
    else:
        destino, i = car / f"{base}.md", 2
        while destino.exists() and destino != p_vieja:
            if tipo in ("ficha_fuente", "ficha_obra"):
                cual = "de fuente" if tipo == "ficha_fuente" else "de obra"
                raise ValueError(f"La obra ya tiene su ficha {cual} en este escrito ({destino.name}): ábrala y corríjala.")
            destino, i = car / f"{base}-{i}.md", i + 1
    # el frontmatter
    meta = {k: previa_meta.get(k, "") for k in config.CLAVES}
    meta.update({"tipo": tipo, "proyecto": proyecto.name, "uso": datos["uso"] or previa_meta.get("uso") or ""})
    if entrada:
        meta.update({"calibre_id": entrada.get("calibre_id") or previa_meta.get("calibre_id") or "",
                     "zotero_key": entrada.get("zotero_key") or previa_meta.get("zotero_key") or "", "clave_bibtex": clave})
    if tipo in ("ficha_textual", "ficha_parafrasis"):
        meta["pagina"] = pagina
    if tipo != "ficha_fuente":
        meta["categoria"] = datos["categoria"]
    # el origen (norma §1, 1.1): el que ya tenía la ficha manda (una corrección no cambia quién la propuso); una ficha nueva
    # del LLM lleva el pedido; una de antes sin bloque, el que dice su marca de §8 si es del LLM; la de la persona, ninguno
    origen = previa_meta.get("origen") if isinstance(previa_meta.get("origen"), dict) else None
    if origen is None and p_vieja is not None:
        de_antes = F.origen_de(previa_meta, cuerpo_previo)
        origen = de_antes if de_antes["autor"] == "llm" else None
    if origen is None and p_vieja is None and datos["origen"] and datos["origen"]["autor"] != "persona":
        # la norma de fichas 1.1 (§1): el bloque solo va si la propuso alguien distinto de quien la firma (el LLM)
        origen = datos["origen"]
    if origen:
        meta["origen"] = {k: str(origen.get(k) or "") for k in config.CLAVES_ORIGEN}
    del_llm = bool(origen) and origen.get("autor") == "llm"
    # el cuerpo
    secs = dict(previas)
    secs.update({k: v for k, v in datos["secciones"].items()})
    fuente = f"{nombre_clave(clave)}-fuente.md" if clave else ""
    if literal_sec and literal:
        secs[literal_sec] = previas[literal_sec] if not cita_cambio and previas.get(literal_sec) else _cita(literal)
    if tipo in ("ficha_textual", "ficha_parafrasis"):
        if str(previa_meta.get("pagina")) != str(pagina) or "Localización para el cotejo" not in previas:
            if tipo == "ficha_textual":
                secs["Localización para el cotejo"] = (f"Calibre {meta['calibre_id']}" if meta.get("calibre_id")
                                                       else "La fuente no existe en Calibre: queda pendiente de los pasos 00–03") + (
                    f", página {pagina} del PDF (impresa)." if isinstance(pagina, int) else f", {pagina}.")
    if tipo not in ("ficha_fuente", "ficha_obra"):
        enc = secs.get("Encadenamiento") or ""
        if fuente and f"]({fuente})" not in enc:
            enc = f"Proviene de [{fuente[:-3]}]({fuente})." + (f"\n\n{enc}" if enc else "")
        secs["Encadenamiento"] = enc or "Ninguno todavía."
    if tipo == "ficha_textual":
        secs.setdefault("Análisis", "")
        secs["Análisis"] = secs["Análisis"] or "Sin análisis todavía: lo escribe quien la lee contra el original."
    if tipo == "ficha_parafrasis":
        secs["Origen literal"] = secs.get("Origen literal") or "Sin origen literal: la paráfrasis no se coteja hasta que lo tenga."
        secs["Control de fidelidad"] = secs.get("Control de fidelidad") or "Pendiente: lo comprueba quien la lee contra el original."
    if tipo == "ficha_fuente":
        secs.setdefault("Datos de verificación de existencia", f"Calibre {meta['calibre_id']}." if meta.get("calibre_id") else
                        "La fuente no existe en Calibre: queda pendiente de los pasos 00–03.")
        secs.setdefault("Fichas derivadas", "Ninguna.")
    if "Observaciones" in config.SECCIONES[tipo] or secs.get("Observaciones"):
        obs = secs.get("Observaciones", "").strip()
        if not archivo and FIRMA not in obs:
            obs = (obs + "\n\n" if obs and obs.lower() not in ("ninguna", "ninguna.") else "") + f"{FIRMA} el {date.today().isoformat()}."
        if not archivo and del_llm and F.MARCA_IA not in obs.lower():
            # la marca legible (§8) también en el cuerpo: sobrevive a una herramienta que reescriba el frontmatter sin el bloque
            obs += (f"\n\nPropuesta por IA el {origen['fecha']} ({origen['herramienta']}): entra a un trabajo cuando la "
                    "persona coteja su página en el PDF.")
        secs["Observaciones"] = obs or "Ninguna."
    for s in config.SECCIONES[tipo]:
        secs.setdefault(s, "Pendiente.")
    # la verificación
    pv = previa_meta.get("verificacion") if isinstance(previa_meta.get("verificacion"), dict) else {}
    cuerpo = _componer({**meta, "verificacion": pv or {}}, secs, tipo).split("---\n", 2)[-1]
    if tipo in LITERAL and not cita_cambio and pv.get("estado") == "verificada_autor" and str(previa_meta.get("pagina")) == str(pagina):
        verif = {k: pv.get(k, "") for k in config.CLAVES_VERIFICACION}
        detalle = "verificada por el autor; el literal no cambió"
    elif tipo in LITERAL and meta.get("calibre_id"):
        r = _verificar(meta, cuerpo, destino)
        verif = {k: (r or {}).get(k, "") for k in config.CLAVES_VERIFICACION} if r else {"estado": "pendiente", "metodo": "", "fecha": ""}
        detalle = (r or {}).get("detalle", "")
    elif tipo == "ficha_sintesis":
        r = _verificar(meta, cuerpo, destino)
        verif = {k: (r or {}).get(k, "") for k in config.CLAVES_VERIFICACION} if r else {"estado": "pendiente", "metodo": "", "fecha": ""}
        detalle = (r or {}).get("detalle", "")
    elif tipo == "ficha_obra":
        hojas = _hojas(meta.get("calibre_id"))
        copias = copiado(" ".join(datos["secciones"].get(s, "") for s in GUIAS_OBRA), hojas)
        if copias:
            verif = {"estado": "observada", "metodo": "palabras propias; repite pasajes de la obra", "fecha": date.today().isoformat()}
            detalle = "Copia de la obra: «" + "», «".join(c[:90] for c in copias[:3]) + "»; escríbelo con tus palabras."
        elif hojas:
            verif = {"estado": "verificada_script", "metodo": f"palabras propias; ninguna serie de {COPIA_PALABRAS} palabras de la obra",
                     "fecha": date.today().isoformat()}
            detalle = ""
        else:
            verif = {"estado": "pendiente", "metodo": "", "fecha": ""}
            detalle = "Sin el texto del libro no se comprueba que esté escrita con palabras propias."
    else:
        verif = {k: pv.get(k, "") for k in config.CLAVES_VERIFICACION} if pv.get("estado") else {"estado": "pendiente", "metodo": "", "fecha": ""}
        detalle = ""
    if del_llm and verif.get("estado") and verif["estado"] != "pendiente" and F.MARCA_IA not in str(verif.get("metodo") or "").lower():
        verif = {**verif, "metodo": "propuesta por IA; " + str(verif.get("metodo") or "cotejo literal")}
    meta["verificacion"] = verif
    texto = _componer(meta, secs, tipo)
    problemas = _validar_texto(destino, texto)
    diff = "".join(difflib.unified_diff(texto_previo.splitlines(keepends=True), texto.splitlines(keepends=True),
                                        fromfile=p_vieja.name if p_vieja else "/dev/null", tofile=destino.name))
    cuerpo_final = texto.split("---\n", 2)[-1]
    si, motivo = F.citable(meta, cuerpo_final)
    salida = {"archivo": destino.name, "ruta": str(destino), "texto": texto, "diff": diff, "nueva": p_vieja is None,
              "renombra": bool(p_vieja is not None and destino != p_vieja), "antes": p_vieja.name if p_vieja else "",
              "verificacion": verif, "detalle": detalle, "problemas": problemas, "escrito": False,
              "origen": F.origen_de(meta, cuerpo_final), "citable": si, "motivo": motivo,
              "registro_ia": {"pendiente": True} if del_llm and p_vieja is None else {}}
    if tipo == "ficha_obra" and verif["estado"] == "observada":
        salida["problemas"] = list(problemas) + [detalle]
    if not aplicar:
        return salida
    if tipo == "ficha_obra" and verif["estado"] == "observada":
        raise ValueError(detalle)
    car.mkdir(parents=True, exist_ok=True)
    _escribir(destino, texto)
    if p_vieja is not None and destino != p_vieja:
        p_vieja.unlink()
        _corregir_enlaces(car, p_vieja.name, destino.name)
    if entrada and tipo != "ficha_fuente":
        f = car / fuente
        if not f.exists():
            _escribir(f, _texto_fuente(entrada, proyecto.name, destino.name, referencia))
        else:
            viejo = f.read_text(encoding="utf-8")
            nuevo = _unir_derivadas(viejo, destino.name)
            if nuevo != viejo:
                _escribir(f, nuevo)
    registro = registrar_ia(proyecto, destino, meta, tipo) if del_llm and p_vieja is None else {}
    return {**salida, **leer(proyecto, destino.name), "escrito": True, "diff": diff, "detalle": detalle, "registro_ia": registro}


def registrar_ia(proyecto: Path, destino: Path, meta: dict, tipo: str) -> dict:
    """C12.1: la ficha que propuso el LLM entra al registro de uso de IA del escrito (`ia/registro.yml`) y a su declaración
    (`ia/declaracion.tex`), por la orden de escritura que los escribe (`scripts/antes_de_entregar.py registrar_ia`; su
    `entrega/ia.py`), para que haya un solo registro por escrito. Sin escritura a mano, se dice y la ficha queda marcada."""
    import json
    import subprocess
    codigo = Path(os.environ.get("ESCRITURA_CODIGO") or RAIZ.parent / "escritura") / "scripts" / "antes_de_entregar.py"
    if not codigo.is_file():
        return {"error": f"No se halló {codigo}: la ficha queda marcada como del LLM, sin el registro del escrito."}
    o = meta.get("origen") or {}
    pagina = f", p. {meta['pagina']}" if meta.get("pagina") not in (None, "") else ""
    datos = {"fecha": o.get("fecha") or date.today().isoformat(), "archivo": f"{CARPETA.as_posix()}/{destino.name}",
             "parte": f"Ficha {NOMBRES.get(DE_TIPO.get(tipo, ''), '').lower()} de {meta.get('clave_bibtex') or 'la obra'}{pagina}",
             "herramienta": o.get("herramienta") or HERRAMIENTA_IA, "prompt": {"titulo": o.get("herramienta") or "estudio de obra"},
             "resumen": "propuso la ficha; la persona la revisó en Biblioteca Studio y la guardó para cotejar su página"}
    try:
        r = subprocess.run([sys.executable, str(codigo), "registrar_ia", str(proyecto), json.dumps(datos, ensure_ascii=False), "--aplicar"],
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "WRITING_DIR": os.environ.get("WRITING_DIR") or str(Path(proyecto).parents[1])})
        salida = json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return {"error": f"No se pudo registrar el uso de la IA: {e}"}
    if salida.get("error") or not salida.get("escrito"):
        return {"error": salida.get("error") or (r.stderr.strip()[:300] or "el registro no se escribió")}
    return {"registro": salida.get("registro", "ia/registro.yml"), "total": salida.get("total", 0)}


def cotejar(proyecto: Path, archivo: str, huella_base: str, aplicar: bool = False) -> dict:
    """La persona cotejó la página en el PDF (norma §8): la ficha pasa a `verificada_autor` y, si la propuso la IA, ya se
    puede citar. Exige la huella con que se abrió (`Cambiada` si en disco es otra); simula sin `aplicar`."""
    p = _ruta(Path(proyecto), archivo)
    texto = p.read_text(encoding="utf-8")
    if huella(texto) != huella_base:
        raise Cambiada(leer(Path(proyecto), p.name))
    meta, cuerpo = F.leer(p)
    if meta.get("tipo") not in ("ficha_textual", "ficha_parafrasis", "ficha_sintesis"):
        raise ValueError("Solo se cotejan en la página las fichas textuales, de paráfrasis y de síntesis.")
    llm = F.origen_de(meta, cuerpo)["autor"] == "llm"
    metodo = ("propuesta por IA; " if llm else "") + "lectura del autor en la página"
    v = {"estado": "verificada_autor", "metodo": metodo, "fecha": date.today().isoformat()}
    # solo cambia el bloque `verificacion` del frontmatter: lo demás de la ficha queda tal cual, byte a byte
    m = re.match(r"^---\n(.*?\n)---\n", texto, re.S)
    if not m or not re.search(r"^verificacion:[ \t]*\n(?:[ \t]+.*\n)*", m.group(1), re.M):
        raise ValueError("La ficha no tiene el bloque «verificacion» de la norma: corríjala a mano.")
    bloque = "verificacion:\n" + "".join(f"  {k}: {F._y(v[k])}\n" for k in config.CLAVES_VERIFICACION)
    front = re.sub(r"^verificacion:[ \t]*\n(?:[ \t]+.*\n)*", lambda _m: bloque, m.group(1), count=1, flags=re.M)
    texto_nuevo = "---\n" + front + "---\n" + texto[m.end():]
    diff = "".join(difflib.unified_diff(texto.splitlines(keepends=True), texto_nuevo.splitlines(keepends=True), fromfile=p.name, tofile=p.name))
    r = {"archivo": p.name, "verificacion": v, "diff": diff, "escrito": False}
    if aplicar:
        _escribir(p, texto_nuevo)
        r = {**r, **leer(Path(proyecto), p.name), "escrito": True}
    return r


def _validar_texto(destino: Path, texto: str) -> list[str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", texto, re.S)
    import yaml
    meta = (yaml.safe_load(m.group(1)) or {}) if m else {}
    return F.validar(destino, meta, m.group(2) if m else texto)


def _corregir_enlaces(car: Path, antes: str, nombre: str) -> None:
    for p in car.glob("*.md"):
        t = p.read_text(encoding="utf-8")
        nuevo = t.replace(f"[{antes[:-3]}]({antes})", f"[{nombre[:-3]}]({nombre})").replace(f"]({antes})", f"]({nombre})")
        if nuevo != t:
            _escribir(p, nuevo)
