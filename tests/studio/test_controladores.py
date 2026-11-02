"""tests/studio/test_controladores.py — los controladores de la ventana en proceso (sin QML), sobre la muestra: espacio
(vistas), libros (tabla, filtros, libro actual, el enlace de los complementos), etapas (las tablas de cada vista, el
elemento), puerta (impedimentos) y operaciones (la actual por vista, su entrada, la orden, simular de verdad una suite
que solo lee, aplicar el índice sobre la muestra, el plan y el registro). Nada toca la biblioteca real y ninguna prueba
aplica una suite que escriba en Calibre o en Zotero (las suites leen su configuración del repo real)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from conftest import requiere_binding

from biblioteca_app.servicios import operaciones as ops  # noqa: E402


def _esperar(app, tareas, segundos=120):
    inicio = time.monotonic()
    while tareas.activa and time.monotonic() - inicio < segundos:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()


@pytest.fixture
def piezas(app, entorno):
    from gui_comun.consola import Consola
    from gui_comun.tareas import Tareas
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.etapas import Etapas
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.controladores.operaciones import Operaciones
    from biblioteca_app.controladores.puerta import Puerta
    from biblioteca_app.servicios import datos
    env = datos.cargar_env()
    consola = Consola()
    tareas = Tareas(consola)
    espacio = Espacio(consola, Ajustes())
    puerta = Puerta(env, vigilar=False)
    libros = Libros(espacio, consola, env, ruta_indice=entorno.indice)
    etapas = Etapas(espacio, libros, env, consola, repo=entorno.repo)
    operaciones = Operaciones(espacio, puerta, consola, tareas, env, cache=entorno.raiz / "cache" / "studio")
    yield dict(env=env, consola=consola, tareas=tareas, espacio=espacio, puerta=puerta, libros=libros, etapas=etapas, operaciones=operaciones, muestra=entorno)
    _esperar(app, tareas, 10)


@requiere_binding
def test_espacio_y_vistas(piezas):
    e = piezas["espacio"]
    assert e.vista == "libros" and e.indiceVista == 0 and [v["nombre"] for v in e.vistas] == list(ops.NOMBRES_ETAPAS)
    e.fijarVista("fichas")
    assert e.vista == "fichas" and e.textoVista == "Fichas" and e.indiceVista == 4
    e.fijarVista("no-existe")
    assert e.vista == "fichas"
    e.fijarVistaPorIndice(0)
    assert e.vista == "libros"
    assert any(x["nombre"] == "ir.puerta" for x in e.entradas_paleta(""))


@requiere_binding
def test_libros_filtros_actual_y_enlace(piezas):
    l = piezas["libros"]
    assert l.total == 8 and l.hayIndice and l.modelo.filas == 8
    assert l.contadores["sin_zotero"] == 3 and l.resumen.startswith("8 libros")
    assert [f["nombre"] for f in l.filasNavegacion] == ["libros", "libros.sin_zotero", "libros.sin_clave", "libros.sin_ficha", "libros.sin_nota"]
    l.fijarFiltro("sin_zotero")
    assert l.modelo.filas == 3 and l.textoFiltro == "Sin Zotero"
    l.fijarFiltro("todos")
    assert not l.hayActual
    l.fijarFila(0)
    assert l.hayActual and l.id == "1" and l.clave == "quispeEconomiaCiudades2021" and l.zoteroKey == "QUISPE01" and l.nFichas == 1
    assert l.rutaArchivo.endswith(".pdf") and Path(l.rutaArchivo).is_file() and l.hayNota and not l.notaEnlazada
    assert l.fichasModelo.filas == 1 and l.fichasModelo.fila(0)["ficha"].startswith("catalogacion/fichas/1_")
    fila = l.filaDe("8")
    assert fila >= 0
    piezas["espacio"].fijarVista("fichas")
    recibido = []
    l.seleccionar.connect(recibido.append)
    assert l.abrirUrl("biblioteca-studio://libro/8") is True
    assert piezas["espacio"].vista == "libros" and l.id == "8" and recibido == [fila]
    assert l.abrirUrl("biblioteca-studio://libro/999") is False and l.id == "8"
    assert any(x["texto"].startswith("Libro: Finanzas") for x in l.entradas_paleta("finanzas"))
    assert l.entradas_paleta("") == []
    l.recargar()
    assert l.id == "8"


@requiere_binding
def test_etapas_tablas_y_elemento(piezas):
    t = piezas["etapas"]
    c = t.contadores
    assert c["adquirir"] == 3 and c["entrada"] == 4 and c["catalogar"] == 4 and c["fichas"] == 2 and c["puerta"] == 2 and c["tareas"] == 3
    assert c["manifiestos"] == ""                                    # perezosa: se lee al mostrarse
    piezas["espacio"].fijarVista("manifiestos")
    assert t.contadores["manifiestos"] == 1
    assert c["sincronizar"] == 3                                     # las comprobaciones con algo que atender
    assert [f["nombre"] for f in t.filasMetodo] == ["adquirir", "entrada", "catalogar", "fichas", "manifiestos"]
    m = t.modeloDe("entrada")
    assert m.filas == 5
    t.fijarFila("entrada", 0)
    assert t.hayElemento and t.vistaElemento == "entrada" and t.elementoTitulo.endswith(".pdf") and t.elementoRuta
    assert t.elementoSubtitulo.startswith("repo/entrada/") or t.elementoSubtitulo.startswith("/")
    assert {x["etiqueta"] for x in t.elementoCampos} >= {"Archivo", "Paso", "Ruta"}
    t.fijarFila("fichas", 0)
    assert t.elementoEsMarkdown and t.elementoTexto.startswith("---\ntipo: ficha_catalogacion")
    t.fijarFila("sincronizar", 0)
    assert t.elementoOperacion == "enlazar_zotero" and any(x["etiqueta"] == "Afectados" for x in t.elementoCampos)
    t.fijarFila("sincronizar", -1)
    assert not t.hayElemento
    assert t.modeloDe("puerta").filas == 2 and t.modeloDe("tareas").filas == 3
    t.recargar("entrada")
    assert t.modeloDe("entrada").filas == 5


@requiere_binding
def test_puerta_impedimentos(piezas, monkeypatch):
    p = piezas["puerta"]
    from biblioteca_app.servicios import puerta as svc
    assert p.impedimento("calibre,zotero") == "" and p.contexto == "Calibre y Zotero cerrados · candados libres"
    monkeypatch.setattr(svc, "abiertas", lambda: {"calibre"})
    p.refrescar()
    assert p.calibreAbierto and "Calibre está abierto" in p.impedimento("calibre") and p.impedimento("zotero") == ""
    assert p.estadoDe("calibre").startswith("Calibre abierto") and p.estadoDe("") == "no escribe en ninguna base"
    assert p.contexto.startswith("Calibre abierto · Zotero cerrado")


@requiere_binding
def test_operaciones_actual_entrada_y_orden(piezas):
    o, e = piezas["operaciones"], piezas["espacio"]
    assert o.actual == "indice" and o.escribe and o.verbo == "Simular" and o.indiceActual == 0
    assert [x["id"] for x in o.lista] == ["indice"]
    o.fijar("fichas_validar")
    assert e.vista == "fichas" and o.actual == "fichas_validar" and not o.escribe and o.verbo == "Ejecutar"
    assert o.entradaTipo == "carpeta" and o.valor == "catalogacion/fichas"
    assert o.ordenSimular.endswith("fichas/main.py validar catalogacion/fichas") and o.ordenAplicar == ""
    o.fijarValor(str(ops.REPO / "catalogacion" / "fichas"))
    assert o.valor == "catalogacion/fichas"                          # relativa al repo
    o.fijarValor("")
    assert not o.puedeSimular and "Falta" in o.motivoNoSimular
    o.fijarValor(str(piezas["muestra"].repo / "catalogacion" / "fichas"))
    assert o.puedeSimular
    o.fijarPorIndice(1)
    assert o.actual == "fichas_estado"
    e.fijarVista("puerta")
    assert not o.hayOperacion and o.lista == [] and "no tiene operaciones" in o.motivoNoSimular
    e.fijarVista("fichas")
    assert o.actual == "fichas_estado"                               # se recuerda por vista
    o.fijar("catalogar")
    assert o.bases == "calibre" and "Calibre" in o.basesTexto and "ingesta/main.sh catalogar --aplicar" in o.textoConfirmacion
    assert any(x["texto"] == "Operación: Catalogar en Calibre" for x in o.entradas_paleta(""))


@requiere_binding
def test_simular_corre_la_suite_y_deja_el_plan(piezas, app):
    """`fichas/main.py validar` sobre las fichas de la muestra: solo lee; la salida queda en la consola y en el plan."""
    o, tareas, consola = piezas["operaciones"], piezas["tareas"], piezas["consola"]
    o.fijar("fichas_validar")
    o.fijarValor(str(piezas["muestra"].repo / "catalogacion" / "fichas"))
    terminadas = []
    o.terminada.connect(lambda i, a, c: terminadas.append((i, a, c)))
    assert o.simular() is True and o.enCurso
    assert o.simular() is False                                      # una a la vez
    _esperar(app, tareas)
    assert terminadas and terminadas[0][0] == "fichas_validar" and terminadas[0][1] is False
    assert not o.enCurso and o.plan.startswith("# ") and "fichas/main.py validar" in o.plan and o.registro == ""
    assert any("fichas/main.py" in l for l in consola.salida.texto.splitlines())


@requiere_binding
def test_aplicar_el_indice_escribe_solo_el_json_de_la_muestra(piezas, app):
    o, tareas, libros, muestra = piezas["operaciones"], piezas["tareas"], piezas["libros"], piezas["muestra"]
    antes = muestra.indice.stat().st_mtime
    o.fijar("indice")
    assert o.puedeAplicar, o.motivoNoAplicar
    time.sleep(0.05)
    assert o.aplicar() is True
    _esperar(app, tareas)
    assert o.registro.startswith("# ") and "aplicado" in o.registro.splitlines()[0] and "8 libros" in o.registro
    assert muestra.indice.stat().st_mtime >= antes
    libros.recargar()
    assert libros.total == 8
    # ninguna prueba aplica una suite que escriba en una base: solo se comprueba que Aplicar exigiría la confirmación de QML
    o.fijar("catalogar")
    assert o.escribe and "ingesta/main.sh catalogar --aplicar" in o.textoConfirmacion
    assert o.puedeAplicar or o.motivoNoAplicar
