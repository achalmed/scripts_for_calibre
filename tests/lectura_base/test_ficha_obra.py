"""La ficha de obra de Yachay en la base de lectura (decisiones §9.13): la ida por la entidad `ficha_obra` de la ruta de
cambios, con su propio cursor, y la vuelta con `version_base` (simula; un 409 no pisa nada). Sobre el mundo de juguete
de conftest.py, con un Yachay falso en memoria: nada contra el Yachay real."""
from __future__ import annotations

import json
import sqlite3

import pytest

from lectura_base.lib import base, consulta, ficha_obra, sincronizar


class ErrorFalso(Exception):
    """La forma de `ErrorYachay` y `Conflicto` del cliente: `estado`, `mensaje`, `detalle` y, en un 409, `actual`."""

    def __init__(self, estado, mensaje, detalle=None):
        super().__init__(mensaje)
        self.estado, self.mensaje, self.detalle = estado, mensaje, detalle
        d = detalle if isinstance(detalle, dict) else {}
        self.codigo, self.version, self.actual = d.get("codigo", ""), d.get("version"), d.get("actual")


VACIA = {"pregunta": "", "metodo": "", "datos": "", "hallazgo": "", "limites": "", "uso": "", "temas": [], "signo": ""}
TITULOS = {"pregunta": "Pregunta", "metodo": "Método", "datos": "Datos", "hallazgo": "Hallazgo", "limites": "Límites",
           "uso": "Uso que le daré"}


class YachayFalso:
    """Lo que el cliente de Yachay hace con la ficha de obra (`cambios` con `entidades`, `guardar_ficha_obra`,
    `dar_por_leida`) y los resaltados, en memoria. Cada escritura sube la versión y la pone al final de la cola."""

    def __init__(self):
        self.obras: dict[int, dict] = {}         # calibre_id → {id, ficha, version, leida_en, _orden}
        self.bajas: list[tuple[int, int]] = []   # (_orden, id)
        self.n, self.puts, self.pedidas = 0, [], []

    def _orden(self) -> int:
        self.n += 1
        return self.n

    def poner(self, calibre_id, **respuestas):
        """Lo que la persona escribe en Yachay (la web)."""
        o = self.obras.setdefault(calibre_id, {"id": 40 + calibre_id, "ficha": dict(VACIA), "version": 0, "leida_en": None})
        o["ficha"] = {**o["ficha"], **respuestas}
        o["version"] += 1
        o["_orden"] = self._orden()

    def _datos(self, cid, o):
        f = o["ficha"]
        return {"id": o["id"], "calibre_id": cid, "ficha": dict(f), "secciones": {TITULOS[k]: f[k] for k in TITULOS},
                "escritas": sum(1 for k in TITULOS if f[k]), "total": 6, "leida": o["leida_en"] is not None,
                "leida_en": o["leida_en"], "version": o["version"], "creado_en": "2026-11-19T10:00:00+00:00",
                "actualizado_en": "2026-11-19T11:00:00+00:00"}

    def cambios(self, desde="0", entidades=None, limite=500):
        self.pedidas.append((str(desde), entidades))
        desde = int(desde or 0)
        cambios = []
        if not entidades or "ficha_obra" in entidades:
            for cid, o in self.obras.items():
                if o["_orden"] > desde:
                    cambios.append({"orden": o["_orden"], "entidad": "ficha_obra", "clave": str(o["id"]), "accion": "alta",
                                    "version": o["version"], "datos": self._datos(cid, o)})
            for orden, ident in self.bajas:
                if orden > desde:
                    cambios.append({"orden": orden, "entidad": "ficha_obra", "clave": str(ident), "accion": "baja", "datos": None})
        cambios.sort(key=lambda c: c["orden"])
        return {"cursor": str(max([desde] + [c["orden"] for c in cambios])), "mas": False, "reiniciar": False, "cambios": cambios}

    def guardar_ficha_obra(self, obra, **respuestas):
        self.puts.append(obra)
        cid = int(obra["calibre_id"])
        o = self.obras.get(cid)
        version = o["version"] if o else 0
        if int(obra.get("version") or 0) != version:
            raise ErrorFalso(409, "Esta lectura cambió en otra pestaña: revise lo actual y vuelva a guardar.",
                             {"codigo": "lectura_modificada", "version": version,
                              "actual": {"ficha": dict(o["ficha"]), "version": version, "leida_en": o["leida_en"]}})
        o = self.obras.setdefault(cid, {"id": 40 + cid, "ficha": dict(VACIA), "version": 0, "leida_en": None})
        o["ficha"] = {**VACIA, **{k: v for k, v in obra["ficha"].items() if k in VACIA}, **respuestas}
        o["version"] += 1
        o["_orden"] = self._orden()
        return {"ficha": dict(o["ficha"]), "version": o["version"], "leida_en": o["leida_en"], "revision": {}, "aviso": ""}

    def dar_por_leida(self, calibre_id, leida=True):
        o = self.obras[int(calibre_id)]
        faltan = [k for k in TITULOS if not o["ficha"][k]]
        if faltan:
            raise ErrorFalso(422, "Para darla por leída, responda con sus palabras: " + ", ".join(faltan) + ".",
                             {"codigo": "ficha_incompleta", "faltan": faltan})
        o["leida_en"] = "2026-11-19T12:00:00+00:00"
        o["version"] += 1
        o["_orden"] = self._orden()
        return {"ficha": dict(o["ficha"]), "version": o["version"], "leida_en": o["leida_en"]}


