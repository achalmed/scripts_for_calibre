"""tests/studio/test_studio.py — Biblioteca Studio (2026-10-31): las acciones, el índice y la ventana sin pantalla.

Nada toca las bases reales: el índice de la ventana es uno falso en un XDG_STATE_HOME temporal y la base de Zotero
del índice es una SQLite mínima creada aquí.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "studio"))
sys.path.insert(0, str(REPO / "lib"))

from biblioteca_app.acciones import PAGINAS, todas  # noqa: E402
import enlazar_notas  # noqa: E402
import indice  # noqa: E402


# --- las acciones ---------------------------------------------------------------------------------------------

def test_cada_accion_corre_un_programa_que_existe():
    ids = [a.id for a in todas()]
    assert len(ids) == len(set(ids)), "ids de acción repetidos"
    for a in todas():
        assert (REPO / a.orden[0]).is_file(), f"{a.id}: no existe {a.orden[0]}"


def test_simular_nunca_aplica_y_aplicar_lleva_su_bandera():
    for a in todas():
        valor = "x" if a.entrada else ""
        assert "--aplicar" not in a.argv(False, valor), a.id
        if a.aplicar:
            assert a.argv(True, valor)[-len(a.aplicar):] == list(a.aplicar), a.id


def test_lo_que_escribe_en_una_base_lo_declara():
    """Las acciones que escriben en Calibre (aplicar) se desactivan con Calibre abierto: deben declararlo."""
    por_id = {a.id: a for a in todas()}
    for i in ("catalogar", "catalogacion", "koreader", "zotero_calibre", "notas", "migracion"):
        assert "calibre" in por_id[i].bases, i
    assert {p.id for p in PAGINAS} == {"entrada", "adquirir", "catalogar", "sincronizar", "fichas", "manifiestos"}


def test_la_entrada_de_texto_se_parte_como_en_la_terminal():
    a = next(x for x in todas() if x.id == "localizar")
    assert a.argv(False, 'openalex "Teoría general"')[-2:] == ["openalex", "Teoría general"]


# --- el índice ------------------------------------------------------------------------------------------------

def test_enlace_de_apuntes():
    assert indice._enlace('<a href="file:///srv/notas/a%20b.md">Apuntes</a>') == "/srv/notas/a b.md"
    assert indice._enlace("") == ""


def test_zotero_lee_claves_y_calibre_id_de_la_ruta(tmp_path):
    db = tmp_path / "zotero.sqlite"
    c = sqlite3.connect(db)
    c.executescript("""
        create table items(itemID integer primary key, key text);
        create table fields(fieldID integer primary key, fieldName text);
        create table itemDataValues(valueID integer primary key, value text);
        create table itemData(itemID int, fieldID int, valueID int);
        create table itemAttachments(itemID int, parentItemID int, path text);
        insert into items values (1, 'PADRE001'), (2, 'ADJUN001');
        insert into fields values (1, 'citationKey');
        insert into itemDataValues values (1, 'perez2020');
        insert into itemData values (1, 1, 1);
        insert into itemAttachments values (2, 1, 'attachments:Pérez, Ana/Un libro (48)/Un libro - Pérez.pdf');
    """)
    c.commit()
    c.close()
    claves, por_id = indice.zotero(db)
    assert claves == {"PADRE001": "perez2020"} and por_id == {48: "PADRE001"}
    assert indice.zotero(tmp_path / "no-existe.sqlite") == ({}, {})


def test_pendientes_de_enlazar(tmp_path):
    nota = tmp_path / "perez2020.md"
    nota.write_text("# nota\n", encoding="utf-8")
    ind = {"libros": {"48": {"titulo": "Un libro", "apuntes": "", "nota": str(nota)},
                      "49": {"titulo": "Otro", "apuntes": "", "nota": str(tmp_path / "falta.md")},
                      "50": {"titulo": "Ya", "apuntes": str(nota), "nota": str(nota)}}}
    assert enlazar_notas.pendientes(ind) == [("48", str(nota), "Un libro")]


# --- la ventana -----------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app(tmp_path_factory):
    estado = tmp_path_factory.mktemp("estado")
    (estado / "biblioteca").mkdir()
    (estado / "biblioteca" / "indice.json").write_text(json.dumps({
        "esquema": 1, "biblioteca": str(estado / "Biblioteca"), "repo": str(REPO), "notas": str(estado),
        "libros": {"48": {"titulo": "Un libro de prueba", "autores": ["Pérez, Ana"], "carpeta": "Pérez, Ana/Un (48)",
                          "formatos": [], "zotero_key": "PADRE001", "clave": "perez2020", "apuntes": "",
                          "fichas": [], "nota": str(estado / "perez2020.md")}}}), encoding="utf-8")
    os.environ["XDG_STATE_HOME"] = str(estado)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import biblioteca_app  # noqa: F401
    from PySide6.QtWidgets import QApplication
    QApplication.setOrganizationName("biblioteca-studio-pruebas")
    QApplication.setApplicationName("biblioteca-studio-pruebas")
    return QApplication.instance() or QApplication([])


def test_la_ventana_busca_y_abre_un_libro_por_su_enlace(app):
    from biblioteca_app.ventana import Ventana
    v = Ventana()
    v.show()
    assert len(v.indice["libros"]) == 1
    v._buscar("pérez")
    assert v.resultados.lista.count() == 1
    v.abrir_url("biblioteca-studio://libro/48")
    assert v.ui.stack.currentWidget() is v.libro
    v.ui.close()


def test_main_smoke(tmp_path):
    entorno = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_CONFIG_HOME": str(tmp_path),
               "XDG_STATE_HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, str(REPO / "studio" / "main.py"), "--smoke"], env=entorno, cwd=tmp_path,
                       capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stderr[-2000:]
