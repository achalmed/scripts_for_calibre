"""tests/fuentes/test_ayuda_marco.py — la ayuda de la IA de una parte cuando el marco elige el prompt (`--cuadro`;
`lib/ayuda_ia.py`, «el cuadro de un marco», 2026-11-24; plan «aprender y enseñar», fase 4.4).

Un marco sin el modelo de componentes de escritura (docencia) declara un cuadro: por la clase, las órdenes o el archivo
que acompaña al documento, qué prompt le toca, qué se pide, qué va de contexto y qué añade al formato de vuelta; sus
partes son sus `\\section`. Sobre una carpeta de prueba en un temporal: la regla que gana, las secciones como partes, el
contexto en la entrada, el documento sin ayuda con su motivo y lo pegado comprobado con la regla común sin escribir.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

CUADRO = """version: 1
partes: seccion
contexto: [sesion.yml]
documentos:
  - nombre: evaluación
    clases: [academic-exam]
    sin_ayuda: Sus preguntas van al banco.
  - nombre: deck de clase
    clases: [beamer]
    prompt: 10 redaccion/prompt_03_redaccion.md
    pide: Escribir las láminas de la sección.
    vuelta: ['Cada lámina, un frame.']
  - nombre: hoja
    clases: [academic-report]
    ordenes: {tipodocumento: [Hoja Cornell]}
    prompt: 10 redaccion/prompt_03_redaccion.md
"""

DECK = ("\\documentclass{beamer}\n\\title{La clase}\n\\begin{document}\n\\begin{frame}\\titlepage\\end{frame}\n"
        "\\section{Activación}\n\\begin{frame}{Una pregunta}\nTexto.\n\\end{frame}\n\n"
        "\\section[Corto]{El \\emph{modelo} lineal}\\label{sec:m}\n\\begin{frame}{Dato}\n\\includegraphics{x}\n\\end{frame}\n"
        "\\end{document}\n")


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def marco(tmp_path):
    d = tmp_path / "sesion"
    d.mkdir()
    (d / "sesion.yml").write_text("titulo: La sesión de prueba\nduracion_min: 90\n", encoding="utf-8")
    (d / "deck.tex").write_text(DECK, encoding="utf-8")
    (d / "hoja.tex").write_text("\\documentclass{academic-report}\n\\tipodocumento{Hoja cornell}\n\\begin{document}\n"
                                "\\section*{Cómo se usa}\nTexto.\n\\end{document}\n", encoding="utf-8")
    (d / "examen.tex").write_text("\\documentclass{academic-exam}\n\\begin{document}\n\\section{P}\nx\n\\end{document}\n",
                                  encoding="utf-8")
    cuadro = tmp_path / "ayuda-ia.yml"
    cuadro.write_text(CUADRO, encoding="utf-8")
    consulta = _cargar("t_consulta_marco", REPO / "lib" / "consulta.py")
    if consulta._ayuda().comun() is None:
        pytest.skip("sin core/py-common/ia_externa.py")
    return d, str(cuadro), consulta


def test_las_secciones_son_las_partes(marco):
    _d, _c, consulta = marco
    ts = consulta._ayuda().secciones(DECK)
    assert [(t["clave"], t["titulo"]) for t in ts] == [("activacion", "Activación"), ("el-modelo-lineal", "El modelo lineal")]
    assert DECK[ts[1]["ini"]:ts[1]["fin"]].startswith("\n\\begin{frame}{Dato}"), "la línea de la sección (y su \\label) queda fuera"
    assert not DECK[ts[1]["ini"]:ts[1]["fin"]].rstrip().endswith("\\end{document}")


def test_el_cuadro_elige_el_prompt_y_pone_el_contexto(marco):
    d, cuadro, consulta = marco
    p = consulta.prompt_parte(d, "deck.tex", "el-modelo-lineal", cuadro=cuadro)
    assert p["fuente"]["ruta"] == "10 redaccion/prompt_03_redaccion.md" and p["documento"] == "deck de clase"
    assert p["componente"] == "el-modelo-lineal" and len(p["componentes"]) == 2
    assert "Escribir las láminas de la sección." in p["prompt"] and "La sesión de prueba" in p["prompt"]
    assert "- Cada lámina, un frame." in p["prompt"] and "«La clase»" in p["prompt"]
    hoja = consulta.prompt_parte(d, "hoja.tex", cuadro=cuadro)            # la orden se compara sin mayúsculas
    assert hoja["documento"] == "hoja" and hoja["componente"] == "como-se-usa"
    with pytest.raises(ValueError, match="Sus preguntas van al banco"):
        consulta.prompt_parte(d, "examen.tex", cuadro=cuadro)
    (d / "otro.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\section{A}\n\\end{document}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no tiene prompt en el cuadro"):
        consulta.prompt_parte(d, "otro.tex", cuadro=cuadro)


def test_sin_cuadro_sigue_pidiendo_un_escrito(marco):
    d, _cuadro, consulta = marco
    with pytest.raises(SystemExit):
        consulta.prompt_parte(d, "deck.tex")


def test_lo_pegado_se_comprueba_con_la_regla_comun(marco):
    d, cuadro, consulta = marco
    pegado = "```latex\n% componente: activacion\n\\begin{frame}{Una pregunta que abre}\nOtra.\n\\end{frame}\n```"
    r = consulta.pegar_parte(d, "deck.tex", pegado, "activacion", cuadro=cuadro)
    assert r["ok"], r["errores"]
    assert "Una pregunta que abre" in r["despues"] and r["antes"].strip().startswith("\\begin{frame}{Una pregunta}")
    otra = consulta.pegar_parte(d, "deck.tex", pegado, "no-existe", cuadro=cuadro)
    assert not otra["ok"] and "ni esa sección" in otra["errores"][0]
    assert (d / "deck.tex").read_text(encoding="utf-8") == DECK, "pegar no escribe"