SEIS = {"pregunta": "Por qué crecen las ciudades pequeñas del sur andino según su vínculo con la región.",
        "metodo": "Compara series de empleo de distritos con y sin carretera asfaltada durante dos décadas.",
        "datos": "Censos nacionales y encuestas de hogares entre 1993 y 2017, a nivel distrital.",
        "hallazgo": "Las conectadas a mercados vecinos crecen más, con independencia de su tamaño inicial.",
        "limites": "No separa la carretera de otras inversiones públicas hechas al mismo tiempo.",
        "uso": "Para el marco del informe: la conectividad como condición del crecimiento local."}


def _sincronizar(cliente, aplicar=True):
    return sincronizar.sincronizar(("yachay",), aplicar=aplicar, cliente=cliente)[0]


def test_la_ida_trae_la_ficha_de_obra_con_su_propio_cursor(mundo):
    y = YachayFalso()
    y.poner(1, **SEIS, temas=["conectividad", "empleo"], signo="positivo")
    y.poner(2)                                                  # una lectura sin ficha (pasadas o mapa)
    simulada = _sincronizar(y, aplicar=False)
    assert simulada.fichas_obra["altas"] == 2 and not mundo.lectura_db.exists(), "simular no escribe"
    plan = _sincronizar(y)
    assert plan.fichas_obra == {"altas": 2, "cambios": 0, "bajas": 0}
    assert ("0", ["ficha_obra"]) in y.pedidas, "las fichas se piden solas, desde su cursor"
    assert base.leer_cursor(sincronizar.CONSUMIDOR_FICHAS) == 2
    f = consulta.ficha_obra_de(1)
    assert f["ficha"]["hallazgo"] == SEIS["hallazgo"] and f["ficha"]["temas"] == ["conectividad", "empleo"]
    assert f["secciones"]["Uso que le daré"] == SEIS["uso"] and f["escritas"] == 6 and f["version"] == 1 and f["origen_id"] == "41"
    assert consulta.ficha_obra_de(2) is None, "una lectura sin ficha no se muestra"
    assert base.ficha_obra(2)["version"] == 1, "pero se guarda: su versión es la que una vuelta manda"
    assert [x["calibre_id"] for x in consulta.fichas_obra()] == [1]
    assert consulta.libro(1)["ficha_obra"]["version"] == 1
    assert _sincronizar(y).vacio(), "la segunda vuelta no trae nada"
    cola = [c for c in base.cambios_desde(0)["cambios"] if c["tabla"] == "fichas_obra"]
    assert len(cola) == 2 and cola[0]["datos"]["ficha"]["signo"] == "positivo"


