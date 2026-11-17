"""Los adaptadores de ida y vuelta (KOReader, Zotero, Okular, Yachay) sobre el mundo de juguete de conftest.py."""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

import pytest

from juguete_lectura import ALTO, ANCHO, estadisticas_koreader, ko_resaltado, rect_de_linea, sidecar_koreader, zotero_anotacion
from lectura_base.lib import base, consulta, exportar, lua, sincronizar
from lectura_base.lib.adaptadores import koreader, okular, zotero
from lectura_base.lib.biblioteca import Resolutor

HAY_POPPLER = shutil.which("pdfinfo") is not None and shutil.which("pdftotext") is not None
requiere_poppler = pytest.mark.skipif(not HAY_POPPLER, reason="sin pdfinfo/pdftotext (poppler-utils)")


def _zotero_abierto() -> bool:
    salida = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
    return any(l.strip().lower().startswith("zotero") for l in salida.splitlines())


@pytest.fixture
def con_koreader(mundo):
    sidecar_koreader(mundo.koreader, mundo.md5_1, mundo.pdf1, [
        ko_resaltado(1, 100, "La producti-\nvidad es casi todo en el largo plazo.", "2026-03-11 12:31:04", nota="clave"),
        ko_resaltado(2, 150, "Las instituciones reducen la incertidumbre economica.", "2026-03-11 12:40:00"),
    ])
    estadisticas_koreader(mundo.koreader / "settings" / "statistics.sqlite3", mundo.md5_1,
                          [(1, 1_000_000, 60), (2, 1_000_070, 120), (1, 1_010_000, 30)], total=210)
    return mundo


@requiere_poppler
def test_koreader_lee_resaltados_sesiones_y_progreso(con_koreader):
    lectura = koreader.leer(Resolutor())
    assert len(lectura.anotaciones) == 2
    a = lectura.anotaciones[0]
    assert a["calibre_id"] == 1 and a["hoja"] == 1 and a["nota"] == "clave" and a["color"] == "yellow"
    assert a["rects"][0][1] == pytest.approx(72 / ANCHO) and a["rects"][0][2] == pytest.approx(89 / ALTO)
    assert len(lectura.sesiones) == 2                         # la pausa de casi tres horas abre otra sesión
    assert lectura.sesiones[0]["segundos"] == 180 and lectura.sesiones[0]["paginas"] == 2
    g = lectura.progreso[0]
    assert g["fraccion"] == pytest.approx(0.42) and g["estado"] == "reading" and g["segundos"] == 210
    assert lectura.alcance == {"c1"}


@requiere_poppler
def test_zotero_lee_anotaciones_con_el_origen_arriba(mundo):
    zotero_anotacion(mundo.zotero_db, 11, "ANOT0001", "La productividad es casi todo en el largo plazo.", 1, 100, comentario="ok")
    lectura = zotero.leer(Resolutor())
    assert len(lectura.anotaciones) == 1
    a = lectura.anotaciones[0]
    assert a["calibre_id"] == 1 and a["hoja"] == 1 and a["nota"] == "ok"
    assert a["rects"][0][2] == pytest.approx((100 - 11) / ALTO)        # y desde arriba
    assert lectura.alcance == {"c1", "c2"}


@requiere_poppler
def test_lo_mismo_en_koreader_y_zotero_es_una_sola_anotacion(con_koreader):
    m = con_koreader
    zotero_anotacion(m.zotero_db, 11, "ANOT0001", "La productividad es casi todo en el largo plazo.", 1, 100)
    planes = sincronizar.sincronizar(("koreader", "zotero"), aplicar=True)
    assert len(planes[0].altas) == 2 and len(planes[1].uniones) == 1 and not planes[1].altas
    r = consulta.libro(1)
    assert len(r["anotaciones"]) == 2
    compartida = next(a for a in r["anotaciones"] if a["hoja"] == 1)
    assert compartida["vive_en"] == ["koreader", "zotero"]
    assert r["segundos"] == 210 and r["n_sesiones"] == 2
    # idempotente
    planes = sincronizar.sincronizar(("koreader", "zotero"), aplicar=True)
    assert all(p.vacio() for p in planes)


