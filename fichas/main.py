#!/usr/bin/env python3
# main.py — suite `fichas` del Método Documental: validar, verificar contra el PDF, indexar y resumir fichas.
#
#   validar   <ficha|carpeta>…            cumple fichas_formato_y_voz.md (frontmatter, nombre, categoría, secciones)
#   verificar <ficha|carpeta>… [--aplicar] [--desfase N] [--tolerancia N]
#                                          coteja textuales y paráfrasis contra el texto del libro (paso 05);
#                                          escribe verificacion.{estado,metodo,fecha} solo con --aplicar
#   indice    <carpeta> [--aplicar]        genera 00-indice_fichas.md (por tipo, conteo por estado)   (paso 09)
#   estado    <carpeta>                    resumen por estado; código 1 si hay fichas «observada» o «pendiente» en uso
#
# Nunca escribe en Calibre; lee el texto del libro por el resolutor core/py-common/biblioteca.py.
# Simula por defecto: sin --aplicar solo informa. Orquestación aquí; reglas en config.py; lógica en lib/.

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config                       # noqa: E402
from lib import ficha as F          # noqa: E402


def cmd_validar(a):
    fichas = F.fichas_en(a.rutas)
    if not fichas:
        print("[fichas] ninguna ficha con frontmatter reconocido en las rutas dadas"); return 1
    mal = avisos = 0; salida = []
    for p in fichas:
        try:
            meta, cuerpo = F.leer(p); prob = F.validar(p, meta, cuerpo)
        except ValueError as e:
            prob = [str(e)]
        salida.append({"ficha": str(p), "problemas": prob})
        faltas = [x for x in prob if not x.startswith("aviso: ")]
        if faltas:
            mal += 1; print(f"  ✗ {p.name}"); [print(f"      - {x}") for x in prob]
        elif prob:
            avisos += 1; print(f"  ~ {p.name}: {prob[0][7:]}")
        else:
            print(f"  ✓ {p.name}")
    if a.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    print(f"[fichas] {len(fichas)} fichas · {len(fichas) - mal - avisos} cumplen · {avisos} con aviso (calibre_id pendiente) · {mal} con faltas (norma: {config.NORMA.name})")
    return 1 if mal else 0


def cmd_verificar(a):
    from lib import verificar as V
    fichas = F.fichas_en(a.rutas)
    if not fichas:
        print("[fichas] ninguna ficha con frontmatter reconocido"); return 1
    cnt = Counter(); cambios = 0
    for p in fichas:
        meta, cuerpo = F.leer(p)
        meta["_ruta"] = str(p)
        r = V.cotejar(meta, cuerpo, a.desfase, a.tolerancia)
        meta.pop("_ruta", None)
        antes = (meta.get("verificacion") or {}).get("estado")
        if r["estado"] is None:
            if r["detalle"]:
                cnt["sin cotejo"] += 1; print(f"  · {p.name}: {r['detalle']}")
            continue
        cnt[r["estado"]] += 1
        marca = {"verificada_script": "✓", "observada": "✗", "pendiente": "…"}[r["estado"]]
        print(f"  {marca} {p.name}: {r['estado']} · {r['detalle']}")
        if antes == "verificada_autor" and r["estado"] == "verificada_script":
            continue                                   # la lectura del autor vale más que el script
        if r["estado"] == "pendiente" and str(antes).startswith("verificada"):
            continue                                   # «no se pudo cotejar» nunca degrada una verificación previa
        if a.aplicar and antes != r["estado"] or (a.aplicar and r["estado"] == "observada"):
            F.marcar(meta, r["estado"], r["metodo"], r["detalle"] if r["estado"] != "verificada_script" else "")
            F.escribir(p, meta, cuerpo); cambios += 1
    print(f"[fichas] {sum(cnt.values())} cotejadas · " + " · ".join(f"{k}: {v}" for k, v in cnt.items())
          + (f" · {cambios} fichas actualizadas" if a.aplicar else " · simulación (usa --aplicar para escribir verificacion)"))
    return 1 if cnt["observada"] else 0


