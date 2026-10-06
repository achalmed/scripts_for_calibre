"""tests/test_escritores_k5.py — catalogación y `metadatos_calibre register` por la puerta (ola 2a, K5; P1, P2, P214).

Objetivo: fijar que `script_catalogacion_biblioteca --aplicar` y `script_metadatos_calibre register` escriben
  solo por la puerta (Calibre cerrado, candado, respaldo verificado), que `metadatos_calibre` simula por
  defecto y que la catalogación hace lo mismo que la referencia sobre una copia.
Método: `register` contra una biblioteca de juguete con un `calibredb` falso que anota (nunca contra el
  espejo: `add_format` copiaría sobre un enlace a un PDF real); la catalogación, contra la copia de la foto
  con el `calibredb` real, comparada con la referencia (simulación: la salida; `--aplicar --ids`: el delta).
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

import calibre_apoyo as ap
import test_calibre_caracterizacion as tc

IDS = "10514,10515,10516"


# ------------------------------------------------------------------ metadatos_calibre register (juguete)
def _juguete(tmp_path):
    lib = tmp_path / "lib"
    libro = lib / "Autor, Prueba" / "Titulo (1)"
    libro.mkdir(parents=True)
    (libro / "libro.pdf").write_bytes(b"%PDF-1.4 juguete")
    c = sqlite3.connect(lib / "metadata.db")
    c.execute("create table books(id integer primary key, title text)")
    c.commit()
    c.close()
    binf = tmp_path / "bin"
    binf.mkdir()
    (binf / "calibredb").write_text(f'#!/bin/sh\necho "$@" >> {tmp_path}/calibredb.log\nexit 0\n')
    (binf / "ps").write_text('#!/bin/sh\necho COMMAND\n[ -f "$PS_CALIBRE" ] && echo calibre\nexit 0\n')
    (binf / "exiftool").write_text("#!/bin/sh\nexit 0\n")
    for f in binf.iterdir():
        f.chmod(0o755)
    env = {"PATH": f"{binf}:{os.environ['PATH']}", "HOME": str(tmp_path / "home"),
           "XDG_STATE_HOME": str(tmp_path / "estado"), "LOCK_CALIBRE": str(tmp_path / "estado" / "calibre.lock"),
           "BIBLIOTECA_DIR": str(lib), "CALIBRE_DB": str(lib / "metadata.db"),
           "PS_CALIBRE": str(tmp_path / "calibre-abierto")}
    return lib, env


def _register(tmp_path, env, lib, *extra):
    return subprocess.run([str(ap.REPO / "script_metadatos_calibre" / "main.sh"), "register", "--library", str(lib),
                           "--root", str(lib / "Autor, Prueba"), *extra], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, cwd=tmp_path)


def _escrituras(tmp_path):
    log = tmp_path / "calibredb.log"
    return [l for l in (log.read_text().splitlines() if log.exists() else []) if l.startswith("add_format")]


def test_register_simula_por_defecto(tmp_path):
    lib, env = _juguete(tmp_path)
    r = _register(tmp_path, env, lib)
    assert "SIMULACIÓN" in r.stdout + r.stderr, r.stdout + r.stderr
    assert _escrituras(tmp_path) == []
    assert not (tmp_path / "estado" / "biblioteca").exists()


def test_register_aplica_por_la_puerta(tmp_path):
    lib, env = _juguete(tmp_path)
    r = _register(tmp_path, env, lib, "--aplicar")
    assert _escrituras(tmp_path) == [f"add_format --with-library {lib} 1 {lib}/Autor, Prueba/Titulo (1)/libro.pdf --dont-replace"], \
        r.stdout + r.stderr
    assert list((tmp_path / "estado" / "biblioteca" / "respaldos" / "metadatos_calibre" / "calibre").glob("metadata_*.db"))


def test_register_con_calibre_abierto_no_escribe(tmp_path):
    lib, env = _juguete(tmp_path)
    (tmp_path / "calibre-abierto").touch()
    r = _register(tmp_path, env, lib, "--aplicar")
    assert r.returncode != 0 and "Calibre está abierto" in r.stdout + r.stderr
    assert _escrituras(tmp_path) == []


# ------------------------------------------------------------------ catalogación (copia de la foto)
def _normalizar(texto, c):
    return [l.replace(str(c.biblioteca), "<BIBLIOTECA>") for l in texto.splitlines() if l.startswith("[SIMULACIÓN]")]


def test_catalogacion_simulacion_igual_a_la_referencia(arboles, corrida):
    salidas = {}
    for impl in ("ref", "act"):
        c = corrida(impl)
        r = ap.correr(arboles[impl], "script_catalogacion_biblioteca", ["--ids", IDS], c.env)
        assert r.returncode == 0, r.stderr
        salidas[impl] = _normalizar(r.stdout, c)
    assert salidas["act"] == salidas["ref"] and len(salidas["act"]) == 3


def test_catalogacion_aplicar_igual_a_la_referencia(arboles, corrida):
    tc.OTRAS["catalogacion"] = ("script_catalogacion_biblioteca", "reportes", "*.tsv")
    m = tc._comparar(arboles, corrida, "catalogacion", ["--aplicar", "--ids", IDS])
    assert "Backup" in m["act"]["texto"], "la catalogación aplicó sin respaldo de la puerta"
