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
    main.py ciclo [--json]                                   # lo que corre el timer: la ida y la vuelta, solo si hay algo
    main.py ficha <calibre_id> [--json]                      # la ficha de obra de Yachay que guarda la base (solo lee)
    main.py ficha-a-yachay <calibre_id> '<json>' [--leida] [--sobre N] [--aplicar] [--json]
                                                             # la vuelta de la ficha de obra (§9.13): simula; un 409 no pisa
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
    fo = r.get("fichas_obra") or {}
    if any(fo.values()):
        print(f"    fichas de obra: +{fo.get('altas', 0)} nuevas · {fo.get('cambios', 0)} cambiadas · {fo.get('bajas', 0)} quitadas")
    for u in p.uniones[:5]:
        print(f"    = libro {u.get('calibre_id')} hoja {u.get('hoja')}: «{(u.get('texto') or u.get('nota') or '')[:60]}» "
              f"(también en {', '.join(base.NOMBRES.get(o, o) for o in u.get('con', []))})")
    for x in p.avisos:
        print(f"    ! {x}")


def cmd_sincronizar(a, log) -> int:
    origenes = tuple(o.strip() for o in (a.origen or ",".join(base.LEIDOS)).split(",") if o.strip())
    malos = [o for o in origenes if o not in base.LEIDOS]
    if malos:
        log.error("origen desconocido: %s (uno de %s; %s vuelca por su cuenta)", ", ".join(malos), ", ".join(base.LEIDOS),
                  ", ".join(base.NOMBRES[o] for o in base.CLIENTES))
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
        cliente = None
        if a.destino == "yachay" and a.aplicar:
            from lectura_base.lib.adaptadores import yachay as ad_yachay
            cliente = ad_yachay.cargar_cliente()       # el token del llavero; None si no hay
        r = exportar.exportar(a.destino, aplicar=a.aplicar, ids=_ids(a.ids), limite=a.limite, cliente=cliente)
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
        como = {"zotero": "por la puerta (Zotero cerrado, candado, respaldo verificado)",
                "koreader": "en el .lua de cada libro (KOReader cerrado, respaldo verificado, escritura atómica)",
                "okular": "en el docdata de cada PDF (Okular cerrado, respaldo verificado; nunca en el PDF)",
                "yachay": "por su API con tu token (sin duplicar: cada una lleva su uid como origen_id)"}.get(a.destino, "")
        print(f"--aplicar las escribe {como}.")
    return 0


def cmd_ciclo(a, log) -> int:
    """Lo que corre el timer de cada hora (systemd/lectura-base.timer): la ida (cada herramienta → la base) y la vuelta
    (la base → cada una). Simula primero y escribe solo si hay algo, así una hora sin cambios no deja respaldos. Una
    herramienta abierta (KOReader, Zotero, Okular) o Yachay sin token se saltan y se reintentan en la vuelta siguiente:
    sale 75 («reintentar luego», no es un fallo). Dos ciclos a la vez no corren: el segundo sale 75."""
    import contextlib
    import fcntl
    from lectura_base.lib.adaptadores import yachay as ad_yachay
    candado = base.ruta_base().with_name("ciclo.lock")
    candado.parent.mkdir(parents=True, exist_ok=True)
    # lo que imprimen la puerta y los respaldos va a stderr: stdout queda para el informe (y el JSON)
    with open(candado, "w") as fd, contextlib.redirect_stdout(sys.stderr):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("otro ciclo de la base de lectura está corriendo")
            return 75
        cliente = ad_yachay.cargar_cliente()
        origenes = base.LEIDOS if cliente is not None else tuple(o for o in base.LEIDOS if o != "yachay")
        informe = {"ida": [], "vuelta": {}, "saltados": []}
        if cliente is None:
            informe["saltados"].append("yachay: sin cliente o sin token en el llavero")
        planes = sincronizar.sincronizar(origenes, cliente=cliente)
        if any(not p.vacio() for p in planes):
            planes = sincronizar.sincronizar(origenes, aplicar=True, cliente=cliente)
            informe["ida"] = [p.resumen() for p in planes if not p.vacio()]
        for destino in exportar.DESTINOS:
            if destino == "yachay" and cliente is None:
                continue
            try:
                r = exportar.exportar(destino, aplicar=True, cliente=cliente if destino == "yachay" else None)
            except Exception as e:  # noqa: BLE001 — abierta, la puerta ocupada, Yachay caído: la próxima vuelta
                informe["saltados"].append(f"{destino}: {e}")
                continue
            if r["hechas"]:
                informe["vuelta"][destino] = len(r["hechas"])
    if a.json:
        print(consulta.a_json(informe))
    else:
        for p in informe["ida"]:
            fo = p.get("fichas_obra") or {}
            print(f"→ base: {base.NOMBRES.get(p['origen'], p['origen'])}: +{p['altas']} nuevas, {p['cambios']} cambiadas, "
                  f"{p['borradas']} borradas · progreso +{p['progreso']['altas']}/~{p['progreso']['cambios']}"
                  + (f" · fichas de obra +{fo.get('altas', 0)}/~{fo.get('cambios', 0)}" if any(fo.values()) else ""))
        for d, n in informe["vuelta"].items():
            print(f"← {base.NOMBRES.get(d, d)}: {n} anotaciones")
        for s in informe["saltados"]:
            print(f"· se reintenta luego: {s}")
        if not informe["ida"] and not informe["vuelta"]:
            print("= Nada nuevo: la base y las herramientas ya coinciden.")
    return 75 if informe["saltados"] else 0


