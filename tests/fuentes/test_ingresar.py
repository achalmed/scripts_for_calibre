"""tests/fuentes/test_ingresar.py — ingresar obras por su DOI o ISBN (decisiones §9.10): la clave de Better BibTeX, el cotejo
con lo que ya existe y el plan. Sin bases reales: lo existente y el esquema de Zotero son de juguete; `aplicar` se ensaya
sobre copias de las bases (decisiones §9.10), no aquí.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ing():
    spec = importlib.util.spec_from_file_location("t_ingresar", REPO / "lib" / "ingresar.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["t_ingresar"] = m
    spec.loader.exec_module(m)
    return m


ESQUEMA = {"validos": {"journalArticle": {"title", "publicationTitle", "volume", "issue", "pages", "date", "DOI", "url", "language",
                                          "citationKey", "accessDate", "libraryCatalog", "extra", "ISSN"},
                       "book": {"title", "publisher", "place", "date", "ISBN", "edition", "url", "language", "citationKey",
                                "accessDate", "libraryCatalog", "extra"},
                       "report": {"title", "institution", "date", "url", "language", "citationKey", "extra", "accessDate", "libraryCatalog"},
                       "document": {"title", "publisher", "date", "url", "language", "citationKey", "extra", "accessDate", "libraryCatalog"}},
           "base": {("report", "publisher"): "institution"},
           "roles": {"journalArticle": {"author", "editor"}, "book": {"author", "editor"}, "report": {"author"}, "document": {"author"}}}

ROEDIGER = {"ref": "Roediger y Karpicke (2006)", "incluir": True, "tipo_zotero": "journalArticle",
            "autores": [{"apellido": "Roediger", "nombre": "Henry L., III"}, {"apellido": "Karpicke", "nombre": "Jeffrey D."}],
            "anio": 2006, "titulo": "Test-enhanced learning: Taking memory tests improves long-term retention",
            "revista": "Psychological Science", "volumen": "17", "numero": "3", "paginas": "249-255",
            "doi": "10.1111/j.1467-9280.2006.01693.x", "doi_cotejado": True, "idioma": "en", "pdf_oa": None,
            "materias": ["aprendizaje"]}
LUMLEY = {"ref": "Lumley (2010)", "tipo_zotero": "book", "autores": [{"apellido": "Lumley", "nombre": "Thomas"}], "anio": 2010,
          "titulo": "Complex surveys: A guide to analysis using R", "editorial": "Wiley", "isbn": "9780470284308",
          "doi": "10.1002/9780470580066", "idioma": "en", "pdf_oa": None}
ICMJE = {"ref": "ICMJE (2025)", "tipo_zotero": "report", "autores": [{"corporativo": "International Committee of Medical Journal Editors"}],
         "anio": 2025, "titulo": "Recommendations for the conduct, reporting, editing, and publication of scholarly work in medical journals",
         "editorial": "ICMJE", "url": "https://www.icmje.org/recommendations/", "idioma": "en",
         "pdf_oa": {"url": "https://www.icmje.org/icmje-recommendations.pdf", "sede": "ICMJE"}}


def test_la_clave_sigue_la_formula_del_ecosistema(ing):
    assert ing.clave_bbt(ROEDIGER["autores"], ROEDIGER["titulo"], 2006) == "roedigerTestenhancedLearningTaking2006"
    assert ing.clave_bbt(LUMLEY["autores"], LUMLEY["titulo"], 2010) == "lumleyComplexSurveysGuide2010"
    assert ing.clave_bbt(ICMJE["autores"], ICMJE["titulo"], 2025) == "internationalcommitteeofmedicaljournaleditorsRecommendationsConductReporting2025"
    # las de Zotero (contrastadas): «y», «de», «la» se saltan; «N.°» da «Ndeg»; la grafía de la institución, sin espacios
    assert ing.clave_bbt([{"apellido": "Ruiz"}], "Historia y Filosofía de las Matemáticas", 2017) == "ruizHistoriaFilosofiaMatematicas2017"
    assert ing.clave_bbt([{"corporativo": "Congreso de la República"}], "Ley N.° 31170. Algo", 2021) == "congresodelarepublicaLeyNdeg311702021"
    assert ing.unica("a2020", {"a2020", "a2020a"}) == "a2020b"


def _ex(ing):
    return {"cal": {7: {"titulo": "Complex surveys", "doi": "", "isbn": "9780470284308"}},
            "zot": {"lumleyComplexSurveysGuide2010": {"zotero_key": "LUML0001", "titulo": "Complex surveys", "doi": "", "isbn": ""}},
            "autor_cal": {7: "Thomas, Lumley"}, "rutas": {}, "claves": {"lumleyComplexSurveysGuide2010", "roedigerTestenhancedLearningTaking2006"}}


def test_el_plan_no_duplica_y_arma_cada_registro(ing):
    planes = ing.plan([ROEDIGER, LUMLEY, ICMJE, {"ref": "una web", "incluir": False, "motivo": "sin documento"}], _ex(ing), ESQUEMA,
                      "flujo-de-conocimiento", "Flujo de conocimiento", hoy="2026-11-18")
    r, l, i, w = planes
    assert r["accion"] == "nueva" and r["clave"] == "roedigerTestenhancedLearningTaking2006a", "la clave ya usada lleva su letra"
    assert r["calibre"]["authors"] == "Henry L. III, Roediger & Jeffrey D., Karpicke"
    assert r["calibre"]["identifiers"] == "doi:10.1111/j.1467-9280.2006.01693.x" and r["calibre"]["#item_type"] == "Journal Article"
    assert r["calibre"]["tags"] == "aprendizaje, flujo-de-conocimiento" and r["calibre"]["languages"] == "eng"
    z = r["zotero"]["campos"]
    assert z["publicationTitle"] == "Psychological Science" and z["citationKey"] == r["clave"] and z["libraryCatalog"] == "Crossref"
    assert [c["rol"] for c in r["zotero"]["creadores"]] == ["author", "author"]
    assert l["accion"] == "enlazar" and l["calibre_existente"] == 7 and l["clave"] == "lumleyComplexSurveysGuide2010", "ya existe: solo etiqueta y colección"
    assert i["accion"] == "nueva" and i["pdf"] and i["zotero"]["campos"]["institution"] == "ICMJE", "publisher → institution en un informe"
    assert i["zotero"]["creadores"][0]["modo"] == 1 and i["calibre"]["#clasificador"] == "Informe técnico"
    assert w["accion"] == "omitir"
    assert ing.resumen(planes) == {"nueva": 2, "enlazar": 1, "omitir": 1, "con_pdf": 1}


def test_lo_que_el_tipo_no_admite_va_a_extra(ing):
    campos = ing.campos_zotero({**LUMLEY, "url": ""}, "book", ESQUEMA, "k", "2026-11-18")
    assert campos["ISBN"] == "9780470284308" and campos["extra"] == "DOI: 10.1002/9780470580066"


def test_bajar_solo_acepta_un_pdf(ing, tmp_path, monkeypatch):
    class R:
        def __init__(self, datos): self.datos = datos
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n): return self.datos[:n]
    monkeypatch.setattr(ing.urllib.request, "urlopen", lambda req, timeout=90: R(b"<html>desafio</html>"))
    assert "no es un PDF" in ing.bajar("https://x/y.pdf", tmp_path / "a.pdf")["error"] and not (tmp_path / "a.pdf").exists()
    monkeypatch.setattr(ing.urllib.request, "urlopen", lambda req, timeout=90: R(b"%PDF-1.4 hola"))
    r = ing.bajar("https://x/y.pdf", tmp_path / "b.pdf")
    assert r["bytes"] == 13 and (tmp_path / "b.pdf").read_bytes().startswith(b"%PDF")


def test_el_pdf_tiene_que_ser_la_obra_citada(ing, tmp_path):
    from conftest import pdf_minimo
    def pdf(nombre, texto):
        p = tmp_path / nombre
        p.write_bytes(pdf_minimo(texto))
        return p
    titulo = "When should you adjust standard errors for clustering?"
    assert ing.es_la_obra(pdf("a.pdf", "When Should You Adjust Standard Errors for Clustering 2023"), titulo, "2023") == ""
    assert "otra version" in ing._normal(ing.es_la_obra(pdf("b.pdf", "arXiv 20 Sep 2022 When Should You Adjust Standard Errors for Clustering"), titulo, "2023"))
    assert ing.es_la_obra(pdf("c.pdf", "Data and Code Availability Standard About Journals"), "Data and code availability standard", "2022") == ""
    assert "titulo" in ing._normal(ing.es_la_obra(pdf("d.pdf", "Una obra cualquiera sobre otra cosa"), titulo, "2023"))
