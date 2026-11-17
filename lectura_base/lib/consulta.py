"""lectura_base/lib/consulta.py — lo que la ventana y la CLI leen de la base de lectura (SOLO LECTURA, `mode=ro`).

Las horas: cada origen es dueño de su reloj (CLAUDE.md: «los relojes de lectura no se copian entre sí»). El tiempo de un
libro es la suma, por origen, del total que ese origen lleva (`progreso.segundos`: el `total_read_time` de KOReader, el
readingTime de Zotero); las sesiones (solo KOReader trae la hora de cada página) dan las semanas, los días y la racha.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from lectura_base.lib import base


def _horas(segundos) -> float:
    return round((segundos or 0) / 3600.0, 2)


def texto_duracion(segundos) -> str:
    """«3 h 20 min», «45 min», «—»."""
    s = int(segundos or 0)
    if s < 60:
        return "—" if s == 0 else "1 min"
    h, m = divmod(s // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def _dia_local(epoch: int) -> date:
    return datetime.fromtimestamp(int(epoch)).date()


def resumen(ruta: Path | None = None, hoy: date | None = None) -> dict:
    """Lo de toda la base: cuántas anotaciones y de dónde, horas, sesiones, días leídos, racha, última sincronía."""
    hoy = hoy or date.today()
    with base.lector(ruta) as c:
        if c is None:
            return {"existe": False, "ruta": str(Path(ruta or base.ruta_base()))}
        activas = c.execute("SELECT count(*) FROM anotaciones WHERE borrada IS NULL").fetchone()[0]
        por_origen = {o: n for o, n in c.execute(
            "SELECT p.origen, count(DISTINCT p.anotacion_id) FROM presencias p JOIN anotaciones a ON a.id = p.anotacion_id "
            "WHERE p.ausente IS NULL AND a.borrada IS NULL GROUP BY p.origen")}
        compartidas = c.execute("SELECT count(*) FROM (SELECT anotacion_id FROM presencias WHERE ausente IS NULL "
                                "GROUP BY anotacion_id HAVING count(DISTINCT origen) > 1)").fetchone()[0]
        segundos = {o: s for o, s in c.execute("SELECT origen, sum(segundos) FROM progreso GROUP BY origen")}
        dias = sorted({_dia_local(i) for (i,) in c.execute("SELECT inicio FROM sesiones")})
        mes = hoy.replace(day=1)
        inicio_mes = int(datetime.combine(mes, datetime.min.time()).timestamp())
        seg_mes = c.execute("SELECT coalesce(sum(segundos), 0), count(*) FROM sesiones WHERE inicio >= ?", (inicio_mes,)).fetchone()
        sesiones = c.execute("SELECT count(*) FROM sesiones").fetchone()[0]
        libros = c.execute("SELECT count(DISTINCT coalesce(calibre_id, md5)) FROM progreso").fetchone()[0]
        ultima = c.execute("SELECT max(momento) FROM corridas").fetchone()[0]
        pendientes = c.execute("SELECT count(*) FROM cambios").fetchone()[0]
    racha, d = 0, hoy if hoy in dias else hoy - timedelta(days=1)
    conjunto = set(dias)
    while d in conjunto:
        racha += 1
        d -= timedelta(days=1)
    total = sum(v or 0 for v in segundos.values())
    return {"existe": True, "ruta": str(Path(ruta or base.ruta_base())), "anotaciones": activas, "por_origen": por_origen,
            "compartidas": compartidas, "segundos": total, "horas": _horas(total), "tiempo": texto_duracion(total),
            "segundos_por_origen": segundos, "sesiones": sesiones, "libros": libros,
            "mes": {"segundos": seg_mes[0], "tiempo": texto_duracion(seg_mes[0]), "sesiones": seg_mes[1],
                    "dias": sum(1 for x in dias if x >= mes)},
            "dias_30": sum(1 for x in dias if x > hoy - timedelta(days=30)), "racha": racha, "ultima_sincronia": ultima or "",
            "cambios": pendientes}


def semanas(n: int = 12, ruta: Path | None = None, hoy: date | None = None) -> list[dict]:
    """Las últimas `n` semanas (lunes a domingo), de la más vieja a la actual: horas leídas y sesiones."""
    hoy = hoy or date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    inicios = [lunes - timedelta(weeks=k) for k in range(n - 1, -1, -1)]
    salida = [{"desde": d.isoformat(), "etiqueta": d.strftime("%d/%m"), "segundos": 0, "sesiones": 0} for d in inicios]
    with base.lector(ruta) as c:
        if c is None:
            return salida
        desde = int(datetime.combine(inicios[0], datetime.min.time()).timestamp())
        for inicio, seg in c.execute("SELECT inicio, segundos FROM sesiones WHERE inicio >= ?", (desde,)):
            k = (_dia_local(inicio) - inicios[0]).days // 7
            if 0 <= k < n:
                salida[k]["segundos"] += seg
                salida[k]["sesiones"] += 1
    maximo = max((s["segundos"] for s in salida), default=0) or 1
    for s in salida:
        s["horas"] = _horas(s["segundos"])
        s["proporcion"] = round(s["segundos"] / maximo, 3)
    return salida


def libros(limite: int = 200, ruta: Path | None = None) -> list[dict]:
    """Los libros con lectura (tiempo, progreso o anotaciones), los más recientes primero."""
    with base.lector(ruta) as c:
        if c is None:
            return []
        filas: dict = {}

        def fila(calibre_id, md5):
            clave = base.clave_libro(calibre_id, md5)
            return filas.setdefault(clave, {"clave": clave, "calibre_id": calibre_id, "md5": md5 or "", "segundos": 0,
                                            "anotaciones": 0, "fraccion": None, "ultima": "", "estado": "", "origenes": set()})

        for g in c.execute("SELECT * FROM progreso"):
            f = fila(g["calibre_id"], g["md5"])
            f["segundos"] += g["segundos"] or 0
            if g["fraccion"] is not None:
                f["fraccion"] = max(f["fraccion"] or 0, g["fraccion"])
            f["ultima"] = max(f["ultima"], g["ultima"] or "")
            f["estado"] = f["estado"] or g["estado"]
            f["origenes"].add(g["origen"])
        for calibre_id, md5, n, ultima in c.execute(
                "SELECT calibre_id, md5, count(*), max(modificada) FROM anotaciones WHERE borrada IS NULL GROUP BY calibre_id, md5"):
            f = fila(calibre_id, md5)
            f["anotaciones"] += n
            f["ultima"] = max(f["ultima"], ultima or "")
        titulos = {r["calibre_id"]: (r["titulo"], r["autores"]) for r in c.execute("SELECT calibre_id, titulo, autores FROM libros")}
    salida = []
    for f in filas.values():
        if not (f["segundos"] or f["anotaciones"] or f["fraccion"]):
            continue
        titulo, autores = titulos.get(f["calibre_id"], ("", ""))
        f.update(titulo=titulo or (f"Libro {f['calibre_id']}" if f["calibre_id"] is not None else "Fuera de la biblioteca"),
                 autores=autores, tiempo=texto_duracion(f["segundos"]), origenes=sorted(f["origenes"]),
                 porcentaje=int(round((f["fraccion"] or 0) * 100)))
        salida.append(f)
    salida.sort(key=lambda f: f["ultima"], reverse=True)
    return salida[:limite]


def libro(calibre_id: int, ruta: Path | None = None, sesiones_max: int = 30) -> dict:
    """Todo lo de un libro: sus anotaciones (con dónde vive cada una), su progreso y tiempo por origen y sus sesiones."""
    with base.lector(ruta) as c:
        if c is None:
            return {}
        datos = c.execute("SELECT * FROM libros WHERE calibre_id = ?", (int(calibre_id),)).fetchone()
        anotaciones = []
        for a in c.execute("SELECT * FROM anotaciones WHERE calibre_id = ? AND borrada IS NULL ORDER BY coalesce(hoja, 1000000), "
                           "json_extract(rects, '$[0][2]'), creada", (int(calibre_id),)):
            d = base.anotacion_publica(c, a)
            d["vive_en"] = [o["origen"] for o in d["origenes"] if not o["ausente"]]
            d["lugar"] = (f"p. {a['pagina']}" if a["pagina"] else (f"hoja {a['hoja']}" if a["hoja"] else (a["capitulo"] or "")))
            anotaciones.append(d)
        progreso = [dict(g) for g in c.execute("SELECT * FROM progreso WHERE calibre_id = ? ORDER BY origen", (int(calibre_id),))]
        sesiones = [dict(s) for s in c.execute("SELECT * FROM sesiones WHERE calibre_id = ? ORDER BY inicio DESC LIMIT ?",
                                               (int(calibre_id), int(sesiones_max)))]
        totales = c.execute("SELECT count(*), coalesce(sum(segundos), 0), coalesce(sum(paginas), 0), min(inicio), max(fin) "
                            "FROM sesiones WHERE calibre_id = ?", (int(calibre_id),)).fetchone()
        dias = {_dia_local(i) for (i,) in c.execute("SELECT inicio FROM sesiones WHERE calibre_id = ?", (int(calibre_id),))}
    segundos = sum(g["segundos"] or 0 for g in progreso)
    for g in progreso:
        g["tiempo"] = texto_duracion(g["segundos"])
        g["porcentaje"] = int(round((g["fraccion"] or 0) * 100)) if g["fraccion"] is not None else None
    for s in sesiones:
        s["fecha"] = datetime.fromtimestamp(s["inicio"]).strftime("%Y-%m-%d %H:%M")
        s["tiempo"] = texto_duracion(s["segundos"])
    paginas_hora = round(totales[2] / (totales[1] / 3600.0), 1) if totales[1] >= 600 else None
    return {"calibre_id": int(calibre_id), "titulo": datos["titulo"] if datos else "", "autores": datos["autores"] if datos else "",
            "md5": datos["md5"] if datos else "", "anotaciones": anotaciones, "progreso": progreso, "sesiones": sesiones,
            "segundos": segundos, "tiempo": texto_duracion(segundos), "n_sesiones": totales[0], "paginas_hora": paginas_hora,
            "dias": len(dias),
            "primera": datetime.fromtimestamp(totales[3]).strftime("%Y-%m-%d") if totales[3] else "",
            "ultima": datetime.fromtimestamp(totales[4]).strftime("%Y-%m-%d") if totales[4] else "",
            "por_origen": {o: sum(1 for a in anotaciones if o in a["vive_en"]) for o in base.ORIGENES}}


def a_json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, indent=1, default=str)


def utc_a_local(iso_utc: str) -> str:
    """«2026-03-11T17:31:04Z» → «2026-03-11 12:31» en la hora de la máquina."""
    if not iso_utc:
        return ""
    try:
        return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_utc