def cmd_ficha(a, log) -> int:
    f = consulta.ficha_obra_de(a.calibre_id)
    if a.json:
        print(consulta.a_json(f))
        return 0
    if not f:
        print(f"El libro {a.calibre_id} no tiene ficha de obra de Yachay en la base (`main.py sincronizar --origen yachay --aplicar` la trae).")
        return 0
    print(f"Ficha de obra en Yachay · libro {a.calibre_id} · versión {f['version']} · {f['escritas']} de {f['total']} respondidas"
          + (f" · leída el {consulta.utc_a_local(f['leida_en'])}" if f["leida"] else " · sin dar por leída"))
    for k in base.CAMPOS_OBRA:
        print(f"  {base.TITULOS_OBRA[k]}: {f['ficha'][k] or '—'}")
    if f["ficha"]["temas"]:
        print(f"  Temas: {', '.join(f['ficha']['temas'])}")
    if f["ficha"]["signo"]:
        print(f"  Signo: {f['ficha']['signo']}")
    return 0


def cmd_ficha_a_yachay(a, log) -> int:
    """La vuelta de la ficha de obra: simula (qué se enviaría y con qué versión); con --aplicar, por el cliente."""
    import json as _json
    from lectura_base.lib import ficha_obra
    texto = sys.stdin.read() if a.datos == "-" else (Path(a.datos).read_text(encoding="utf-8")
                                                     if len(a.datos) < 4096 and Path(a.datos).is_file() else a.datos)
    try:
        p = ficha_obra.plan(a.calibre_id, _json.loads(texto), sobre=a.sobre, leida=a.leida)
    except (ValueError, TypeError) as e:
        log.error("%s", e)
        return 2
    cliente = None
    if a.aplicar:
        from lectura_base.lib.adaptadores import yachay as ad_yachay
        cliente = ad_yachay.cargar_cliente()
    try:
        r = ficha_obra.llevar(p, cliente, aplicar=a.aplicar)
    except ficha_obra.SinCanal as e:
        log.error("%s", e)
        return 3
    except Exception as e:  # noqa: BLE001 — Yachay caído o sin permiso
        log.error("Yachay: %s", e)
        return 1
    if a.json:
        print(consulta.a_json(r))
    else:
        for linea in ficha_obra.texto(r):
            print(linea)
    return 4 if r.get("codigo") == "lectura_modificada" else 0


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
    ci = sub.add_parser("ciclo", help="la ida y la vuelta, solo si hay algo (lo que corre el timer)")
    ci.add_argument("--json", action="store_true")
    fo = sub.add_parser("ficha", help="la ficha de obra de Yachay de un libro, como la guarda la base (solo lee)")
    fo.add_argument("calibre_id", type=int)
    fo.add_argument("--json", action="store_true")
    fy = sub.add_parser("ficha-a-yachay", help="llevar la ficha de obra a Yachay (simula; --aplicar la envía con version_base)")
    fy.add_argument("calibre_id", type=int)
    fy.add_argument("datos", help="JSON con las respuestas (pregunta, metodo, datos, hallazgo, limites, uso o sus títulos; "
                                  "temas, signo); «-» lo lee de la entrada estándar; una ruta, de su archivo")
    fy.add_argument("--leida", action="store_true", help="después, darla por leída (Yachay la exige completa)")
    fy.add_argument("--sobre", type=int, help="tras un conflicto: llevar la tuya sobre esta versión de Yachay")
    fy.add_argument("--aplicar", action="store_true")
    fy.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    log = config.logger(a.verbose)
    if a.orden in (None, "estado"):
        if a.orden is None:
            a.json = False
        return cmd_estado(a, log)
    if a.orden == "ruta":
        print(base.ruta_base())
        return 0
    return {"sincronizar": cmd_sincronizar, "exportar": cmd_exportar, "libro": cmd_libro, "cambios": cmd_cambios, "ciclo": cmd_ciclo,
            "ficha": cmd_ficha, "ficha-a-yachay": cmd_ficha_a_yachay}[a.orden](a, log)


if __name__ == "__main__":
    sys.exit(main())
