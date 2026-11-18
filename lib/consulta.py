#!/usr/bin/env python3
"""lib/consulta.py — la biblioteca para los otros programas (LaTeX Studio, Datafw Studio): buscar un libro, las fichas de un escrito, citar un libro en un escrito, en qué escritos se usa un libro, fichar desde el PDF y los prompts del ecosistema; en JSON.

Objetivo: que quien escribe en LaTeX Studio cite cualquier libro de la biblioteca (no solo lo que ya está en su
  `.bib`), inserte una ficha textual con su página y abra el PDF o el libro en Biblioteca Studio, y que Biblioteca
  Studio diga en qué escritos se usa cada libro (decisiones §9.1).
Método: `buscar` y `usos` SOLO LEEN: el índice compartido (`lib/indice.py`, `$XDG_STATE_HOME/biblioteca/indice.json`),
  el año de `metadata.db` en modo lectura y los `fuentes.yml` y `fuentes/fichas/` de escritura. `fichas` lee las fichas
  de un proyecto con el lector único (`fichas/lib/ficha.py`). `citar` es la única que escribe, y solo en el proyecto:
  añade el libro a su `fuentes/fuentes.yml` con la clave de Better BibTeX (Zotero manda) y regenera su `references.bib`
  con el manifiesto (`manifiesto/lib/bibtex.py`), que conserva toda clave existente; simula sin `--aplicar`.
Fundamento: docs/citar.md (Zotero manda en la clave); decisiones §8.2 y §8.5 (el proyecto declara qué usa, y su
  `.bib` sale de Calibre); la norma de fichas (`prompts/00 metodo/fichas_formato_y_voz.md`).
Límite: un libro sin clave de Zotero recibe la que arma el manifiesto (`apellidoAAAApalabra`); el índice es el de su
  última corrida (el timer lo renueva cada 30 min, y «Actualizar el índice» del Studio).

    python3 lib/consulta.py buscar "economía regional" [--limite 40]
    python3 lib/consulta.py fichas <carpeta del proyecto>
    python3 lib/consulta.py citar <carpeta del proyecto> <calibre_id> [--aplicar]
    python3 lib/consulta.py usos <calibre_id>
    python3 lib/consulta.py escritos                                    # todos los escritos de escritura
    python3 lib/consulta.py formulario                                  # los tipos de ficha, sus secciones y los once rótulos
    python3 lib/consulta.py ficha <proyecto> <archivo>                  # una ficha para editarla, con su huella
    python3 lib/consulta.py nueva_ficha <proyecto> '<json>' [--aplicar]
    python3 lib/consulta.py guardar_ficha <proyecto> <archivo> <huella> '<json>' [--aplicar]
    python3 lib/consulta.py cotejar_ficha <proyecto> <archivo> <huella> [--aplicar]   # la persona cotejó su página
    python3 lib/consulta.py pasaje <calibre_id> <hoja>                  # el texto de una hoja del PDF
    python3 lib/consulta.py miradas
    python3 lib/consulta.py prompt_obra <calibre_id> <mirada> <desde> <hasta> [--proposito …]
    python3 lib/consulta.py pegar_obra <calibre_id> <archivo con lo pegado>
    python3 lib/consulta.py prompt_parte <proyecto> <archivo .tex> [--componente c]
    python3 lib/consulta.py pegar_parte <proyecto> <archivo .tex> <archivo con lo pegado> [--componente c] [--tex buffer]

Fichar y los prompts (decisiones §9.4 y §9.5): `nueva_ficha` y `guardar_ficha` escriben solo en `fuentes/fichas/` del
  proyecto y solo con `--aplicar` (`lib/fichar.py`, con la huella sha256 del archivo: una ficha que cambió en disco
  responde `{"codigo": "ficha_cambiada"}`); si el libro aún no es fuente del escrito, `nueva_ficha --aplicar` lo cita
  antes (`citar`). Los prompts no escriben nada (`lib/ayuda_ia.py`). Un error de lo pedido sale como `{"error": …}`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "lib"))


def _modulo(nombre: str, ruta: Path):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


def _env():
    import indice
    return indice._env()


def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _indice() -> dict:
    import indice
    ruta = indice.ruta_indice()
    if ruta.is_file():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return indice.construir()                       # sin índice todavía: se arma en memoria (solo lee)


def _anios(db: Path, ids: list[int]) -> dict[int, str]:
    if not ids or not db.is_file():
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        marcas = ",".join("?" * len(ids))
        filas = con.execute(f"select id, substr(pubdate, 1, 4) from books where id in ({marcas})", ids).fetchall()
        con.close()
    except sqlite3.Error:
        return {}
    return {i: a for i, a in filas if a and a not in ("0101", "0000", "1970")}


def _cita(clave: str, pagina="") -> str:
    p = str(pagina or "").strip()
    return f"\\parencite[p.~{p}]{{{clave}}}" if p else f"\\parencite{{{clave}}}"


def buscar(texto: str, limite: int = 40) -> list[dict]:
    """Los libros cuyo título, autor, clave o número contienen todas las palabras de `texto` (los de clave primero)."""
    ind = _indice()
    palabras = _normal(texto).split()
    biblioteca = Path(ind.get("biblioteca") or "")
    hallados = []
    for bid, d in ind["libros"].items():
        heno = _normal(" ".join([d.get("titulo", ""), " ".join(d.get("autores", [])), d.get("clave", ""), bid]))
        if all(p in heno for p in palabras):
            hallados.append((bid, d))
    hallados.sort(key=lambda x: (not x[1].get("clave"), _normal(x[1].get("titulo", ""))))
    hallados = hallados[:limite]
    env = _env()
    anios = _anios(Path(env.CALIBRE_DB), [int(b) for b, _ in hallados])
    salida = []
    for bid, d in hallados:
        pdf = next((f for f in d.get("formatos", []) if f.lower().endswith(".pdf")), "")
        portada = biblioteca / d.get("carpeta", "") / "cover.jpg"
        salida.append({"calibre_id": int(bid), "clave": d.get("clave", ""), "titulo": d.get("titulo", ""),
                       "autores": d.get("autores", []), "anio": anios.get(int(bid), ""),
                       "pdf": str(biblioteca / pdf) if pdf else "", "portada": str(portada) if portada.is_file() else "",
                       "fichas": len(d.get("fichas") or []), "insertar": _cita(d["clave"]) if d.get("clave") else ""})
    return salida


def _proyecto(carpeta: str | Path) -> Path:
    p = Path(carpeta).expanduser().resolve()
    if not (p / "proyecto.yaml").is_file() and not (p / "fuentes").is_dir():
        raise SystemExit(f"[ERROR] {p} no es un proyecto de escritura (sin proyecto.yaml ni fuentes/)")
    return p


def fichas(carpeta: str | Path) -> list[dict]:
    """Las fichas de `fuentes/fichas/` del proyecto: tipo, clave, página, la cita y lo que se inserta en el texto."""
    ficha = _modulo("fichas_ficha", RAIZ / "fichas" / "lib" / "ficha.py")
    salida = []
    for f in sorted((_proyecto(carpeta) / "fuentes" / "fichas").glob("*.md")):
        if f.name.startswith("00-") or f.name == "README.md":
            continue
        try:
            meta, cuerpo = ficha.leer(f)
        except (ValueError, OSError):
            continue
        tipo = str(meta.get("tipo") or "")
        clave = str(meta.get("clave_bibtex") or "")
        pagina = meta.get("pagina") or ""
        cita = ficha.literal(cuerpo, tipo) if tipo else ""
        secciones = ficha.secciones(cuerpo)
        resumen = cita or (secciones.get("Paráfrasis") or secciones.get("Síntesis") or secciones.get("Hallazgo")
                           or secciones.get("Análisis") or "").strip()
        origen = ficha.origen_de(meta, cuerpo)
        si, motivo = ficha.citable(meta, cuerpo)
        if not si:
            insertar = ""                           # C3.3: lo del LLM sin cotejar, o lo que no casa con el PDF, no se cita
        elif tipo == "ficha_textual" and cita and clave:
            insertar = f"“{cita}” {_cita(clave, pagina)}"
        elif clave:
            insertar = _cita(clave, pagina)
        else:
            insertar = ""
        salida.append({"archivo": str(f), "nombre": f.stem, "tipo": tipo.replace("ficha_", ""), "clave": clave,
                       "calibre_id": meta.get("calibre_id") or "", "pagina": str(pagina), "categoria": meta.get("categoria") or "",
                       "tema": str(meta.get("tema") or ""), "parafrasis": " ".join((secciones.get("Paráfrasis") or "").split())[:400],
                       "verificacion": (meta.get("verificacion") or {}).get("estado", "") if isinstance(meta.get("verificacion"), dict) else "",
                       "texto": " ".join(resumen.split())[:400], "insertar": insertar,
                       "origen": origen["autor"], "herramienta": origen["herramienta"], "citable": si, "motivo": motivo})
    return salida


def citar(carpeta: str | Path, calibre_id: int, aplicar: bool = False) -> dict:
    """Añade el libro a `fuentes/fuentes.yml` (con la clave de Better BibTeX si la tiene) y regenera `references.bib`."""
    proyecto = _proyecto(carpeta)
    fuentes = proyecto / "fuentes"
    sys.path.insert(0, str(RAIZ / "manifiesto"))
    from lib import bibtex as B
    from lib import manifiesto as M
    data = M.cargar(fuentes)
    previa = next((e for e in data["fuentes"] if str(e.get("calibre_id")) == str(calibre_id)), None)
    if previa and previa.get("clave_bibtex"):
        return {"clave": previa["clave_bibtex"], "nueva": False, "escrito": False, "insertar": _cita(previa["clave_bibtex"])}
    libro = _indice()["libros"].get(str(calibre_id))
    if libro is None:
        raise SystemExit(f"[ERROR] el libro {calibre_id} no está en la biblioteca (o el índice es viejo: lib/indice.py --aplicar)")
    if previa is None:
        e = M._entrada("", int(calibre_id))
        e["clave_bibtex"] = libro.get("clave", "")
        e["uso"] = "citado desde LaTeX Studio"
        data["fuentes"].append(e)
    elif libro.get("clave"):
        previa["clave_bibtex"] = libro["clave"]
    if not aplicar:
        return {"clave": libro.get("clave") or "(la arma el manifiesto)", "nueva": True, "escrito": False,
                "insertar": _cita(libro.get("clave") or "…")}
    fuentes.mkdir(exist_ok=True)
    M.guardar(fuentes, data)
    _texto, res = B.generar(fuentes, None, True)
    clave = next((e["clave_bibtex"] for e in M.cargar(fuentes, recargar=True)["fuentes"] if str(e.get("calibre_id")) == str(calibre_id)), "")
    return {"clave": clave, "nueva": True, "escrito": True, "bib": str(res["bib"]), "insertar": _cita(clave)}


def usos(calibre_id: int) -> list[dict]:
    """Los escritos que declaran el libro en su `fuentes.yml` o tienen fichas de él, con su documento principal."""
    import yaml
    env = _env()
    escritura = Path(os.environ.get("WRITING_DIR") or env.WRITING_DIR)
    salida = []
    for fam in ("reports", "theses", "monographs", "essays", "articles", "books"):
        for y in sorted((escritura / fam).glob("*/fuentes/fuentes.yml")):
            proyecto = y.parent.parent
            try:
                data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            declarado = any(str(e.get("calibre_id")) == str(calibre_id) for e in data.get("fuentes") or [])
            nfichas = 0
            for f in (proyecto / "fuentes" / "fichas").glob("*.md"):
                try:
                    cabeza = f.read_text(encoding="utf-8", errors="replace")[:600]
                except OSError:
                    continue
                if re.search(rf"^calibre_id:\s*{int(calibre_id)}\s*$", cabeza, re.M):
                    nfichas += 1
            if not declarado and not nfichas:
                continue
            ficha = {}
            if (proyecto / "proyecto.yaml").is_file():
                ficha = yaml.safe_load((proyecto / "proyecto.yaml").read_text(encoding="utf-8")) or {}
            principal = ((ficha.get("productos") or {}).get("documento")) or next(
                (n for n in ("informe.tex", "main.tex", "tesis.tex") if (proyecto / n).is_file()), "")
            salida.append({"proyecto": f"{fam}/{proyecto.name}", "titulo": ficha.get("titulo") or proyecto.name,
                           "principal": str(proyecto / principal) if principal else "", "fichas": nfichas})
    return salida


def escritos() -> list[dict]:
    """Todos los escritos de escritura (las familias de `usos`), con su título y su documento principal."""
    import yaml
    env = _env()
    escritura = Path(os.environ.get("WRITING_DIR") or env.WRITING_DIR)
    salida = []
    for fam in ("reports", "theses", "monographs", "essays", "articles", "books"):
        for p in sorted((escritura / fam).glob("*/proyecto.yaml")):
            proyecto = p.parent
            try:
                ficha = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                ficha = {}
            principal = ((ficha.get("productos") or {}).get("documento")) or next(
                (n for n in ("informe.tex", "main.tex", "tesis.tex") if (proyecto / n).is_file()), "")
            salida.append({"proyecto": f"{fam}/{proyecto.name}", "carpeta": str(proyecto), "titulo": ficha.get("titulo") or proyecto.name,
                           "principal": str(proyecto / principal) if principal else ""})
    return salida


def _fichar():
    return _modulo("biblioteca_fichar", RAIZ / "lib" / "fichar.py")


def _ayuda():
    return _modulo("biblioteca_ayuda_ia", RAIZ / "lib" / "ayuda_ia.py")


def _entrada(proyecto: Path, calibre_id) -> dict | None:
    """La fuente del proyecto que es ese libro ({clave, calibre_id, zotero_key}), de su `fuentes.yml`; None si no lo declara."""
    import yaml
    y = proyecto / "fuentes" / "fuentes.yml"
    try:
        data = (yaml.safe_load(y.read_text(encoding="utf-8")) or {}) if y.is_file() else {}
    except (OSError, yaml.YAMLError):
        data = {}
    e = next((e for e in data.get("fuentes") or [] if str(e.get("calibre_id")) == str(calibre_id)), None)
    if not e or not e.get("clave_bibtex"):
        return None
    return {"clave": str(e["clave_bibtex"]), "calibre_id": int(calibre_id), "zotero_key": str(e.get("zotero_key") or ""),
            "uso": str(e.get("uso") or "")}


def nueva_ficha(carpeta: str | Path, datos: dict, aplicar: bool = False) -> dict:
    """Una ficha nueva del libro `datos["calibre_id"]` en el escrito (textual, paráfrasis, síntesis o fuente); simula sin
    `aplicar`. Si el libro aún no es fuente del escrito, `aplicar` lo cita antes (fuentes.yml y references.bib)."""
    proyecto = _proyecto(carpeta)
    fichar = _fichar()
    tipo = str(datos.get("tipo") or "textual")
    entrada, nueva_fuente = None, False
    if tipo != "sintesis":
        cid = datos.get("calibre_id")
        if not str(cid or "").isdigit():
            raise ValueError("Elija el libro de la ficha (su número de Calibre).")
        entrada = _entrada(proyecto, cid)
        if entrada is None:
            nueva_fuente = True
            libro = _indice()["libros"].get(str(int(cid))) or {}
            if aplicar:
                citar(proyecto, int(cid), aplicar=True)
                entrada = _entrada(proyecto, cid)
            if entrada is None:
                entrada = {"clave": libro.get("clave") or "", "calibre_id": int(cid), "zotero_key": libro.get("zotero_key") or ""}
                if aplicar or not entrada["clave"]:
                    raise ValueError("El libro no tiene clave para citar todavía (Zotero): fichelo cuando la tenga.")
    r = fichar.guardar(proyecto, datos, entrada, aplicar=aplicar)
    return {**r, "nueva_fuente": nueva_fuente, "clave": (entrada or {}).get("clave", "")}


def guardar_ficha(carpeta: str | Path, archivo: str, huella: str, datos: dict, aplicar: bool = False) -> dict:
    """Corrige una ficha con la huella con que se abrió (`{"codigo": "ficha_cambiada", "actual": …}` si cambió en disco)."""
    proyecto = _proyecto(carpeta)
    fichar = _fichar()
    actual = fichar.leer(proyecto, archivo)
    if actual.get("error"):
        raise ValueError(actual["error"])
    previas = {s["titulo"]: s["texto"] for s in actual.get("secciones") or []}
    datos = {"tipo": actual["tipo"], "pagina": actual["pagina"], "categoria": actual["categoria"], "uso": actual["uso"], **datos,
             "secciones": {**previas, **(datos.get("secciones") or {})}}
    entrada = None
    if actual["tipo"] != "sintesis":
        cid = actual.get("calibre_id")
        entrada = (_entrada(proyecto, cid) if str(cid or "").isdigit() else None) or {
            "clave": actual["clave"], "calibre_id": cid or "", "zotero_key": ""}
    try:
        return fichar.guardar(proyecto, datos, entrada, archivo=archivo, huella_base=huella, aplicar=aplicar)
    except fichar.Cambiada as e:
        return {"codigo": "ficha_cambiada", "error": str(e), "actual": e.actual}


def cotejar_ficha(carpeta: str | Path, archivo: str, huella: str, aplicar: bool = False) -> dict:
    """La persona cotejó la página de la ficha en el PDF (`verificada_autor`); la del LLM pasa a ser citable (C3.3)."""
    proyecto = _proyecto(carpeta)
    fichar = _fichar()
    try:
        return fichar.cotejar(proyecto, archivo, huella, aplicar)
    except fichar.Cambiada as e:
        return {"codigo": "ficha_cambiada", "error": str(e), "actual": e.actual}


def paginas(calibre_id: int) -> list[str]:
    """Las hojas de texto del PDF del libro (índice 0 = hoja 1), por el resolutor único; [] sin texto."""
    env = _env()
    sys.path.insert(0, str(env.PY_COMMON))
    import biblioteca as bib
    return bib.texto(int(calibre_id))


def pasaje(calibre_id: int, hoja: int) -> dict:
    hojas = paginas(calibre_id)
    h = max(1, min(int(hoja), len(hojas))) if hojas else 0
    return {"calibre_id": int(calibre_id), "hoja": h, "hojas": len(hojas), "texto": hojas[h - 1] if h else ""}


def _libro(calibre_id: int) -> dict:
    d = _indice()["libros"].get(str(int(calibre_id)))
    if d is None:
        raise ValueError(f"El libro {calibre_id} no está en la biblioteca (o el índice es viejo).")
    env = _env()
    return {"calibre_id": int(calibre_id), "titulo": d.get("titulo", ""), "autores": d.get("autores", []), "clave": d.get("clave", ""),
            "anio": _anios(Path(env.CALIBRE_DB), [int(calibre_id)]).get(int(calibre_id), "")}


def prompt_obra(calibre_id: int, mirada: str, desde: int, hasta: int, proposito: str = "") -> dict:
    return _ayuda().prompt_obra(_libro(calibre_id), mirada, paginas(calibre_id), desde, hasta, proposito)


def pegar_obra(calibre_id: int, pegado: str) -> dict:
    return _ayuda().pegar_obra(pegado, paginas(calibre_id))


def prompt_parte(carpeta: str | Path, archivo: str, componente: str = "") -> dict:
    proyecto = _proyecto(carpeta)
    return _ayuda().prompt_parte(proyecto, archivo, componente, fichas(proyecto))


def pegar_parte(carpeta: str | Path, archivo: str, pegado: str, componente: str = "", tex: str | None = None) -> dict:
    return _ayuda().pegar_parte(_proyecto(carpeta), archivo, pegado, componente, tex)


def _leer_arg(v: str) -> str:
    """Un argumento largo (lo pegado, el texto del editor): `-` es la entrada estándar; una ruta existente, su archivo."""
    if v == "-":
        return sys.stdin.read()
    p = Path(v)
    return p.read_text(encoding="utf-8") if len(v) < 4096 and p.is_file() else v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("buscar"); b.add_argument("texto", nargs="?", default=""); b.add_argument("--limite", type=int, default=40)
    f = sub.add_parser("fichas"); f.add_argument("proyecto")
    c = sub.add_parser("citar"); c.add_argument("proyecto"); c.add_argument("calibre_id", type=int); c.add_argument("--aplicar", action="store_true")
    u = sub.add_parser("usos"); u.add_argument("calibre_id", type=int)
    sub.add_parser("escritos")
    sub.add_parser("formulario")
    x = sub.add_parser("ficha"); x.add_argument("proyecto"); x.add_argument("archivo")
    n = sub.add_parser("nueva_ficha"); n.add_argument("proyecto"); n.add_argument("datos"); n.add_argument("--aplicar", action="store_true")
    g = sub.add_parser("guardar_ficha"); g.add_argument("proyecto"); g.add_argument("archivo"); g.add_argument("huella"); g.add_argument("datos")
    g.add_argument("--aplicar", action="store_true")
    k = sub.add_parser("cotejar_ficha"); k.add_argument("proyecto"); k.add_argument("archivo"); k.add_argument("huella")
    k.add_argument("--aplicar", action="store_true")
    s = sub.add_parser("pasaje"); s.add_argument("calibre_id", type=int); s.add_argument("hoja", type=int)
    sub.add_parser("miradas")
    po = sub.add_parser("prompt_obra"); po.add_argument("calibre_id", type=int); po.add_argument("mirada")
    po.add_argument("desde", type=int); po.add_argument("hasta", type=int); po.add_argument("--proposito", default="")
    pe = sub.add_parser("pegar_obra"); pe.add_argument("calibre_id", type=int); pe.add_argument("pegado")
    pp = sub.add_parser("prompt_parte"); pp.add_argument("proyecto"); pp.add_argument("archivo"); pp.add_argument("--componente", default="")
    pg = sub.add_parser("pegar_parte"); pg.add_argument("proyecto"); pg.add_argument("archivo"); pg.add_argument("pegado")
    pg.add_argument("--componente", default=""); pg.add_argument("--tex", default=None)
    a = ap.parse_args(argv)
    try:
        r = _orden(a)
    except (ValueError, LookupError) as e:
        r = {"error": str(e)}
    print(json.dumps(r, ensure_ascii=False))
    return 0


def _orden(a):
    if a.orden == "escritos":
        return escritos()
    if a.orden == "formulario":
        return _fichar().formulario()
    if a.orden == "ficha":
        return _fichar().leer(_proyecto(a.proyecto), a.archivo)
    if a.orden == "nueva_ficha":
        return nueva_ficha(a.proyecto, json.loads(_leer_arg(a.datos)), a.aplicar)
    if a.orden == "guardar_ficha":
        return guardar_ficha(a.proyecto, a.archivo, a.huella, json.loads(_leer_arg(a.datos)), a.aplicar)
    if a.orden == "pasaje":
        return pasaje(a.calibre_id, a.hoja)
    if a.orden == "cotejar_ficha":
        return cotejar_ficha(a.proyecto, a.archivo, a.huella, a.aplicar)
    if a.orden == "miradas":
        return _ayuda().miradas()
    if a.orden == "prompt_obra":
        return prompt_obra(a.calibre_id, a.mirada, a.desde, a.hasta, a.proposito)
    if a.orden == "pegar_obra":
        return pegar_obra(a.calibre_id, _leer_arg(a.pegado))
    if a.orden == "prompt_parte":
        return prompt_parte(a.proyecto, a.archivo, a.componente)
    if a.orden == "pegar_parte":
        return pegar_parte(a.proyecto, a.archivo, _leer_arg(a.pegado), a.componente, _leer_arg(a.tex) if a.tex else None)
    if a.orden == "buscar":
        return buscar(a.texto, a.limite)
    if a.orden == "fichas":
        return fichas(a.proyecto)
    if a.orden == "citar":
        return citar(a.proyecto, a.calibre_id, a.aplicar)
    return usos(a.calibre_id)


if __name__ == "__main__":
    sys.exit(main())
