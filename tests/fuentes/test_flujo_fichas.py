"""tests/fuentes/test_flujo_fichas.py — el origen de cada ficha, el cotejo antes de citar, el registro de la IA y la ficha de
obra (FLUJO_DE_CONOCIMIENTO C3.3, C12.1 y C3.1; decisiones §9.10).

Sobre un escrito de prueba en un temporal (nunca escritura real), con el texto del PDF simulado y un `antes_de_entregar.py`
falso (ESCRITURA_CODIGO) que solo apunta lo que recibe: ninguna prueba toca escritura ni las bases.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOJAS = ["Portada del libro de muestra.",
         "Capítulo 1. La escala urbana importa: las ciudades pequeñas crecen cuando se integran a su región. 12",
         "Capítulo 2. El mercado de trabajo local depende de la conectividad vial y del crédito. 13"]
FALSO = '''import json, sys
from pathlib import Path
proyecto, datos = Path(sys.argv[2]), json.loads(sys.argv[3])
(proyecto / "ia").mkdir(exist_ok=True)
with open(proyecto / "ia" / "llamadas.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"orden": sys.argv[1], "datos": datos, "aplicar": "--aplicar" in sys.argv}, ensure_ascii=False) + "\\n")
print(json.dumps({"uso": datos, "total": 1, "registro": "ia/registro.yml", "escrito": True}))
'''


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def escrito(tmp_path, monkeypatch):
    d = tmp_path / "escritura" / "reports" / "2026-11-18-muestra"
    (d / "fuentes" / "fichas").mkdir(parents=True)
    (d / "proyecto.yaml").write_text("titulo: Informe de muestra\ntipo: informe\n", encoding="utf-8")
    (d / "fuentes" / "fuentes.yml").write_text(
        "proyecto: 2026-11-18-muestra\nfuentes:\n- calibre_id: 1\n  zotero_key: QUISPE01\n  clave_bibtex: quispeEconomiaCiudades2021\n"
        "  titulo: Economía de las ciudades pequeñas\n  uso: ''\n", encoding="utf-8")
    codigo = tmp_path / "escritura-codigo" / "scripts"
    codigo.mkdir(parents=True)
    (codigo / "antes_de_entregar.py").write_text(FALSO, encoding="utf-8")
    monkeypatch.setenv("ESCRITURA_CODIGO", str(codigo.parent))
    monkeypatch.setenv("WRITING_DIR", str(tmp_path / "escritura"))
    for k in [k for k in sys.modules if k in ("biblioteca_fichar", "fichas_ficha", "fichas_verificar")]:
        del sys.modules[k]
    consulta = _cargar("t_consulta_flujo", REPO / "lib" / "consulta.py")
    fichar = consulta._fichar()
    V = fichar._verificador()
    monkeypatch.setattr(V.bib, "texto", lambda cid, cache=True, layout=True: list(HOJAS) if int(cid) == 1 else [])
    monkeypatch.setattr(fichar, "_hojas", lambda cid: list(HOJAS) if str(cid) == "1" else [])
    return d, fichar, consulta


TEXTUAL = {"tipo": "textual", "calibre_id": 1, "pagina": "2", "categoria": "Idea principal", "tema": "escala urbana",
           "secciones": {"Cita exacta": "las ciudades pequeñas crecen cuando se integran a su región"}}


def test_la_ficha_de_la_persona_lleva_su_origen_y_se_cita(escrito):
    d, _fichar, consulta = escrito
    r = consulta.nueva_ficha(d, TEXTUAL, aplicar=True)
    texto = (d / "fuentes" / "fichas" / r["archivo"]).read_text(encoding="utf-8")
    assert "origen:" not in texto, "norma de fichas 1.1: el bloque solo va si la propuso otro (el LLM)"
    assert r["citable"] and not (d / "ia").exists(), "la ficha de una persona no se registra como uso de IA"
    f = next(x for x in consulta.fichas(d) if x["nombre"] == r["archivo"][:-3])
    assert f["origen"] == "persona" and f["citable"] and f["insertar"].startswith("“las ciudades")
    assert [x for x in r["problemas"] if not x.startswith("aviso")] == []


def test_la_ficha_del_llm_no_se_cita_hasta_cotejar_su_pagina(escrito):
    d, fichar, consulta = escrito
    datos = {**TEXTUAL, "origen": {"autor": "llm", "herramienta": "Un chat de IA externo, mirada «Fichas textuales»"}}
    sim = consulta.nueva_ficha(d, datos)
    assert sim["origen"]["autor"] == "llm" and not sim["citable"] and sim["registro_ia"] == {"pendiente": True}
    assert not (d / "ia").exists(), "simular no registra"
    r = consulta.nueva_ficha(d, datos, aplicar=True)
    p = d / "fuentes" / "fichas" / r["archivo"]
    texto = p.read_text(encoding="utf-8")
    assert "  autor: llm\n" in texto and "metodo: propuesta por IA; pdftotext" in texto, "la marca de §8 en el método"
    assert texto.index("origen:") < texto.index("verificacion:"), "el bloque va antes de la verificación (§1)"
    assert "Propuesta por IA el" in texto, "y legible en Observaciones"
    assert r["verificacion"]["estado"] == "verificada_script" and not r["citable"]
    # C12.1: quedó registrada en el escrito, una sola vez
    llamadas = [json.loads(l) for l in (d / "ia" / "llamadas.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(llamadas) == 1 and llamadas[0]["orden"] == "registrar_ia" and llamadas[0]["aplicar"]
    assert llamadas[0]["datos"]["archivo"] == f"fuentes/fichas/{r['archivo']}" and "p. 2" in llamadas[0]["datos"]["parte"]
    f = next(x for x in consulta.fichas(d) if x["nombre"] == r["archivo"][:-3])
    assert f["origen"] == "llm" and not f["citable"] and f["insertar"] == "" and "coteja su página" in f["motivo"]
    # la persona coteja: simula, exige la huella y después se puede citar
    with pytest.raises(fichar.Cambiada):
        fichar.cotejar(d, r["archivo"], "huella-vieja")
    s = consulta.cotejar_ficha(d, r["archivo"], r["huella"])
    assert s["escrito"] is False and "verificada_autor" in s["diff"] and p.read_text(encoding="utf-8") == texto
    c = consulta.cotejar_ficha(d, r["archivo"], r["huella"], aplicar=True)
    nuevo = p.read_text(encoding="utf-8")
    assert c["citable"] and "estado: verificada_autor" in nuevo and "metodo: propuesta por IA; lectura del autor" in nuevo
    assert nuevo.split("verificacion:")[0] == texto.split("verificacion:")[0], "solo cambia el bloque de la verificación"
    f = next(x for x in consulta.fichas(d) if x["nombre"] == r["archivo"][:-3])
    assert f["citable"] and f["insertar"].startswith("“las ciudades")
    # corregirla después no cambia quién la propuso, ni vuelve a registrarla
    g = consulta.guardar_ficha(d, r["archivo"], c["huella"], {"secciones": {"Análisis": "La integración regional."}}, aplicar=True)
    assert "  autor: llm\n" in (d / "fuentes" / "fichas" / g["archivo"]).read_text(encoding="utf-8")
    assert len((d / "ia" / "llamadas.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_la_marca_de_antes_basta_para_saber_que_es_del_llm(escrito):
    d, fichar, consulta = escrito
    p = d / "fuentes" / "fichas" / "quispeEconomiaCiudades2021-p002-textual-escala.md"
    p.write_text("---\ntipo: ficha_textual\ncalibre_id: 1\nzotero_key: QUISPE01\nclave_bibtex: quispeEconomiaCiudades2021\n"
                 "proyecto: 2026-11-18-muestra\npagina: 2\ncategoria: Cita clave\nuso:\nverificacion:\n  estado: verificada_script\n"
                 "  metodo: propuesta por IA; cotejo literal\n  fecha: 2026-11-16\n---\n\n## Cita exacta\n“las ciudades pequeñas crecen”\n",
                 encoding="utf-8")
    f = next(x for x in consulta.fichas(d) if x["nombre"] == p.stem)
    assert f["origen"] == "llm" and not f["citable"] and f["insertar"] == ""


def test_una_ficha_observada_no_se_cita(escrito):
    d, _fichar, consulta = escrito
    r = consulta.nueva_ficha(d, {**TEXTUAL, "secciones": {"Cita exacta": "una frase que el libro no dice en ninguna parte"}}, aplicar=True)
    assert r["verificacion"]["estado"] == "observada" and not r["citable"]
    f = next(x for x in consulta.fichas(d) if x["nombre"] == r["archivo"][:-3])
    assert f["insertar"] == "" and "no coincide" in f["motivo"]


def test_el_origen_pedido_se_valida(escrito):
    d, _fichar, consulta = escrito
    with pytest.raises(ValueError):
        consulta.nueva_ficha(d, {**TEXTUAL, "origen": {"autor": "robot"}})


OBRA = {"tipo": "obra", "calibre_id": 1, "secciones": {
    "Pregunta": "Por qué unas ciudades chicas prosperan y otras no.",
    "Método": "Compara municipios con datos de varios censos.",
    "Datos": "Censos nacionales y registros de vías.",
    "Hallazgo": "Prosperan las que se conectan bien con su entorno.",
    "Límites": "No separa la causa del vínculo vial de la del crédito.",
    "Uso que le daré": "El marco de la sección 2."}}


def test_la_ficha_de_obra_se_escribe_con_palabras_propias(escrito):
    d, _fichar, consulta = escrito
    form = {t["clave"]: t for t in consulta._fichar().formulario()["tipos"]}
    assert form["obra"]["secciones"][:6] == ["Pregunta", "Método", "Datos", "Hallazgo", "Límites", "Uso que le daré"]
    assert form["obra"]["guias"]["Límites"] and "Fiorella y Mayer (2016)" in form["obra"]["fuente"] and not form["obra"]["pagina"]
    r = consulta.nueva_ficha(d, OBRA, aplicar=True)
    assert r["archivo"] == "quispeEconomiaCiudades2021-obra.md"
    texto = (d / "fuentes" / "fichas" / r["archivo"]).read_text(encoding="utf-8")
    assert "tipo: ficha_obra" in texto and "pagina:" not in texto and "categoria:" not in texto
    assert "estado: verificada_script" in texto and "palabras propias" in texto
    assert [x for x in r["problemas"] if not x.startswith("aviso")] == [], r["problemas"]
    with pytest.raises(ValueError, match="ya tiene su ficha de obra"):
        consulta.nueva_ficha(d, OBRA)


def test_la_ficha_de_obra_que_copia_no_se_guarda(escrito):
    d, _fichar, consulta = escrito
    copia = {**OBRA, "secciones": {**OBRA["secciones"], "Hallazgo": "La escala urbana importa: las ciudades pequeñas crecen cuando se integran a su región."}}
    sim = consulta.nueva_ficha(d, copia)
    assert sim["verificacion"]["estado"] == "observada" and any("Copia de la obra" in x for x in sim["problemas"])
    with pytest.raises(ValueError, match="Copia de la obra"):
        consulta.nueva_ficha(d, copia, aplicar=True)
    assert not (d / "fuentes" / "fichas" / "quispeEconomiaCiudades2021-obra.md").exists()
    with pytest.raises(ValueError, match="seis preguntas"):
        consulta.nueva_ficha(d, {**OBRA, "secciones": {"Pregunta": "¿Por qué?"}})


def test_copiado_halla_las_series_de_ocho_palabras(escrito):
    _d, fichar, _c = escrito
    assert fichar.copiado("Dice que las ciudades pequeñas crecen cuando se integran a su región, y más.", HOJAS)
    assert fichar.copiado("Las ciudades chicas prosperan si se integran.", HOJAS) == []
