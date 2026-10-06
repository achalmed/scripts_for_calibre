"""bibtex.py — el `references.bib` de un proyecto a partir de su `fuentes.yml` (2026-09-16).

Objetivo : que ninguna entrada bibliográfica se teclee a mano cuando la obra ya
           está en Calibre. El manifiesto dice QUÉ obra usa el proyecto
           (`calibre_id`); Calibre es la autoridad de sus metadatos; este
           módulo los traduce a BibLaTeX (APA 7 vía biblatex-apa) y deja la
           `clave_bibtex` escrita en el manifiesto, que es el vínculo que las
           fichas (`fuentes/fichas/`) y el texto (`\\textcite{clave}`) usan.
Método   : una entrada por fuente con `calibre_id`; el tipo BibLaTeX sale del
           `#item_type` / `#clasificador` de Calibre (Statute → @legislation,
           Report → @report, Book → @book, Document → @report, resto → @misc);
           el autor corporativo va entero entre dobles llaves con `shortauthor`
           (normas_apa7.md §14); las normas llevan `shorttitle` con su número
           para que la cita parentética sea «(Ley N.° 30057, 2013)» y no el
           título completo. El bloque generado vive entre los marcadores
           `% manifiesto:inicio` / `% manifiesto:fin` del `.bib`: lo escrito a
           mano fuera de ellos se conserva (mismo patrón que `suite:inicio`
           en los README).
Fundamento: normas_apa7.md §1 (correspondencia total), §7 (corporativos),
           §14 (equivalencias del framework); docs/16 §2 (fuentes por
           `calibre_id`); prueba de composición con `\\documentclass{informe}`
           (2026-09-16): @legislation con `shorttitle` cita por número.
Alternativa: exportar desde Zotero con Better BibTeX. Se descarta como paso
           obligatorio: no todas las obras tienen `zotero_key`, y el sync
           Calibre → Zotero es nocturno; Calibre siempre está.
Límite   : no inventa lo que Calibre no tiene (sin año → `date` vacío y aviso);
           un título mal catalogado sale mal catalogado: se corrige en Calibre,
           no aquí (regla 0b).
"""
import re
import unicodedata
from datetime import date
from pathlib import Path

from . import manifiesto as M

bib = M.bib
config = M.config

INICIO = "% manifiesto:inicio"
FIN = "% manifiesto:fin"

# Tipo BibLaTeX según lo que Calibre sabe del libro.
_TIPO = {"statute": "legislation", "report": "report", "book": "book",
         "document": "report", "journalarticle": "article", "thesis": "thesis"}
_TIPO_CLAS = {"normativa": "legislation", "informe": "report", "informe técnico": "report",
              "documento oficial": "report", "libro": "book", "artículo": "article"}

# Normas: el número que va en `shorttitle` (la cita parentética) y en la clave.
_RE_NORMA = re.compile(
    r"^(Ley|Decreto Legislativo|Decreto Supremo|Decreto de Urgencia|Resoluci[oó]n Ministerial|"
    r"Resoluci[oó]n Directoral|Resoluci[oó]n Suprema|Ordenanza Regional|Directiva|Oficio|"
    r"Texto [ÚU]nico Ordenado de la Ley|Convenio)\s+(?:N\.?\s*[°º]\s*)?([\w./-]+)", re.I)
_ABREV = {"ley": "ley", "decreto legislativo": "dleg", "decreto supremo": "ds", "decreto de urgencia": "du",
          "resolución ministerial": "rm", "resolucion ministerial": "rm", "resolución directoral": "rd",
          "resolucion directoral": "rd", "resolución suprema": "rs", "resolucion suprema": "rs",
          "ordenanza regional": "or", "directiva": "directiva", "oficio": "oficio",
          "texto único ordenado de la ley": "tuoley", "texto unico ordenado de la ley": "tuoley", "convenio": "convenio"}

