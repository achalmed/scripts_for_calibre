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
    assert [t["clave"] for t in fichado.formulario["tipos"]] == ["textual", "parafrasis", "sintesis", "fuente", "obra"]
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


class CanalFalso:
    """La CLI de la ficha de obra en Yachay (`ficha-a-yachay`, `sincronizar --origen yachay`), en memoria: nada contra el
    Yachay real. La primera vez que se aplica responde un 409; sobre la versión que dio, acepta."""

    def __init__(self):
        self.llamadas = []

    def ficha_a_yachay(self, calibre_id, respuestas, aplicar, sobre=None):
        self.llamadas.append(("ficha", calibre_id, dict(respuestas), aplicar, sobre))
        plan = {"calibre_id": calibre_id, "ficha": {"limites": respuestas.get("Límites", "")}, "version_base": sobre if sobre is not None else 3,
                "cambian": ["Límites"], "nueva": False, "leida": False, "faltan": [], "escrita": False}
        if not aplicar:
            return plan
        if sobre is None:
            return {**plan, "codigo": "lectura_modificada", "version": 4, "actual": {"ficha": {"limites": "Otra cosa"}, "version": 4}}
        return {**plan, "escrita": True, "version": sobre + 1, "aviso": ""}

    def sincronizar_yachay(self):
        self.llamadas.append(("sincronizar",))
        return {"ok": True, "error": ""}