@requiere_poppler
def test_okular_lee_y_recorta_el_texto_del_pdf(mundo):
    r = rect_de_linea(1, 200)
    xml = mundo.docdata / f"{mundo.pdf1.stat().st_size}.{mundo.pdf1.name}.xml"
    xml.write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE documentInfo>
<documentInfo url="{mundo.pdf1}">
 <pageList><page number="0"><annotationList>
  <annotation type="4"><base creationDate="2026-11-10T09:00:00" modifyDate="2026-11-10T09:00:00" uniqueName="okular-abc"
     color="#ffffff00" contents="para la tesis" author="yo"><boundary l="{r[1]}" t="{r[2]}" r="{r[1] + r[3]}" b="{r[2] + r[4]}"/></base>
   <hl type="0"><quad ax="{r[1]}" ay="{r[2]}" bx="{r[1] + r[3]}" by="{r[2]}" cx="{r[1] + r[3]}" cy="{r[2] + r[4]}" dx="{r[1]}" dy="{r[2] + r[4]}" feather="1"/></hl>
  </annotation>
 </annotationList></page></pageList>
 <generalInfo><history><current viewport="1;C2:0.5:0.5:1"/></history></generalInfo>
</documentInfo>''', encoding="utf-8")
    lectura = okular.leer(Resolutor())
    assert len(lectura.anotaciones) == 1
    a = lectura.anotaciones[0]
    assert "acumulacion de capital" in a["texto"] and a["nota"] == "para la tesis" and a["color"] == "#ffffff00"
    assert lectura.progreso[0]["hoja"] == 2


@requiere_poppler
def test_exportar_a_zotero_por_la_puerta_y_no_duplicar(con_koreader):
    if _zotero_abierto():
        pytest.skip("Zotero está abierto: la puerta no deja escribir (ni siquiera en la copia de juguete)")
    m = con_koreader
    sincronizar.sincronizar(("koreader",), aplicar=True)
    simulado = exportar.exportar("zotero")
    assert len(simulado["plan"]) == 2 and not simulado["hechas"]
    with sqlite3.connect(m.zotero_db) as c:
        assert c.execute("select count(*) from itemAnnotations").fetchone()[0] == 0          # simular no escribe
    hecho = exportar.exportar("zotero", aplicar=True)
    assert len(hecho["hechas"]) == 2
    with sqlite3.connect(m.zotero_db) as c:
        filas = c.execute("select n.type, n.text, n.comment, n.position, i.synced from itemAnnotations n join items i using (itemID)").fetchall()
        assert len(filas) == 2 and all(f[4] == 0 for f in filas)           # sin sincronizar: la cuenta las sube
        assert c.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert list((m.raiz / "respaldos" / "lectura_base" / "zotero").glob("zotero_*")), "sin respaldo verificado de Zotero"
    # lo escrito vuelve como la misma anotación
    planes = sincronizar.sincronizar(("zotero",), aplicar=True)
    assert not planes[0].altas and not planes[0].uniones
    assert exportar.exportar("zotero")["plan"] == []
    # y los rectángulos van y vuelven
    vuelta = zotero.leer(Resolutor()).anotaciones
    ida = next(a for a in koreader.leer(Resolutor()).anotaciones if a["hoja"] == 1)
    z = next(a for a in vuelta if a["hoja"] == 1)
    assert z["rects"][0][1:] == pytest.approx(ida["rects"][0][1:], abs=1e-3)


@requiere_poppler
def test_koreader_y_okular_no_se_escriben_con_la_aplicacion_abierta(con_koreader, monkeypatch):
    """Aprobados por el autor (§9.7, 2026-11-17), pero solo con la herramienta cerrada: al cerrar un libro, KOReader y
    Okular reescriben su archivo con lo que tienen en memoria y borrarían lo escrito."""
    m = con_koreader
    zotero_anotacion(m.zotero_db, 11, "ANOT0003", "El crecimiento depende de la acumulacion de capital.", 1, 200)
    sincronizar.sincronizar(("koreader", "zotero"), aplicar=True)
    assert {"zotero", "koreader", "okular"} <= exportar.ESCRIBE and "yachay" not in exportar.ESCRIBE
    sidecar = m.koreader / "hashdocsettings" / m.md5_1[:2] / f"{m.md5_1}.sdr" / "metadata.pdf.lua"
    antes = sidecar.read_bytes()
    monkeypatch.setattr(koreader, "abierto", lambda: True)
    monkeypatch.setattr(okular, "abierto", lambda: True)
    with pytest.raises(RuntimeError, match="abierto"):
        exportar.exportar("koreader", aplicar=True)
    with pytest.raises(RuntimeError, match="abierto"):
        exportar.exportar("okular", aplicar=True)
    assert sidecar.read_bytes() == antes and not list(m.docdata.glob("*.xml"))
    with pytest.raises(PermissionError):
        exportar.exportar("yachay", aplicar=True)


@requiere_poppler
def test_escribir_en_koreader_deja_el_sidecar_legible_y_reconocible(con_koreader, monkeypatch):
    """Respalda, escribe atómico, en orden de lectura, y lo escrito vuelve como la misma anotación."""
    m = con_koreader
    monkeypatch.setattr(koreader, "abierto", lambda: False)
    zotero_anotacion(m.zotero_db, 11, "ANOT0003", "El crecimiento depende de la acumulacion de capital.", 1, 200)
    sincronizar.sincronizar(("koreader", "zotero"), aplicar=True)
    assert len(exportar.exportar("koreader")["plan"]) == 1
    hecho = exportar.exportar("koreader", aplicar=True)
    assert len(hecho["hechas"]) == 1
    sidecar = m.koreader / "hashdocsettings" / m.md5_1[:2] / f"{m.md5_1}.sdr" / "metadata.pdf.lua"
    datos = lua.leer(sidecar.read_bytes())
    assert len(datos["annotations"]) == 3 and datos["stats"]["highlights"] == 3
    assert [a["page"] for a in datos["annotations"].values()] == [1, 1, 2]       # en orden de lectura
    assert list((m.raiz / "respaldos" / "lectura" / "koreader").glob("*.lua"))
    planes = sincronizar.sincronizar(("koreader",), aplicar=True)
    assert not planes[0].altas and not planes[0].uniones
    assert exportar.exportar("koreader")["plan"] == []


@requiere_poppler
def test_escribir_en_okular_crea_su_docdata_y_lo_reconoce(con_koreader, monkeypatch):
    m = con_koreader
    monkeypatch.setattr(okular, "abierto", lambda: False)
    sincronizar.sincronizar(("koreader",), aplicar=True)
    assert len(exportar.exportar("okular")["plan"]) == 2
    exportar.exportar("okular", aplicar=True)
    xml = m.docdata / okular.nombre_docdata(m.pdf1)
    raiz = ET.parse(xml).getroot()
    assert raiz.get("url") == str(m.pdf1) and len(list(raiz.iter("annotation"))) == 2
    leidas = okular.leer(Resolutor()).anotaciones
    assert all(a.get("uid_base") for a in leidas)                  # lo que escribió la base se reconoce por su uid
    planes = sincronizar.sincronizar(("okular",), aplicar=True)
    assert not planes[0].altas and not planes[0].uniones and not planes[0].ausentes
    assert exportar.exportar("okular")["plan"] == []


@requiere_poppler
def test_okular_sin_texto_recortable_no_se_pierde(mundo):
    """Un resaltado sobre un escaneo (o una franja que pdftotext no recorta) sigue siendo un resaltado: basta su lugar."""
    xml = mundo.docdata / f"{mundo.pdf1.stat().st_size}.{mundo.pdf1.name}.xml"
    xml.write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<documentInfo url="{mundo.pdf1}"><pageList><page number="0"><annotationList>
  <annotation type="4"><base uniqueName="okular-0123456789abcdef" creationDate="2026-11-10T09:00:00"><boundary l="0.1" t="0.9" r="0.2" b="0.92"/></base>
   <hl type="0"><quad ax="0.1" ay="0.9" bx="0.2" by="0.9" cx="0.2" cy="0.92" dx="0.1" dy="0.92" feather="1"/></hl></annotation>
</annotationList></page></pageList></documentInfo>''', encoding="utf-8")
    a, = okular.leer(Resolutor()).anotaciones
    assert a["texto"] == "" and a["rects"] and a["uid_base"] == "0123456789abcdef"


