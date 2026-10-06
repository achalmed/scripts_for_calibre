#!/usr/bin/env python3
# main.py — sistema central de adquisición de FUENTES DOCUMENTALES.
#
#   verificar <referencia>…        ¿ya está en la biblioteca? (paso 00 del Método Documental; FD2)
#   fuentes                        qué fuentes sabe adquirir
#   localizar <fuente> <ref>…      busca el documento (no descarga)
#   descargar <fuente> <ref>…      descarga a entrada/ con hash y procedencia
#   estado                         qué se ha adquirido
#
# La división del ecosistema (directiva de Edison, 2026-09-06):
#   · DATOS       → los conectores de datafw (series, microdatos, APIs) → data/raw
#   · DOCUMENTOS  → este sistema (normas, informes, libros, artículos, tesis)
#                   → entrada/ → ingesta/ → Calibre + Zotero
#
# Este sistema NO cataloga ni gestiona referencias: descarga y deja constancia de
# dónde vino cada archivo. Catalogar es de Calibre; citar, de Zotero.
#
# Añadir una fuente = una carpeta en fuentes/ con `config.py` (qué es, qué tipos
# acepta) y `localizar.py` con una función `localizar(referencia, cfg)` que
# devuelva {url, fuente} o {error}. Nada más.

import argparse
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config                                        # noqa: E402
from lib import comun                                # noqa: E402


def fuentes_disponibles():
    return sorted(d.name for d in config.DIR_FUENTES.iterdir()
                  if d.is_dir() and (d / "localizar.py").exists())


def cargar(nombre):
    if nombre not in fuentes_disponibles():
        print(f"[ERROR] fuente desconocida: {nombre}. Disponibles: "
              f"{', '.join(fuentes_disponibles()) or '(ninguna)'}")
        sys.exit(1)
    cfg = importlib.import_module(f"fuentes.{nombre}.config")
    mod = importlib.import_module(f"fuentes.{nombre}.localizar")
    return cfg, mod


def _refs(a):
    """[(referencia, nombre)]: en --lista cada línea es «referencia|nombre» (el nombre, opcional, es el del archivo
    en entrada/, por ejemplo la clave BibTeX; así ingesta/main.sh bib lo empareja con el .bib)."""
    if a.lista:
        out = []
        for l in Path(a.lista).read_text(encoding="utf-8").splitlines():
            if not l.strip() or l.startswith("#"):
                continue
            partes = [x.strip() for x in l.split("|")]
            out.append((partes[0], partes[1] if len(partes) > 1 and partes[1] else ""))
        return out
    return [(r, "") for r in a.referencias]


def cmd_fuentes(_a):
    print("Fuentes documentales que este sistema sabe adquirir\n" + "─" * 62)
    for n in fuentes_disponibles():
        cfg, _ = cargar(n)
        print(f"  {n:<14} {getattr(cfg, 'DESCRIPCION', '')}")
        tipos = getattr(cfg, "TIPOS", None)
        if tipos:
            print(f"  {'':<14} acepta: {', '.join(tipos)}")
    print("\n  Los DATOS (series, microdatos, APIs) no se piden aquí: "
          "son de los conectores de datafw.")
    return 0


def cmd_localizar(a):
    cfg, mod = cargar(a.fuente)
    print(f"localizar en «{a.fuente}» (solo lectura)\n" + "─" * 62)
    ok = mal = 0
    for ref, _nombre in _refs(a):
        r = mod.localizar(ref, cfg)
        if r.get("url"):
            ok += 1; print(f"  ✓ {ref:<28} {r['fuente']:<16} {r['url']}")
        else:
            mal += 1; print(f"  ✗ {ref:<28} {r.get('error', 'no localizada')}")
    print("─" * 62 + f"\nLocalizadas: {ok} | No localizadas: {mal}")
    return 0


