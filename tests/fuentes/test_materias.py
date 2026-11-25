"""tests/fuentes/test_materias.py — de qué trata cada obra según los catálogos abiertos (decisiones §9.20).

Sin red: los catálogos son funciones falsas. La caché va a un XDG_STATE_HOME temporal y el índice es de juguete; nada
toca la biblioteca real ni ninguna base. Comprueba lo que se saca de cada catálogo, el filtro de los nombres de persona
que Open Library guarda como materia, la cola de pendientes, la vigencia, la migración del formato anterior y que una
caída de red no se guarda como «no está».
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def mat(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    spec = importlib.util.spec_from_file_location("t_materias", REPO / "lib" / "materias.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["t_materias"] = m
    spec.loader.exec_module(m)
    return m


OBRA_OA = {"id": "https://openalex.org/W1", "title": "The Science of Monetary Policy",
           "topics": [{"display_name": "Monetary Policy and Economic Impact", "score": 0.998,
                       "subfield": {"display_name": "General Economics"}, "field": {"display_name": "Economics"},
                       "domain": {"display_name": "Social Sciences"}},
                      {"display_name": "Casi nada", "score": 0.0002, "subfield": {}, "field": {}, "domain": {}}],
           "keywords": [{"display_name": "central banking", "score": 0.6}]}


def test_de_openalex_salen_los_topics_con_score_y_las_palabras_clave(mat):
    ms = mat.materias_openalex(OBRA_OA)
    assert [m["nombre"] for m in ms] == ["Monetary Policy and Economic Impact", "central banking"]
    assert ms[0]["tipo"] == "materia" and ms[0]["dominio"] == "Social Sciences"
    assert ms[1]["tipo"] == "palabra"                      # las palabras clave no cuentan como materia del tema


def test_de_open_library_salen_las_materias_de_la_obra_sin_los_autores(mat):
    """Open Library guarda «Hayek, Friedrich A. von, 1899-1992» como materia; «Economics, Mathematical» sí lo es."""
    paginas = {"https://openlibrary.org/isbn/9788420636061.json":
               {"key": "/books/OL1M", "title": "Camino de servidumbre", "subjects": ["Economic Policy"],
                "works": [{"key": "/works/OL1W"}]},
               "https://openlibrary.org/works/OL1W.json":
               {"key": "/works/OL1W", "subjects": ["Hayek, Friedrich A. von, 1899-1992", "Economics, Mathematical",
                                                   "Economic Policy", "Fascism"]}}
    d = mat.consultar_openlibrary("978-84-206-3606-1", pedir=lambda u, timeout=25: (200, paginas.get(u)))
    assert d["estado"] == "hallado" and d["ref"] == "/works/OL1W"
    assert [m["nombre"] for m in d["materias"]] == ["Economic Policy", "Economics, Mathematical", "Fascism"]


def test_los_encabezados_genericos_del_catalogo_no_son_materia(mat):
    """«filosofia» salía como «General · Fiction - General · Philosophy»: los dos primeros no dicen nada del tema."""
    assert mat.util("Philosophy") and mat.util("Economics, Mathematical")
    assert not mat.util("General") and not mat.util("Fiction - General") and not mat.util("Nonfiction")
    assert not mat.util("Hayek, Friedrich A. von, 1899-1992") and not mat.util("  ")
    assert not mat.util("Spanish: Adult Nonfiction") and mat.util("Spanish literature")
    # y lo ya guardado antes de afinar el filtro tampoco pasa, sin volver a consultar
    cache = {"libros": {"9": {"openlibrary": {"materias": [{"nombre": "General", "tipo": "materia"},
                                                           {"nombre": "Philosophy", "tipo": "materia"}]}}}}
    assert mat.por_libro(cache) == {9: ["Philosophy"]}


def test_una_obra_sin_materias_queda_como_no_hallada(mat):
    d = mat.consultar_openlibrary("9786071620859", pedir=lambda u, timeout=25: (200, {"title": "Hegel", "subjects": []}))
    assert d["estado"] == "no_hallado" and d["materias"] == []


def test_un_fallo_de_red_no_se_guarda_como_que_no_esta(mat):
    d = mat.consultar_openalex("10.1/x", pedir=lambda u, timeout=25: (0, None))
    assert d["estado"] == "error"
    d = mat.consultar_openalex("10.1/x", pedir=lambda u, timeout=25: (404, None))
    assert d["estado"] == "no_hallado"


def test_la_cola_toma_el_doi_de_openalex_y_el_isbn_de_open_library(mat):
    indice = {"libros": {"1": {"doi": "10.1/a", "isbn": "9780262025539"}, "2": {"isbn": "9788420636061"},
                         "3": {}, "4": {"doi": "10.1/b"}}}
    cola = mat.pendientes(indice, {"libros": {}})
    assert cola == [("1", "openalex", "10.1/a"), ("1", "openlibrary", "9780262025539"),
                    ("2", "openlibrary", "9788420636061"), ("4", "openalex", "10.1/b")]
    ayer = (date.today() - timedelta(days=1)).isoformat()
    viejo = (date.today() - timedelta(days=200)).isoformat()
    cache = {"libros": {"1": {"openalex": {"estado": "hallado", "fecha": ayer},
                              "openlibrary": {"estado": "hallado", "fecha": viejo}}}}
    assert ("1", "openalex", "10.1/a") not in mat.pendientes(indice, cache)       # vigente
    assert ("1", "openlibrary", "9780262025539") in mat.pendientes(indice, cache)  # caducó a los 180 días


def test_la_cache_del_formato_anterior_se_lee_sin_consultar_nada(mat):
    """La primera caché del día tenía una sola fuente por libro, sin nombrarla: se lee como OpenAlex."""
    ruta = mat.ruta_cache()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"libros": {"51": {"estado": "hallado", "fecha": "2026-11-24",
                                                  "materias": [{"nombre": "Monetary Policy", "tipo": "materia"}]}}}),
                    encoding="utf-8")
    c = mat.leer_cache()
    assert c["libros"]["51"]["openalex"]["estado"] == "hallado"
    assert mat.por_libro(c) == {51: ["Monetary Policy"]}


def test_por_libro_junta_las_dos_fuentes_sin_repetir(mat):
    cache = {"libros": {"7": {"openalex": {"materias": [{"nombre": "Fascism", "tipo": "materia"},
                                                        {"nombre": "central banking", "tipo": "palabra"}]},
                              "openlibrary": {"materias": [{"nombre": "Fascism", "tipo": "materia"},
                                                           {"nombre": "Economic Policy", "tipo": "materia"}]}}}}
    assert mat.por_libro(cache) == {7: ["Fascism", "Economic Policy"]}


OBRA_TIT = {"id": "https://openalex.org/W9", "title": "International Economics: Theory and Policy",
            "authorships": [{"author": {"display_name": "Paul R. Krugman"}},
                            {"author": {"display_name": "Maurice Obstfeld"}}],
            "topics": [{"display_name": "International Trade and Policy", "score": 0.9,
                        "subfield": {}, "field": {}, "domain": {}}], "keywords": []}


def test_la_via_por_titulo_exige_parecido_y_afloja_si_coincide_el_autor(mat):
    """El título manda; un apellido en común rebaja el listón, porque la traducción cambia el título."""
    assert mat.coincide("International Economics: Theory and Policy", [], OBRA_TIT) > 0.9
    # mismo libro en español y con su autor: pasa por el apellido aunque el título se parezca poco
    assert mat.coincide("Economía internacional: teoría y política", ["Krugman, Paul"], OBRA_TIT) == 0.0
    assert mat.coincide("International Economics: Theory", ["Krugman, Paul"], OBRA_TIT) > 0.0
    # otro libro con un título parecido pero de otro autor: no pasa
    assert mat.coincide("International Economics", ["Feenstra, Robert"], OBRA_TIT) == 0.0
    # un autor cuyo nombre no deja letras latinas no da apellido, y no por eso se cae (pasaba en la corrida real)
    raro = dict(OBRA_TIT, authorships=[{"author": {"display_name": "张三"}}, {"author": {}}])
    assert mat.coincide("International Economics: Theory and Policy", ["Krugman, Paul"], raro) > 0.9


def test_la_via_por_titulo_se_queda_con_el_mejor_candidato_o_con_ninguno(mat):
    otra = dict(OBRA_TIT, id="https://openalex.org/W8", title="Economía de la empresa", authorships=[], topics=[])
    pedir = lambda u, timeout=25: (200, {"results": [otra, OBRA_TIT]})          # noqa: E731
    d = mat.consultar_openalex_titulo("International Economics: Theory and Policy", [], pedir=pedir)
    assert d["estado"] == "hallado" and d["ref"].endswith("W9") and d["incierta"] is True
    assert [m["nombre"] for m in d["materias"]] == ["International Trade and Policy"]
    d = mat.consultar_openalex_titulo("Memoria anual 2019", [], pedir=lambda u, timeout=25: (200, {"results": [otra]}))
    assert d["estado"] == "no_hallado" and d["materias"] == []
    d = mat.consultar_openalex_titulo("Ley", [], pedir=lambda u, timeout=25: (200, {"results": [OBRA_TIT]}))
    assert d["estado"] == "no_hallado"                        # un título de dos palabras encuentra cualquier cosa


def test_la_via_incierta_es_el_ultimo_recurso(mat):
    """Solo para lo que no tiene identificador que consultar ni materias ya: no se gasta una consulta de más."""
    indice = {"libros": {"1": {"doi": "10.1/a", "titulo": "Con DOI"}, "2": {"titulo": "Sin nada, sin materias"},
                         "3": {"titulo": "Sin nada, pero ya tiene materias"}}}
    cache = {"libros": {"3": {"openlibrary": {"materias": [{"nombre": "Philosophy", "tipo": "materia"}]}}}}
    cola = mat.pendientes(indice, cache, fuentes=mat.FUENTES)
    assert ("2", "openalex_titulo", "Sin nada, sin materias") in cola
    assert not [x for x in cola if x[0] in ("1", "3") and x[1] == "openalex_titulo"]
    assert mat.EXACTAS == ("openalex", "openlibrary")         # `traer` sin --fuente no gasta la vía incierta
