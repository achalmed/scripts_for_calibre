"""tests/fuentes/test_lista_referencias.py — una lista de referencias pegada (de un chat de IA o del Deep Research de un
cuaderno de Gemini Notebook; 2026-11-22): qué saca del texto, qué ya está en la biblioteca y qué falta, y al aplicar, lo
que dicen las agencias (el DOI inventado no existe; el real de otra obra discrepa) y la lista de candidatos.

Sin red (las agencias son una función falsa) y sin bases: lo existente es un diccionario de juguete como el de
`ingresar.existentes`; el estado, la caché y la entrada van a un temporal.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

LISTA = """## Fuentes que encontró la investigación

1. Roediger, H. L., y Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention.
   Psychological Science, 17(3), 249-255. https://doi.org/10.1111/j.1467-9280.2006.01693.x
2. Lumley, T. (2010). Complex surveys: A guide to analysis using R. Wiley. ISBN 978-0-470-28430-8
3. Pérez, A. (2024). Un estudio que la IA inventó sobre la lectura profunda. Revista Imaginaria. doi:10.9999/inventado.2024.1
4. Smith, J. (2019). La memoria de trabajo en lectores adultos. Journal of Reading, 12, 1-20. DOI 10.1000/real.de.otra
5. Dunlosky, J. et al. (2013). Improving students' learning with effective learning techniques.
- https://www.ejemplo.org/un-informe
Texto suelto sin referencia.
"""


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def lr(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    monkeypatch.delenv("CROSSREF_MAILTO", raising=False)
    for n in ("biblioteca_ingresar", "biblioteca_verificar_ids", "t_lista_referencias"):
        sys.modules.pop(n, None)
    return _cargar("t_lista_referencias", REPO / "lib" / "lista_referencias.py")


def _ex():
    """Calibre tiene Lumley (por su ISBN) y Dunlosky (por su título); Zotero, Roediger (por su DOI)."""
    return {"cal": {7: {"titulo": "Complex surveys", "doi": "", "isbn": "9780470284308"},
                    11124: {"titulo": "Improving students' learning with effective learning techniques", "doi": "", "isbn": ""}},
            "zot": {"roedigerTestenhancedLearningTaking2006": {"zotero_key": "ROED0001", "titulo": "Test-enhanced learning",
                                                               "doi": "10.1111/j.1467-9280.2006.01693.x", "isbn": ""}},
            "autor_cal": {7: "Thomas, Lumley", 11124: "John, Dunlosky"}, "rutas": {}, "claves": {"roedigerTestenhancedLearningTaking2006"}}


def agencias(registro):
    def pedir(url, timeout=20):
        registro.append(url)
        if "crossref.org/works/10.1000/real.de.otra" in url:
            return 200, {"message": {"title": ["Quantum chromodynamics at high energies"], "issued": {"date-parts": [[2001]]}}}
        if "crossref.org/works/10.9999/inventado" in url:
            return 404, None
        if "doi.org/api/handles/10.9999/inventado" in url:
            return 404, None
        return 0, None
    return pedir


def test_extrae_identificadores_urls_y_referencias(lr):
    cands = lr.extraer(LISTA)
    assert [(c["tipo"], c["valor"]) for c in cands] == [
        ("doi", "10.1111/j.1467-9280.2006.01693.x"), ("isbn", "9780470284308"), ("doi", "10.9999/inventado.2024.1"),
        ("doi", "10.1000/real.de.otra"),
        ("referencia", "Dunlosky, J. et al. (2013). Improving students' learning with effective learning techniques."),
        ("url", "https://www.ejemplo.org/un-informe")]
    assert lr.extraer("Nada que ver aquí.\nNi aquí.") == []
    assert lr.extraer("ISBN 978-0-470-28430-9 (mal)") == []                 # dígito de control malo: no es un ISBN


def test_coteja_con_calibre_y_zotero_sin_abrir_las_bases(lr):
    lista = lr.cotejar_lista(lr.extraer(LISTA), _ex())
    def de(prefijo):
        c = next(c for c in lista if c["valor"].startswith(prefijo))
        return c["estado"], c["calibre"], c["zotero"]
    assert de("10.1111/") == ("en_biblioteca", [], ["roedigerTestenhancedLearningTaking2006"])
    assert de("9780470284308") == ("en_biblioteca", [7], [])
    assert de("10.9999/")[0] == "falta"
    assert de("Dunlosky") == ("en_biblioteca", [11124], [])
    assert de("https://")[0] == "por_identificar"
    assert lr.cuentas(lista) == {"total": 6, "en_biblioteca": 3, "falta": 2, "por_identificar": 1, "no_existe": 0, "discrepa": 0}


def test_al_aplicar_el_doi_inventado_no_existe_y_el_de_otra_obra_discrepa(lr):
    lista = lr.cotejar_lista(lr.extraer(LISTA), _ex())
    urls = []
    cache = {}
    lr.verificar(lista, cache, pedir=agencias(urls), pausa=0)
    por = {c["valor"]: c.get("agencia", {}).get("estado") for c in lista}
    assert por["10.9999/inventado.2024.1"] == "no_existe"
    assert por["10.1000/real.de.otra"] == "discrepa"
    assert all("crossref" in u or "doi.org" in u for u in urls) and not any("1467-9280" in u for u in urls)   # lo que ya está no se consulta
    obras = lr.candidatos(lista)
    assert [o.get("doi") for o in obras] == ["10.1000/real.de.otra"]       # el inexistente no es candidato
    assert obras[0]["verificacion"] == "discrepa" and "autores" in obras[0]["por_completar"]
    texto = lr.texto_informe(lista, True)
    assert "NO EXISTE" in texto and "de otra obra" in texto


def test_la_orden_simula_y_al_aplicar_deja_los_candidatos_en_la_entrada(lr, tmp_path, monkeypatch, capsys):
    archivo = tmp_path / "lista.txt"
    archivo.write_text(LISTA, encoding="utf-8")
    ing = lr._ing()
    monkeypatch.setattr(ing, "_env", lambda: None)
    monkeypatch.setattr(ing, "existentes", lambda env: _ex())
    monkeypatch.setattr(lr, "ENTRADA", tmp_path / "repo" / "entrada")
    assert lr.main([str(archivo)]) == 0
    salida = capsys.readouterr().out
    assert "3 ya en la biblioteca · 2 faltan · 1 por identificar" in salida and "Simulado" in salida
    informe = json.loads((tmp_path / "estado" / "biblioteca" / "lista-referencias" / "ultimo.json").read_text(encoding="utf-8"))
    assert informe["aplicado"] is False and not (tmp_path / "repo" / "entrada").exists()
    vi = lr._vi()
    monkeypatch.setattr(vi, "consultar", lambda lista, cache, **kw: cache.update(
        {vi._id(t, v): {"estado": "existe", "fuente": "Crossref", "titulo": "La memoria de trabajo en lectores adultos", "anio": 2019,
                        "fecha": "2026-11-22"} for t, v in lista}) or {})
    assert lr.main([str(archivo), "--aplicar", "--lote", "deep research 1"]) == 0
    datos = json.loads((tmp_path / "repo" / "entrada" / "deep-research-1" / "candidatos.json").read_text(encoding="utf-8"))
    assert len(datos["obras"]) == 2 and datos["origen"] == "lista.txt"
    assert lr.main([str(tmp_path / "no-esta.txt")]) == 2
