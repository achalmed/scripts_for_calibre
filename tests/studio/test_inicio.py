"""Las áreas nuevas del rediseño del 2026-11-18 (decisiones §9.9), en proceso y sobre la muestra: Fichas (las de los
escritos y las canónicas, sus filtros y el repaso Leitner, que escribe solo en la `REPASO_DB` de la muestra) e Inicio (las
cifras, «Seguir leyendo», «Siguiente paso» y a dónde lleva cada botón). Nada toca una base real."""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import requiere_binding


@pytest.fixture
def areas(app, entorno):
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichas import Fichas
    from biblioteca_app.controladores.inicio import Inicio
    from biblioteca_app.controladores.lectura import Lectura
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    consola = Consola()
    espacio = Espacio(consola, Ajustes())
    libros = Libros(espacio, consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    lectura = Lectura(libros, vigilar=False)
    fichas = Fichas(libros, consola, repo=entorno.repo, en_hilo=False)
    inicio = Inicio(espacio, libros, lectura, fichas)
    return dict(espacio=espacio, libros=libros, lectura=lectura, fichas=fichas, inicio=inicio, muestra=entorno)


@requiere_binding
def test_fichas_de_los_escritos_y_canonicas_con_sus_filtros(areas):
    fi = areas["fichas"]
    assert fi.leidas and not fi.cargando
    cuentas = {f["clave"]: f["n"] for f in fi.filtros}
    assert cuentas == {"todas": 5, "textual": 1, "parafrasis": 1, "obra": 0, "revisar": 2, "ia": 0} and fi.porRevisar == 2
    textual = next(f for f in fi.lista if f["tipo"] == "textual")
    assert textual["cita"].startswith("La escala importa") and textual["cotejo"] == "cotejada con el PDF"
    assert textual["obra"] == "Economía de las ciudades pequeñas" and "p. 12" in textual["detalle"]
    assert textual["insertar"].startswith("“La escala") and "\\parencite[p.~12]{quispeEconomiaCiudades2021}" in textual["insertar"]
    assert textual["principal"].endswith("informe.tex")
    parafrasis = next(f for f in fi.lista if f["tipo"] == "parafrasis")
    assert parafrasis["cita"].startswith("El empleo de una ciudad") and parafrasis["porRevisar"]   # de una paráfrasis, la paráfrasis
    fi.fijarFiltro("revisar")
    assert {f["tipo"] for f in fi.lista} == {"parafrasis", "catalogacion"}
    fi.fijarFiltro("todas")
    fi.buscar("escala")
    assert [f["tipo"] for f in fi.lista] == ["textual"]
    fi.buscar("")
    fi.elegir(textual["clave"])
    assert fi.actual == textual["clave"] and areas["libros"].id == textual["calibreId"]   # «Nueva ficha» va sobre su libro


@requiere_binding
def test_el_repaso_leitner_sube_y_escribe_solo_en_la_base_de_la_muestra(areas):
    fi = areas["fichas"]
    db = Path(areas["muestra"].entorno["REPASO_DB"])
    assert fi.paraHoy == 1 and fi.resumenRepaso == "1 por repasar hoy · próximas en 2 días"
    t = fi.tarjeta
    assert t["hay"] and t["pregunta"] == "Argumento: ¿qué sostiene la obra en esta página?" and t["caja"] == 1 and t["nueva"]
    assert t["obra"] == "Economía de las ciudades pequeñas, p. 13" and t["cita"].startswith("El empleo")
    assert not fi.mostrada
    fi.mostrar()
    assert fi.mostrada
    import sqlite3
    antes = sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute("select clave, caja from tarjetas").fetchall()
    fi.responder(True)                                                       # «La sabía»: a la caja 2, simulado
    assert fi.paraHoy == 0 and not fi.tarjeta["hay"] and not fi.mostrada
    assert fi.sinGuardar == 1 and fi.resumenSinGuardar == "1 respuesta sin guardar: 1 sube de caja"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        assert c.execute("select clave, caja from tarjetas").fetchall() == antes, "simular no escribe"
    fi.descartarRepaso()                                                     # descartar: la ficha vuelve a la cola
    assert fi.sinGuardar == 0 and fi.paraHoy == 1
    fi.mostrar()
    fi.responder(True)
    fi.guardarRepaso()                                                       # ahora sí se escribe
    assert fi.sinGuardar == 0 and fi.paraHoy == 0
    assert fi.resumenRepaso == "0 por repasar hoy · próximas en 2 días"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
        cajas = dict(c.execute("select clave, caja from tarjetas"))
    assert sorted(cajas.values()) == [2, 2] and all(k.startswith("reports/2026-11-17-informe-de-muestra/") for k in cajas)


@requiere_binding
def test_inicio_cifras_seguir_leyendo_y_siguiente_paso(areas):
    ini, libros = areas["inicio"], areas["libros"]
    cifras = {c["rotulo"]: c["valor"] for c in ini.cifras}
    assert list(cifras) == ["Leído esta semana", "Subrayados nuevos", "Fichas por revisar", "Pendientes"]
    assert cifras["Subrayados nuevos"] == "2" and cifras["Fichas por revisar"] == "2"
    c = libros.contadores
    assert cifras["Pendientes"] == str(c["clasificar"] + c["fichas"] + c["sin_clave"] + c["sin_zotero"])
    seguir = ini.seguir
    assert len(seguir) == 1 and seguir[0]["titulo"] == "Economía de las ciudades pequeñas"   # el otro está terminado
    assert seguir[0]["texto"] == "42 % · en KOReader" and seguir[0]["color"] == "#378ADD" and seguir[0]["fraccion"] == 0.42
    pasos = ini.pasos
    assert [p["accion"] for p in pasos] == ["ficha", "repaso", "latex", "bandeja"]
    assert pasos[0]["texto"] == "Fichar 1 subrayado de «Economía de las ciudades pequeñas»"         # los otros ya tienen ficha
    assert pasos[0]["datos"]["texto"].startswith("Las ciudades pequeñas crecen")
    assert pasos[1]["texto"] == "Repaso: 1 ficha para hoy"
    assert pasos[2]["texto"] == "Fuentes nuevas en «Informe de muestra sobre ciudades»" and pasos[2]["datos"]["principal"].endswith("informe.tex")
    assert pasos[3]["texto"] == "1 libro sin clave para citar" and pasos[3]["datos"]["bandeja"] == "sin_clave"
    assert ini.fecha.split()[1].isdigit()


@requiere_binding
def test_inicio_lleva_a_cada_lugar(areas):
    ini, espacio, libros, fichas = areas["inicio"], areas["espacio"], areas["libros"], areas["fichas"]
    ini.ir("bandeja", {"bandeja": "sin_clave"})
    assert espacio.area == "bandejas" and libros.bandeja == "sin_clave"
    ini.ir("repaso", {})
    assert espacio.area == "fichas" and fichas.modo == "repaso"
    ini.ir("revisar", {})
    assert fichas.modo == "lista" and fichas.filtro == "revisar"
    ini.ir("area", {"area": "lectura"})
    assert espacio.area == "lectura"
    ini.ir("libro", {"id": "2"})
    assert espacio.area == "catalogo" and libros.id == "2"


@requiere_binding
def test_inicio_sin_base_de_lectura_no_inventa(app, entorno, monkeypatch, tmp_path):
    monkeypatch.setenv("LECTURA_DB", str(tmp_path / "no-existe" / "lectura.sqlite"))
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichas import Fichas
    from biblioteca_app.controladores.inicio import Inicio
    from biblioteca_app.controladores.lectura import Lectura
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    consola = Consola()
    espacio = Espacio(consola, Ajustes())
    libros = Libros(espacio, consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    lectura = Lectura(libros, vigilar=False)
    ini = Inicio(espacio, libros, lectura, Fichas(libros, consola, repo=entorno.repo, en_hilo=False))
    assert [c["rotulo"] for c in ini.cifras] == ["Fichas por revisar", "Pendientes"]       # sin horas ni subrayados
    assert ini.seguir == [] and all(p["accion"] != "ficha" for p in ini.pasos)
    assert not (tmp_path / "no-existe").exists()


def test_la_pregunta_del_repaso_es_una_pista_de_recuperacion():
    """Una pregunta que se responde sin mirar (Roediger y Karpicke, 2006), no un rótulo (§9.9)."""
    from biblioteca_app.controladores.fichas import pregunta_de
    assert pregunta_de({"tema": "escala urbana", "tipoTexto": "Paráfrasis"}) == "¿Qué sostiene la obra sobre «escala urbana»?"
    assert pregunta_de({"tema": "escala urbana", "tipoTexto": "Textual"}) == "¿Qué dice la obra, con sus palabras, sobre «escala urbana»?"
    assert pregunta_de({"tema": "", "categoria": "Idea principal"}) == "Idea principal: ¿qué sostiene la obra en esta página?"
