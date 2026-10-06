"""La puerta de escritura en Calibre (ola 2, F2; normativa 9.1, RQ-PRE-06).

Toda escritura de `ingesta` en `metadata.db` pasa por `lib/escribir.sh` (Bash) y `lib/escribir.py` (Python):
core/shell-lib cargado, Calibre cerrado, candado único (core/shell-lib/lock.sh), respaldo verificado
(`backup_metadata_db`) y `calibredb`. Si algo falta, sale ≠ 0 de forma ruidosa y no escribe nada.

Salidas: 75 (Calibre abierto o candado ocupado: «reintentar luego»), 74 (sin respaldo verificado),
69 (falta core/shell-lib).
"""
import ast
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, CandadoOcupado, pdf_minimo, saltar_si_calibre

NOMBRE = "informe_prueba_puerta"


def _preparar(caja):
    destino = caja.repo / "entrada" / "programa-prueba" / f"{NOMBRE}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(pdf_minimo("Informe de prueba de la puerta"))
    r = caja.ingesta("identificar")
    assert r.returncode == 0, r.stderr
    return destino


def _foto(caja):
    """Lo que una escritura cambiaría: la base, el ledger y los respaldos."""
    resp = sorted(p.name for d in (caja.respaldos, caja.respaldos_puerta) if d.exists() for p in d.rglob("*.db"))
    return caja.huella_db(), (caja.repo / "ingesta" / "ingesta.tsv").read_bytes(), resp


COMANDOS = [("catalogar", "--aplicar", "--solo", NOMBRE), ("ocr", "--aplicar"), ("paquetes", "--aplicar")]


@pytest.mark.parametrize("comando", COMANDOS, ids=[c[0] for c in COMANDOS])
def test_candado_ocupado_sale_75_y_no_escribe(caja, comando):
    _preparar(caja)
    antes = _foto(caja)
    with CandadoOcupado(caja.lock_calibre):
        r = caja.ingesta(*comando)
    assert r.returncode == 75, r.stdout + r.stderr
    assert "reintenta" in (r.stdout + r.stderr).lower()
    assert _foto(caja) == antes


@pytest.fixture
def calibre_falso():
    """Un proceso cuyo nombre (comm) empieza por «calibre», como lo ve core/shell-lib/detectar_apps.sh.

    Mientras dura (un par de segundos) cualquier herramienta de la máquina creerá que Calibre está abierto
    y se abstendrá de escribir: es el lado seguro.
    """
    codigo = ("import ctypes, time; ctypes.CDLL(None).prctl(15, b'calibre-prueba', 0, 0, 0); time.sleep(60)")
    p = subprocess.Popen([sys.executable, "-c", codigo])
    for _ in range(50):
        if "calibre-prueba" in subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout:
            break
        time.sleep(0.1)
    yield p
    p.kill(); p.wait()


@pytest.mark.parametrize("comando", COMANDOS, ids=[c[0] for c in COMANDOS])
def test_calibre_abierto_sale_75_y_no_escribe(caja, calibre_falso, comando):
    _preparar(caja)
    antes = _foto(caja)
    r = caja.ingesta(*comando)
    assert r.returncode == 75, r.stdout + r.stderr
    assert "calibre está abierto" in (r.stdout + r.stderr).lower()
    assert _foto(caja) == antes


def test_sin_core_falla_ruidoso_y_no_escribe(caja):
    _preparar(caja)
    shutil.rmtree(caja.docs / "core" / "shell-lib")
    antes = _foto(caja)
    r = caja.ingesta("catalogar", "--aplicar", "--solo", NOMBRE)
    assert r.returncode == 69, r.stdout + r.stderr
    assert "shell-lib" in r.stdout + r.stderr
    assert _foto(caja) == antes


def test_sin_respaldo_verificado_sale_74_y_no_escribe(caja, sin_calibre_abierto):
    _preparar(caja)
    caja.respaldos_puerta.mkdir(parents=True)
    caja.respaldos_puerta.chmod(0o500)   # no se puede crear la carpeta del respaldo
    try:
        antes = _foto(caja)
        r = caja.ingesta("catalogar", "--aplicar", "--solo", NOMBRE)
    finally:
        caja.respaldos_puerta.chmod(0o700)
    saltar_si_calibre(r)
    assert r.returncode == 74, r.stdout + r.stderr
    assert _foto(caja) == antes


