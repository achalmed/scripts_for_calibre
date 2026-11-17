"""La base de lectura (decisiones §9.6): conciliar sin duplicar, la cola de cambios, las ausencias y la guarda de rutas."""
from __future__ import annotations

import sqlite3

import pytest

from lectura_base.lib import base
from lectura_base.lib import texto as tx


def _lectura(origen, *anotaciones, alcance=None, **k):
    return base.Lectura(origen, anotaciones=list(anotaciones), alcance=set(alcance or {"c1"}), **k)


def _a(origen_id, texto="La productividad es casi todo en el largo plazo.", hoja=1, nota="", modificada="2026-03-01T10:00:00Z",
       rects=None, **k):
    return {"origen_id": origen_id, "calibre_id": 1, "hoja": hoja, "texto": texto, "nota": nota, "modificada": modificada,
            "rects": rects if rects is not None else [[hoja, 0.12, 0.11, 0.5, 0.02]], **k}


def _contar(ruta, tabla, donde="1"):
    with sqlite3.connect(ruta) as c:
        return c.execute(f"select count(*) from {tabla} where {donde}").fetchone()[0]


def test_simular_no_escribe_nada(mundo):
    planes = base.importar([_lectura("koreader", _a("k1"))])
    assert len(planes[0].altas) == 1
    assert not mundo.lectura_db.exists()


