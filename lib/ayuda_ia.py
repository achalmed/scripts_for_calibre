#!/usr/bin/env python3
"""lib/ayuda_ia.py — los prompts del ecosistema en los studios: copiar el prompt de una parte de un escrito o de un estudio
de obra con su traductor, y leer de vuelta lo que respondió el chat; sin llamar a ningún modelo.

Objetivo: lo que Yachay ofrece con «Ayuda de la IA» y «Estudiar por partes» también en LaTeX Studio (la parte abierta del
  escrito) y en Biblioteca Studio (un tramo de un libro): el prompt de `~/Documents/prompts` con su sección «4 Entrada»
  rellena, traducido para una IA externa, y lo pegado, comprobado sin IA y mostrado como cambio sugerido que el autor
  acepta (decisiones §9.5).
Método: el prompt se lee del disco cada vez. Qué prompt sirve a cada parte lo dice el cuadro de Yachay
  (`yachay/estudios/prompts_por_parte.py`) y cuáles son las miradas del estudio de obra, su catálogo
  (`yachay/estudios/catalogo.py`): los dos son puros y se cargan por su ruta, como el traductor
  (`prompts/scripts/para_ia_externa.py`); sin ellos, el prompt general de redacción y ninguna mirada. Lo pegado se lee como
  Yachay: el bloque ```latex de una parte (`ayuda_componente.verificar`: sin `\\componente` ni `\\section`, con las claves de
  su bibliografía, sin las marcas de trabajo) y el bloque `tipo: estudio-de-obra` de un estudio (el contrato
  `estudio-de-obra.yml` de Qillqa): sus fichas, cotejadas en su unidad con el cotejo de la suite `fichas`.
Fundamento: Yachay, `docs/prompts-por-parte.md` y `docs/prompts-del-flujo.md`; `prompts/14 estudio/README.md`.
Límite: no escribe nada. Lo que el autor acepta lo guarda LaTeX Studio con Ctrl+S (la parte) o `lib/fichar.py` (las
  fichas). El tramo de una obra va por hojas del PDF (las unidades `uN` son hojas; Yachay usa las de su acervo).
"""
from __future__ import annotations