_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "e", "o", "u", "en", "a", "al", "por", "para", "con",
           "sin", "sobre", "un", "una", "unos", "unas", "que", "su", "sus", "n", "ley", "decreto", "informe",
           "the", "of", "and", "an"}


def _ascii(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()


def _palabra(titulo):
    """Primera palabra significativa del título, para la clave `apellidoAAAApalabra`."""
    for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", titulo or ""):
        w2 = _ascii(w).lower()
        if len(w2) > 2 and w2 not in _VACIAS:
            return w2
    return "obra"


def tipo_de(d):
    it = (d.get("#item_type") or "").strip().lower()
    if it in _TIPO:
        return _TIPO[it]
    cl = (d.get("#clasificador") or "").strip().lower()
    return _TIPO_CLAS.get(cl, "misc")


def _norma(titulo):
    """('ley', '30057') si el título es el de una norma; None si no."""
    m = _RE_NORMA.match(titulo or "")
    if not m:
        return None
    return _ABREV.get(m.group(1).lower(), _ascii(m.group(1)).lower().replace(" ", "")), m.group(2).rstrip(".")


def _corporativo(nombre):
    """Una institución que el ecosistema conoce por su sigla es corporativa aunque
    su nombre no lleve una palabra delatora («Mesa de Concertación…»)."""
    return bool(sigla(nombre)) or bib.es_corporativo(nombre)


def _ordenes_calibre(bid):
    """{nombre: sort} de los autores del libro, tal como Calibre los guarda."""
    with bib.conn() as c:
        return {n: s for n, s in c.execute(
            "select a.name, a.sort from authors a join books_authors_link l on l.author=a.id where l.book=?", (int(bid),))}


def _autor_bib(nombre, orden=None):
    """Autor en la forma que BibLaTeX invierte bien: corporativo entre llaves, persona «Apellido, Nombre».

    `orden` es el `sort` que Calibre guarda para ese autor. Una parte de la
    biblioteca (importaciones antiguas) tiene el nombre escrito «Nombre,
    Apellido» («Karl, Marx», «José Carlos, Mariátegui»): Calibre no pudo
    invertirlo y su `sort` es idéntico al nombre. Ese es el delator: nombre
    con coma y `sort` igual → se da la vuelta. Un «Cotler, Julio» de verdad
    tiene nombre «Julio Cotler» y `sort` distinto.
    """
    a = (nombre or "").replace("|", ",").strip()
    if _corporativo(a):
        return "{" + a + "}", a
    if "," in a:
        antes, despues = [x.strip() for x in a.split(",", 1)]
        # Tras la coma de un «Apellido, N.» de verdad van iniciales; tras la de
        # un «Karl, Marx» va un apellido entero. Eso, y el `sort` idéntico,
        # deciden la vuelta.
        iniciales = re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.?\s?)+", despues or "") is not None
        if orden is not None and orden.replace("|", ",").strip() == a and antes and despues and not iniciales:
            return f"{despues}, {antes}", despues
        return a, antes
    apa = bib.autor_apa(a)                  # «Cotler, J.»
    apellido = apa.split(",", 1)[0].strip()
    nombres = a[: -len(apellido)].strip() if a.endswith(apellido) else " ".join(a.split()[:-1])
    return f"{apellido}, {nombres}".strip(", "), apellido


def sigla(nombre):
    """Sigla del autor corporativo (shortauthor), si el ecosistema la conoce."""
    n = bib.norm(nombre or "")
    for s, inst in config.SIGLAS.items():
        if bib.norm(inst) == n:
            return s
    return ""


