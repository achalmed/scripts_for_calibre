"""tests/fuentes/test_importar_zotero.py — fusionar e importar a Zotero (decisiones §2.15): los lectores de RIS, BibTeX y
CSL-JSON, la fusión sin duplicados, el cotejo con lo que ya está y la fecha como la guarda Zotero. Sin bases: Calibre y
Zotero son de juguete. El `--aplicar` se ensaya sobre copias de las bases en tests/calibre/test_importar_zotero.py.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def iz():
    spec = importlib.util.spec_from_file_location("t_importar_zotero", REPO / "lib" / "importar_zotero.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["t_importar_zotero"] = m
    spec.loader.exec_module(m)
    return m


RIS = """TY  - STAT
T1  - Decreto Legislativo N.° 1621. Decreto Legislativo que regula un retorno gradual
AU  - Ministerio de Economía y Finanzas
DA  - 2024/01/01
M1  - 1621
ST  - Decreto Legislativo N.° 1621
PB  - Diario Oficial El Peruano
KW  - norma
KW  - politica_fiscal
DB  - Calibre
L1  - /biblioteca/Ministerio/Decreto (11005)/Decreto.pdf
ID  - calibre:11005
ER  -

TY  - JOUR
T1  - Test-enhanced learning: Taking memory tests improves long-term retention
AU  - Roediger, Henry L.
AU  - Karpicke, Jeffrey D.
DA  - 2006
PB  - Psychological Science
DO  - https://doi.org/10.1111/j.1467-9280.2006.01693.x
KW  - aprendizaje
DB  - Calibre
L1  - /biblioteca/Henry L., Roediger/Test-enhanced learning (48)/Test.pdf
ID  - calibre:48
ER  -
"""

BIB = r"""@article{roedigerTestenhancedLearningTaking2006,
  title = {Test-Enhanced Learning: {{Taking}} Memory Tests Improves Long-Term Retention},
  author = {Roediger, Henry L. and Karpicke, Jeffrey D.},
  journal = {Psychological Science},
  year = 2006, volume = {17}, number = {3}, pages = {249--255},
  doi = {10.1111/j.1467-9280.2006.01693.x},
  keywords = {memoria, recuperación}
}
@comment{nada}
@book{lumley2010,
  title = "Complex Surveys: A Guide to Analysis Using {R}",
  author = {Lumley, Thomas},
  publisher = {Wiley}, address = {Hoboken}, year = {2010}, isbn = {978-0-470-28430-8}
}
@techreport{inei2024,
  title = {Ficha t{\'e}cnica de la {ENAHO}},
  author = {{Instituto Nacional de Estad\'istica e Inform\'atica}},
  institution = {INEI}, number = {12}, year = {2024}
}
"""

CSL = """[{"id": "page2021", "type": "article-journal", "title": "The PRISMA 2020 statement",
  "author": [{"family": "Page", "given": "Matthew J."}, {"literal": "PRISMA Group"}],
  "issued": {"date-parts": [[2021, 3, 29]]}, "container-title": "BMJ", "DOI": "10.1136/bmj.n71", "volume": "372"}]"""


def test_lee_ris_de_calibre(iz):
    norma, art = iz.leer_ris(RIS, "a.ris")
    assert norma["tipo"] == "statute" and norma["numero_doc"] == "1621" and norma["calibre_id"] == 11005
    assert norma["fecha"] == "2024", "el 1 de enero de Calibre es un año, no una fecha"
    assert norma["autores"] == [{"corporativo": "Ministerio de Economía y Finanzas"}]
    assert norma["etiquetas"] == ["norma", "politica_fiscal"] and norma["titulo_corto"] == "Decreto Legislativo N.° 1621"
    assert art["autores"][0] == {"apellido": "Roediger", "nombre": "Henry L."}
    assert art["revista"] == "Psychological Science" and art["editorial"] == "", "en Calibre la revista va en la editorial"


def test_lee_bibtex_y_csl(iz):
    roe, lum, inei = iz.leer_bib(BIB, "b.bib")
    assert roe["tipo"] == "journalArticle" and roe["clave"] == "roedigerTestenhancedLearningTaking2006"
    assert roe["titulo"] == "Test-Enhanced Learning: Taking Memory Tests Improves Long-Term Retention"
    assert roe["paginas"] == "249-255" and roe["numero"] == "3" and roe["etiquetas"] == ["memoria", "recuperación"]
    assert lum["isbn"] == "9780470284308" and lum["lugar"] == "Hoboken" and lum["editorial"] == "Wiley"
    assert inei["autores"] == [{"corporativo": "Instituto Nacional de Estadística e Informática"}]
    assert inei["titulo"] == "Ficha técnica de la ENAHO" and inei["numero_doc"] == "12" and inei["tipo"] == "report"
    (page,) = iz.leer_csl(CSL, "c.json")
    assert page["fecha"] == "2021-03-29" and page["revista"] == "BMJ" and page["clave"] == "page2021"
    assert page["autores"][1] == {"corporativo": "PRISMA Group"}


def test_lee_por_extension_o_contenido(iz, tmp_path):
    for nombre, texto, n in (("x.ris", RIS, 2), ("x.bib", BIB, 3), ("x.json", CSL, 1), ("sin.txt", RIS, 2)):
        (tmp_path / nombre).write_text(texto, encoding="utf-8")
        assert len(iz.leer(tmp_path / nombre)) == n, nombre


def test_fusiona_lo_repetido_entre_archivos(iz):
    regs = iz.leer_ris(RIS, "a.ris") + iz.leer_bib(BIB, "b.bib") + iz.leer_csl(CSL, "c.json")
    obras, fundidos = iz.fusionar(regs)
    assert fundidos == 1 and len(obras) == 5
    roe = next(o for o in obras if o["titulo"].startswith("Test-enhanced"))
    assert roe["origenes"] == ["a.ris", "b.bib"] and roe["calibre_id"] == 48
    assert roe["clave"] == "roedigerTestenhancedLearningTaking2006" and roe["paginas"] == "249-255", "lo vacío se rellena"
    assert roe["etiquetas"] == ["aprendizaje", "memoria", "recuperación"]


def test_la_fecha_como_la_guarda_zotero(iz):
    f = iz._ing().fecha_zotero
    assert f("2023") == "2023-00-00 2023" and f(2006) == "2006-00-00 2006"
    assert f("2024-03-05") == "2024-03-05 2024-03-05" and f("2024/05") == "2024-05-00 2024-05"
    assert f("primavera de 1998") == "1998-00-00 primavera de 1998" and f("") == ""


def _zot(iz):
    items = {"AAAA0001": {"key": "AAAA0001", "tipo": "journalArticle", "papelera": False, "titulo": "Test-enhanced learning",
                          "anio": "2006", "doi": "", "isbn": "", "clave": "", "autor": "Roediger"},
             "BBBB0002": {"key": "BBBB0002", "tipo": "book", "papelera": False, "titulo": "Complex surveys: a guide to analysis using R",
                          "anio": "2004", "doi": "", "isbn": "", "clave": "", "autor": "Lumley"},
             "CCCC0003": {"key": "CCCC0003", "tipo": "statute", "papelera": False,
                          "titulo": "Decreto Legislativo N.° 1280. Ley marco", "anio": "2016", "doi": "", "isbn": "", "clave": "", "autor": ""},
             "DDDD0004": {"key": "DDDD0004", "tipo": "report", "papelera": True, "titulo": "Ficha técnica de la ENAHO",
                          "anio": "2024", "doi": "", "isbn": "", "clave": "", "autor": "Instituto"}}
    indice = {}
    for d in items.values():
        for k in (f"titulo:{iz._normal(d['titulo'])}", f"corto:{iz._corto(d['titulo'])}"):
            indice.setdefault(k, []).append(d["key"])
    return {"items": items, "indice": indice, "carpetas": {"Autor/Libro (7)": {"AAAA0001"}}, "claves": set()}


def test_coteja_ya_dudoso_y_nuevo(iz):
    z = _zot(iz)
    roe, lum, inei = iz.leer_bib(BIB, "b.bib")
    norma = iz.leer_ris(RIS, "a.ris")[0]
    assert iz.cotejar_zotero(roe, None, z)[0] == "ya", "el mismo título (sin subtítulo), año y autor"
    estado, key, motivo = iz.cotejar_zotero(lum, None, z)
    assert (estado, key) == ("dudoso", "BBBB0002") and "otro año" in motivo
    assert iz.cotejar_zotero(inei, None, z)[0] == "dudoso" and "papelera" in iz.cotejar_zotero(inei, None, z)[2]
    assert iz.cotejar_zotero(norma, None, z)[0] == "nuevo", "dos decretos con otro número no se confunden"
    libro = {"zotero_key": "", "ruta": "Autor/Libro (7)"}
    assert iz.cotejar_zotero({**norma, "titulo": "Otra cosa"}, libro, z) == ("ya", "AAAA0001", "un adjunto enlaza su archivo de Calibre")


def test_la_coleccion_por_defecto_sale_del_lote(iz):
    assert iz.coleccion_por_defecto([Path("ingesta_20261116_canon-de-las-miradas.ris")], "2026-11-18") == "Canon de las miradas"
    assert iz.coleccion_por_defecto([Path("ingesta_20261004_213412.ris")], "2026-11-18") == "Importado 2026-11-18"
    assert iz.coleccion_por_defecto([Path("a.ris"), Path("b.bib")], "2026-11-18") == "Importado 2026-11-18"