def _filas(carpeta):
    filas = []
    for p in F.fichas_en([carpeta]):
        if p.name == config.INDICE_NOMBRE:
            continue
        meta, _ = F.leer(p)
        v = meta.get("verificacion") or {}
        filas.append({"archivo": p.name, "tipo": meta.get("tipo", ""), "clave": meta.get("clave_bibtex", ""), "calibre_id": meta.get("calibre_id", ""),
                      "pagina": meta.get("pagina", ""), "categoria": meta.get("categoria", ""), "uso": meta.get("uso", ""), "estado": v.get("estado", "")})
    return filas


def cmd_indice(a):
    carpeta = Path(a.carpeta).expanduser()
    filas = _filas(carpeta)
    if not filas:
        print("[fichas] carpeta sin fichas"); return 1
    por_estado = Counter(f["estado"] for f in filas); por_tipo = Counter(f["tipo"] for f in filas)
    out = ["---", "tipo: indice", f"proyecto: {a.proyecto or ''}", f"generado: {date.today().isoformat()}", "---", "",
           f"Índice generado por `scripts_for_fuentes/fichas/main.py indice` el {date.today().isoformat()}; no se edita a mano.", "",
           "## Estado de verificación", "", "| Estado | Fichas |", "|---|---|"]
    out += [f"| {k or '(sin estado)'} | {v} |" for k, v in sorted(por_estado.items())]
    out += ["", "## Fichas por tipo", ""]
    for tipo in config.TIPOS:
        grupo = [f for f in filas if f["tipo"] == tipo]
        if not grupo:
            continue
        out += [f"### {tipo} ({len(grupo)})", "", "| Ficha | Clave | Calibre | Página | Categoría | Uso | Estado |", "|---|---|---|---|---|---|---|"]
        out += [f"| [{f['archivo']}]({f['archivo']}) | {f['clave']} | {f['calibre_id']} | {f['pagina']} | {f['categoria']} | {f['uso']} | {f['estado']} |" for f in grupo]
        out.append("")
    texto = "\n".join(out)
    destino = carpeta / config.INDICE_NOMBRE
    if a.aplicar:
        destino.write_text(texto, encoding="utf-8"); print(f"[fichas] índice escrito: {destino} ({len(filas)} fichas, {dict(por_tipo)})")
    else:
        print(texto); print(f"[fichas] simulación: --aplicar escribe {destino}")
    return 0


def cmd_estado(a):
    filas = _filas(Path(a.carpeta).expanduser())
    c = Counter(f["estado"] for f in filas)
    en_uso_mal = [f for f in filas if f["uso"] and f["estado"] in ("pendiente", "observada", "")]
    print(f"[fichas] {len(filas)} fichas · " + " · ".join(f"{k or '(sin estado)'}: {v}" for k, v in sorted(c.items())))
    for f in en_uso_mal:
        print(f"  ! en uso ({f['uso']}) sin verificar: {f['archivo']} [{f['estado'] or 'sin estado'}]")
    return 1 if en_uso_mal else 0


def cmd_claves(a):
    """Rellena calibre_id y zotero_key de las fichas desde el fuentes.yml del proyecto (por clave_bibtex)."""
    carpeta = Path(a.carpeta).expanduser()
    sys.path.insert(0, str(config.DOCS / "scripts_for_fuentes" / "manifiesto"))
    from lib import manifiesto as M
    raiz = Path(a.fuentes).expanduser().parent if a.fuentes else M.raiz_de(carpeta / "x.md")
    por_clave = {str(e.get("clave_bibtex") or e.get("origen")): e for e in M.cargar(raiz)["fuentes"]}
    n = sin = 0
    for p in F.fichas_en([carpeta]):
        meta, cuerpo = F.leer(p)
        e = por_clave.get(str(meta.get("clave_bibtex", "")))
        if not e:
            sin += 1; continue
        cambio = False
        if meta.get("calibre_id") in (None, "") and e.get("calibre_id"):
            meta["calibre_id"] = int(e["calibre_id"]); cambio = True
        if meta.get("zotero_key") in (None, "") and e.get("zotero_key"):
            meta["zotero_key"] = e["zotero_key"]; cambio = True
        if cambio:
            n += 1; print(f"  {'✓' if a.aplicar else '·'} {p.name}: calibre_id {meta['calibre_id']}" + (f", zotero_key {meta['zotero_key']}" if meta.get("zotero_key") else ""))
            if a.aplicar:
                cuerpo = cuerpo.replace("Fuente aún no catalogada en Calibre: cotejo pendiente de los pasos 00–03.", f"Libro {meta['calibre_id']} de Calibre.")
                cuerpo = cuerpo.replace("- Fuente aún no catalogada en Calibre: pendiente de los pasos 00–03 del Método Documental\n", "")
                F.escribir(p, meta, cuerpo)
    print(f"[fichas] claves: {n} fichas {'actualizadas' if a.aplicar else 'por actualizar'} desde {raiz / 'fuentes.yml'} · {sin} sin entrada en el manifiesto"
          + ("" if a.aplicar else " · simulación (--aplicar escribe)"))
    return 0