def test_un_cambio_y_una_baja_en_yachay_llegan(mundo):
    y = YachayFalso()
    y.poner(1, **SEIS)
    _sincronizar(y)
    y.poner(1, hallazgo="Crecen más las conectadas, aunque el efecto se diluye tras diez años.")
    assert _sincronizar(y).fichas_obra["cambios"] == 1
    assert base.ficha_obra(1)["version"] == 2
    y.bajas.append((y._orden(), 41))
    assert _sincronizar(y).fichas_obra["bajas"] == 1
    assert base.ficha_obra(1) is None and consulta.fichas_obra() == []


def test_la_vuelta_simula_y_dice_que_enviaria(mundo):
    y = YachayFalso()
    y.poner(1, **{k: v for k, v in SEIS.items() if k != "limites"})
    _sincronizar(y)
    p = ficha_obra.plan(1, {"Límites": SEIS["limites"], "temas": "conectividad; empleo"})
    assert p["version_base"] == 1 and p["cambian"] == ["Límites", "Temas"] and not p["faltan"] and not p["nueva"]
    assert p["ficha"]["hallazgo"] == SEIS["hallazgo"], "viaja la ficha entera: el PUT de Yachay la reemplaza"
    r = ficha_obra.llevar(p, y, aplicar=False)
    assert not r["escrita"] and y.puts == [], "simular no llama a Yachay"
    assert any("[simulación]" in x and "versión 1" in x for x in ficha_obra.texto(r))
    with pytest.raises(ValueError):
        ficha_obra.plan(1, {"signo": "excelente"})
    with pytest.raises(ValueError):
        ficha_obra.plan(1, {"otra": "cosa"})


def test_la_vuelta_escribe_con_version_base_y_la_base_queda_al_dia(mundo):
    y = YachayFalso()
    y.poner(1, **{k: v for k, v in SEIS.items() if k != "limites"})
    _sincronizar(y)
    r = ficha_obra.llevar(ficha_obra.plan(1, {"limites": SEIS["limites"]}, leida=True), y, aplicar=True)
    assert r["escrita"] and y.puts[-1]["version"] == 1 and y.puts[-1]["ficha"]["limites"] == SEIS["limites"]
    assert r["leida_en"], "con las seis, se dio por leída"
    f = base.ficha_obra(1)
    assert f["version"] == y.obras[1]["version"] == 3 and f["leida"] and f["ficha"]["limites"] == SEIS["limites"]
    assert f["origen_id"] == "41", "el id de Yachay se conserva aunque el PUT no lo devuelva"
    assert list((mundo.raiz / "respaldos").rglob("*.sqlite")), "antes de escribir la base, su respaldo"
    _sincronizar(y)
    assert base.ficha_obra(1)["version"] == 3


