"""tests/studio/test_fichado.py — fichar desde la ficha de un libro y estudiarlo con la IA (decisiones §9.4 y §9.5), con
el controlador en proceso sobre la muestra: los escritos (primero los que usan el libro), el formulario, las miradas, la
revisión (simula) y el guardado (solo en fuentes/fichas/ del informe de muestra), y lo pegado de un estudio de obra.
Nunca la biblioteca ni la escritura reales; ningún modelo de IA."""
from __future__ import annotations

import time
from pathlib import Path

from conftest import HAY_CALIBREDB, requiere_binding

REPO = Path(__file__).resolve().parents[2]


def _esperar(app, fichado, segundos=60):
    inicio = time.monotonic()
    app.processEvents()
    while fichado.ocupado and time.monotonic() - inicio < segundos:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()


@requiere_binding
def test_fichar_un_libro_en_el_informe_de_muestra(app, entorno, monkeypatch):
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichado import Fichado
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    monkeypatch.setenv("PROMPTS_DIR", str(REPO.parent / "prompts"))
    monkeypatch.setenv("YACHAY_CODIGO", str(REPO.parent / "yachay"))
    consola = Consola()
    libros = Libros(Espacio(consola, Ajustes()), consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    fichado = Fichado(libros, consola, entorno.raiz / "cache" / "fichado")
    revisadas, pegados = [], []
    fichado.revisada.connect(lambda r: revisadas.append(dict(r)))
    fichado.pegadoObra.connect(lambda r: pegados.append(dict(r)))

    fichado.preparar(1)
    _esperar(app, fichado)
    assert fichado.escritos and fichado.escritos[0]["usa"] and fichado.escritos[0]["proyecto"] == "reports/2026-11-17-informe-de-muestra"
    assert [t["clave"] for t in fichado.formulario["tipos"]] == ["textual", "parafrasis", "sintesis", "fuente"]
    carpeta = fichado.escritos[0]["carpeta"]
    campos = {"tipo": "textual", "pagina": "12", "categoria": "Idea principal", "tema": "escala urbana",
              "secciones": {"Cita exacta": "Las ciudades pequeñas crecen cuando se integran a su región."}}
    fichado.revisar(carpeta, campos, False)
    _esperar(app, fichado)
    sim = revisadas[-1]
    assert not sim.get("error"), sim
    assert sim["archivo"] == "quispeEconomiaCiudades2021-p012-textual-escala-urbana.md" and not sim["escrito"]
    destino = Path(carpeta) / "fuentes" / "fichas" / sim["archivo"]
    assert not destino.exists(), "revisar no escribe"
    if HAY_CALIBREDB:
        assert sim["verificacion"]["estado"] == "verificada_script", sim["detalle"]
    fichado.revisar(carpeta, campos, True)
    _esperar(app, fichado)
    assert revisadas[-1]["escrito"] and destino.is_file()
    assert (Path(carpeta) / "fuentes" / "fichas" / "quispeEconomiaCiudades2021-fuente.md").is_file()

    if fichado.miradas:                                   # con el código de Yachay: el estudio de obra
        fichado.leerPegado("```yaml\ntipo: estudio-de-obra\nversion: 1\ndimension: obra_fichas\nafirmaciones: []\nfichas:\n"
                           "  - tipo: textual_simple\n    tema: escala\n    cita: u2\n    localizador: p. 12\n"
                           "    texto_citado: Las ciudades pequeñas crecen cuando se integran a su región.\n```")
        _esperar(app, fichado)
        r = pegados[-1]
        assert r["ok"] and r["fichas"][0]["clase"] == "textual" and r["fichas"][0]["pagina"] == "12"
        if HAY_CALIBREDB:
            assert r["fichas"][0]["verificacion"] == "verificada_script"