@requiere_poppler
def test_las_hojas_giradas_no_se_exportan(con_koreader, monkeypatch):
    """En una hoja girada cada herramienta mide los rectángulos a su modo: lo de ahí se queda en la base, con su aviso."""
    sincronizar.sincronizar(("koreader",), aplicar=True)
    monkeypatch.setattr(exportar, "giros", lambda pdf: [90, 0])
    r = exportar.exportar("okular")
    assert [p["hoja"] for p in r["plan"]] == [2]
    assert any("giradas" in x for x in r["avisos"])


class ClienteFalso:
    """La forma del cliente de Yachay de la fase 3b (`cambios`, `resaltar`), en memoria."""

    def __init__(self):
        self.resaltados, self.n = [], 500

    def cambios(self, desde="0"):
        filas = [r for r in self.resaltados if r["_orden"] > int(desde or 0)]
        cambios = [{"orden": r["_orden"], "entidad": "resaltado", "clave": str(r["id"]), "accion": "alta",
                    "datos": {k: v for k, v in r.items() if not k.startswith("_")}} for r in filas]
        return {"cursor": str(max([int(desde or 0)] + [r["_orden"] for r in filas])), "mas": False, "reiniciar": False, "cambios": cambios}

    def resaltar(self, calibre_id, hoja, rects, seleccion, intencion, nota, origen, origen_id):
        self.n += 1
        self.resaltados.append({"_orden": self.n, "id": self.n, "calibre_id": calibre_id, "hoja": hoja, "rects": rects, "texto": seleccion,
                                "intencion": intencion, "nota": nota, "origen": origen, "origen_id": origen_id, "lugar": ""})
        return {"id": self.n}


