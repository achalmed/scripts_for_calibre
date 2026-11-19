"""La posición en un libro de flujo (esquema 3, decisiones §9.14): la columna `posicion`, su migración, los `pos0`/`pos1` de
KOReader en un EPUB y la vuelta a KOReader de lo que Ñawinchay anotó en un EPUB. Todo en el mundo de juguete."""
from __future__ import annotations

import shutil
import sqlite3

import pytest

from juguete_lectura import sidecar_koreader
from lectura_base.lib import base, exportar, lua, sincronizar
from lectura_base.lib.adaptadores import koreader

HAY_POPPLER = shutil.which("pdfinfo") is not None and shutil.which("pdftotext") is not None
requiere_poppler = pytest.mark.skipif(not HAY_POPPLER, reason="sin pdfinfo/pdftotext (poppler-utils)")

MD5_EPUB = "e" * 32
P0 = "/body/DocFragment[9]/body/p[1]/text().0"
P1 = "/body/DocFragment[9]/body/p[1]/text().28"
TEXTO = "ENTRE EL INSTINTO Y LA RAZÓN"


def _epub_ko(cuando="2026-03-11 12:31:04", texto=TEXTO, p0=P0, p1=P1) -> dict:
    return {"chapter": "Capítulo I", "color": "yellow", "datetime": cuando, "drawer": "lighten", "page": p0, "pageno": 31,
            "pos0": p0, "pos1": p1, "text": texto}


def _sidecar_epub(m, anotaciones):
    """Un sidecar de KOReader para el EPUB del libro 1 (`metadata.epub.lua`), junto al del PDF."""
    doc = m.pdf1.with_suffix(".epub")
    p = sidecar_koreader(m.koreader, MD5_EPUB, doc, anotaciones)
    epub = p.with_name("metadata.epub.lua")
    p.rename(epub)
    return epub


def _de_nawinchay(origen_id="nw-1", texto="La razón, en cambio, pesa las consecuencias.", **k) -> dict:
    return {"origen_id": origen_id, "calibre_id": 1, "md5": MD5_EPUB, "hoja": None, "capitulo": "Capítulo I", "texto": texto,
            "intencion": "concepto", "color": "#a28ae5", "nota": "", "modificada": "2026-11-19T10:00:00Z", "creada": "2026-11-19T10:00:00Z",
            "posicion": {"pos0": "/body/DocFragment[9]/body/p[2]/text().0", "pos1": "/body/DocFragment[9]/body/p[2]/text().44",
                         "cita": {"exacto": texto, "prefijo": "la razón. ", "sufijo": " Así"}, "inicio": 3, "fin": 47}, **k}


def test_nawinchay_es_un_origen_con_nombre_pero_no_se_lee_desde_aqui():
    assert "nawinchay" in base.ORIGENES and base.NOMBRES["nawinchay"] == "Ñawinchay"
    assert "nawinchay" in base.CLIENTES and "nawinchay" not in base.LEIDOS
    assert sincronizar.leer.__defaults__[0] == base.LEIDOS


def test_posicion_limpia_guarda_solo_lo_que_sirve():
    p = base.posicion_limpia({"pos0": P0, "pos1": P1, "inicio": 3, "xpointer": ["x"], "cita": {"exacto": "a", "otro": 1}})
    assert p == {"pos0": P0, "pos1": P1, "cita": {"exacto": "a"}}
    assert base.posicion_limpia({"pos0": "no es xpointer", "pos1": P1}) == {}
    assert base.posicion_limpia('{"pos0": "%s", "pos1": "%s"}' % (P0, P1)) == {"pos0": P0, "pos1": P1}
    assert base.posicion_limpia(None) == {} and base.posicion_limpia("roto{") == {}


def test_una_base_del_esquema_2_gana_la_columna_sin_perder_nada(mundo):
    ruta = mundo.lectura_db
    viejo = base.SQL_ESQUEMA.replace(",\n    posicion TEXT NOT NULL DEFAULT '{}'", "")
    assert "posicion" not in viejo.split("CREATE TABLE IF NOT EXISTS presencias")[0]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ruta) as c:
        c.executescript(viejo)
        c.execute("PRAGMA user_version = 2")
        c.execute("INSERT INTO anotaciones(uid, calibre_id, texto, huella) VALUES ('a1b2c3d4e5f60718', 1, 'hola', 'h')")
    with base.lector(ruta) as c:                       # el código nuevo lee una base vieja sin migrarla
        assert base.anotacion_publica(c, c.execute("SELECT * FROM anotaciones").fetchone())["posicion"] == {}
    base.conectar(ruta, escribir=True).close()
    with sqlite3.connect(ruta) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == base.ESQUEMA == 3
        assert c.execute("SELECT texto, posicion FROM anotaciones").fetchone() == ("hola", "{}")


