#!/usr/bin/env python3
"""lib/prisma.py — el diagrama de flujo PRISMA 2020 de una revisión, generado de su bitácora (FLUJO_DE_CONOCIMIENTO C2.2;
decisiones §9.10).

Objetivo: que el diagrama nunca se dibuje a mano: sale de `fuentes/revision.yml` (`lib/revision.py`), y si la bitácora
  cambia, se sabe que el diagrama quedó viejo.
Método: las cuentas de `revision.cuentas` se vuelven un `standalone` de TikZ con las cajas de PRISMA 2020 para revisiones
  nuevas (la columna de bases de datos y registros y, si hubo, la de otros métodos), con los textos de su traducción al
  español; se compila con LuaLaTeX (la norma del ecosistema, N 5.14) en un temporal, y solo si compila se escriben
  `fuentes/prisma.tex` y `fuentes/prisma.pdf` en el escrito, listos para `\\includegraphics{fuentes/prisma}`. El `.tex`
  guarda en su primera línea la huella de las cuentas: `al_dia` compara con la bitácora de hoy. La vista previa de la
  ventana (un PNG de `pdftoppm`) va a la caché, nunca al escrito.
Fundamento: Page et al. (2021, Calibre 11073; traducción, Calibre 11074): el diagrama y sus cajas; Haddaway et al. (2022):
  el diagrama se produce de los datos de la revisión.
Límite: escribe solo `fuentes/prisma.tex` y `fuentes/prisma.pdf` del escrito, y solo con `aplicar`.

    python3 lib/prisma.py <escrito> [--aplicar] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEX = Path("fuentes") / "prisma.tex"
PDF = Path("fuentes") / "prisma.pdf"
MARCA = "% prisma-cuentas: "


def _revision():
    if "biblioteca_revision" in sys.modules:
        return sys.modules["biblioteca_revision"]
    s = importlib.util.spec_from_file_location("biblioteca_revision", Path(__file__).resolve().parent / "revision.py")
    m = importlib.util.module_from_spec(s)
    sys.modules["biblioteca_revision"] = m
    s.loader.exec_module(m)
    return m


def huella_cuentas(c: dict) -> str:
    sin_avisos = {k: v for k, v in c.items() if k not in ("avisos", "cuadra")}
    return hashlib.sha256(json.dumps(sin_avisos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def archivos(escrito: Path) -> dict:
    tex, pdf = Path(escrito) / TEX, Path(escrito) / PDF
    return {"tex": str(tex) if tex.is_file() else "", "pdf": str(pdf) if pdf.is_file() else ""}


def al_dia(escrito: Path, r: dict | None = None) -> bool | None:
    """¿El diagrama del escrito es el de su bitácora de hoy? None si aún no hay diagrama."""
    tex = Path(escrito) / TEX
    if not tex.is_file() or not (Path(escrito) / PDF).is_file():
        return None
    r = r if r is not None else _revision().leer(escrito)[0]
    primera = tex.read_text(encoding="utf-8").split("\n", 1)[0]
    return primera == MARCA + huella_cuentas(_revision().cuentas(r))


def _esc(t) -> str:
    reemplazos = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
                  "^": r"\textasciicircum{}", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}"}
    return "".join(reemplazos.get(ch, ch) for ch in str(t))


def _n(x) -> str:
    return f"(n = {int(x)})"


def tikz(c: dict) -> str:
    """El `standalone` de TikZ del diagrama, con las cuentas `c` de `revision.cuentas`."""
    b, o = c["bases"], c["otros"]
    pc = b["por_clase"]
    motivos = b["motivos"] or {}
    lineas_motivos = r"\\".join(f"{_esc(m)} {_n(k)}" for m, k in sorted(motivos.items(), key=lambda x: -x[1])) or "(n = 0)"
    otros = c.get("otros_metodos")
    po = o["por_clase"]
    nombres = {"web": "Sitios web", "organizacion": "Organizaciones", "citas": "Búsqueda de citas"}
    ident_otros = r"\\".join(f"{nombres[k]} {_n(po.get(k, 0))}" for k in ("web", "organizacion", "citas")) if otros else ""
    mot_otros = r"\\".join(f"{_esc(m)} {_n(k)}" for m, k in sorted((o["motivos"] or {}).items(), key=lambda x: -x[1])) or "(n = 0)"
    t = [MARCA + huella_cuentas(c),
         "% GENERADO por biblioteca-studio/lib/prisma.py desde fuentes/revision.yml; no editar: se regenera.",
         "% PRISMA 2020 (Page et al., 2021): diagrama de flujo para revisiones nuevas.",
         r"\documentclass[tikz,border=6pt]{standalone}",
         r"\usetikzlibrary{positioning,fit,arrows.meta,calc}",
         r"\begin{document}",
         r"\begin{tikzpicture}[",
         r"  caja/.style={draw, rounded corners=1.5pt, text width=6cm, align=left, inner sep=5pt, font=\small},",
         r"  cabeza/.style={draw, fill=black!8, rounded corners=1.5pt, inner sep=0pt},",
         r"  flecha/.style={-{Stealth[length=2.2mm]}, thick}, node distance=0.9cm and 0.8cm]",
         # la columna de bases de datos y registros; cada caja lateral, alineada por arriba con la suya
         rf"\node[caja] (ident) {{Registros identificados desde:\\Bases de datos {_n(pc.get('base', 0))}\\Registros {_n(pc.get('registro', 0))}}};",
         rf"\node[caja, right=of ident.north east, anchor=north west] (elim) {{Registros eliminados antes del cribado:\\Duplicados {_n(b['duplicados'])}\\"
         rf"Marcados como no elegibles por herramientas de automatización {_n(b['automatizacion'])}\\Eliminados por otras razones {_n(b['otras_razones'])}}};",
         r"\path let \p1=(ident.south), \p2=(elim.south) in coordinate (f1) at (\x1, {min(\y1,\y2)});",
         rf"\node[caja, anchor=north] (crib) at ($(f1) + (0,-0.9)$) {{Registros cribados\\{_n(b['cribados'])}}};",
         rf"\node[caja, right=of crib.north east, anchor=north west] (excl) {{Registros excluidos\\{_n(b['excluidos_titulo'])}}};",
         r"\path let \p1=(crib.south), \p2=(excl.south) in coordinate (f2) at (\x1, {min(\y1,\y2)});",
         rf"\node[caja, anchor=north] (busc) at ($(f2) + (0,-0.9)$) {{Publicaciones buscadas para su recuperación\\{_n(b['buscados'])}}};",
         rf"\node[caja, right=of busc.north east, anchor=north west] (norec) {{Publicaciones no recuperadas\\{_n(b['no_recuperados'])}}};",
         r"\path let \p1=(busc.south), \p2=(norec.south) in coordinate (f3) at (\x1, {min(\y1,\y2)});",
         rf"\node[caja, anchor=north] (eval) at ($(f3) + (0,-0.9)$) {{Publicaciones evaluadas para decidir su elegibilidad\\{_n(b['evaluados'])}}};",
         rf"\node[caja, right=of eval.north east, anchor=north west] (exct) {{Publicaciones excluidas:\\{lineas_motivos}}};"]
    if otros:
        t += [rf"\node[caja, right=1.6cm of elim.north east, anchor=north west] (oident) {{Registros identificados desde:\\{ident_otros}}};",
              rf"\node[caja, right=1.6cm of norec.north east, anchor=north west] (obusc) {{Publicaciones buscadas para su recuperación\\{_n(o['buscados'])}}};",
              rf"\node[caja, right=of obusc.north east, anchor=north west] (onorec) {{Publicaciones no recuperadas\\{_n(o['no_recuperados'])}}};",
              rf"\node[caja, right=1.6cm of exct.north east, anchor=north west] (oeval) {{Publicaciones evaluadas para decidir su elegibilidad\\{_n(o['evaluados'])}}};",
              rf"\node[caja, right=of oeval.north east, anchor=north west] (oexct) {{Publicaciones excluidas:\\{mot_otros}}};"]
    t += [r"\path let \p1=(eval.south), \p2=(exct.south) in coordinate (f4) at (\x1, {min(\y1,\y2)});",
          rf"\node[caja, anchor=north] (incl) at ($(f4) + (0,-1.2)$) {{Estudios incluidos en la revisión {_n(c['estudios'])}\\"
          rf"Informes de los estudios incluidos {_n(c['incluidos'])}}};",
          r"\draw[flecha] (ident.east) -- (ident.east -| elim.west);",
          r"\draw[flecha] (crib.east) -- (crib.east -| excl.west);",
          r"\draw[flecha] (busc.east) -- (busc.east -| norec.west);",
          r"\draw[flecha] (eval.east) -- (eval.east -| exct.west);",
          r"\draw[flecha] (ident) -- (crib); \draw[flecha] (crib) -- (busc); \draw[flecha] (busc) -- (eval); \draw[flecha] (eval) -- (incl);",
          # las cabeceras de columna y las bandas de las fases, por coordenadas (no tapan ninguna caja)
          r"\node[cabeza, fit={($(ident.north west |- elim.north) + (0,0.35)$) ($(elim.north east) + (0,1.05)$)}] (h1) {};",
          r"\node[font=\small\bfseries] at (h1) {Identificación de estudios mediante bases de datos y registros};",
          r"\coordinate (c1) at ($(f1)!0.5!(crib.north)$); \coordinate (c2) at ($(f4)!0.5!(incl.north)$);",
          r"\node[cabeza, fit={($(ident.west |- elim.north) + (-1.05,0)$) ($(ident.west |- c1) + (-0.4,0.12)$)}] (b1) {};",
          r"\node[rotate=90, font=\footnotesize\bfseries] at (b1) {Identificación};",
          r"\node[cabeza, fit={($(ident.west |- c1) + (-1.05,-0.12)$) ($(ident.west |- c2) + (-0.4,0.12)$)}] (b2) {};",
          r"\node[rotate=90, font=\footnotesize\bfseries] at (b2) {Cribado};",
          r"\node[cabeza, fit={($(ident.west |- c2) + (-1.05,-0.12)$) ($(incl.south west) + (-0.4,0)$)}] (b3) {};",
          r"\node[rotate=90, font=\footnotesize\bfseries] at (b3) {Incluidos};"]
    if otros:
        t += [r"\draw[flecha] (oident) -- (obusc); \draw[flecha] (obusc) -- (oeval);",
              r"\draw[flecha] (obusc.east) -- (obusc.east -| onorec.west); \draw[flecha] (oeval.east) -- (oeval.east -| oexct.west);",
              r"\draw[flecha] (oeval.south) |- (incl.east);",
              r"\node[cabeza, fit={($(oident.north west |- elim.north) + (0,0.35)$) ($(oexct.east |- elim.north) + (0,1.05)$)}] (h2) {};",
              r"\node[font=\small\bfseries] at (h2) {Identificación de estudios mediante otros métodos};"]
    t += [r"\end{tikzpicture}", r"\end{document}", ""]
    return "\n".join(t)


def compilar(tex: str) -> tuple[bytes | None, str]:
    """(el PDF, el registro): LuaLaTeX en un temporal; nada se escribe junto al escrito."""
    if not shutil.which("lualatex"):
        return None, "No está lualatex."
    with tempfile.TemporaryDirectory(prefix="prisma-") as d:
        (Path(d) / "prisma.tex").write_text(tex, encoding="utf-8")
        r = subprocess.run(["lualatex", "-interaction=nonstopmode", "-halt-on-error", "prisma.tex"], cwd=d,
                           capture_output=True, text=True, errors="replace", timeout=180)
        pdf = Path(d) / "prisma.pdf"
        if r.returncode != 0 or not pdf.is_file():
            errores = [l for l in r.stdout.splitlines() if l.startswith("!")][:5]
            return None, "\n".join(errores) or r.stdout[-800:]
        return pdf.read_bytes(), ""


def vista_previa(escrito: Path, cache: Path | None = None) -> str:
    """Un PNG del diagrama para la ventana, en la caché (por la huella del PDF); «» si no hay diagrama o pdftoppm."""
    pdf = Path(escrito) / PDF
    if not pdf.is_file() or not shutil.which("pdftoppm"):
        return ""
    cache = cache or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "biblioteca-studio" / "prisma"
    cache.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(pdf.read_bytes()).hexdigest()[:16]
    png = cache / f"{h}.png"
    if not png.is_file():
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-singlefile", str(pdf), str(png.with_suffix(""))], capture_output=True, timeout=60)
    return str(png) if png.is_file() else ""


def generar(escrito: Path, aplicar: bool = False) -> dict:
    """Simula (las cuentas, si cuadran y el .tex) o escribe `fuentes/prisma.tex` y `fuentes/prisma.pdf` si compila."""
    rev = _revision()
    r, _h = rev.leer(escrito)
    if not r["busquedas"]:
        raise ValueError("La bitácora no tiene búsquedas: el diagrama sale de ella.")
    c = rev.cuentas(r)
    tex = tikz(c)
    salida = {"cuentas": c, "cuadra": c["cuadra"], "avisos": c["avisos"], "tex": str(Path(escrito) / TEX),
              "pdf": str(Path(escrito) / PDF), "escrito": False}
    if not aplicar:
        return salida
    pdf, registro = compilar(tex)
    if pdf is None:
        raise ValueError("El diagrama no compiló con LuaLaTeX: " + registro)
    destino = Path(escrito) / "fuentes"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in (("prisma.tex", tex.encode("utf-8")), ("prisma.pdf", pdf)):
        tmp = destino / f".{nombre}.guardando"
        tmp.write_bytes(contenido)
        os.replace(tmp, destino / nombre)
    return {**salida, "escrito": True, "incluir": r"\includegraphics[width=\textwidth]{fuentes/prisma}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("escrito")
    ap.add_argument("--aplicar", action="store_true", help="compila y escribe fuentes/prisma.tex y .pdf (sin esto, simula)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = generar(Path(a.escrito).expanduser().resolve(), a.aplicar)
    except ValueError as e:
        r = {"error": str(e)}
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    elif r.get("error"):
        print(f"✗ {r['error']}", file=sys.stderr)
    else:
        print(("✓ " + r["pdf"] + "\n  " + r["incluir"]) if r["escrito"] else "[simulación] --aplicar compila y escribe " + r["pdf"])
        if not r["cuadra"]:
            print("  aviso: " + " ".join(r["avisos"]))
    return 1 if r.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
