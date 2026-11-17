"""El área «Lectura» (decisiones §9.6): el controlador lee la base de lectura de la muestra, en solo lectura."""
from __future__ import annotations

from pathlib import Path

from conftest import requiere_binding


@requiere_binding
def test_lectura_resumen_libros_y_subrayados(app, entorno, muestra):
    from biblioteca_app.controladores.lectura import Lectura
    db = Path(muestra.entorno["LECTURA_DB"])
    antes = db.stat().st_mtime_ns
    lec = Lectura(None, vigilar=False)
    assert lec.hayBase and lec.rutaBase == str(db)
    r = lec.resumen
    assert r["anotaciones"] == 4 and r["compartidas"] == 1 and "KOReader 2" in r["origenes"]
    assert len(lec.semanas) == 12
    assert [l["titulo"] for l in lec.libros][0].startswith("Economía")
    primero = lec.libros[0]["id"]
    assert lec.actualId == primero                       # sin libro en el catálogo, el más reciente
    b = lec.libro
    assert b["hay"] and b["total"] == 4 and {p["origen"] for p in b["progreso"]} == {"KOReader", "Zotero"}
    assert [o["nombre"] for o in lec.origenes] == ["", "koreader", "zotero", "okular", "yachay"]
    compartido = lec.anotaciones[0]
    assert "KOReader, Zotero" in compartido["detalle"] and compartido["cita"].startswith("“Las ciudades") and "(p. 12)" in compartido["cita"]
    lec.fijarOrigen("zotero")
    assert len(lec.anotaciones) == 1
    lec.fijarOrigen("")
    assert len(lec.anotaciones) == 4
    assert db.stat().st_mtime_ns == antes                # la ventana no escribe la base


@requiere_binding
def test_lectura_sin_base(app, entorno, muestra, monkeypatch, tmp_path):
    from biblioteca_app.controladores.lectura import Lectura
    monkeypatch.setenv("LECTURA_DB", str(tmp_path / "no-existe" / "lectura.sqlite"))
    lec = Lectura(None, vigilar=False)
    assert not lec.hayBase and lec.libros == [] and not lec.libro["hay"]
    assert not (tmp_path / "no-existe").exists()


def test_las_operaciones_de_la_base_de_lectura():
    from biblioteca_app.servicios import operaciones as ops
    o = ops.operacion("base_lectura")
    assert o.argv(False) == ["python3", "lectura_base/main.py", "sincronizar"] and o.bases == ()
    z = ops.operacion("lectura_a_zotero")
    assert z.argv(True)[-1] == "--aplicar" and z.bases == ("zotero",)
    for destino in ("koreader", "okular"):
        o = ops.operacion(f"lectura_a_{destino}")
        assert o.argv(True)[-3:] == ["exportar", destino, "--aplicar"] and o.bases == ()