@requiere_binding
def test_la_vuelta_a_yachay_simula_choca_y_deja_elegir(app, entorno):
    """«Nueva ficha» de obra ofrece llevarla a Yachay (§9.13): simula (qué y sobre qué versión), un 409 no pisa y trae la
    versión actual, y la persona elige llevar la suya sobre ella o quedarse con la de Yachay. Todo por el canal (la CLI)."""
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichado import CanalYachay, Fichado
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    assert hasattr(CanalYachay, "ficha_a_yachay") and hasattr(CanalYachay, "sincronizar_yachay")
    consola = Consola()
    libros = Libros(Espacio(consola, Ajustes()), consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    canal = CanalFalso()
    fichado = Fichado(libros, consola, entorno.raiz / "cache" / "fichado", canal=canal)
    vistos = []
    fichado.yachay.connect(lambda r: vistos.append(dict(r)))
    fichado._calibre_id = 1
    secciones = {"Límites": "No separa la carretera de otras obras del mismo año."}
    fichado.simularYachay(secciones)
    _esperar(app, fichado)
    assert vistos[-1]["accion"] == "simular" and vistos[-1]["version_base"] == 3 and canal.llamadas[-1][3] is False
    fichado.llevarAYachay(secciones, -1)
    _esperar(app, fichado)
    assert vistos[-1]["codigo"] == "lectura_modificada" and vistos[-1]["version"] == 4 and canal.llamadas[-1][4] is None
    fichado.llevarAYachay(secciones, 4)                 # «Llevar la mía sobre la versión 4»
    _esperar(app, fichado)
    assert vistos[-1]["escrita"] and vistos[-1]["version"] == 5 and canal.llamadas[-1][3:] == (True, 4)
    fichado.quedarseConYachay()                         # o «Quedarme con la de Yachay»: la sincronía, nada se envía
    _esperar(app, fichado)
    assert vistos[-1]["accion"] == "quedarse" and vistos[-1]["ok"] and canal.llamadas[-1] == ("sincronizar",)


def test_el_canal_simula_por_la_cli_sobre_la_base_de_la_muestra(entorno):
    """El canal de verdad, sin `--aplicar`: la CLI solo lee la base de la muestra (no carga el cliente ni el token)."""
    import sys
    sys.path.insert(0, str(REPO))
    from lectura_base.lib import consulta
    from biblioteca_app.controladores.fichado import CanalYachay
    obra = consulta.fichas_obra()[0]
    r = CanalYachay().ficha_a_yachay(obra["calibre_id"], {"Límites": "No separa la carretera de otras obras del mismo año."}, False)
    assert not r.get("error"), r
    assert r["version_base"] == 3 and r["cambian"] == ["Límites"] and not r["escrita"] and r["faltan"] == []
    assert r["ficha"]["hallazgo"].startswith("Crecen las que se integran"), "viaja la ficha entera"


@requiere_binding
def test_corregir_una_ficha_de_obra_que_ya_existe_y_llevarla_a_yachay(app, entorno, monkeypatch):
    """Corregir desde el área Fichas (§9.13, nota del 2026-11-19): la ficha de obra que ya existe en el escrito se abre con
    su huella, la corrección se simula y se escribe por `guardar_ficha`, una huella vieja no pisa (`ficha_cambiada`) y la
    vuelta a Yachay es la misma (el canal, con el libro explícito)."""
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichado import Fichado
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    monkeypatch.setenv("PROMPTS_DIR", str(REPO.parent / "prompts"))
    consola = Consola()
    libros = Libros(Espacio(consola, Ajustes()), consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    canal = CanalFalso()
    fichado = Fichado(libros, consola, entorno.raiz / "cache" / "fichado", canal=canal)
    revisadas, leidas, yachay = [], [], []
    fichado.revisada.connect(lambda r: revisadas.append(dict(r)))
    fichado.corregible.connect(lambda r: leidas.append(dict(r)))
    fichado.yachay.connect(lambda r: yachay.append(dict(r)))
    fichado.preparar(1)
    _esperar(app, fichado)
    carpeta = fichado.escritos[0]["carpeta"]
    seis = {"Pregunta": "Si las ciudades chicas ganan algo al unirse a su región.", "Método": "Compara series de varias décadas.",
            "Datos": "Censos nacionales.", "Hallazgo": "Las que se unen a su región ganan más.",
            "Límites": "No separa el efecto de la carretera.", "Uso que le daré": "El marco del capítulo dos."}
    fichado.revisar(carpeta, {"tipo": "obra", "secciones": seis}, True)
    _esperar(app, fichado)
    assert revisadas[-1].get("escrito"), revisadas[-1]
    archivo = revisadas[-1]["archivo"]
    ruta = Path(carpeta) / "fuentes" / "fichas" / archivo
    assert archivo.endswith("-obra.md") and ruta.is_file()

    fichado.leerFicha(carpeta, str(ruta))                 # el área Fichas da la ruta entera
    _esperar(app, fichado)
    abierta = leidas[-1]
    assert not abierta.get("error") and abierta["tipo"] == "obra" and abierta["huella"]
    assert {s["titulo"]: s["texto"] for s in abierta["secciones"]}["Límites"] == seis["Límites"]

    corregidas = {**seis, "Límites": "No separa la carretera de otras obras del mismo año."}
    antes = ruta.read_text(encoding="utf-8")
    fichado.corregir(carpeta, archivo, abierta["huella"], {"secciones": corregidas, "uso": "", "tema": ""}, False)
    _esperar(app, fichado)
    sim = revisadas[-1]
    assert sim["correccion"] and not sim["escrito"] and not sim.get("error") and sim["archivo"] == archivo, sim
    assert ruta.read_text(encoding="utf-8") == antes, "simular no escribe"

    fichado.simularYachayDe(1, corregidas)                # la misma vuelta: qué cambia y sobre qué versión
    _esperar(app, fichado)
    assert yachay[-1]["accion"] == "simular" and canal.llamadas[-1][1] == 1 and canal.llamadas[-1][3] is False

    fichado.corregir(carpeta, archivo, abierta["huella"], {"secciones": corregidas, "uso": "", "tema": ""}, True)
    _esperar(app, fichado)
    assert revisadas[-1]["escrito"] and revisadas[-1]["correccion"]
    assert corregidas["Límites"] in ruta.read_text(encoding="utf-8")

    fichado.corregir(carpeta, archivo, abierta["huella"], {"secciones": seis, "uso": "", "tema": ""}, True)   # la huella vieja
    _esperar(app, fichado)
    assert revisadas[-1]["codigo"] == "ficha_cambiada" and revisadas[-1]["actual"]["huella"] != abierta["huella"]
    assert corregidas["Límites"] in ruta.read_text(encoding="utf-8"), "una huella vieja no pisa"

    fichado.llevarAYachayDe(1, corregidas, -1)            # y se lleva tras confirmar, con el libro explícito
    _esperar(app, fichado)
    assert yachay[-1]["codigo"] == "lectura_modificada" and canal.llamadas[-1][:2] == ("ficha", 1) and canal.llamadas[-1][3] is True


@requiere_binding
def test_corregir_la_de_yachay_sin_escrito_no_toca_ningun_escrito(app, entorno):
    """«Corregir…» de la ficha de obra en Yachay (§9.13): solo el canal, con el libro explícito y sin preparar el PDF ni
    elegir un escrito; ninguna ficha de un escrito cambia."""
    from gui_comun.consola import Consola
    from biblioteca_app.controladores.ajustes import Ajustes
    from biblioteca_app.controladores.espacio import Espacio
    from biblioteca_app.controladores.fichado import Fichado
    from biblioteca_app.controladores.libros import Libros
    from biblioteca_app.servicios import datos
    consola = Consola()
    libros = Libros(Espacio(consola, Ajustes()), consola, datos.cargar_env(), ruta_indice=entorno.indice, repo=entorno.repo)
    canal = CanalFalso()
    fichado = Fichado(libros, consola, entorno.raiz / "cache" / "fichado", canal=canal)
    vistos = []
    fichado.yachay.connect(lambda r: vistos.append(dict(r)))
    escritura = entorno.raiz / "escritura"                # el WRITING_DIR de la muestra
    antes = {p: p.stat().st_mtime_ns for p in escritura.rglob("fuentes/fichas/*.md")}
    assert antes, "la muestra tiene fichas en sus escritos"
    secciones = {"Límites": "No separa la carretera de otras obras del mismo año."}
    fichado.simularYachayDe(1, secciones)
    _esperar(app, fichado)
    assert vistos[-1]["accion"] == "simular" and fichado.calibreId == 0, "no prepara el libro: el diálogo de ficha sigue igual"
    fichado.llevarAYachayDe(1, secciones, 4)
    _esperar(app, fichado)
    assert vistos[-1]["escrita"] and canal.llamadas[-1] == ("ficha", 1, secciones, True, 4)
    assert {p: p.stat().st_mtime_ns for p in escritura.rglob("fuentes/fichas/*.md")} == antes