import difflib
import importlib.util
import os
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REDACCION = "10 redaccion/prompt_03_redaccion.md"
LARGO = 60000          # caracteres: por encima, un chat externo puede cortar el mensaje (Yachay, prompts_del_flujo.LARGO)
MAX_FICHAS = 30
MAX_FICHA = 600
RE_ABRE = re.compile(r"^\\componente(?:\[([^\]\n]*)\])?\{([^}\n]*)\}", re.M)
RE_CITA = re.compile(r"\\(?:paren|text|auto|foot)?cites?\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
RE_ENTRADA_BIB = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
PROHIBIDO = [(re.compile(r"\\componente\b"), "la línea \\componente la pone el escrito: el bloque trae solo el cuerpo"),
             (re.compile(r"\\(?:chapter|section)\*?\s*[\[{]"), "el componente ya es la sección: use \\subsection si necesita subtítulos"),
             (re.compile(r"\\(?:documentclass|usepackage|input|include|begin\{document\}|end\{document\})\b"),
              "el maestro y el preámbulo no se tocan desde aquí"),
             (re.compile(r"\\(?:write18|immediate|openout|directlua|luaexec)\b"), "esa orden no va en una parte")]
_ROTULOS = r"(?:H|I|O|PRENSA|HECHO|INTERPRETACI[ÓO]N|VALORACI[ÓO]N|OPINI[ÓO]N|C[ÁA]LCULO|ESTIMACI[ÓO]N|DATO)"
RE_MARCA_AL_COMIENZO = re.compile(rf"(?m)^([ \t]*)\[{_ROTULOS}\][ \t]*")
RE_MARCA_ROTULO = re.compile(rf"[ \t]*(?<![\\\w\]])\[{_ROTULOS}\]")
RE_MARCA_FALTA = re.compile(r"(?<![\\\w])\[(VERIFICAR|VAC[ÍI]O|CONFLICTO|SUPUESTO|PENDIENTE)\b[:\s]*([^\]]*)\]", re.I)
QUE_FALTA = {"VERIFICAR": "confirmar en la fuente oficial", "VACIO": "laguna que resolver", "CONFLICTO": "antinomia que resolver",
             "SUPUESTO": "supuesto que confirmar", "PENDIENTE": "por completar"}
# Las fichas del estudio de obra (estudio-de-obra.yml, bloque `ficha`) y la ficha del escrito que les toca.
CLASE_DE = {"textual_simple": "textual", "textual_compuesta": "textual", "textual_con_interpolacion": "textual", "mixta": "textual",
            "comentario": "textual", "parafrasis": "parafrasis", "resumen": "parafrasis"}

FORMATO_DE_VUELTA = (
    "## Formato de vuelta para el editor (manda sobre el «7 Formato de salida» del prompt)\n"
    "Devuelve PRIMERO un solo bloque de código `latex`, y después, si el prompt lo pide, su control en texto llano:\n\n"
    "```latex\n% componente: {clave}\n(el cuerpo de la parte)\n```\n\n"
    "- Párrafos separados por una línea en blanco; `\\textit{{…}}` y `\\emph{{…}}` para resaltar; `\\subsection{{…}}` si hace falta un subtítulo.\n"
    "- Citas solo con `\\parencite[p.~N]{{clave}}` o `\\textcite{{clave}}` y solo con las claves de la entrada; la cita textual, con su página.\n"
    "- Sin `\\componente`, `\\section`, `\\documentclass`, `\\usepackage` ni `\\input`.\n"
    "- Texto final, como irá en el documento entregado: sin las marcas de trabajo del prompt (`[H]`, `[I]`, `[VERIFICAR]`, `[VACÍO]`…); "
    "lo que dirían va en el control, después del bloque.\n"
    "- Lo que falte, marcado en el texto: `[dato pendiente: …]` o `[ficha pendiente: …]`; nunca inventado.\n"
    "- El editor lo comprueba sin IA y lo muestra como cambio sugerido: la persona lo acepta o lo descarta.")


# --- carpetas y módulos cargados por su ruta ----------------------------------------------------------------------------

def _env():
    sys.path.insert(0, str(RAIZ / "lib"))
    import indice
    return indice._env()


def prompts_dir() -> Path:
    return Path(os.environ.get("PROMPTS_DIR") or _env().PROMPTS_DIR)


def yachay_dir() -> Path:
    """El código de Yachay (de él se leen, por su ruta, el cuadro de prompts por parte y el catálogo de miradas)."""
    return Path(os.environ.get("YACHAY_CODIGO") or Path(_env().DOCS_ROOT) / "yachay")


def _cargar(nombre: str, ruta: Path):
    clave = f"{nombre}:{ruta}"
    if clave in sys.modules:
        return sys.modules[clave]
    if not ruta.is_file():
        return None
    spec = importlib.util.spec_from_file_location(clave, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[clave] = m
    try:
        spec.loader.exec_module(m)
    except Exception:  # noqa: BLE001 — un módulo ajeno roto no tumba el studio: se sigue sin él
        del sys.modules[clave]
        return None
    return m


def comun():
    """`core/py-common/ia_externa.py`: lo común de «copiar el prompt / pegar lo de la IA» (2026-11-23); None sin él."""
    return _cargar("core_ia_externa", Path(os.environ.get("PY_COMMON") or _env().PY_COMMON) / "ia_externa.py")


def traductor():
    c = comun()
    if c is not None:
        return c.traductor(prompts_dir())
    return _cargar("para_ia_externa", prompts_dir() / "scripts" / "para_ia_externa.py")


def sensible(texto: str) -> str:
    """El aviso C12.3 de un prompt que declara `datos_sensibles` (estudiantes, despacho, personales), o ""."""
    c = comun()
    return (c.aviso_sensible(texto, prompts_dir()) or "") if c is not None else ""


def cuadro():
    """`prompts_por_parte` de Yachay (qué prompt escribe cada parte); None sin Yachay."""
    return _cargar("yachay_prompts_por_parte", yachay_dir() / "yachay" / "estudios" / "prompts_por_parte.py")


def catalogo():
    return _cargar("yachay_catalogo", yachay_dir() / "yachay" / "estudios" / "catalogo.py")


def _frontmatter(texto: str) -> dict:
    import yaml
    m = re.match(r"\A---\n(.*?)\n---\n", texto or "", re.S)
    try:
        d = yaml.safe_load(m.group(1)) if m else {}
    except yaml.YAMLError:
        d = {}
    return d if isinstance(d, dict) else {}


def leer_prompt(rel: str) -> str:
    c = comun()
    if c is not None:                            # con la guarda del módulo común: nunca un archivo fuera del repo
        try:
            return c.leer_prompt(rel, prompts_dir())
        except ValueError:
            raise LookupError(f"No está el prompt {rel} en la carpeta de prompts: sin él no hay método que copiar.") from None
    ruta = prompts_dir() / rel
    if not ruta.is_file():
        raise LookupError(f"No está el prompt {rel} en la carpeta de prompts: sin él no hay método que copiar.")
    return ruta.read_text(encoding="utf-8")


def para_ia_externa(texto: str, extra: tuple[str, ...] = (), claves: dict | None = None) -> str:
    """El prompt listo para un chat externo (sin frontmatter ni rutas, con lo esencial de las normas que cita)."""
    c = comun()
    if c is not None:                            # el traductor del repo, cargado una vez por el módulo común
        return c.para_ia(texto, prompts_dir(), extra=extra, claves=claves or {}) + "\n"
    m = traductor()
    if m is None:
        return re.sub(r"\A---\n.*?\n---\n", "", texto or "", count=1, flags=re.S).strip() + "\n"
    return m.para_ia_externa(texto, prompts_dir(), extra=extra, claves=claves or {})


def problemas_externos(texto: str) -> list[str]:
    m = traductor()
    return m.problemas(texto) if m and hasattr(m, "problemas") else []


def _fuente(rel: str, texto: str) -> dict:
    fm = _frontmatter(texto)
    return {"ruta": rel, "titulo": str(fm.get("titulo") or Path(rel).stem), "version": str(fm.get("version") or "")}


# --- una parte de un escrito (LaTeX Studio) -----------------------------------------------------------------------------

def tramos(tex: str) -> list[dict]:
    r"""Los componentes de un archivo, de su línea `\componente` a la siguiente: [{clave, titulo, ini, fin}]."""
    ms = list(RE_ABRE.finditer(tex or ""))
    return [{"clave": m.group(2).strip(), "titulo": (m.group(1) or "").strip() if (m.group(1) or "").strip() != "\\relax" else "",
             "ini": m.end(), "fin": ms[k + 1].start() if k + 1 < len(ms) else len(tex)} for k, m in enumerate(ms)]


def _proyecto_yaml(d: Path) -> dict:
    import yaml
    p = Path(d) / "proyecto.yaml"
    try:
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}
    except (OSError, yaml.YAMLError):
        return {}


def claves_bib(d: Path) -> dict[str, str]:
    """{clave: tipo} de los .bib del proyecto (references.bib y los de la raíz)."""
    salida: dict[str, str] = {}
    for b in sorted(set(Path(d).glob("*.bib")) | set(Path(d).glob("bib/*.bib"))):
        try:
            for tipo, clave in RE_ENTRADA_BIB.findall(b.read_text(encoding="utf-8", errors="replace")):
                if tipo.lower() not in ("comment", "string", "preamble"):
                    salida.setdefault(clave, tipo.lower())
        except OSError:
            continue
    return salida


def sin_comentarios(tex: str) -> str:
    return "\n".join(ln for ln in (tex or "").split("\n") if not ln.lstrip().startswith("%")).strip()


def _plano(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def _destino(esquema: str, clave: str, tipo: str):
    """(ruta del prompt, parte que se le pide, aviso) de la parte; ValueError si no lleva ayuda."""
    pp = cuadro()
    if pp is None:
        return REDACCION, "", "Sin el cuadro de prompts por parte de Yachay: va el prompt general de redacción."
    d = pp.resolver(esquema, clave, tipo)
    if d is None:
        return REDACCION, "", ""
    if isinstance(d, pp.SinAyuda):
        if d in (pp.PARATEXTO, pp.MATERIAL, pp.APARATO, pp.AJENO):
            return REDACCION, "", (f"{d.motivo} Por eso la IA no la escribe: solo pule la redacción de lo que el autor ya "
                                   "escribió, sin añadir personas, hechos, datos ni citas que no estén en el texto.")
        raise ValueError(f"Esta parte no lleva ayuda de la IA. {d.motivo}")
    return d.ruta, d.parte, ""


def _ficha_en_texto(f: dict) -> str:
    lugar = f", p. {f['pagina']}" if f.get("pagina") else ""
    return f"- `{f.get('clave') or '—'}`{lugar} ({f.get('tipo') or 'ficha'}): {(f.get('texto') or '')[:MAX_FICHA]}"


def prompt_parte(d: Path, archivo: str, componente: str = "", fichas: list[dict] | None = None) -> dict:
    """El prompt de UNA parte (el de su componente según el cuadro de Yachay), traducido, con su entrada: el escrito, el
    texto actual de la parte, las fichas que la respaldan, las obras que puede citar y el formato de vuelta.
    → {prompt, componente, titulo, componentes, fuente, aviso, contexto, largo}."""
    d = Path(d)
    ruta = (d / archivo) if not Path(archivo).is_absolute() else Path(archivo)
    tex = ruta.read_text(encoding="utf-8", errors="replace")
    ts = tramos(tex)
    if not ts:
        raise ValueError("Esta parte no declara su componente (\\componente{…}): la ayuda necesita saber qué redacta.")
    tramo = next((t for t in ts if t["clave"] == componente), None) if componente else ts[0]
    if tramo is None:
        raise ValueError(f"Esta parte no tiene el componente «{componente}».")
    ficha = _proyecto_yaml(d)
    esquema, tipo = str(ficha.get("esquema") or ""), str(ficha.get("tipo") or "")
    clave = tramo["clave"]
    titulo_parte = tramo["titulo"] or clave
    rel, parte_del_prompt, aviso = _destino(esquema, clave, tipo)
    texto_prompt = leer_prompt(rel)
    actual = sin_comentarios(tex[tramo["ini"]:tramo["fin"]])
    fichas = list(fichas or [])
    propias = [f for f in fichas if clave in _plano(f.get("uso", "")) or _plano(titulo_parte) in _plano(f.get("uso", ""))]
    usadas = (propias or fichas)[:MAX_FICHAS]
    bib = claves_bib(d)
    titulo_escrito = str(ficha.get("titulo") or d.name)
    entrada = [
        f"Parte que se pide: `{clave}`, «{titulo_parte}»" + (f" (en este prompt, la parte `{parte_del_prompt}`)" if parte_del_prompt and parte_del_prompt != clave else ""),
        f"Escrito: {tipo or 'escrito'} «{titulo_escrito}», " + (f"esquema `{esquema}`." if esquema else "sin esquema declarado."),
        *([f"Atención: {aviso}"] if aviso else []),
        "Componentes de este archivo:\n" + "\n".join(f"{'▶' if t['clave'] == clave else '·'} {t['titulo'] or t['clave']} (`{t['clave']}`)" for t in ts),
        "Texto actual de la parte (lo guardado):\n" + (actual or "(vacía: todavía no tiene texto)"),
        ("Fichas que respaldan esta parte:\n" if propias else
         "Fichas del proyecto (ninguna declara esta parte en su `uso`: elige las que la respaldan y no uses las demás):\n")
        + ("\n".join(_ficha_en_texto(f) for f in usadas) if usadas else "ninguna: lo que no sea del autor queda marcado [ficha pendiente: …]"),
        "Obras que el escrito puede citar (su bibliografía; ninguna otra):\n" + (
            "\n".join(f"- `{k}` ({v})" for k, v in bib.items()) if bib else "ninguna todavía: no cites nada; marca [ficha pendiente: …]"),
    ]
    fuente = _fuente(rel, texto_prompt)
    bloques = [f"# {fuente['titulo']} · para «{titulo_parte}» del {tipo or 'escrito'} «{titulo_escrito}»",
               f"(Versión {fuente['version'] or '—'} de este prompt. Su sección «4 Entrada» la trae, ya rellena, el bloque «entrada» "
               "de abajo: no hace falta abrir nada más.)",
               para_ia_externa(texto_prompt).strip(),
               "<entrada>\n" + "\n\n".join(entrada) + "\n</entrada>",
               FORMATO_DE_VUELTA.format(clave=clave)]
    texto = "\n\n".join(b for b in bloques if b.strip())
    return {"prompt": texto, "componente": clave, "titulo": titulo_parte, "componentes": [{"clave": t["clave"], "titulo": t["titulo"] or t["clave"]} for t in ts],
            "fuente": fuente, "aviso": aviso, "largo": len(texto) > LARGO, "problemas": problemas_externos(texto),
            "sensible": sensible(texto_prompt),
            "contexto": {"fichas": len(usadas), "fichas_de_la_parte": bool(propias), "obras": len(bib)}}


def bloque_latex(texto: str) -> str:
    m = re.search(r"```(?:latex|tex)?[ \t]*\n(.*?)```", texto or "", re.S | re.I)
    return (m.group(1) if m else (texto or "")).strip("\n")


def quitar_marcas(cuerpo: str) -> tuple[str, int, int]:
    cuerpo, al_comienzo = RE_MARCA_AL_COMIENZO.subn(r"\1", cuerpo or "")
    cuerpo, rotulos = RE_MARCA_ROTULO.subn("", cuerpo)

    def pendiente(m: re.Match) -> str:
        clase = unicodedata.normalize("NFKD", m.group(1).upper()).encode("ascii", "ignore").decode()
        return f"[dato pendiente: {(m.group(2) or '').strip() or QUE_FALTA.get(clase, 'por completar')}]"

    cuerpo, faltas = RE_MARCA_FALTA.subn(pendiente, cuerpo)
    return cuerpo, rotulos + al_comienzo, faltas


def _equilibrado(t: str) -> str:
    sin = re.sub(r"\\[{}%]", "", re.sub(r"(?<!\\)%.*$", "", t, flags=re.M))
    n = 0
    for c in sin:
        n += 1 if c == "{" else -1 if c == "}" else 0
        if n < 0:
            return "hay una llave } de más"
    return f"faltan {n} llave{'s' if n != 1 else ''} }}" if n else ""


def pegar_parte(d: Path, archivo: str, pegado: str, componente: str = "", tex: str | None = None) -> dict:
    """Lo que devolvió el chat para una parte, comprobado contra el escrito, sin escribir nada. `tex` es el texto del
    archivo que se tiene abierto (el del editor; sin él, el de disco). → {ok, errores, avisos, componente, ini, fin,
    antes, despues, diff}: el editor reemplaza [ini, fin) por `despues` si la persona acepta."""
    d = Path(d)
    ruta = (d / archivo) if not Path(archivo).is_absolute() else Path(archivo)
    tex = tex if tex is not None else ruta.read_text(encoding="utf-8", errors="replace")
    ts = tramos(tex)
    tramo = (next((t for t in ts if t["clave"] == componente), None) if componente else (ts[0] if ts else None))
    vacio = {"ok": False, "avisos": [], "componente": componente, "ini": 0, "fin": 0, "antes": "", "despues": "", "diff": ""}
    if tramo is None:
        return {**vacio, "errores": ["Esta parte no tiene ese componente (\\componente{…})."]}
    clave = tramo["clave"]
    cuerpo = bloque_latex(pegado)
    errores: list[str] = []
    avisos: list[str] = []
    m = re.match(r"^\s*%\s*componente:\s*([A-Za-z0-9_-]+)\s*$", cuerpo.split("\n", 1)[0]) if cuerpo else None
    if m:
        if m.group(1) != clave:
            errores.append(f"Este bloque es del componente «{m.group(1)}», no de «{clave}». ¿Lo pegó en otra parte?")
        cuerpo = cuerpo.split("\n", 1)[1] if "\n" in cuerpo else ""
    cuerpo = cuerpo.strip()
    if not cuerpo:
        errores.append("No llegó texto: pegue el bloque ```latex que devolvió el chat.")
    cuerpo, rotulos, faltas = quitar_marcas(cuerpo)
    if rotulos or faltas:
        avisos.append("Se quitaron las marcas de trabajo que el documento entregado no lleva"
                      + (f" ({rotulos} como [H] o [I])" if rotulos else "")
                      + (f"; {faltas} {'quedó' if faltas == 1 else 'quedaron'} como [dato pendiente: …]" if faltas else "") + ".")
    sin_com = re.sub(r"(?<!\\)%.*$", "", cuerpo, flags=re.M)
    for patron, porque in PROHIBIDO:
        if patron.search(sin_com):
            errores.append(f"Trae algo que no va: {porque}.")
    bib = claves_bib(d)
    usadas = [k.strip() for g in RE_CITA.findall(cuerpo) for k in g.split(",") if k.strip()]
    faltan = sorted({k for k in usadas if k not in bib})
    if faltan:
        errores.append("Cita obras que el escrito no tiene en su bibliografía: " + ", ".join(faltan)
                       + ". Cítelas antes desde la biblioteca (Citas) o quítelas.")
    roto = _equilibrado(cuerpo)
    if roto:
        errores.append(f"El LaTeX no está cerrado: {roto}.")
    for c in re.finditer(r"[«\"“]([^»\"”]{12,})[»\"”]\s*\\(?:paren|text)cite(\[[^\]]*\])?(?:\[[^\]]*\])?\{", cuerpo):
        if not c.group(2) or not re.search(r"\d", c.group(2)):
            avisos.append("Una cita textual va sin página: APA 7 la pide («…» \\parencite[p.~N]{clave}).")
            break
    pendientes = re.findall(r"\[(?:dato|ficha) pendiente[^\]]*\]", cuerpo)
    if pendientes:
        avisos.append(f"La IA dejó {len(pendientes)} marca{'s' if len(pendientes) != 1 else ''} de pendiente: complételas antes de entregar.")
    antes = tex[tramo["ini"]:tramo["fin"]]
    despues = "\n\n" + cuerpo + ("\n\n" if tramo["fin"] < len(tex) else "\n")
    diff = "".join(difflib.unified_diff(antes.strip("\n").splitlines(keepends=True), cuerpo.splitlines(keepends=True),
                                        fromfile="lo guardado", tofile="lo sugerido"))
    return {"ok": not errores, "errores": errores, "avisos": avisos, "componente": clave, "ini": tramo["ini"], "fin": tramo["fin"],
            "antes": antes, "despues": despues if not errores else "", "diff": diff}


# --- un estudio de obra (Biblioteca Studio) -----------------------------------------------------------------------------

def miradas() -> list[dict]:
    """Las miradas del estudio de una obra por partes (catálogo de Yachay), en su orden de estudio, con su etapa."""
    c = catalogo()
    if c is None:
        return []
    etapa_de = {}
    for etapa, claves in getattr(c, "ETAPAS", ()):
        for k in claves:
            etapa_de.setdefault(k, etapa)
    carpeta = str(getattr(c, "CARPETA_OBRA", "14 estudio")).removeprefix("prompts/")
    salida = []
    for k, dim in c.POR_CLAVE.items():
        if getattr(dim, "objeto", "") != "obra":
            continue
        rel = f"{carpeta}/{dim.archivo}"
        salida.append({"clave": k, "nombre": dim.nombre, "pregunta": dim.pregunta, "numero": dim.numero, "etapa": etapa_de.get(k, ""),
                       "prompt": rel, "existe": (prompts_dir() / rel).is_file()})
    orden = list(getattr(c, "ORDEN_DE_ESTUDIO", ()))
    salida.sort(key=lambda m: (orden.index(m["clave"]) if m["clave"] in orden else 999, m["numero"]))
    return salida


def prompt_obra(libro: dict, mirada: str, paginas: list[str], desde: int, hasta: int, proposito: str = "",
                ya_fichado: str = "") -> dict:
    """El prompt de una mirada sobre un tramo de un libro (hojas `desde`–`hasta` del PDF), traducido, con el paquete: la
    obra y el tramo en unidades «[uN] hoja N» en orden. → {prompt, mirada, fuente, unidades, largo, aviso}."""
    m = next((x for x in miradas() if x["clave"] == mirada), None)
    if m is None:
        raise ValueError("Esa mirada no está en el catálogo del estudio de obra (o falta Yachay).")
    if not paginas:
        raise ValueError("El libro no tiene texto extraíble (¿escaneado sin OCR?): no hay tramo que estudiar.")
    desde, hasta = max(1, int(desde)), min(len(paginas), int(hasta))
    if hasta < desde:
        raise ValueError(f"El tramo va de la hoja {desde} a una anterior: el PDF tiene {len(paginas)} hojas.")
    texto_prompt = leer_prompt(m["prompt"])
    fuente = _fuente(m["prompt"], texto_prompt)
    unidades = []
    for h in range(desde, hasta + 1):
        cuerpo = "\n".join(ln.rstrip() for ln in (paginas[h - 1] or "").splitlines()).strip()
        cuerpo = re.sub(r"\n{3,}", "\n\n", cuerpo)
        unidades.append(f"[u{h}] hoja {h} del PDF\n{cuerpo or '(hoja sin texto)'}")
    autores = "; ".join(libro.get("autores") or [])
    cabeza = [f"Obra: «{libro.get('titulo') or ''}»" + (f", de {autores}" if autores else "") + (f" ({libro['anio']})" if libro.get("anio") else "")
              + (f"; clave de cita `{libro['clave']}`" if libro.get("clave") else "") + ".",
              f"Parte estudiada: hojas {desde} a {hasta} del PDF. Cada unidad es una hoja: cítala como `u<N>`; en `localizador`, la "
              "página impresa que se lee en la hoja (si no la tiene, «hoja N»).",
              "Léxico de la parte: no se cuenta aquí; sale de la lectura.",
              f"Para qué se estudia: {proposito or 'comprender la parte'}.",
              f"Lo que ya está fichado de esta parte: {ya_fichado or 'nada'}."]
    paquete = "\n\n".join(cabeza) + "\n\n" + "\n\n".join(unidades)
    bloques = [f"# {fuente['titulo']}",
               f"(Versión {fuente['version'] or '—'} de este prompt. Su sección «4 Entrada» la trae el bloque «entrada» de abajo: "
               "no hace falta abrir nada más.)",
               para_ia_externa(texto_prompt, ("fichas_formato_y_voz",)).strip(),
               "<entrada>\n" + paquete + "\n</entrada>",
               "## Formato de vuelta\nDevuelve el bloque ```yaml `tipo: estudio-de-obra` de su «7 Formato de salida», con `cita` igual "
               "a la unidad `uN` de cada pasaje y el `texto_citado` literal de esa hoja. Lo que pegues se coteja sin IA en su hoja."]
    texto = "\n\n".join(bloques)
    aviso = ("El tramo es largo para un chat externo: pártalo en menos hojas." if len(texto) > LARGO else "")
    return {"prompt": texto, "mirada": mirada, "nombre": m["nombre"], "fuente": fuente, "unidades": hasta - desde + 1,
            "largo": len(texto) > LARGO, "aviso": aviso, "problemas": problemas_externos(texto), "sensible": sensible(texto_prompt)}


def _bloque_yaml(texto: str) -> str:
    t = (texto or "").replace("\r\n", "\n")
    for m in re.finditer(r"```[ \t]*(?:yaml|yml)?[ \t]*\n(.*?)\n[ \t]*```", t, re.S | re.I):
        if re.search(r"^\s*tipo\s*:|\"tipo\"\s*:", m.group(1), re.M):
            return m.group(1)
    m = re.search(r"^tipo\s*:.*", t, re.M | re.S)
    return m.group(0) if m else ""


def _hoja(cita) -> int | None:
    m = re.match(r"^\s*u?(\d+)\s*$", str(cita or ""), re.I)
    return int(m.group(1)) if m else None


def _pagina_impresa(localizador: str, hoja: int | None):
    m = re.match(r"^\s*pp?\.\s*(\d+)", str(localizador or ""), re.I) or re.match(r"^\s*(\d+)\s*$", str(localizador or ""))
    if m:
        return int(m.group(1))
    return hoja or (localizador or "")


def pegar_obra(pegado: str, paginas: list[str], cotejar=None) -> dict:
    """El bloque `tipo: estudio-de-obra` que devolvió el chat, leído sin IA: el estudio (mirada, unidad, resumen, las
    afirmaciones) y sus fichas propuestas, cada una con su literal cotejado en su hoja (`cotejar(fragmentos, hoja)` → bool;
    sin él, el de la suite `fichas`). → {ok, errores, avisos, estudio, fichas: [{clase, tema, categoria, pagina, hoja,
    cita, parafrasis, analisis, verificacion, detalle}]}."""
    import yaml
    bloque = _bloque_yaml(pegado)
    vacio = {"ok": False, "avisos": [], "estudio": {}, "fichas": []}
    if not bloque:
        return {**vacio, "errores": ["No encuentro el bloque `tipo: estudio-de-obra`: pegue el bloque yaml que devolvió el chat."]}
    try:
        d = yaml.safe_load(bloque) or {}
    except yaml.YAMLError as e:
        return {**vacio, "errores": [f"El bloque no es YAML válido: {str(e).splitlines()[0]}"]}
    if not isinstance(d, dict) or str(d.get("tipo") or "") != "estudio-de-obra":
        return {**vacio, "errores": [f"El bloque es de tipo «{d.get('tipo') if isinstance(d, dict) else '?'}», no un estudio de obra."]}
    sys.path.insert(0, str(RAIZ / "lib"))
    import fichar
    V = fichar._verificador()
    categorias = fichar.config.CATEGORIAS

    def en(hoja: int, texto: str) -> bool:
        frs = V.fragmentos(texto)
        if cotejar is not None:
            return bool(cotejar(frs, hoja))
        return 1 <= hoja <= len(paginas) and V.en_pagina(frs, paginas[hoja - 1])

    avisos: list[str] = []
    fichas = []
    for i, f in enumerate(d.get("fichas") or [], 1):
        if not isinstance(f, dict):
            continue
        tipo = str(f.get("tipo") or "").strip().lower().replace(" ", "_")
        clase = CLASE_DE.get(tipo)
        if clase is None:
            avisos.append(f"La ficha {i} es de un tipo desconocido («{tipo}»): se omite.")
            continue
        literal = " ".join(str(f.get("texto_citado") or "").split())
        hoja = _hoja(f.get("cita"))
        categoria = str(f.get("categoria") or "").strip()
        if categoria not in categorias:
            categoria = "Cita clave" if clase == "textual" else "Idea principal"
        verif, detalle = "pendiente", "sin literal: no se coteja"
        if literal:
            if hoja and en(hoja, literal):
                verif, detalle = "verificada_script", f"el literal está en la hoja {hoja}"
            else:
                otra = next((h for h in range(1, len(paginas) + 1) if h != hoja and en(h, literal)), None)
                verif = "observada"
                detalle = (f"el literal está en la hoja {otra}, no en la {hoja}" if otra and hoja else
                           f"el literal está en la hoja {otra}" if otra else "el literal no está en el PDF: corríjalo antes de guardarla")
                hoja = otra or hoja
        analisis = str(f.get("comentario") or "").strip()
        fichas.append({"n": i, "clase": clase, "tipo_estudio": tipo, "tema": str(f.get("tema") or "").strip(), "categoria": categoria,
                       "pagina": str(_pagina_impresa(f.get("localizador"), hoja) or ""), "hoja": hoja or 0, "cita": literal,
                       "parafrasis": str(f.get("parafrasis") or "").strip(), "analisis": analisis,
                       "verificacion": verif, "detalle": detalle})
    afirmaciones = [a for a in (d.get("afirmaciones") or []) if isinstance(a, dict)]
    estudio = {"mirada": str(d.get("dimension") or ""), "titulo": str(d.get("titulo") or ""), "obra": str(d.get("obra") or ""),
               "unidad": str(d.get("unidad") or ""), "resumen": str(d.get("resumen") or "").strip(),
               "afirmaciones": len(afirmaciones), "observaciones": [str(x) for x in (d.get("observaciones") or [])]}
    errores = [] if (fichas or afirmaciones) else ["El estudio no trae fichas ni afirmaciones."]
    malas = sum(1 for f in fichas if f["verificacion"] == "observada")
    if malas:
        avisos.append(f"{malas} ficha{'s' if malas != 1 else ''} con el literal fuera de su hoja o ausente del PDF: revíselas antes de guardarlas.")
    return {"ok": not errores, "errores": errores, "avisos": avisos, "estudio": estudio, "fichas": fichas}