def test_puerta_abierta_respalda_antes_de_escribir(caja, sin_calibre_abierto):
    _preparar(caja)
    antes = caja.huella_db()
    ultimo = caja.max_id()
    r = caja.ingesta("catalogar", "--aplicar", "--solo", NOMBRE)
    saltar_si_calibre(r)
    assert r.returncode == 0, r.stdout + r.stderr
    assert caja.max_id() == ultimo + 1
    respaldos = list(caja.respaldos_puerta.rglob("metadata_*.db"))
    assert len(respaldos) == 1
    assert respaldos[0].is_relative_to(caja.respaldos_puerta / "ingesta")
    from conftest import sha256
    assert sha256(respaldos[0]) == antes          # el respaldo es la base de ANTES de escribir
    assert not (caja.repo / "ingesta" / "backups").exists()   # ningún respaldo dentro del repo


def test_escribir_py_rechaza_escrituras_sin_puerta(caja):
    """Un módulo Python que llama a calibredb sin pasar por la puerta recibe PuertaCerrada (y la lectura pasa)."""
    codigo = (
        "import importlib.util, sys\n"
        f"s = importlib.util.spec_from_file_location('escribir', {str(caja.repo / 'lib' / 'escribir.py')!r})\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "try:\n"
        f"    m.calibredb({str(caja.biblioteca)!r}, 'add', '/no/existe.pdf')\n"
        "except m.PuertaCerrada as e:\n"
        "    print('cerrada', e)\n"
        f"r = m.calibredb({str(caja.biblioteca)!r}, 'list', '--fields', 'title', '--limit', '1', '--for-machine')\n"
        "print('lectura', r.returncode)\n")
    r = caja.correr("python3", "-c", codigo)
    assert r.returncode == 0, r.stderr
    assert "cerrada" in r.stdout
    assert "lectura 0" in r.stdout


# ---------------------------------------------------------------- nadie escribe fuera de la puerta
_PUERTA = {"lib/escribir.sh", "lib/escribir.py"}

def _codigo():
    archivos = subprocess.run(["git", "ls-files", "*.py", "*.sh"], cwd=REPO, capture_output=True, text=True).stdout.split()
    return [a for a in archivos if a not in _PUERTA and not a.startswith("tests/")]


def _llamadas_python(texto):
    """Python: cadenas literales «calibredb» (argumento de subprocess) y sqlite3.connect sin mode=ro."""
    malas = []
    for nodo in ast.walk(ast.parse(texto)):
        if isinstance(nodo, ast.Constant) and nodo.value == "calibredb":
            malas.append(f"línea {nodo.lineno}: invoca calibredb")
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "connect" \
                and getattr(getattr(nodo.func, "value", None), "id", "") == "sqlite3":
            fuente = ast.get_source_segment(texto, nodo) or ""
            if "mode=ro" not in fuente:
                malas.append(f"línea {nodo.lineno}: sqlite3.connect sin mode=ro")
    return malas


def _llamadas_shell(texto):
    malas = []
    for n, linea in enumerate(texto.splitlines(), 1):
        codigo = linea.split("#", 1)[0] if not linea.lstrip().startswith("#") else ""
        if re.search(r'(^|[;&|(`]|\$\()\s*("?\$\{?CALIBREDB\b|calibredb(\s|$))', codigo):
            malas.append(f"línea {n}: invoca calibredb")
        if re.search(r"(^|[;&|(`]|\$\()\s*sqlite3\s", codigo) and "mode=ro" not in codigo:
            malas.append(f"línea {n}: sqlite3 sin mode=ro")
    return malas


# La regla estática (nadie escribe fuera de la puerta) vive en tests/calibre/test_puerta.py y cubre todo el
# repo fusionado (ola 2, fase E): una sola regla, la más fina (distingue lecturas y admite la puerta de Zotero).


def test_cursos_con_candado_ocupado_sale_75_y_no_escribe(caja):
    from test_ingesta_cursos import _curso, cursos
    curso, pdf = _curso(caja)
    tsv = caja.base / "candidatos.tsv"
    tsv.write_text("decision\tclase\tpaginas\tMB\tautor\ttitulo\tcurso\truta\tduplicado_id\n"
                   f"ingestar\tlectura\t1\t0\tUnknown\tLectura\tcurso-prueba\t{pdf.relative_to(caja.docs)}\t\n", encoding="utf-8")
    antes = _foto(caja), (curso / "curso.yml").read_bytes()
    with CandadoOcupado(caja.lock_calibre):
        r = cursos(caja, "--aplicar", "--tsv", tsv)
    assert r.returncode == 75, r.stdout + r.stderr
    assert (_foto(caja), (curso / "curso.yml").read_bytes()) == antes
    assert pdf.exists()