def cmd_descargar(a):
    cfg, mod = cargar(a.fuente)
    print(f"descargar de «{a.fuente}» → {config.ENTRADA.name}/\n" + "─" * 62)
    ok = mal = rep = 0
    for ref, nombre in _refs(a):
        r = mod.localizar(ref, cfg)
        if not r.get("url"):
            print(f"  ✗ {ref}: {r.get('error', 'no localizada')}"); mal += 1; continue
        base = nombre or f"{a.fuente}__{r.get('tipo', 'doc').replace(' ', '_')}_{r.get('numero', '')}".rstrip("_")
        try:
            ruta, sha, n = comun.descargar(r["url"], config.ENTRADA, base)
        except Exception as exc:
            print(f"  ✗ {ref}: {type(exc).__name__}: {str(exc)[:70]}"); mal += 1; continue
        if comun.ya_adquirido(sha):
            print(f"  = {ref:<26} ya adquirido (mismo hash)"); rep += 1
        else:
            print(f"  ✓ {ref:<26} {n/1e6:.1f} MB · {r['fuente']}"); ok += 1
        comun.anotar({"sha256": sha, "fuente": a.fuente, "tipo": r.get("tipo", ""),
                      "referencia": ref, "titulo": r.get("titulo", ref),
                      "url": r["url"], "origen": r["fuente"],
                      "archivo": ruta.name, "bytes": n, "estado": "descargado"})
    print("─" * 62 + f"\nNuevos: {ok} | Ya estaban: {rep} | Fallidos: {mal}")
    if ok:
        print("\n  Siguiente paso — catalogar en Calibre y generar la referencia:\n"
              "    cd ~/Documents/scripts_for_fuentes/ingesta\n"
              "    ./main.sh todo --aplicar\n"
              f"  `entrada/` está declarada como raíz de entrada y se archiva en modo\n"
              f"  «{config.ARCHIVAR_MODO}»: el archivo pasa a Calibre y no queda copia aquí.")
    return 0


def cmd_verificar(a):
    """Paso 00 del Método Documental: existe | otra edición | no existe, con las búsquedas ejecutadas.

    Delega en el resolutor único (core/py-common/biblioteca.py) y añade lo que solo este
    sistema sabe: si el archivo ya se descargó (ledger de procedencia) o ya se catalogó (ledger de ingesta).
    """
    import csv
    import json
    sys.path.insert(0, str(config.PY_COMMON))
    import biblioteca as bib
    ref = " ".join(a.referencias) if a.referencias else None
    if not any((ref, a.titulo, a.isbn, a.doi, a.norma, a.archivo)):
        print("[ERROR] indica una referencia, --titulo, --isbn, --doi, --norma o --archivo"); return 2
    r = bib.existe(a.titulo, a.autor, a.isbn, a.doi, a.norma, a.archivo, a.paginas, ref)
    notas = []
    if a.archivo and Path(a.archivo).exists():
        sha = bib._sha256(a.archivo)
        led = comun.leer_ledger().get(sha)
        if led:
            notas.append(f"descargado por este sistema el {led['fecha'][:10]} desde {led['url']} (estado: {led['estado']})")
        if config.LEDGER_INGESTA.exists():
            with open(config.LEDGER_INGESTA, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    if row.get("sha256") == sha:
                        notas.append(f"ingesta: calibre_id {row['calibre_id']} ({row['estado']}) desde {row['origen']}"); break
    if a.json:
        print(json.dumps({**r, "ledgers": notas}, ensure_ascii=False, indent=2))
    else:
        bib.imprimir_existe(r)
        for n in notas:
            print(f"Ledgers: {n}")
    return {"existe": 0, "otra-edicion": 2, "no-existe": 1}[r["resultado"]]


def cmd_estado(_a):
    filas = list(comun.leer_ledger().values())
    print(f"Fuentes documentales adquiridas: {len(filas)}\n" + "─" * 62)
    por_fuente = {}
    for r in filas:
        por_fuente.setdefault(r["fuente"], []).append(r)
    for f, rs in sorted(por_fuente.items()):
        mb = sum(int(r["bytes"] or 0) for r in rs) / 1e6
        print(f"  {f:<14} {len(rs):>3} documentos · {mb:>6.1f} MB")
    pendientes = [r for r in filas if (config.ENTRADA / r["archivo"]).exists()]
    if pendientes:
        print(f"\n  {len(pendientes)} en entrada/ sin catalogar todavía en Calibre.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="adquisición de fuentes documentales")
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("fuentes", help="qué fuentes sabe adquirir")
    for n, h in (("localizar", "busca el documento sin descargarlo"),
                 ("descargar", "descarga con hash y procedencia")):
        p = sub.add_parser(n, help=h)
        p.add_argument("fuente"); p.add_argument("referencias", nargs="*")
        p.add_argument("--lista", help="archivo con una referencia por línea")
    sub.add_parser("estado", help="qué se ha adquirido")
    p = sub.add_parser("verificar", help="¿ya está en la biblioteca? (paso 00 del Método Documental)")
    p.add_argument("referencias", nargs="*", help="cita, título, número de norma, ISBN o DOI en texto libre")
    for o in ("--titulo", "--autor", "--isbn", "--doi", "--norma", "--archivo"):
        p.add_argument(o)
    p.add_argument("--paginas", type=int); p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    return {"fuentes": cmd_fuentes, "localizar": cmd_localizar, "descargar": cmd_descargar,
            "estado": cmd_estado, "verificar": cmd_verificar}[a.comando](a)


if __name__ == "__main__":
    sys.exit(main())