def test_un_409_no_pisa_y_deja_elegir(mundo):
    y = YachayFalso()
    y.poner(1, **SEIS)
    _sincronizar(y)
    y.poner(1, hallazgo="Lo que la persona corrigió en Yachay después.")    # la base no lo sabe aún
    antes = sqlite3.connect(mundo.lectura_db).execute("select ficha, version from fichas_obra").fetchall()
    r = ficha_obra.llevar(ficha_obra.plan(1, {"uso": "Para la discusión, en contra."}), y, aplicar=True)
    assert r["codigo"] == "lectura_modificada" and not r["escrita"] and r["version"] == 2
    assert r["actual"]["ficha"]["hallazgo"].startswith("Lo que la persona")
    assert y.obras[1]["ficha"]["uso"] == SEIS["uso"], "Yachay no cambió"
    assert sqlite3.connect(mundo.lectura_db).execute("select ficha, version from fichas_obra").fetchall() == antes, "la base tampoco"
    assert any("--sobre 2" in x for x in ficha_obra.texto(r))
    # elegir la suya: sobre la versión actual (viaja la ficha que la persona tiene, con su respuesta encima)
    r = ficha_obra.llevar(ficha_obra.plan(1, {"uso": "Para la discusión, en contra."}, sobre=2), y, aplicar=True)
    assert r["escrita"] and y.obras[1]["ficha"]["uso"] == "Para la discusión, en contra."
    # o quedarse con la de Yachay: la sincronía la trae
    y.poner(1, hallazgo="Otra vez cambiada en Yachay.")
    _sincronizar(y)
    assert base.ficha_obra(1)["ficha"]["hallazgo"] == "Otra vez cambiada en Yachay."


def test_dar_por_leida_incompleta_guarda_y_dice_que_falta(mundo):
    y = YachayFalso()
    r = ficha_obra.llevar(ficha_obra.plan(2, {"pregunta": SEIS["pregunta"]}, leida=True), y, aplicar=True)
    assert r["escrita"] and r["nueva"] and y.puts[-1]["version"] == 0
    assert r["leida_error"] and "Método" in r["faltan"], r
    assert base.ficha_obra(2)["ficha"]["pregunta"] == SEIS["pregunta"] and not base.ficha_obra(2)["leida"]


def test_sin_cliente_no_se_aplica(mundo):
    with pytest.raises(ficha_obra.SinCanal):
        ficha_obra.llevar(ficha_obra.plan(1, {"pregunta": "x"}), None, aplicar=True)


def test_la_cli_simula_y_un_409_sale_4(mundo, monkeypatch, capsys):
    from lectura_base import main as cli
    from lectura_base.lib.adaptadores import yachay as ad_yachay
    y = YachayFalso()
    y.poner(1, **SEIS)
    monkeypatch.setattr(ad_yachay, "cargar_cliente", lambda: y)
    _sincronizar(y)
    assert cli.main(["ficha", "1"]) == 0
    assert "Ficha de obra en Yachay" in capsys.readouterr().out
    assert cli.main(["ficha-a-yachay", "1", json.dumps({"Hallazgo": "Dicho de otro modo por la persona."})]) == 0
    assert "[simulación]" in capsys.readouterr().out and not y.puts
    y.poner(1, metodo="Cambiado en Yachay.")
    assert cli.main(["ficha-a-yachay", "1", json.dumps({"hallazgo": "Dicho de otro modo."}), "--aplicar", "--json"]) == 4
    assert json.loads(capsys.readouterr().out)["codigo"] == "lectura_modificada"


def test_el_esquema_viejo_gana_la_tabla_sin_perder_nada(mundo):
    """Una base del esquema 1 (sin `fichas_obra`) se abre y gana la tabla: la migración es aditiva."""
    from lectura_base.lib import base as b
    b.importar([b.Lectura("koreader", anotaciones=[{"origen_id": "k1", "calibre_id": 1, "hoja": 1, "texto": "Uno.",
                                                    "rects": [[1, 0.1, 0.1, 0.5, 0.02]]}], alcance=None)], aplicar=True)
    with sqlite3.connect(mundo.lectura_db) as c:
        c.execute("DROP TABLE fichas_obra")
        c.execute("PRAGMA user_version = 1")
    b.conectar(mundo.lectura_db, escribir=True).close()
    with sqlite3.connect(mundo.lectura_db) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == b.ESQUEMA      # aditivas: 2 (fichas_obra) y 3 (posicion)
        assert c.execute("select count(*) from anotaciones").fetchone()[0] == 1
        assert c.execute("select count(*) from fichas_obra").fetchone()[0] == 0
