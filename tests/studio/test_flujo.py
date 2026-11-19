"""El flujo de producción de conocimiento en la ventana (decisiones §9.10), en proceso y sobre la muestra: el área Revisión
(el tipo, la bitácora, el cribado y el diagrama PRISMA, escritos en el informe de muestra), el origen de las fichas con
«Cotejé la página» y la tarjeta «Referencias» de Coherencia. Nada toca un escrito ni una base reales."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from conftest import requiere_binding


@pytest.fixture
def piezas(app, entorno):
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichas import Fichas
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.controladores.revision import Revision
    from biblioteca_app.servicios import datos
    consola = Consola()
    espacio = Espacio(consola, Ajustes())
    libros = Libros(espacio, consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    fichas = Fichas(libros, consola, repo=entorno.repo, en_hilo=False)
    revision = Revision(fichas, consola, en_hilo=False)
    return dict(espacio=espacio, libros=libros, fichas=fichas, revision=revision, muestra=entorno)


def _informe(piezas) -> Path:
    return next(Path(e["carpeta"]) for e in piezas["fichas"].escritos() if e["proyecto"].startswith("reports/"))


@requiere_binding
def test_la_revision_de_un_escrito_desde_la_ventana(piezas):
    rv = piezas["revision"]
    informe = _informe(piezas)
    rv.elegir(str(informe))
    assert rv.escrito == str(informe) and rv.tituloEscrito.startswith("Informe de muestra")
    assert not rv.datos["existe"] and rv.datos["requisitos"] == [], "sin tipo, nada exige"
    assert [t["clave"] for t in rv.tipos] == ["narrativa", "alcance", "sistematica", "metaanalisis", "rapida", "paraguas"]
    rv.declarar("sistematica", "¿Qué explica la pobreza?", "Perú\n- 2015-2025", "Sin datos")
    r = rv.datos["revision"]
    assert r["tipo"] == "sistematica" and r["criterios"]["inclusion"] == ["Perú", "2015-2025"]
    assert not (informe / "fuentes" / "revision.yml").is_file(), "el botón simula: nada escrito todavía"
    assert rv.pendientes == 1 and rv.resumenPendientes == "1 cambio sin aplicar: tipo" and "+tipo: sistematica" in rv.diferencia
    rv.elegir(str(informe.parent))                                  # con cambios sin aplicar no se cambia de escrito
    assert rv.escrito == str(informe)
    rv.aplicar()
    assert (informe / "fuentes" / "revision.yml").is_file() and rv.pendientes == 0 and rv.diferencia == ""
    assert rv.datos["porque"]["tipo"]["fuente"] == "Grant y Booth (2009); Snyder (2019)"
    rv.anadirBusqueda({"base": "Scopus", "clase": "base", "cadena": "pobreza AND empleo", "filtros": "2015-2025", "fecha": "2026-11-18",
                       "resultados": 2})
    ris = informe.parent / "exportacion.ris"
    ris.write_text("TY  - JOUR\nTI  - Pobreza y empleo\nPY  - 2020\nER  - \nTY  - JOUR\nTI  - Turismo\nPY  - 2019\nER  - \n", encoding="utf-8")
    rv.importar("b1", "file://" + str(ris))
    assert [f["n"] for f in rv.fases] == [2, 0, 0, 0, 0] and len(rv.registros) == 2
    rv.cribar("r0002", 1, "excluir", "otro tema")
    rv.cribar("r0001", 1, "incluir", "")
    rv.fijarFase("fase2")
    assert [x["id"] for x in rv.registros] == ["r0001"]
    rv.cribar("r0001", 2, "incluir", "")
    assert rv.pendientes == 5 and rv.resumenPendientes == "5 cambios sin aplicar: búsqueda, importar, cribado"
    assert rv.datos["cuentas"]["incluidos"] == 1 and rv.datos["cuentas"]["cuadra"]
    rv.generarPrisma()                                              # el diagrama sale del archivo: pide aplicar antes
    assert not (informe / "fuentes" / "prisma.pdf").is_file()
    rv.aplicar()
    import biblioteca_app.controladores.revision as mod
    assert mod._lib("revision").leer(informe)[0]["registros"][0]["fase2"] == "incluido"
    req = {x["clave"]: x["cumple"] for x in rv.datos["requisitos"]}
    assert req == {"pregunta": True, "criterios": True, "bitacora": True, "cribado": True, "prisma": True}
    if shutil.which("lualatex"):
        rv.generarPrisma()
        assert (informe / "fuentes" / "prisma.pdf").is_file() and rv.datos["prisma"]["al_dia"] is True
        assert not shutil.which("pdftoppm") or rv.vistaPrevia.endswith(".png")


@requiere_binding
def test_otra_mano_cambio_la_bitacora_y_no_se_pisa(piezas):
    rv = piezas["revision"]
    informe = _informe(piezas)
    rv.elegir(str(informe))
    rv.declarar("narrativa", "", "", "")
    rv.aplicar()
    avisos = []
    rv.aviso.connect(lambda texto, tipo: avisos.append((texto, tipo)))
    import biblioteca_app.controladores.revision as mod
    m = mod._lib("revision")
    leer = m.leer
    m.leer = lambda e: (leer(e)[0], "huella-de-otro-momento")      # alguien escribió entre la lectura y la escritura
    try:
        rv.anadirBusqueda({"base": "SciELO", "cadena": "x", "resultados": 1})
    finally:
        m.leer = leer
    assert avisos and avisos[-1][1] == "aviso" and "cambió fuera" in avisos[-1][0]
    assert rv.datos["revision"]["busquedas"] == [] and rv.pendientes == 0
    # y si otra mano escribe entre la simulación y «Aplicar», tampoco se pisa
    rv.anadirBusqueda({"base": "SciELO", "cadena": "y", "resultados": 1})
    assert rv.pendientes == 1
    (informe / "fuentes" / "revision.yml").write_text((informe / "fuentes" / "revision.yml").read_text(encoding="utf-8") + "# otra mano\n",
                                                       encoding="utf-8")
    rv.aplicar()
    assert "cambió fuera" in avisos[-1][0] and rv.pendientes == 0 and rv.datos["revision"]["busquedas"] == []


@requiere_binding
def test_la_ficha_de_la_ia_se_coteja_antes_de_citarla(piezas):
    fi = piezas["fichas"]
    informe = _informe(piezas)
    from biblioteca_app.controladores.fichado import _consulta
    fichar = _consulta()._fichar()
    import yaml
    f = (yaml.safe_load((informe / "fuentes" / "fuentes.yml").read_text(encoding="utf-8")) or {})["fuentes"][0]
    entrada = {"clave": f["clave_bibtex"], "calibre_id": f["calibre_id"], "zotero_key": f.get("zotero_key") or ""}
    previo = fichar._verificar
    fichar._verificar = lambda meta, _c, _r: {"estado": "verificada_script", "metodo": "texto", "fecha": "2026-11-18", "detalle": "", "pagina_pdf": None}
    registrar = fichar.registrar_ia
    fichar.registrar_ia = lambda *a, **k: {"registro": "ia/registro.yml", "total": 1}
    try:
        fichar.guardar(informe, {"tipo": "textual", "pagina": "14", "categoria": "Hallazgo", "origen": {"autor": "llm"},
                                 "secciones": {"Cita exacta": "Las ciudades pequeñas crecen cuando se integran a su región."}}, entrada, aplicar=True)
    finally:
        fichar._verificar, fichar.registrar_ia = previo, registrar
    fi.recargar()
    assert {x["clave"]: x["n"] for x in fi.filtros}["ia"] == 1
    fi.fijarFiltro("ia")
    ia = fi.lista[0]
    assert ia["deIa"] and ia["porCotejar"] and not ia["citable"] and ia["insertar"] == "" and "propuesta por la IA" in ia["detalle"]
    assert ia["porRevisar"], "la de la IA sin cotejar está por revisar"
    assert "COPE (2023)" in fi.porqueOrigen
    fi.cotejar(ia["clave"])
    ia = next(x for x in fi.lista if x["clave"] == ia["clave"])
    assert ia["citable"] and not ia["porCotejar"] and ia["insertar"].startswith("“Las ciudades")


@requiere_binding
def test_la_tarjeta_de_referencias_de_coherencia(piezas):
    from biblioteca_app.controladores.etapas import Etapas
    from biblioteca_app.servicios import datos
    etapas = Etapas(piezas["espacio"], piezas["libros"], datos.cargar_env(), piezas["fichas"].consola, repo=piezas["muestra"].repo)
    ref = etapas.tarjetasCoherencia[3]
    assert ref["titulo"] == "Referencias" and ref["operacion"] == "verificar_ids" and ref["vista"] == "sincronizar"
