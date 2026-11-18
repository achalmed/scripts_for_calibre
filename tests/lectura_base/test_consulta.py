"""Las consultas nuevas de la base de lectura (decisiones §9.9): el mapa de calor por día, los subrayados nuevos de la
semana, los libros en curso y los subrayados con texto. Solo leen: la base se arma en el temporal del mundo de juguete."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

from lectura_base.lib import base, consulta


def _sesion(oid: str, cuando: datetime, segundos: int, calibre_id: int = 1) -> dict:
    inicio = int(cuando.timestamp())
    return {"origen_id": oid, "calibre_id": calibre_id, "inicio": inicio, "fin": inicio + segundos, "segundos": segundos, "paginas": 5}


def _subrayado(oid: str, texto: str, creada: str, hoja: int = 1, calibre_id: int = 1) -> dict:
    return {"origen_id": oid, "calibre_id": calibre_id, "hoja": hoja, "texto": texto, "creada": creada, "modificada": creada,
            "rects": [[hoja, 0.1, 0.1 * hoja, 0.5, 0.02]]}


def test_sin_base_no_falla_y_no_crea_nada(mundo):
    assert consulta.nuevas(7) == 0 and consulta.en_curso() == [] and consulta.subrayados() == []
    dias = consulta.dias(12)
    assert len(dias) == 84 and all(d["nivel"] == 0 for d in dias)
    assert not mundo.lectura_db.exists()


def test_el_mapa_de_calor_ubica_cada_dia_y_gradua_las_horas(mundo):
    hoy = date.today()
    mediodia = datetime.combine(hoy, datetime.min.time()) + timedelta(hours=12)
    lunes = hoy - timedelta(days=hoy.weekday())
    sesiones = [_sesion("s1", mediodia, 3600), _sesion("s2", mediodia - timedelta(days=1), 600),
                _sesion("s3", datetime.combine(lunes - timedelta(weeks=11), datetime.min.time()) + timedelta(hours=9), 1800),
                _sesion("vieja", mediodia - timedelta(weeks=13), 7200)]          # fuera de las doce semanas
    base.importar([base.Lectura("koreader", sesiones=sesiones, alcance=None)], aplicar=True)
    dias = consulta.dias(12)
    assert len(dias) == 84 and dias[0]["semana"] == 0 and dias[0]["dia"] == 0 and dias[-1]["semana"] == 11
    hoy_ = next(d for d in dias if d["fecha"] == hoy.isoformat())
    assert hoy_["semana"] == 11 and hoy_["dia"] == hoy.weekday() and hoy_["segundos"] == 3600 and hoy_["nivel"] == 4
    assert dias[0]["segundos"] == 1800 and 1 <= dias[0]["nivel"] < 4             # el lunes de hace once semanas
    assert sum(d["segundos"] for d in dias) == 3600 + 600 + 1800                    # la de hace trece semanas no entra
    assert all(d["futuro"] for d in dias if d["fecha"] > hoy.isoformat())
    assert all(d["nivel"] == 0 for d in dias if not d["segundos"])


def test_subrayados_nuevos_de_la_semana_y_con_texto(mundo):
    ahora = datetime.now(timezone.utc)
    reciente = (ahora - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    viejo = (ahora - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    base.importar([base.Lectura("koreader", anotaciones=[
        _subrayado("k1", "La productividad es casi todo en el largo plazo.", reciente),
        _subrayado("k2", "El crecimiento sigue a las instituciones.", viejo, hoja=2),
        _subrayado("k3", "", reciente, hoja=3)], alcance=None)], aplicar=True)
    assert consulta.nuevas(7) == 2 and consulta.nuevas(30) == 3
    textos = [s["texto"] for s in consulta.subrayados()]
    assert textos == ["La productividad es casi todo en el largo plazo.", "El crecimiento sigue a las instituciones."]


def test_en_curso_el_ultimo_leido_primero_y_sin_los_terminados(mundo):
    base.importar([base.Lectura("koreader", progreso=[
        {"calibre_id": 1, "fraccion": 0.42, "estado": "reading", "ultima": "2026-11-10T10:00:00Z"},
        {"calibre_id": 2, "fraccion": 1.0, "estado": "complete", "ultima": "2026-11-12T10:00:00Z"}],
        libros={1: {"titulo": "Economía de juguete", "autores": "Rosa Quispe"}}, alcance=None),
        base.Lectura("zotero", progreso=[{"calibre_id": 1, "fraccion": 0.5, "ultima": "2026-11-15T10:00:00Z"}], alcance=None)],
        aplicar=True)
    curso = consulta.en_curso(3)
    assert [l["calibre_id"] for l in curso] == [1]                                 # el 2 está terminado
    assert curso[0]["origen"] == "zotero" and curso[0]["porcentaje"] == 50 and curso[0]["titulo"] == "Economía de juguete"


def test_las_consultas_no_escriben(mundo):
    base.importar([base.Lectura("koreader", sesiones=[_sesion("s1", datetime.now(), 900)], alcance=None)], aplicar=True)
    antes = mundo.lectura_db.stat().st_mtime_ns
    time.sleep(0.01)
    consulta.dias(12), consulta.nuevas(7), consulta.en_curso(3), consulta.subrayados()
    assert mundo.lectura_db.stat().st_mtime_ns == antes
