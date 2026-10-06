#!/usr/bin/env python3
# main.py — suite `lecturas` (Método Documental, paso 07): pasajes con número de página por concepto.
#
#   main.py <lecturas.yml> [--aplicar] [--destino DIR] [--unico ARCHIVO.md] [--solo ID…] [--proyecto RUTA]
#
# lecturas.yml:
#   proyecto: 03 writing/reports/delegacion-facultades-2026     # relativo a ~/Documents (opcional)
#   destino: 12_documentacion/lecturas                                       # relativo al proyecto (opcional)
#   lecturas:
#     - calibre_id: 1068
#       clave_bibtex: marx1848manifiesto      # opcional: si falta se deriva <apellido><año><palabra>
#       etiqueta: "Marx y Engels, Manifiesto comunista: el Estado como junta de la burguesía"
#       patrones: ["negocios comunes", "junta que administra"]   # regex sin tildes, insensible a mayúsculas
#       max: 6
#
# Salida por ítem: <destino>/<clave>-lectura-extraida.md con el frontmatter único (tipo: lectura) y las secciones
# de la norma vacías para que el prompt 07 las complete; los pasajes van entre marcas y se regeneran al reejecutar.
# --unico escribe además un solo Markdown con todo (formato del script original de datafw).
# La página es el índice del PDF desde 1 (pdftotext), NO la impresa: el analista la confirma al fichar.
# Simula por defecto; --aplicar escribe. Solo lectura sobre la biblioteca. Orquestación aquí; valores en config.py; lógica en lib/lecturas.py.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config                                            # noqa: E402
sys.path.insert(0, str(config.PY_COMMON))
import biblioteca as bib                                 # noqa: E402
import yaml                                              # noqa: E402
from lib import lecturas as LEC                          # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="pasajes con página por concepto (paso 07 del Método Documental)")
    ap.add_argument("spec"); ap.add_argument("--aplicar", action="store_true"); ap.add_argument("--destino"); ap.add_argument("--unico")
    ap.add_argument("--proyecto"); ap.add_argument("--solo", nargs="*", type=int)
    a = ap.parse_args()
    spec_p = Path(a.spec).expanduser(); spec = yaml.safe_load(spec_p.read_text(encoding="utf-8")) or {}
    proyecto = a.proyecto or spec.get("proyecto") or ""
    raiz = (config.DOCS / proyecto) if proyecto else spec_p.parent
    destino = Path(a.destino).expanduser() if a.destino else raiz / (spec.get("destino") or config.DESTINO_DEFECTO)
    items = spec.get("lecturas") or []
    if a.solo:
        items = [i for i in items if int(i["calibre_id"]) in a.solo]
    unico = ["# Lecturas extraídas de la biblioteca (borrador de trabajo)\n",
             "Pasajes con número de página (pdftotext; página = índice desde 1 del PDF, NO la paginación impresa). Generado por `scripts_for_fuentes/lecturas`; el analista verifica y cura al fichar (paso 05).\n"]
    n_ok = n_sin = 0
    for it in items:
        cid = int(it["calibre_id"]); d = bib.datos(cid)
        if not d:
            print(f"  [{cid}] no existe en la biblioteca"); n_sin += 1; continue
        pags = bib.texto(cid)
        etiqueta = it.get("etiqueta", "")
        if not pags:
            print(f"  [{cid}] sin texto legible: {d['titulo'][:60]}"); n_sin += 1
            unico.append(f"\n## [{cid}] {etiqueta}\n\n(sin archivo legible)\n"); continue
        ps, total = LEC.pasajes(pags, it.get("patrones") or [], int(it.get("max") or config.MAX_POR_PATRON))
        clave = it.get("clave_bibtex") or LEC.clave_de(d)
        if not it.get("clave_bibtex"):
            print(f"      (clave derivada «{clave}»: fija clave_bibtex en el spec cuando Zotero la asigne)")
        p, accion = LEC.escribir_item(destino, d, clave, proyecto, etiqueta, ps, a.aplicar)
        print(f"  [{cid}] {d['titulo'][:58]:<58} {len(pags):>4} págs · {total:>3} pasajes → {p.name} ({accion})"); n_ok += 1
        unico.append(f"\n## [{cid}] {etiqueta or d['titulo']}\n\n*{d['titulo']}* · {len(pags)} páginas\n")
        unico += [f"- «{pat}»: sin coincidencias" if i is None else f"- **p. {i}** «{pat}»: …{frag}…" for i, pat, frag in ps]
    if a.unico:
        u = Path(a.unico).expanduser()
        if a.aplicar:
            u.parent.mkdir(parents=True, exist_ok=True); u.write_text("\n".join(unico), encoding="utf-8")
        print(f"[lecturas] archivo único: {u} ({'escrito' if a.aplicar else 'simulado'})")
    print(f"[lecturas] {n_ok} ítems · {n_sin} sin texto o inexistentes · destino {destino} · {'APLICADO' if a.aplicar else 'simulación (--aplicar escribe)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
