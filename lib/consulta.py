#!/usr/bin/env python3
"""lib/consulta.py — la biblioteca para los otros programas (LaTeX Studio, Datafw Studio): buscar un libro, las fichas de un escrito, citar un libro en un escrito y en qué escritos se usa un libro; en JSON.

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
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
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
        resumen = cita or (secciones.get("Paráfrasis") or secciones.get("Síntesis") or secciones.get("Análisis") or "").strip()
        if tipo == "ficha_textual" and cita and clave:
            insertar = f"“{cita}” {_cita(clave, pagina)}"
        elif clave:
            insertar = _cita(clave, pagina)
        else:
            insertar = ""
        salida.append({"archivo": str(f), "nombre": f.stem, "tipo": tipo.replace("ficha_", ""), "clave": clave,
                       "calibre_id": meta.get("calibre_id") or "", "pagina": str(pagina), "categoria": meta.get("categoria") or "",
                       "verificacion": (meta.get("verificacion") or {}).get("estado", "") if isinstance(meta.get("verificacion"), dict) else "",
                       "texto": " ".join(resumen.split())[:400], "insertar": insertar})
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    b = sub.add_parser("buscar"); b.add_argument("texto", nargs="?", default=""); b.add_argument("--limite", type=int, default=40)
    f = sub.add_parser("fichas"); f.add_argument("proyecto")
    c = sub.add_parser("citar"); c.add_argument("proyecto"); c.add_argument("calibre_id", type=int); c.add_argument("--aplicar", action="store_true")
    u = sub.add_parser("usos"); u.add_argument("calibre_id", type=int)
    a = ap.parse_args(argv)
    if a.orden == "buscar":
        r = buscar(a.texto, a.limite)
    elif a.orden == "fichas":
        r = fichas(a.proyecto)
    elif a.orden == "citar":
        r = citar(a.proyecto, a.calibre_id, a.aplicar)
    else:
        r = usos(a.calibre_id)
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
