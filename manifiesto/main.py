#!/usr/bin/env python3
# main.py — suite `manifiesto` (FD4): el `fuentes.yml` de cada proyecto sustituye a los enlaces simbólicos a la biblioteca.
#
#   generar <carpeta> [--aplicar]         construye o actualiza fuentes.yml desde los enlaces hacia la biblioteca, el ledger
#                                          de ingesta y el manifiesto previo (conserva clave_bibtex, uso y nota)
#   verificar <carpeta|fuentes.yml>…       cada entrada existe en Calibre y tiene archivo (o anexo)
#   ruta <carpeta> <origen|calibre_id>     ruta física por el resolutor (para scripts); código 1 si no resuelve
#   quitar-enlaces <carpeta> [--aplicar]   borra los enlaces hacia la biblioteca que el manifiesto ya cubre
#   raiz <archivo>                         qué carpeta lleva el manifiesto de ese archivo (config.REGLAS_RAIZ)
#   bib <carpeta> [--aplicar] [--salida references.bib]
#                                          el bloque generado del references.bib del proyecto desde fuentes.yml y
#                                          Calibre (APA 7 vía biblatex); escribe clave_bibtex en el manifiesto (2026-09-16)
#   todo [--aplicar]                       generar + verificar en todas las raíces vigiladas
#
# Simula por defecto. Solo lectura sobre Calibre. Orquestación aquí; reglas en config.py; lógica en lib/.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import manifiesto as M       # noqa: E402

config = M.config


def _r(x):
    return M.rel_docs(x)


def cmd_generar(a):
    if a.bib:
        asignar = dict(x.split("=", 1) for x in (a.asignar or []))
        data, res = M.generar_desde_bib(a.carpeta, a.bib, asignar, a.aplicar)
        print(f"  {_r(a.carpeta)}/{config.NOMBRE}: {res['entradas']} entradas desde {Path(a.bib).name}" + (f" · sin libro en Calibre: {', '.join(res['sin_libro'])}" if res["sin_libro"] else ""))
        for e in data["fuentes"]:
            print(f"      - {e['origen']:<20} → {e['calibre_id']} {e['titulo'][:60]}")
        print(f"[manifiesto] {'escrito' if a.aplicar else 'simulación (--aplicar escribe)'}")
        return 1 if res["sin_libro"] else 0
    data, res = M.generar(a.carpeta, a.aplicar)
    print(f"  {_r(a.carpeta)}/{config.NOMBRE}: {res['entradas']} entradas (enlaces {res['desde_enlaces']}, ledger {res['desde_ledger']}, previas {res['previas']}; anexos {res['anexos']}; sin libro {res['sin_libro']}; ids vivos conservados {res.get('conservadas', 0)})")
    if not a.aplicar:
        for e in data["fuentes"][:8]:
            print(f"      - {e['origen']} → {e['calibre_id']} {e['titulo'][:60]}" + (f" [data/{e['anexo']}]" if e["anexo"] else ""))
        if len(data["fuentes"]) > 8: print(f"      … {len(data['fuentes']) - 8} más")
    print(f"[manifiesto] {'escrito' if a.aplicar else 'simulación (--aplicar escribe)'}")
    return 0


def cmd_verificar(a):
    mal = 0
    for c in a.carpetas:
        c = Path(c).expanduser(); c = c.parent if c.is_file() else c
        prob, data = M.verificar(c)
        print(f"  {'✗' if prob else '✓'} {_r(c)}: {len(data['fuentes'])} entradas" + (f" · {len(prob)} problema(s)" if prob else ""))
        for p in prob[:15]: print(f"      - {p}")
        mal += bool(prob)
    return 1 if mal else 0


def cmd_ruta(a):
    p = M.ruta(Path(a.carpeta).expanduser(), a.clave)
    print(p or ""); return 0 if p else 1


def cmd_quitar(a):
    borrados, sin = M.quitar_enlaces(a.carpeta, a.aplicar)
    print(f"  {_r(a.carpeta)}: {len(borrados)} enlace(s) {'borrados' if a.aplicar else 'a borrar'} cubiertos por el manifiesto; {len(sin)} sin cubrir")
    for s in sin[:10]: print(f"      ! sin cubrir: {s}")
    print(f"[manifiesto] {'APLICADO' if a.aplicar else 'simulación (--aplicar borra)'}")
    return 1 if sin else 0


def cmd_raiz(a):
    print(M.raiz_de(a.archivo)); return 0


def cmd_bib(a):
    from lib import bibtex as B
    c = Path(a.carpeta).expanduser()
    c = c / "fuentes" if (c / "fuentes" / config.NOMBRE).exists() and not (c / config.NOMBRE).exists() else c
    texto, res = B.generar(c, a.salida, a.aplicar)
    print(f"  {_r(c)}/{config.NOMBRE} → {_r(res['bib'])}: {res['entradas']} entrada(s) generada(s)")
    for k in res["sin_anio"]:
        print(f"      ! {k}: sin año en Calibre (APA escribirá «s. f.»; corrija pubdate en Calibre)")
    for o in res["sin_libro"]:
        print(f"      ! {o}: sin calibre_id o el libro no existe; no entra al .bib")
    if not a.aplicar:
        print(texto)
    print(f"[manifiesto] {'escrito (bib + clave_bibtex del manifiesto)' if a.aplicar else 'simulación (--aplicar escribe)'}")
    return 1 if res["sin_libro"] else 0


def cmd_todo(a):
    raices = set(M.manifiestos_en())
    for r in config.RAICES_VIGILADAS:
        if Path(r).is_dir():
            for enlace, *_ in M.enlaces_biblioteca(r):
                raices.add(M.raiz_de(enlace))
    mal = 0
    for c in sorted(raices):
        data, res = M.generar(c, a.aplicar)
        prob, _ = M.verificar(c) if a.aplicar else ([], None)
        print(f"  {'✗' if prob else '·'} {_r(c)}: {res['entradas']} entradas · anexos {res['anexos']} · sin libro {res['sin_libro']}" + (f" · {len(prob)} problema(s)" if prob else ""))
        mal += bool(prob)
    print(f"[manifiesto] {len(raices)} manifiesto(s) · {'APLICADO' if a.aplicar else 'simulación'}")
    return 1 if mal else 0


def main():
    ap = argparse.ArgumentParser(description="fuentes.yml por proyecto en vez de enlaces simbólicos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("generar"); p.add_argument("carpeta"); p.add_argument("--aplicar", action="store_true")
    p.add_argument("--bib", help="trabajo de escritura: una entrada por clave del .bib, localizada en Calibre por DOI, URL o título")
    p.add_argument("--asignar", nargs="*", help="clave=calibre_id para fijar a mano (ediciones, obras sin DOI)")
    p = sub.add_parser("verificar"); p.add_argument("carpetas", nargs="+")
    p = sub.add_parser("ruta"); p.add_argument("carpeta"); p.add_argument("clave")
    p = sub.add_parser("quitar-enlaces"); p.add_argument("carpeta"); p.add_argument("--aplicar", action="store_true")
    p = sub.add_parser("raiz"); p.add_argument("archivo")
    p = sub.add_parser("bib"); p.add_argument("carpeta"); p.add_argument("--aplicar", action="store_true")
    p.add_argument("--salida", help="ruta del .bib (por defecto <proyecto>/references.bib)")
    p = sub.add_parser("todo"); p.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    return {"generar": cmd_generar, "verificar": cmd_verificar, "ruta": cmd_ruta, "quitar-enlaces": cmd_quitar, "raiz": cmd_raiz, "bib": cmd_bib, "todo": cmd_todo}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
