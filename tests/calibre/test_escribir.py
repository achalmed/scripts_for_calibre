"""tests/test_escribir.py — la puerta de escritura por dentro (ola 2a, K2).

Objetivo: fijar el contrato de lib/escribir.sh y lib/escribir.py: con Calibre abierto no se abre; con el
  candado ocupado sale 75 sin escribir; sin puerta, `calibredb_escribe` y `set_campos` se niegan; al abrir
  queda un respaldo verificado fuera del repo; Zotero igual con su candado y su respaldo.
Método: bases SQLite de juguete en tmp_path, `calibredb` y `ps` falsos en el PATH (anotan o fingen), y la
  puerta cargada con `source` en un bash hijo con su propio estado (XDG_STATE_HOME) y candados.
Límite: no ejercita la API real de Calibre (eso lo hace la caracterización sobre copias).
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))
import escribir  # noqa: E402
import escribir_zotero  # noqa: E402


def _base(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.execute("create table books(id integer primary key, title text)")
    c.execute("insert into books(title) values ('uno')")
    c.commit()
    c.close()
    return p


@pytest.fixture
def mundo(tmp_path):
    bib = tmp_path / "bib"
    _base(bib / "metadata.db")
    zot = _base(tmp_path / "Zotero" / "zotero.sqlite")
    binf = tmp_path / "bin"
    binf.mkdir()
    (binf / "calibredb").write_text(f'#!/bin/sh\necho "$@" >> {tmp_path}/calibredb.log\n')
    (binf / "ps").write_text("#!/bin/sh\necho COMMAND\n[ -f \"$PS_CALIBRE\" ] && echo calibre\nexit 0\n")
    for f in binf.iterdir():
        f.chmod(0o755)
    env = {
        "PATH": f"{binf}:{os.environ['PATH']}", "HOME": str(tmp_path / "home"),
        "XDG_STATE_HOME": str(tmp_path / "estado"), "LOCK_CALIBRE": str(tmp_path / "estado" / "calibre.lock"),
        "LOCK_ZOTERO": str(tmp_path / "estado" / "zotero.lock"), "BIBLIOTECA_DIR": str(bib),
        "CALIBRE_DB": str(bib / "metadata.db"), "ZOTERO_DB": str(zot), "PS_CALIBRE": str(tmp_path / "calibre-abierto"),
    }
    return tmp_path, bib, zot, env


def _bash(env, guion):
    return subprocess.run(["bash", "-c", f'set -euo pipefail; source "{REPO}/lib/escribir.sh"\n{guion}'],
                          env=env, capture_output=True, text=True)


def test_abrir_respalda_fuera_del_repo_y_escribe(mundo):
    tmp, bib, zot, env = mundo
    r = _bash(env, f'puerta_calibre_abrir prueba "{bib}"\ncalibredb_escribe set_custom col 1 valor\n'
                   'echo "PUERTA=$PUERTA_CALIBRE"')
    assert r.returncode == 0, r.stderr
    assert "PUERTA=abierta" in r.stdout
    respaldos = list((tmp / "estado" / "biblioteca" / "respaldos" / "prueba" / "calibre").glob("metadata_*.db"))
    assert len(respaldos) == 1
    assert (tmp / "calibredb.log").read_text().split() == ["set_custom", "--with-library", str(bib), "col", "1", "valor"]


def test_calibre_abierto_no_abre_ni_respalda(mundo):
    tmp, bib, zot, env = mundo
    (tmp / "calibre-abierto").touch()
    r = _bash(env, f'puerta_calibre_abrir prueba "{bib}"\ncalibredb_escribe set_custom col 1 x')
    assert r.returncode == 1 and "Calibre está abierto" in r.stderr
    assert not (tmp / "calibredb.log").exists()
    assert not (tmp / "estado" / "biblioteca" / "respaldos").exists()


def test_candado_ocupado_sale_75_sin_escribir(mundo):
    tmp, bib, zot, env = mundo
    lock = Path(env["LOCK_CALIBRE"])
    lock.parent.mkdir(parents=True, exist_ok=True)
    ocupante = subprocess.Popen(["flock", str(lock), "sleep", "5"])
    try:
        import time
        time.sleep(0.3)
        r = _bash(env, f'puerta_calibre_abrir prueba "{bib}"\ncalibredb_escribe set_custom col 1 x')
    finally:
        ocupante.kill()
    assert r.returncode == 75
    assert not (tmp / "calibredb.log").exists()


def test_sin_puerta_calibredb_escribe_se_niega(mundo):
    tmp, bib, zot, env = mundo
    r = _bash(env, "calibredb_escribe set_custom col 1 x")
    assert r.returncode == 1 and "cerrada" in r.stderr
    assert not (tmp / "calibredb.log").exists()


def test_zotero_con_su_candado_y_su_respaldo(mundo):
    tmp, bib, zot, env = mundo
    r = _bash(env, f'puerta_zotero_abrir prueba "{zot}"\npuerta_integridad\necho "Z=$PUERTA_ZOTERO"')
    assert r.returncode == 0, r.stderr
    assert "Z=abierta" in r.stdout
    assert len(list((tmp / "estado" / "biblioteca" / "respaldos" / "prueba" / "zotero").glob("zotero_*.sqlite"))) == 1


def test_python_exige_la_puerta(mundo, monkeypatch):
    tmp, bib, zot, env = mundo
    for k in ("PUERTA_ZOTERO", "PUERTA_ZOTERO_DB", "PUERTA_CALIBRE", "PUERTA_BIBLIOTECA"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(escribir.PuertaCerrada):
        escribir_zotero.conexion_zotero(zot)
    monkeypatch.setenv("PUERTA_ZOTERO", "abierta")
    monkeypatch.setenv("PUERTA_ZOTERO_DB", str(tmp / "otra.sqlite"))
    with pytest.raises(escribir.PuertaCerrada):        # abierta para otra base
        escribir_zotero.conexion_zotero(zot)


def test_python_puerta_respalda_y_restaura_el_entorno(mundo, monkeypatch):
    tmp, bib, zot, env = mundo
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("PUERTA_ZOTERO", raising=False)
    with escribir.puerta("prueba", zotero=zot):
        c = escribir_zotero.conexion_zotero(zot)
        c.execute("select 1")
        c.close()
    assert "PUERTA_ZOTERO" not in os.environ
    assert len(list((tmp / "estado" / "biblioteca" / "respaldos" / "prueba" / "zotero").glob("zotero_*"))) == 1


def test_respaldo_rota_y_conserva_n(tmp_path):
    db = _base(tmp_path / "x.sqlite")
    import time
    for _ in range(4):
        escribir.respaldar(db, tmp_path / "r", "zotero", 2)
        time.sleep(1.05)   # el nombre lleva la hora al segundo
    assert len(list((tmp_path / "r").glob("zotero_*"))) == 2
