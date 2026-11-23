"""tests/fuentes/test_fichar_y_ayuda.py — fichar desde los studios y los prompts del ecosistema (decisiones §9.4 y §9.5).

Sobre un escrito de prueba en un temporal (nunca escritura real) y con el texto del PDF simulado: la ficha nueva sale
con su nombre normativo, su frontmatter único y su cotejo; corregirla exige la huella; la ficha de fuente lista sus
derivadas; los prompts no escriben nada y lo pegado se comprueba sin IA.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOJAS = ["Portada del libro de muestra.",
         "Capítulo 1. La escala urbana importa: las ciudades pequeñas crecen cuando se integran a su región. 12",
         "Capítulo 2. El mercado de trabajo local depende de la conectividad vial y del crédito. 13"]


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def escrito(tmp_path, monkeypatch):
    """Un escrito con su fuentes.yml, su references.bib y una parte con su \\componente; el PDF simulado en HOJAS."""
    d = tmp_path / "escritura" / "reports" / "2026-11-17-muestra"
    (d / "fuentes" / "fichas").mkdir(parents=True)
    (d / "content").mkdir()
    (d / "proyecto.yaml").write_text("titulo: Informe de muestra\ntipo: informe\nesquema: informe-tecnico\n", encoding="utf-8")
    (d / "fuentes" / "fuentes.yml").write_text(
        "proyecto: 2026-11-17-muestra\nfuentes:\n- calibre_id: 1\n  zotero_key: QUISPE01\n  clave_bibtex: quispeEconomiaCiudades2021\n"
        "  titulo: Economía de las ciudades pequeñas\n  uso: ''\n", encoding="utf-8")
    (d / "references.bib").write_text("% calibre_id: 1\n@book{quispeEconomiaCiudades2021,\n  title = {Economía},\n}\n", encoding="utf-8")
    (d / "content" / "01-introduccion.tex").write_text(
        "% parte de muestra\n\\componente[Introducción]{introduccion}\n\nTexto viejo de la introducción.\n", encoding="utf-8")
    monkeypatch.setenv("WRITING_DIR", str(tmp_path / "escritura"))
    fichar = _cargar("t_fichar", REPO / "lib" / "fichar.py")
    V = fichar._verificador()
    monkeypatch.setattr(V.bib, "texto", lambda cid, cache=True, layout=True: list(HOJAS) if int(cid) == 1 else [])
    consulta = _cargar("t_consulta", REPO / "lib" / "consulta.py")
    monkeypatch.setattr(consulta, "paginas", lambda cid: list(HOJAS))
    return d, fichar, consulta


def test_nueva_textual_simula_y_luego_escribe(escrito):
    d, fichar, consulta = escrito
    datos = {"tipo": "textual", "calibre_id": 1, "pagina": "2", "categoria": "Idea principal",
             "secciones": {"Cita exacta": "las ciudades pequeñas crecen cuando se integran a su región"}, "tema": "escala urbana"}
    sim = consulta.nueva_ficha(d, datos)
    assert sim["escrito"] is False and sim["archivo"] == "quispeEconomiaCiudades2021-p002-textual-escala-urbana.md"
    assert not (d / "fuentes" / "fichas" / sim["archivo"]).exists(), "simular no escribe"
    assert sim["verificacion"]["estado"] == "verificada_script"
    r = consulta.nueva_ficha(d, datos, aplicar=True)
    p = d / "fuentes" / "fichas" / r["archivo"]
    texto = p.read_text(encoding="utf-8")
    assert texto.startswith("---\ntipo: ficha_textual\ncalibre_id: 1\nzotero_key: QUISPE01\nclave_bibtex: quispeEconomiaCiudades2021\n")
    assert "## Cita exacta\n“las ciudades pequeñas crecen cuando se integran a su región”" in texto
    assert "estado: verificada_script" in texto and fichar.FIRMA in texto
    assert [x for x in r["problemas"] if not x.startswith("aviso")] == [], r["problemas"]
    fuente = (d / "fuentes" / "fichas" / "quispeEconomiaCiudades2021-fuente.md").read_text(encoding="utf-8")
    assert f"]({r['archivo']})" in fuente, "la ficha de fuente lista la derivada"
    assert r["huella"] == fichar.huella(texto)


def test_literal_ausente_queda_observada(escrito):
    d, _fichar, consulta = escrito
    r = consulta.nueva_ficha(d, {"tipo": "textual", "calibre_id": 1, "pagina": "2", "categoria": "Cita clave",
                                 "secciones": {"Cita exacta": "una frase que el libro no dice en ninguna parte"}})
    assert r["verificacion"]["estado"] == "observada"


def test_corregir_exige_la_huella_y_renombra_con_la_pagina(escrito):
    d, fichar, consulta = escrito
    r = consulta.nueva_ficha(d, {"tipo": "textual", "calibre_id": 1, "pagina": "2", "categoria": "Cita clave", "tema": "escala",
                                 "secciones": {"Cita exacta": "las ciudades pequeñas crecen cuando se integran a su región"}}, aplicar=True)
    malo = consulta.guardar_ficha(d, r["archivo"], "0" * 64, {"secciones": {"Análisis": "Otro."}}, aplicar=True)
    assert malo["codigo"] == "ficha_cambiada"
    leida = consulta._fichar().leer(d, r["archivo"])
    assert [s["titulo"] for s in leida["secciones"]] == ["Cita exacta", "Análisis", "Observaciones"]
    bien = consulta.guardar_ficha(d, r["archivo"], leida["huella"], {"pagina": "3", "secciones": {
        "Cita exacta": "El mercado de trabajo local depende de la conectividad vial", "Análisis": "Lo dice del empleo."}}, aplicar=True)
    assert bien["escrito"] and bien["archivo"].startswith("quispeEconomiaCiudades2021-p003-textual-")
    assert not (d / "fuentes" / "fichas" / r["archivo"]).exists()
    fuente = (d / "fuentes" / "fichas" / "quispeEconomiaCiudades2021-fuente.md").read_text(encoding="utf-8")
    assert f"]({bien['archivo']})" in fuente and f"]({r['archivo']})" not in fuente, "los enlaces siguen al nombre nuevo"


def test_libro_que_no_es_fuente_lo_avisa_al_simular(escrito):
    d, _fichar, consulta = escrito
    consulta._indice = lambda: {"libros": {"2": {"clave": "arangoEstadistica2015", "zotero_key": ""}}}
    r = consulta.nueva_ficha(d, {"tipo": "textual", "calibre_id": 2, "pagina": "1", "secciones": {"Cita exacta": "Portada del libro"}})
    assert r["nueva_fuente"] is True and r["escrito"] is False


def test_prompt_y_pegado_de_una_parte(escrito):
    d, _fichar, consulta = escrito
    p = consulta.prompt_parte(d, "content/01-introduccion.tex")
    assert p["componente"] == "introduccion" and "<entrada>" in p["prompt"] and "Texto viejo de la introducción." in p["prompt"]
    assert "quispeEconomiaCiudades2021" in p["prompt"] and not p["prompt"].startswith("---")
    pegado = ("```latex\n% componente: introduccion\n[H] La escala importa \\parencite[p.~12]{quispeEconomiaCiudades2021}. "
              "[VERIFICAR: el dato de 2020]\n```")
    r = consulta.pegar_parte(d, "content/01-introduccion.tex", pegado)
    assert r["ok"], r["errores"]
    assert "[H]" not in r["despues"] and "[dato pendiente: el dato de 2020]" in r["despues"]
    assert r["antes"].strip() == "Texto viejo de la introducción."
    tex = (d / "content" / "01-introduccion.tex").read_text(encoding="utf-8")
    assert "Texto viejo" in tex, "pegar no escribe"
    malo = consulta.pegar_parte(d, "content/01-introduccion.tex", "```latex\n\\section{X} \\parencite{otraClave}\n```")
    assert not malo["ok"] and any("otraClave" in e for e in malo["errores"]) and any("sección" in e for e in malo["errores"])
    # la regla común de escritura (core/parte.py), la misma de Yachay: una tabla o una figura no las escribe la IA
    tabla = consulta.pegar_parte(d, "content/01-introduccion.tex", "```latex\n\\begin{table}x\\end{table}\n```")
    assert not tabla["ok"] and any("figuras y tablas" in e for e in tabla["errores"])


def test_estudio_de_obra_prompt_y_pegado(escrito):
    d, _fichar, consulta = escrito
    ayuda = consulta._ayuda()
    if not ayuda.miradas():
        pytest.skip("sin el catálogo de Yachay")
    consulta._libro = lambda cid: {"calibre_id": 1, "titulo": "Economía de las ciudades pequeñas", "autores": ["Rosa Quispe"], "clave": "q", "anio": "2021"}
    p = consulta.prompt_obra(1, "obra_fichas", 2, 3)
    assert "[u2] hoja 2 del PDF" in p["prompt"] and "[u3] hoja 3" in p["prompt"] and p["unidades"] == 2
    import yaml
    pegado = yaml.safe_dump({"tipo": "estudio-de-obra", "version": 1, "dimension": "obra_fichas", "titulo": "t", "obra": "o", "unidad": "cap. 1",
                         "afirmaciones": [], "fichas": [
                             {"tipo": "textual_simple", "tema": "escala", "categoria": "Idea principal", "cita": "u2", "localizador": "p. 12",
                              "texto_citado": "las ciudades pequeñas crecen cuando se integran a su región", "comentario": "Tesis."},
                             {"tipo": "parafrasis", "tema": "empleo", "categoria": "rótulo inventado", "cita": "u2", "localizador": "p. 13",
                              "texto_citado": "El mercado de trabajo local depende de la conectividad vial", "parafrasis": "El empleo sigue a las vías."}]}, allow_unicode=True)
    r = consulta.pegar_obra(1, "```yaml\n" + pegado + "\n```")
    assert r["ok"], r["errores"]
    f1, f2 = r["fichas"]
    assert f1["clase"] == "textual" and f1["verificacion"] == "verificada_script" and f1["pagina"] == "12"
    assert f2["clase"] == "parafrasis" and f2["verificacion"] == "observada" and f2["hoja"] == 3, "hallada en otra hoja"
    assert f2["categoria"] == "Idea principal", "un rótulo fuera de los once vuelve al de omisión"


def test_el_verificador_carga_aunque_lib_sea_el_paquete_del_repo(monkeypatch):
    """En Biblioteca Studio `lib` ya es el paquete de este repo: el cotejo de la suite `fichas` igual se carga, y el `lib`
    de antes vuelve a su sitio."""
    monkeypatch.syspath_prepend(str(REPO))
    for k in [k for k in sys.modules if k == "lib" or k.startswith("lib.") or k in ("fichas_verificar", "fichas_ficha")]:
        monkeypatch.delitem(sys.modules, k)
    import lib  # noqa: F401 — el de biblioteca-studio
    fichar = _cargar("t_fichar_lib", REPO / "lib" / "fichar.py")
    V = fichar._verificador()
    assert hasattr(V, "cotejar") and Path(sys.modules["lib"].__file__) == REPO / "lib" / "__init__.py"


def test_ayuda_por_el_modulo_comun_con_su_guarda_y_el_aviso():
    """2026-11-23: la ayuda carga lo común de `core/py-common/ia_externa.py`: no lee fuera del repo de prompts y da el
    aviso C12.3 de un prompt que declara datos de estudiantes (`05 docencia/prompt_04`)."""
    a = _cargar("t_ayuda_ia_comun", REPO / "lib" / "ayuda_ia.py")
    if a.comun() is None:
        pytest.skip("sin core/py-common/ia_externa.py")
    with pytest.raises(LookupError):
        a.leer_prompt("../biblioteca-studio/CLAUDE.md")
    texto = a.leer_prompt("05 docencia/prompt_04_analisis_de_errores.md")
    assert "estudiantes" in a.sensible(texto)
    assert a.sensible(a.leer_prompt("14 estudio/prompt_00_plan_de_estudio.md")) == ""
    assert not a.para_ia_externa(texto).startswith("---")


def test_una_ficha_puede_ir_a_un_curso_que_se_toma_y_entra_en_la_cola_de_repaso(escrito, tmp_path, monkeypatch):
    """Plan «aprender y enseñar», fase 2.5: la carpeta de un curso con su `curso-tomado.yml` es un destino de fichas como un
    escrito (`destinos`, como `cursos/<id>`), y `usos` la cuenta con su carpeta, de donde sale la cola única de repaso."""
    d, _fichar, consulta = escrito
    curso = tmp_path / "notas" / "40-cursos-y-formacion" / "caf_13"
    (curso / "fuentes").mkdir(parents=True)
    (curso / "curso-tomado.yml").write_text("tipo: curso-tomado\nversion: 1\ntitulo: Econometría I\ninstitucion: CAF\n"
                                            "modalidad: en_linea\nestado: en_curso\n", encoding="utf-8")
    (curso / "fuentes" / "fuentes.yml").write_text(
        "proyecto: caf_13\nfuentes:\n- calibre_id: 1\n  zotero_key: QUISPE01\n  clave_bibtex: quispeEconomiaCiudades2021\n"
        "  titulo: Economía de las ciudades pequeñas\n  uso: ''\n", encoding="utf-8")
    monkeypatch.setenv("NOTES_DIR", str(tmp_path / "notas"))
    destinos = consulta.destinos()
    assert {e["destino"] for e in destinos} == {"escrito", "curso"}
    del_curso = next(e for e in destinos if e["destino"] == "curso")
    assert del_curso["proyecto"] == "cursos/caf_13" and del_curso["titulo"] == "Curso: Econometría I"
    assert all(e["proyecto"] != "cursos/caf_13" for e in consulta.escritos()), "LaTeX Studio sigue viendo solo escritos"
    r = consulta.nueva_ficha(curso, {"tipo": "textual", "calibre_id": 1, "pagina": "2", "categoria": "Idea principal",
                                     "secciones": {"Cita exacta": "las ciudades pequeñas crecen cuando se integran a su región"}},
                             aplicar=True)
    assert (curso / "fuentes" / "fichas" / r["archivo"]).is_file()
    usos = {u["proyecto"]: u for u in consulta.usos(1)}
    assert usos["cursos/caf_13"]["fichas"] == 2 and usos["cursos/caf_13"]["carpeta"] == str(curso)   # la textual y su fuente
    assert Path(r["archivo"]).stem in [f["nombre"] for f in consulta.fichas(curso) if f["tipo"] == "textual"]