def clave_para(d, usadas):
    """`apellidoAAAApalabra`; normas `ley30057`; corporativos `inei2026pobreza`. Única en `usadas`."""
    titulo = d.get("titulo") or ""
    anio = (d.get("pubdate") or "")[:4]
    anio = anio if anio.isdigit() and anio not in ("0101", "0000", "1970") else ""
    n = _norma(titulo)
    if n:
        base = f"{n[0]}{_ascii(n[1]).lower().replace('/', '').replace('.', '')}"
    else:
        autores = d.get("autores") or []
        primero = autores[0] if autores else ""
        s = sigla(primero)
        if s:
            ap = _ascii(s.split()[0]).lower()          # «GORE Ayacucho» → gore
        elif primero and bib.es_corporativo(primero):
            ap = _palabra(primero)                    # «Congreso de la República» → congreso
        elif primero:
            ordenes = _ordenes_calibre(d.get("calibre_id"))
            ap = _ascii(_autor_bib(primero, ordenes.get(primero.replace(",", "|")) or ordenes.get(primero))[1]).lower().replace(" ", "")
        else:
            ap = "anon"
        base = f"{ap}{anio}{_palabra(titulo)}"
    base = re.sub(r"[^a-z0-9-]", "", base) or "obra"
    k, i = base, 2
    while k in usadas:
        k = f"{base}{i}"; i += 1
    return k


def _campo(k, v):
    v = str(v).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
    return f"  {k:<11} = {{{v}}},\n"


def entrada(e, d, clave):
    """Texto BibLaTeX de una fuente del manifiesto (`e`) con sus datos de Calibre (`d`)."""
    tipo = tipo_de(d)
    titulo = (d.get("titulo") or "").strip()
    fecha = d.get("pubdate") or ""
    anio = fecha[:4] if fecha[:4].isdigit() and fecha[:4] not in ("0101", "0000", "1970") else ""
    # Calibre pone 01-01 cuando solo conoce el año (y calibredb lo guarda como
    # 01-02 UTC al fijarlo desde la línea de órdenes): no se finge un día
    # exacto. APA 7 fecha los informes y libros por año; el día completo solo
    # aporta en una norma (fecha de promulgación).
    dia_conocido = bool(anio) and fecha[5:] not in ("01-01", "01-02", "")
    date_ = fecha if (dia_conocido and tipo == "legislation") else anio
    out = [f"@{tipo}{{{clave},\n"]
    n = _norma(titulo)
    if tipo == "legislation":
        out.append(_campo("title", titulo))
        # La cita parentética lleva el nombre corto: el número de la norma
        # («Ley N.° 30057») o, si no lo hay, el título hasta el primer
        # inciso («Constitución Política del Perú (texto actualizado…)»).
        corto = (titulo.split(".")[0].split(",")[0] if n else re.split(r"\s[(:]", titulo)[0]).strip()
        if corto and corto != titulo:
            out.append(_campo("shorttitle", corto))
        if date_:
            out.append(_campo("date", date_))
        out.append(_campo("note", "Perú"))
    else:
        autores = d.get("autores") or []
        if autores:
            ordenes = _ordenes_calibre(d.get("calibre_id"))
            # Obra coordinada o compilada (etiqueta `obra_coordinada` en Calibre): quienes figuran como autores son
            # sus coordinadores, y APA 7 los da como editores, «Navarro, F. (Ed.)», no como autores. (2026-09-29)
            rol = "editor" if "obra_coordinada" in (d.get("tags") or []) else "author"
            out.append(_campo(rol, " and ".join(_autor_bib(a, ordenes.get(a.replace(",", "|")) or ordenes.get(a))[0] for a in autores)))
            if len(autores) == 1 and _corporativo(autores[0]):
                s = sigla(autores[0])
                if s:
                    out.append(_campo("shortauthor", "{" + s + "}"))
        out.append(_campo("title", titulo))
        presentacion = (d.get("#item_type") or "").strip().lower() == "presentation"
        if presentacion:
            # APA 7 describe el formato entre corchetes tras el título: «El párrafo [Diapositivas]». (2026-09-29)
            out.append(_campo("titleaddon", "Diapositivas"))
        ed_num = d.get("#edition")
        if ed_num and str(ed_num).isdigit() and int(ed_num) > 1 and tipo == "book":
            # APA 7 da la edición si no es la primera: «(8.ª ed.)». Calibre la guarda en #edition. (2026-09-29)
            # como texto y no como número: biblatex-apa escribiría «3a ed.», y la ortografía pide «3.ª ed.»
            out.append(_campo("edition", f"{int(ed_num)}.ª ed."))
        if date_:
            out.append(_campo("date", date_))
        ed = d.get("editorial") or ""
        if ed and (not autores or bib.norm(ed) != bib.norm(autores[0])):
            # biblatex-apa no imprime `publisher` en @misc: la institución de unas diapositivas va en organization.
            out.append(_campo("institution" if tipo == "report" else ("organization" if tipo == "misc" else "publisher"), ed))
        elif tipo == "report" and autores and sigla(autores[0]):
            # APA 7: cuando el autor ES la editorial no se repite; biblatex-apa
            # lo omite solo si coinciden letra a letra, así que se da la sigla.
            out.append(_campo("institution", sigla(autores[0])))
        isbn = (d.get("identificadores") or {}).get("isbn")
        if isbn and tipo == "book":
            out.append(_campo("isbn", isbn))
        doi = (d.get("identificadores") or {}).get("doi")
        if doi:
            out.append(_campo("doi", doi))
    out.append(_campo("langid", "spanish" if "eng" not in (d.get("idiomas") or []) else "english"))
    out.append("}\n")
    # El vínculo con la biblioteca va en comentario: Biber avisa de todo campo
    # que su modelo de datos no conoce, y un aviso por entrada es ruido.
    return f"% calibre_id: {d.get('calibre_id')}\n" + "".join(out)


