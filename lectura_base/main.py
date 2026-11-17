#!/usr/bin/env python3
"""lectura_base/main.py — la base de lectura de Biblioteca Studio (decisiones §9.6): una sola base para los subrayados,
resaltados y notas de KOReader, Zotero, Okular y Yachay, y las horas, sesiones y progreso de lectura.

Simula por omisión; `--aplicar` escribe (en la base, tras su respaldo verificado; en Zotero, por la puerta).

    main.py estado [--json]                                  # qué hay en la base (solo lee)
    main.py sincronizar [--origen koreader,zotero] [--aplicar]   # la ida: cada herramienta → la base
    main.py exportar zotero [--ids 12,48] [--limite N] [--aplicar]  # la vuelta: la base → una herramienta
    main.py libro <calibre_id> [--json]                      # los subrayados, el tiempo y las sesiones de un libro
    main.py cambios [--desde N | --consumidor X [--avanzar]] [--json]   # la cola de cambios para otros programas
    main.py ruta                                             # dónde vive la base
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lectura_base import config  # noqa: E402

config.cargar_entorno()
from lectura_base.lib import base, consulta, exportar, sincronizar  # noqa: E402


def _ids(texto: str | None) -> set[int] | None:
    return {int(x) for x in texto.split(",") if x.strip()} if texto else None


def cmd_estado(a, log) -> int:
    r = consulta.resumen()
    if a.json:
        print(consulta.a_json(r))
        return 0
    if not r["existe"]:
        print(f"La base de lectura aún no existe ({r['ruta']}): `main.py sincronizar --aplicar` la crea.")
        return 0
    origenes = " · ".join(f"{base.NOMBRES.get(o, o)} {n}" for o, n in sorted(r["por_origen"].items()))
    print(f"Base de lectura: {r['ruta']}")
    print(f"  {r['anotaciones']} anotaciones ({origenes or 'ninguna'}; {r['compartidas']} en más de una herramienta)")
    print(f"  {r['tiempo']} de lectura en {r['libros']} libros · {r['sesiones']} sesiones · este mes {r['mes']['tiempo']} "
          f"en {r['mes']['dias']} días · racha de {r['racha']} días")
    print(f"  última sincronía: {consulta.utc_a_local(r['ultima_sincronia']) or 'nunca'} · {r['cambios']} cambios en la cola")
    return 0


def _imprimir_plan(p: base.Plan, aplicar: bool) -> None:
    r = p.resumen()
    verbo = "" if aplicar else "[simulación] "
    print(f"{verbo}{base.NOMBRES.get(p.origen, p.origen)}: {r['leidas']} leídas · {r['altas']} nuevas · {r['uniones']} unidas a otra "
          f"herramienta · {r['cambios']} cambiadas · {r['ausentes']} ya no están · {r['borradas']} borradas · sesiones "
          f"+{r['sesiones']['altas']}/~{r['sesiones']['cambios']} · progreso +{r['progreso']['altas']}/~{r['progreso']['cambios']}")
    for u in p.uniones[:5]:
        print(f"    = libro {u.get('calibre_id')} hoja {u.get('hoja')}: «{(u.get('texto') or u.get('nota') or '')[:60]}» "
              f"(también en {', '.join(base.NOMBRES.get(o, o) for o in u.get('con', []))})")
    for x in p.avisos:
        print(f"    ! {x}")


def cmd_sincronizar(a, log) -> int:
    origenes = tuple(o.strip() for o in (a.origen or ",".join(base.ORIGENES)).split(",") if o.strip())
    malos = [o for o in origenes if o not in base.ORIGENES]
    if malos:
        log.error("origen desconocido: %s (uno de %s)", ", ".join(malos), ", ".join(base.ORIGENES))
        return 2
    planes = sincronizar.sincronizar(origenes, aplicar=a.aplicar, recortar_okular=not a.sin_recorte)
    if a.json:
        print(consulta.a_json([p.resumen() for p in planes]))
    else:
        for p in planes:
            _imprimir_plan(p, a.aplicar)
        if not a.aplicar:
            print("Nada se escribió. --aplicar concilia en la base (tras su respaldo verificado).")
        else:
            print(f"✓ Base de lectura al día: {base.ruta_base()}")
    return 0


def cmd_exportar(a, log) -> int:
    try:
        r = exportar.exportar(a.destino, aplicar=a.aplicar, ids=_ids(a.ids), limite=a.limite)
    except PermissionError as e:
        log.error("%s", e)
        return 3
    except Exception as e:  # noqa: BLE001 — la puerta ocupada, Zotero abierto…
        log.error("%s", e)
        return 75 if "abierto" in str(e) or "ocupad" in str(e) else 1
    if a.json:
        r = {**r, "plan": [{k: v for k, v in p.items() if k not in ("fila", "entrada", "nodo")} for p in r["plan"]]}
        print(consulta.a_json(r))
        return 0
    nombre = base.NOMBRES.get(a.destino, a.destino)
    if r["hechas"]:
        print(f"✓ {len(r['hechas'])} anotaciones escritas en {nombre} y apuntadas en la base.")
        return 0
    print(f"[simulación] {len(r['plan'])} anotaciones de la base irían a {nombre}:")
    for p in r["plan"][:20]:
        print(f"    + libro {p['calibre_id']} hoja {p['hoja']}: «{p['texto'][:60]}»")
    for x in r["avisos"]:
        print(f"    ! {x}")
    if not r["escribe"]:
        print(f"    (aplicar aún no: {exportar.PENDIENTES[a.destino]})")
    elif r["plan"]:
        print("--aplicar las escribe por la puerta (aplicación cerrada, candado, respaldo verificado).")
    return 0


def cmd_libro(a, log) -> int:
    r = consulta.libro(a.calibre_id)
    if a.json:
        print(consulta.a_json(r))
        return 0
    if not r:
        print("La base de lectura aún no existe.")
        return 0
    print(f"{r['titulo'] or 'Libro ' + str(a.calibre_id)} — {r['tiempo']} · {r['n_sesiones']} sesiones · {len(r['anotaciones'])} anotaciones")
    for g in r["progreso"]:
        pct = f"{g['porcentaje']} %" if g["porcentaje"] is not None else "—"
        print(f"  {base.NOMBRES.get(g['origen'], g['origen'])}: {pct} · {g['tiempo']} · {g['estado'] or ''}")
    for x in r["anotaciones"]:
        print(f"  [{x['lugar']}] «{(x['texto'] or x['nota'])[:90]}» ({', '.join(base.NOMBRES.get(o, o) for o in x['vive_en'])})")
    return 0


def cmd_cambios(a, log) -> int:
    desde = a.desde if a.desde is not None else (base.leer_cursor(a.consumidor) if a.consumidor else 0)
    r = base.cambios_desde(int(desde or 0), limite=a.limite)
    if a.consumidor and a.avanzar and a.aplicar:
        base.guardar_cursor(a.consumidor, r["hasta"])
    if a.json:
        print(consulta.a_json(r))
    else:
        for c in r["cambios"]:
            print(f"{c['seq']:>6} {c['momento']} {c['tabla']:<11} {c['operacion']:<7} {c['origen']:<9} libro {c['calibre_id']}")
        print(f"hasta {r['hasta']}" + (" (cursor guardado)" if a.consumidor and a.avanzar and a.aplicar else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="La base de lectura de Biblioteca Studio (simula por omisión).")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="orden")
    e = sub.add_parser("estado", help="qué hay en la base (solo lee)")
    e.add_argument("--json", action="store_true")
    s = sub.add_parser("sincronizar", help="cada herramienta → la base")
    s.add_argument("--origen", help="koreader,zotero,okular,yachay (todos por omisión)")
    s.add_argument("--aplicar", action="store_true")
    s.add_argument("--sin-recorte", action="store_true", help="no recortar con pdftotext el texto de Okular")
    s.add_argument("--json", action="store_true")
    x = sub.add_parser("exportar", help="la base → una herramienta")
    x.add_argument("destino", choices=exportar.DESTINOS)
    x.add_argument("--ids", help="solo estos libros (calibre_id separados por comas)")
    x.add_argument("--limite", type=int)
    x.add_argument("--aplicar", action="store_true")
    x.add_argument("--json", action="store_true")
    li = sub.add_parser("libro", help="un libro: subrayados, tiempo y sesiones")
    li.add_argument("calibre_id", type=int)
    li.add_argument("--json", action="store_true")
    c = sub.add_parser("cambios", help="la cola de cambios")
    c.add_argument("--desde", type=int)
    c.add_argument("--consumidor")
    c.add_argument("--avanzar", action="store_true", help="con --consumidor y --aplicar: guarda su cursor al final")
    c.add_argument("--aplicar", action="store_true")
    c.add_argument("--limite", type=int, default=500)
    c.add_argument("--json", action="store_true")
    sub.add_parser("ruta", help="dónde vive la base")
    a = ap.parse_args(argv)
    log = config.logger(a.verbose)
    if a.orden in (None, "estado"):
        if a.orden is None:
            a.json = False
        return cmd_estado(a, log)
    if a.orden == "ruta":
        print(base.ruta_base())
        return 0
    return {"sincronizar": cmd_sincronizar, "exportar": cmd_exportar, "libro": cmd_libro, "cambios": cmd_cambios}[a.orden](a, log)


if __name__ == "__main__":
    sys.exit(main())