def cmd_grafia(a):
    """M2 (meta/NORMATIVA_ARCHIVOS.md): claves y valores del frontmatter en snake_case; proyecto = id."""
    from lib import grafia
    cambios, d = grafia.migrar(a.carpetas, aplicar=a.aplicar,
                               raiz_respaldos=config.RESPALDOS)
    for f, _ in cambios[:12]:
        print("  ~", f)
    if len(cambios) > 12:
        print(f"  … {len(cambios) - 12} más")
    print(f"{len(cambios)} fichas {'migradas' if a.aplicar else 'por migrar (simulación; usa --aplicar)'}"
          + (f" · respaldo y UNDO en {d}" if d else ""))
    return 0


def cmd_migrar(a):
    from lib import migrar as M
    carpeta = Path(a.carpeta).expanduser()
    if a.aplicar:   # P240: migrar respalda antes de escribir, como grafia (fuera del repo)
        from lib import grafia
        d = grafia.respaldar(sorted(carpeta.rglob("*.md")), config.RESPALDOS, f"FD3_migrar_{a.formato}")
        print(f"  respaldo y UNDO en {d}")
    if a.formato == "catalogacion":
        plan = M.migrar_catalogacion(carpeta, a.aplicar); creados = []
    else:
        proyecto = a.proyecto or str(carpeta.resolve().relative_to(config.DOCS)).split("/notes/")[0]
        plan, creados = M.migrar_hibrida(carpeta, proyecto, a.aplicar)
    for nombre, accion in plan:
        print(f"  {nombre}: {accion}")
    print(f"[fichas] migrar {a.formato}: {len(plan)} fichas de origen" + (f" · {len(creados)} archivos nuevos" if creados else "")
          + (" · APLICADO" if a.aplicar else " · simulación (--aplicar escribe; backup y UNDO antes)"))
    return 0


def main():
    ap = argparse.ArgumentParser(description="fichas del Método Documental: validar, verificar, indexar, migrar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("claves", help="rellena calibre_id y zotero_key desde el fuentes.yml del proyecto"); p.add_argument("carpeta")
    p.add_argument("--fuentes", help="ruta del fuentes.yml (por defecto, el de la raíz del proyecto)"); p.add_argument("--aplicar", action="store_true")
    p = sub.add_parser("grafia", help="M2: claves y valores en snake_case (meta/NORMATIVA_ARCHIVOS.md §1)")
    p.add_argument("carpetas", nargs="+"); p.add_argument("--aplicar", action="store_true"); p.set_defaults(fn=cmd_grafia)
    p = sub.add_parser("migrar", help="FD3: lleva fichas anteriores al formato único"); p.add_argument("carpeta")
    p.add_argument("--formato", choices=["catalogacion", "hibrida"], required=True); p.add_argument("--aplicar", action="store_true"); p.add_argument("--proyecto")
    p = sub.add_parser("validar"); p.add_argument("rutas", nargs="+"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("verificar"); p.add_argument("rutas", nargs="+"); p.add_argument("--aplicar", action="store_true")
    p.add_argument("--desfase", type=int, help="páginas que hay que sumar a la impresa para llegar a la del PDF")
    p.add_argument("--tolerancia", type=int, help=f"páginas vecinas que se prueban (defecto {config.TOLERANCIA_PAGINAS})")
    p = sub.add_parser("indice"); p.add_argument("carpeta"); p.add_argument("--aplicar", action="store_true"); p.add_argument("--proyecto")
    p = sub.add_parser("estado"); p.add_argument("carpeta")
    a = ap.parse_args()
    return {"validar": cmd_validar, "verificar": cmd_verificar, "indice": cmd_indice, "estado": cmd_estado, "migrar": cmd_migrar, "claves": cmd_claves, "grafia": cmd_grafia}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