def test_koreader_lee_pos0_y_pos1_de_un_epub(mundo):
    _sidecar_epub(mundo, [_epub_ko()])
    lectura = koreader.leer()
    a = next(x for x in lectura.anotaciones if x["md5"] == MD5_EPUB)
    assert a["calibre_id"] == 1 and a["hoja"] is None and a["posicion"] == {"pos0": P0, "pos1": P1}


def test_lo_de_koreader_visto_antes_del_esquema_3_gana_su_posicion_sin_contar_como_edicion(mundo):
    _sidecar_epub(mundo, [_epub_ko()])
    lectura = koreader.leer()
    sin_pos = base.Lectura("koreader", anotaciones=[dict(a, posicion={}) for a in lectura.anotaciones], alcance=lectura.alcance)
    base.importar([sin_pos], aplicar=True)             # así quedó en una base anterior
    plan = base.importar([koreader.leer()], aplicar=True)[0]
    assert plan.posiciones == 1 and not plan.cambios and not plan.altas and not plan.vacio()
    assert base.importar([koreader.leer()])[0].vacio()      # la segunda vez, nada
    with base.lector() as c:
        filas = c.execute("SELECT posicion FROM anotaciones WHERE md5 = ?", (MD5_EPUB,)).fetchall()
        assert [base.posicion_limpia(f[0]) for f in filas] == [{"pos0": P0, "pos1": P1}]
        assert not c.execute("SELECT count(*) FROM cambios WHERE operacion = 'cambio'").fetchone()[0]


def test_lo_de_nawinchay_se_une_con_su_posicion_y_un_vacio_no_la_borra(mundo):
    base.importar([base.Lectura("nawinchay", anotaciones=[_de_nawinchay()], alcance={"c1"})], aplicar=True)
    sin = _de_nawinchay(posicion={}, nota="releer", modificada="2026-11-19T11:00:00Z")
    plan = base.importar([base.Lectura("nawinchay", anotaciones=[sin], alcance={"c1"})], aplicar=True)[0]
    assert len(plan.cambios) == 1
    with base.lector() as c:
        a = base.anotacion_publica(c, c.execute("SELECT * FROM anotaciones").fetchone())
    assert a["nota"] == "releer" and a["posicion"]["pos1"].endswith("text().44") and a["posicion"]["cita"]["prefijo"]
    assert [o["origen"] for o in a["origenes"]] == ["nawinchay"]


@requiere_poppler
def test_lo_anotado_en_nawinchay_en_un_epub_vuelve_a_koreader(mundo, monkeypatch):
    """La vuelta: el sidecar del EPUB gana la entrada con sus xpointers y la marca para que KOReader pagine y ordene; la
    próxima lectura de KOReader la reconoce (presencia) y no la duplica ni la vuelve a exportar."""
    monkeypatch.setattr(koreader, "abierto", lambda: False)
    epub = _sidecar_epub(mundo, [_epub_ko()])
    base.importar([koreader.leer(), base.Lectura("nawinchay", anotaciones=[_de_nawinchay()], alcance={"c1"})], aplicar=True)
    antes = epub.read_bytes()
    plan = exportar.exportar("koreader")
    assert [(p["hoja"], p["sidecar"]) for p in plan["plan"]] == [(None, str(epub))]
    assert epub.read_bytes() == antes                                    # simular no escribe
    hecho = exportar.exportar("koreader", aplicar=True)
    assert len(hecho["hechas"]) == 1
    datos = lua.leer(epub.read_bytes())
    nueva = [e for e in datos["annotations"].values() if e["text"].startswith("La razón")]
    assert len(nueva) == 1 and nueva[0]["page"] == nueva[0]["pos0"] == "/body/DocFragment[9]/body/p[2]/text().0"
    assert nueva[0]["pos1"].endswith("text().44") and nueva[0]["color"] == "purple" and nueva[0]["drawer"] == "lighten"
    assert datos["annotations_externally_modified"] is True and datos["stats"]["highlights"] == 2
    assert list((mundo.raiz / "respaldos" / "lectura" / "koreader").glob("*.lua"))
    plan = sincronizar.sincronizar(("koreader",), aplicar=True)[0]
    assert not plan.altas and not plan.uniones
    assert exportar.exportar("koreader")["plan"] == []
    with base.lector() as c:
        vive = c.execute("SELECT group_concat(origen) FROM presencias GROUP BY anotacion_id HAVING count(*) > 1").fetchall()
    assert [sorted(v[0].split(",")) for v in vive] == [["koreader", "nawinchay"]]


def test_sin_sidecar_del_epub_no_hay_donde_escribir(mundo):
    base.importar([base.Lectura("nawinchay", anotaciones=[_de_nawinchay()], alcance={"c1"})], aplicar=True)
    assert exportar.candidatas("koreader") and exportar.exportar("koreader")["plan"] == []
    assert exportar.candidatas("zotero") == [] and exportar.candidatas("okular") == []     # sin hoja ni rectángulos