def generar(raiz, bib_path=None, aplicar=False):
    """Escribe el bloque generado del `.bib` y las `clave_bibtex` del manifiesto. Devuelve (texto, resumen)."""
    raiz = Path(raiz).absolute()
    data = M.cargar(raiz)
    proyecto = raiz.parent if raiz.name == "fuentes" else raiz
    bib_path = Path(bib_path) if bib_path else proyecto / "references.bib"
    usadas = {e["clave_bibtex"] for e in data["fuentes"] if e.get("clave_bibtex")}
    entradas, sin_libro, sin_anio, por_id = [], [], [], {}
    for e in data["fuentes"]:
        bid = e.get("calibre_id")
        d = bib.datos(bid) if bid else None
        if not d:
            sin_libro.append(e.get("origen", "?")); continue
        if bid in por_id:                      # dos orígenes, un libro: una sola entrada
            e["clave_bibtex"] = por_id[bid]; continue
        if not e.get("clave_bibtex"):
            e["clave_bibtex"] = clave_para(d, usadas); usadas.add(e["clave_bibtex"])
        por_id[bid] = e["clave_bibtex"]
        if not (d.get("pubdate") or "")[:4].isdigit() or (d.get("pubdate") or "")[:4] in ("0101", "0000", "1970"):
            sin_anio.append(e["clave_bibtex"])
        entradas.append(entrada(e, d, e["clave_bibtex"]))
    bloque = (f"{INICIO} — generado por `scripts_for_fuentes/manifiesto/main.py bib` desde fuentes.yml y Calibre "
              f"({date.today().isoformat()}); no se edita a mano: se corrige en Calibre y se regenera.\n\n"
              + "\n".join(entradas) + f"\n{FIN}\n")
    previo = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""
    if INICIO in previo and FIN in previo:
        texto = previo[: previo.index(INICIO)] + bloque + previo[previo.index(FIN) + len(FIN) + 1:]
    else:
        texto = (previo.rstrip("\n") + "\n\n" if previo.strip() else "") + bloque
    res = {"entradas": len(entradas), "sin_libro": sin_libro, "sin_anio": sin_anio, "bib": bib_path}
    if aplicar:
        bib_path.write_text(texto, encoding="utf-8")
        M.guardar(raiz, data)
    return texto, res
