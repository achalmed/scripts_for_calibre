"""tests/test_entorno_k6.py — rutas, entorno y timers (ola 2a, K6; RQ-RUT-01, RQ-RUT-02, P217, P221).

Objetivo: que el código no lleve la carpeta de inicio ni `$HOME/Documents` (las rutas salen de core/env),
  que las tres plantillas de timers se rendericen con `%h` y sin anaconda, pasen `systemd-analyze verify`
  y que `instalar.sh --verificar` distinga lo instalado de la plantilla; y que los sincronizadores corran
  con el PATH mínimo de los timers (sin el `sqlite3` de anaconda).
Método: render e instalación en carpetas temporales (`--destino`, nunca ~/.config/systemd/user); las
  corridas, sobre la copia aislada de la caracterización.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

import calibre_apoyo as ap

INSTALAR = ap.REPO / "systemd" / "instalar.sh"
UNIDADES = ["ecosistema-lectura", "ecosistema-metadatos", "koreader-calibre-sync"]


def test_sin_rutas_de_maquina_en_el_codigo():
    r = subprocess.run(["git", "-C", str(ap.REPO), "grep", "-nI", "-e", "/home/[a-z]", "-e", "$HOME/Documents",
                        "--", "*.sh", "*.py", "*.service", "*.timer", "*.yml", ":!script_normalizacion_metadatos",
                        ":!tests"], capture_output=True, text=True)
    assert r.stdout == "", r.stdout


def test_plantillas_renderizadas_con_h_y_sin_anaconda(tmp_path):
    subprocess.run([str(INSTALAR), "--renderizar", str(tmp_path)], check=True, capture_output=True)
    for u in UNIDADES:
        servicio = (tmp_path / f"{u}.service").read_text()
        entorno = [l for l in servicio.splitlines() if l.startswith("Environment=")]
        assert entorno == ['Environment="PATH=/usr/local/bin:/usr/bin:/bin"']
        assert "ExecStart=%h/" in servicio and "/home/" not in servicio
        assert "SuccessExitStatus=75" in servicio
    if shutil.which("systemd-analyze"):
        r = subprocess.run(["systemd-analyze", "--user", "verify", *map(str, sorted(tmp_path.iterdir()))],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_instalar_simula_y_verificar_distingue(tmp_path):
    destino = tmp_path / "user"
    r = subprocess.run([str(INSTALAR), "--destino", str(destino)], capture_output=True, text=True)
    assert r.returncode == 0 and not destino.exists()                      # simula por defecto
    subprocess.run([str(INSTALAR), "--destino", str(destino), "--aplicar"], check=True, capture_output=True)
    assert subprocess.run([str(INSTALAR), "--destino", str(destino), "--verificar"]).returncode == 0
    (destino / "koreader-calibre-sync.service").write_text("[Unit]\nDescription=a mano\n")
    assert subprocess.run([str(INSTALAR), "--destino", str(destino), "--verificar"],
                          capture_output=True).returncode == 1


@pytest.mark.parametrize("suite,args", [
    ("script_ecosistema_lectura", ["--aplicar"]),
    ("script_koreader_estudio", ["--aplicar"]),
    ("script_sincronizar_zotero", ["--aplicar"]),
])
def test_corre_con_el_path_de_los_timers(corrida, suite, args):
    c = corrida("path")
    c.env["PATH"] = f"{c.raiz / 'bin'}:/usr/local/bin:/usr/bin:/bin"
    c.env["KOREADER_RESPALDO_DIR"] = str(c.raiz / "koreader-respaldo")
    r = ap.correr(ap.REPO, suite, args, c.env)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    if suite == "script_koreader_estudio":
        assert "CREATE TABLE" in (c.raiz / "koreader-respaldo" / "statistics.sql").read_text()