@requiere_poppler
def test_yachay_por_su_cliente_ida_y_vuelta(con_koreader):
    cliente = ClienteFalso()
    cliente.resaltados.append({"_orden": 1, "id": 7, "calibre_id": 2, "hoja": 1, "rects": [rect_de_linea(1, 100)],
                               "texto": "La productividad es casi todo en el largo plazo.", "intencion": "cita", "nota": "",
                               "origen": "propio", "origen_id": "", "lugar": "12"})
    planes = sincronizar.sincronizar(("koreader", "yachay"), aplicar=True, cliente=cliente)
    assert len(planes[1].altas) == 1                        # el resaltado propio de Yachay entra a la base
    assert base.leer_cursor(sincronizar.CONSUMIDOR_YACHAY) == 1
    plan = exportar.exportar("yachay")["plan"]
    assert len(plan) == 2 and {p["cuerpo"]["origen"] for p in plan} == {"koreader"}
    exportar.aplicar_yachay(plan, cliente)
    planes = sincronizar.sincronizar(("yachay",), aplicar=True, cliente=cliente)
    assert not planes[0].altas and not planes[0].uniones   # lo que se le dio vuelve como la misma anotación
    assert exportar.exportar("yachay")["plan"] == []


def test_yachay_sin_cliente_avisa_y_sigue(mundo):
    planes = sincronizar.sincronizar(("yachay",))
    assert planes[0].avisos and "fase 3b" in planes[0].avisos[0]


def test_lua_ida_y_vuelta_byte_a_byte():
    texto = ('-- /ruta/libro (3)/libro.pdf\nreturn {\n    ["annotations"] = {\n        [1] = {\n            ["note"] = "línea\\\n'
             'otra \\"cita\\"",\n            ["page"] = 6,\n            ["x"] = 13.618041992188,\n        },\n    },\n'
             '    ["percent_finished"] = nan,\n    ["summary"] = {},\n}\n').encode("utf-8")
    datos = lua.leer(texto)
    assert datos["annotations"][1]["note"] == 'línea\notra "cita"'
    assert lua.escribir(datos, "/ruta/libro (3)/libro.pdf") == texto