def test_aplicar_crea_la_base_con_su_cola(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    assert _contar(mundo.lectura_db, "anotaciones") == 1
    assert _contar(mundo.lectura_db, "presencias") == 1
    ops = [r["operacion"] for r in base.cambios_desde(0)["cambios"]]
    assert ops == ["alta", "alta"]                     # la anotación y su presencia


def test_dos_veces_lo_mismo_no_duplica_ni_ensucia_la_cola(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    hasta = base.cambios_desde(0)["hasta"]
    planes = base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    assert planes[0].vacio()
    assert _contar(mundo.lectura_db, "anotaciones") == 1
    assert base.cambios_desde(hasta)["cambios"] == []


def test_el_mismo_pasaje_en_dos_herramientas_es_una_anotacion(mundo):
    """KOReader parte la línea con guion; Zotero la da entera y con otra mayúscula: la misma anotación, dos presencias."""
    base.importar([_lectura("koreader", _a("k1", texto="La producti-\nvidad es casi todo en el largo plazo"))], aplicar=True)
    planes = base.importar([_lectura("zotero", _a("ZKEY0001", texto="la productividad es casi todo en el largo plazo.", nota="clave"))],
                           aplicar=True)
    assert len(planes[0].uniones) == 1 and not planes[0].altas
    assert _contar(mundo.lectura_db, "anotaciones") == 1
    assert _contar(mundo.lectura_db, "presencias") == 2
    with sqlite3.connect(mundo.lectura_db) as c:
        assert c.execute("select nota from anotaciones").fetchone()[0] == "clave"     # la unión completa lo que faltaba


def test_dos_subrayados_iguales_en_una_herramienta_son_dos(mundo):
    base.importar([_lectura("koreader", _a("k1"), _a("k2"))], aplicar=True)
    assert _contar(mundo.lectura_db, "anotaciones") == 2


def test_okular_sin_texto_se_une_por_sus_rectangulos(mundo):
    base.importar([_lectura("koreader", _a("k1", rects=[[1, 0.12, 0.11, 0.5, 0.02]]))], aplicar=True)
    planes = base.importar([_lectura("okular", _a("okular-1", texto="", nota="ver", rects=[[1, 0.125, 0.112, 0.49, 0.02]]))], aplicar=True)
    assert len(planes[0].uniones) == 1
    assert _contar(mundo.lectura_db, "anotaciones") == 1


def test_hojas_lejanas_no_se_unen(mundo):
    base.importar([_lectura("koreader", _a("k1", hoja=1))], aplicar=True)
    base.importar([_lectura("zotero", _a("Z1", hoja=9, rects=[[9, 0.1, 0.1, 0.5, 0.02]]))], aplicar=True)
    assert _contar(mundo.lectura_db, "anotaciones") == 2


def test_un_cambio_mas_nuevo_gana_y_uno_viejo_no(mundo):
    base.importar([_lectura("koreader", _a("k1", nota="primera", modificada="2026-03-01T10:00:00Z"))], aplicar=True)
    planes = base.importar([_lectura("koreader", _a("k1", nota="segunda", modificada="2026-03-02T10:00:00Z"))], aplicar=True)
    assert len(planes[0].cambios) == 1
    planes = base.importar([_lectura("koreader", _a("k1", nota="vieja", modificada="2026-01-01T10:00:00Z"))], aplicar=True)
    assert not planes[0].cambios
    with sqlite3.connect(mundo.lectura_db) as c:
        assert c.execute("select nota from anotaciones").fetchone()[0] == "segunda"


def test_lo_que_falta_en_un_libro_leido_entero_queda_ausente_y_luego_borrado(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    base.importar([_lectura("zotero", _a("Z1"))], aplicar=True)
    planes = base.importar([_lectura("koreader", alcance={"c1"})], aplicar=True)
    assert len(planes[0].ausentes) == 1 and not planes[0].borradas     # sigue viva en Zotero
    planes = base.importar([_lectura("zotero", alcance={"c1"})], aplicar=True)
    assert len(planes[0].borradas) == 1
    assert base.cambios_desde(0)["cambios"][-1]["operacion"] == "baja"
    # si vuelve a aparecer, revive
    planes = base.importar([_lectura("zotero", _a("Z1"))], aplicar=True)
    assert _contar(mundo.lectura_db, "anotaciones", "borrada is null") == 1


def test_un_libro_no_leido_no_marca_ausencias(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    planes = base.importar([_lectura("koreader", alcance={"c2"})], aplicar=True)
    assert not planes[0].ausentes


def test_lo_devuelto_por_yachay_con_el_uid_es_la_misma_anotacion(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    with sqlite3.connect(mundo.lectura_db) as c:
        uid = c.execute("select uid from anotaciones").fetchone()[0]
    otra = _a("501", texto="un literal recortado distinto", hoja=1, rects=[], uid_base=uid)
    planes = base.importar([base.Lectura("yachay", anotaciones=[otra], alcance=None)], aplicar=True)
    assert len(planes[0].uniones) == 1
    assert _contar(mundo.lectura_db, "presencias") == 2


def test_sesiones_y_progreso_se_actualizan_en_su_lugar(mundo):
    s = {"origen_id": "m:100", "md5": "m", "calibre_id": 1, "inicio": 100, "fin": 200, "segundos": 90, "paginas": 2}
    g = {"calibre_id": 1, "fraccion": 0.2, "segundos": 90}
    base.importar([base.Lectura("koreader", sesiones=[s], progreso=[g])], aplicar=True)
    planes = base.importar([base.Lectura("koreader", sesiones=[{**s, "fin": 400, "segundos": 250}], progreso=[{**g, "fraccion": 0.3}])],
                           aplicar=True)
    assert planes[0].sesiones == {"altas": 0, "cambios": 1} and planes[0].progreso == {"altas": 0, "cambios": 1}
    assert _contar(mundo.lectura_db, "sesiones") == 1


def test_lo_conocido_solo_por_md5_toma_su_libro(mundo):
    sin = _a("k1")
    sin["calibre_id"], sin["md5"] = None, "abc"
    base.importar([base.Lectura("koreader", anotaciones=[sin], alcance={"mabc"})], aplicar=True)
    base.importar([base.Lectura("koreader", libros={1: {"md5": "abc", "titulo": "Economia"}}, alcance=None)], aplicar=True)
    with sqlite3.connect(mundo.lectura_db) as c:
        assert c.execute("select calibre_id from anotaciones").fetchone()[0] == 1


def test_cursores_de_los_consumidores(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    assert base.leer_cursor("otro-studio") == 0
    base.guardar_cursor("otro-studio", base.cambios_desde(0)["hasta"])
    assert base.cambios_desde(base.leer_cursor("otro-studio"))["cambios"] == []
    base.guardar_cursor("yachay-entrada", "c:2026-11-17T10:00:00Z/88")
    assert base.leer_cursor("yachay-entrada") == "c:2026-11-17T10:00:00Z/88"


def test_aplicar_respalda_antes(mundo):
    base.importar([_lectura("koreader", _a("k1"))], aplicar=True)
    base.importar([_lectura("koreader", _a("k2", texto="otro pasaje"))], aplicar=True)
    respaldos = list((mundo.raiz / "respaldos" / "lectura").glob("lectura_*"))
    assert respaldos, "sin respaldo de la base antes de aplicar"


def test_la_base_no_se_abre_dentro_de_calibre_ni_de_zotero(mundo):
    with pytest.raises(base.RutaProhibida):
        base.conectar(mundo.calibre_db, escribir=True)
    with pytest.raises(base.RutaProhibida):
        base.conectar(mundo.zotero_db, escribir=True)
    with pytest.raises(base.RutaProhibida):
        base.conectar(mundo.biblioteca / "lectura.sqlite", escribir=True)


def test_texto_normal_y_parecido():
    assert tx.normal("Comuni-\ndades «andinas»,  Ñuñoa") == "comunidades andinas ñuñoa"
    assert tx.parecido(tx.normal("la productividad es casi todo"), tx.normal("La productividad es casi todo.")) == 1.0
    assert tx.parecido("preguntaquehabiamos", "pregunta que habiamos") >= 0.99
    assert tx.color("#80ffff00") == "#FFFF00" and tx.color("yellow") == "#E9C46A" and tx.nombre_de_color("#ffd400") == "yellow"
