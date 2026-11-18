"""tests/fuentes/test_verificar_ids.py — «referencia que no existe» (FLUJO_DE_CONOCIMIENTO C12.5; decisiones §9.10).

Sin red: las agencias son una función falsa (`pedir`). Las bases son de juguete en un temporal (las reales nunca se abren
aquí) y la caché va a un XDG_STATE_HOME temporal. Comprueba los identificadores, la caché y su vigencia, el título que
discrepa, un escrito y que el índice publica los campos nuevos sin tocar los de antes.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import types
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def vi(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    return _cargar("t_verificar_ids", REPO / "lib" / "verificar_ids.py")


def agencias(registro=None):
    """Crossref conoce un DOI; doi.org, otro (de DataCite); Open Library, un ISBN."""
    def pedir(url, timeout=20):
        if registro is not None:
            registro.append(url)
        if "crossref.org/works/10.1111/j.1467-9280.2006.01693.x" in url:
            return 200, {"message": {"title": ["Test-enhanced learning: Taking memory tests improves long-term retention"],
                                     "issued": {"date-parts": [[2006]]}}}
        if "crossref.org" in url:
            return 404, None
        if "doi.org/api/handles/10.5281/zenodo.7436134" in url:
            return 200, {"responseCode": 1}
        if "doi.org/api/handles" in url:
            return 404, {"responseCode": 100}
        if "openlibrary.org/isbn/9780470284308" in url:
            return 200, {"title": "Complex surveys", "subtitle": "a guide to analysis using R", "publish_date": "2010"}
        if "openlibrary.org" in url:
            return 404, None
        return 0, None
    return pedir


def test_los_identificadores_se_normalizan(vi):
    assert vi.normalizar_doi("https://doi.org/10.1111/J.1467-9280.2006.01693.X") == "10.1111/j.1467-9280.2006.01693.x"
    assert vi.normalizar_doi("doi: 10.1037/0033-2909.132.3.354.") == "10.1037/0033-2909.132.3.354"
    assert vi.normalizar_doi("no es un doi") == ""
    assert vi.normalizar_isbn("0-470-28430-7") == ("9780470284308", True)
    assert vi.normalizar_isbn("0-470-28430-X")[1] is False
    assert vi.normalizar_isbn("978-0-470-28430-8") == ("9780470284308", True)
    assert vi.normalizar_isbn("9780470284309")[1] is False, "dígito de control malo"


def test_crossref_doi_org_y_open_library(vi):
    p = agencias()
    assert vi.consultar_doi("10.1111/j.1467-9280.2006.01693.x", p)["estado"] == "existe"
    datacite = vi.consultar_doi("10.5281/zenodo.7436134", p)
    assert datacite["estado"] == "existe" and "doi.org" in datacite["fuente"], "un DOI de DataCite existe aunque Crossref no lo tenga"
    assert vi.consultar_doi("10.9999/inventado.2024", p)["estado"] == "no_existe"
    assert vi.consultar_isbn("9780470284308", p)["titulo"].startswith("Complex surveys")
    assert vi.consultar_isbn("9786120000000", p)["estado"] == "no_hallado", "que Open Library no lo tenga no prueba que no exista"
    assert vi.consultar_doi("10.1111/x", lambda u, timeout=20: (0, None))["estado"] == "error", "sin red no se declara inexistente"


def test_la_cache_evita_volver_a_preguntar_y_vence(vi):
    urls = []
    cache = {}
    lista = [{"doi": "10.1111/j.1467-9280.2006.01693.x", "isbn": "9780470284308", "titulo": "x"},
             {"doi": "", "isbn": "9780470284309", "titulo": "mal"}]
    por = vi.pendientes(lista, cache)
    assert por == [("doi", "10.1111/j.1467-9280.2006.01693.x"), ("isbn", "9780470284308")], "el ISBN mal formado no se consulta"
    vi.consultar(por, cache, pausa=0, pedir=agencias(urls))
    vi.guardar_cache(cache)
    assert vi.pendientes(lista, vi.leer_cache()) == [], "lo de la caché no se vuelve a pedir"
    viejo = {k: {**e, "fecha": (date.today() - timedelta(days=200)).isoformat()} for k, e in cache.items()}
    assert len(vi.pendientes(lista, viejo)) == 2, "a los 180 días se vuelve a mirar"
    errores = {}
    vi.consultar([("doi", "10.1/x")], errores, pausa=0, pedir=lambda u, timeout=20: (0, None))
    assert errores == {}, "un error de red no se guarda"


def test_un_doi_real_de_otra_obra_discrepa(vi):
    cache = {}
    vi.consultar([("doi", "10.1111/j.1467-9280.2006.01693.x")], cache, pausa=0, pedir=agencias())
    bien = vi.campos("10.1111/j.1467-9280.2006.01693.x", "", "Test-enhanced learning", cache)
    assert bien["doi_verificado"] is True and bien["verificacion_ids"]["doi"] == "existe"
    mal = vi.campos("10.1111/j.1467-9280.2006.01693.x", "", "La economía de las ciudades pequeñas del Perú", cache)
    assert mal["doi_verificado"] is False and mal["verificacion_ids"]["doi"] == "discrepa"
    assert vi.campos("", "", "x", cache)["doi_verificado"] is None


# ------------------------------------------------------------------ bases de juguete
def _calibre(ruta: Path):
    c = sqlite3.connect(ruta)
    c.executescript("""
        create table books (id integer primary key, title text, path text);
        create table authors (id integer primary key, name text);
        create table books_authors_link (id integer primary key, book integer, author integer);
        create table data (id integer primary key, book integer, format text, name text);
        create table identifiers (id integer primary key, book integer, type text, val text);
        create table custom_columns (id integer primary key, label text);
        insert into books values (1, 'Test-enhanced learning', 'Roediger/Test (1)'), (2, 'Complex surveys', 'Lumley/Complex (2)'),
                                 (3, 'Inventado', 'Nadie/Inventado (3)');
        insert into identifiers (book, type, val) values (1, 'doi', '10.1111/j.1467-9280.2006.01693.x'),
                                 (2, 'isbn', '9780470284308'), (3, 'doi', '10.9999/inventado.2024');
    """)
    c.commit()
    c.close()


def _zotero(ruta: Path):
    c = sqlite3.connect(ruta)
    c.executescript("""
        create table items (itemID integer primary key, key text, itemTypeID integer);
        create table fields (fieldID integer primary key, fieldName text);
        create table itemDataValues (valueID integer primary key, value text);
        create table itemData (itemID integer, fieldID integer, valueID integer);
        create table itemAttachments (itemID integer, parentItemID integer, path text);
        insert into fields values (1, 'citationKey'), (2, 'title'), (3, 'DOI'), (4, 'ISBN'), (5, 'extra');
        insert into items values (10, 'ROED0001', 1), (11, 'LUML0001', 2), (12, 'SOLO0001', 1);
        insert into itemDataValues values (1, 'roedigerTestenhancedLearningTaking2006'), (2, 'Test-enhanced learning'),
            (3, '10.1111/j.1467-9280.2006.01693.x'), (4, 'lumleyComplexSurveysGuide2010'), (5, 'Complex surveys'),
            (6, '978-0-470-28430-8'), (7, 'soloEnZotero2020'), (8, 'Solo en Zotero'), (9, 'DOI: 10.9999/inventado.2024');
        insert into itemData values (10,1,1),(10,2,2),(10,3,3),(11,1,4),(11,2,5),(11,4,6),(12,1,7),(12,2,8),(12,5,9);
        insert into itemAttachments values (100, 10, 'attachments:Roediger/Test (1)/test.pdf'),
                                           (101, 11, 'attachments:Lumley/Complex (2)/c.pdf');
    """)
    c.commit()
    c.close()


def test_el_indice_publica_doi_verificado_sin_romper_lo_de_antes(vi, tmp_path, monkeypatch):
    _calibre(tmp_path / "metadata.db")
    _zotero(tmp_path / "zotero.sqlite")
    cache = {}
    vi.consultar([("doi", "10.1111/j.1467-9280.2006.01693.x"), ("isbn", "9780470284308"), ("doi", "10.9999/inventado.2024")],
                 cache, pausa=0, pedir=agencias())
    vi.guardar_cache(cache)
    env = types.SimpleNamespace(CALIBRE_DB=tmp_path / "metadata.db", ZOTERO_DB=tmp_path / "zotero.sqlite",
                                BIBLIOTECA_DIR=tmp_path, DOCS_ROOT=tmp_path)
    indice = _cargar("t_indice", REPO / "lib" / "indice.py")
    d = indice.construir(env)
    l1, l2, l3 = d["libros"]["1"], d["libros"]["2"], d["libros"]["3"]
    # lo de antes, igual (lo que leen los complementos y el control de escritura)
    assert d["esquema"] == 1 and l1["clave"] == "roedigerTestenhancedLearningTaking2006" and l1["zotero_key"] == "ROED0001"
    assert {"titulo", "autores", "carpeta", "formatos", "zotero_key", "clave", "apuntes", "fichas", "nota"} <= set(l1)
    # lo nuevo
    assert l1["doi_verificado"] is True and l2["isbn_verificado"] is True and l2["isbn"] == "9780470284308"
    assert l3["doi_verificado"] is False and l3["verificacion_ids"]["doi"] == "no_existe"
    r = d["referencias"]
    assert r["roedigerTestenhancedLearningTaking2006"]["calibre_id"] == 1
    assert r["soloEnZotero2020"]["calibre_id"] is None and r["soloEnZotero2020"]["doi"] == "10.9999/inventado.2024", "el DOI de Extra"
    assert r["soloEnZotero2020"]["doi_verificado"] is False
    json.dumps(d)                                   # se serializa entero


def test_un_escrito_dice_que_clave_falla(vi, tmp_path):
    _zotero(tmp_path / "zotero.sqlite")
    e = tmp_path / "escrito"
    e.mkdir()
    (e / "references.bib").write_text("@article{roedigerTestenhancedLearningTaking2006,\n title={x}\n}\n"
                                      "@misc{soloEnZotero2020,\n title={y}\n}\n@book{fantasma2023,\n title={z}\n}\n", encoding="utf-8")
    cache = {}
    vi.consultar([("doi", "10.1111/j.1467-9280.2006.01693.x"), ("doi", "10.9999/inventado.2024")], cache, pausa=0, pedir=agencias())
    filas = {f["clave"]: f for f in vi.revisar_escrito(e, cache, vi.de_zotero(tmp_path / "zotero.sqlite"))}
    assert filas["roedigerTestenhancedLearningTaking2006"]["estado"] == "verificada"
    assert filas["soloEnZotero2020"]["estado"] == "falla" and "no existe" in filas["soloEnZotero2020"]["detalle"]
    assert filas["fantasma2023"]["estado"] == "fuera_de_zotero"


def test_simular_no_consulta(vi, monkeypatch, capsys):
    monkeypatch.setattr(vi, "obras", lambda **k: [{"doi": "10.1/a", "isbn": "", "titulo": "a"}])
    monkeypatch.setattr(vi, "_pedir", lambda *a, **k: pytest.fail("simular no consulta la red"))
    assert vi.main(["verificar"]) == 0
    assert "[simulación] consultaría 1" in capsys.readouterr().out
    assert not vi.ruta_cache().exists()


def test_una_errata_de_la_agencia_no_es_otra_obra(vi):
    assert vi.mismo_titulo("La genealogía de la moral", "Genealgía de la Moral (Spanish Edition)") is True
    assert vi.mismo_titulo("Historia y filosofía de las matemáticas", "El café de las cuatro") is False
    assert vi.mismo_titulo("", "x") is None
    assert vi.mismo_titulo("Economical writing: Thirty-five rules for clear and persuasive prose", "Economical Writing, Third Edition") is True
