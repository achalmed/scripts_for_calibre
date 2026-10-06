"""La red de `scripts_for_fuentes` sale de `core/py-common/red.py` (ola 2, F4; RQ-MAN-04, excepción E5).

Antes, `lib/comun.py` importaba `datafw/connectors/_lib` y había un ciclo `datafw ↔ scripts_for_fuentes`.
La caja de arena ya no lleva `datafw/connectors`: si el código lo necesitara, estas pruebas fallarían.
"""
import http.server
import re
import subprocess
import threading

import pytest

from conftest import REPO, pdf_minimo

PDF = pdf_minimo("Descarga de prueba")


class _Servidor(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        cuerpo = PDF if self.path == "/doc.pdf" else b"<html>WAF</html>"
        self.send_response(200); self.send_header("Content-Length", str(len(cuerpo))); self.end_headers()
        self.wfile.write(cuerpo)


@pytest.fixture(scope="module")
def servidor():
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Servidor)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}"
    s.shutdown()


def test_descargar_por_core_red(caja, servidor):
    assert not (caja.docs / "datafw" / "connectors").exists()
    codigo = (
        "import sys; from pathlib import Path\n"
        f"sys.path.insert(0, {str(caja.repo)!r})\n"
        "import config; from lib import comun\n"
        f"ruta, sha, n = comun.descargar('{servidor}/doc.pdf', config.ENTRADA, 'prueba')\n"
        "print(ruta.name, n, sha == comun.red.sha256(ruta))\n"
        "try:\n"
        f"    comun.descargar('{servidor}/waf.pdf', config.ENTRADA, 'waf')\n"
        "except ValueError as e:\n"
        "    print('rechazado')\n"
        "print(sorted(p.name for p in config.ENTRADA.iterdir()))\n")
    r = caja.correr("python3", "-c", codigo)
    assert r.returncode == 0, r.stderr
    lineas = r.stdout.splitlines()
    assert lineas[0] == f"prueba.pdf {len(PDF)} True"
    assert lineas[1] == "rechazado"
    assert lineas[2] == "['prueba.pdf']"


def test_main_funciona_sin_02_analysis(caja):
    r = caja.py("main.py", "fuentes")
    assert r.returncode == 0, r.stderr


def test_ningun_codigo_importa_connectors():
    """`git grep connectors` = 0 en el código (la prueba de salida de F4)."""
    archivos = subprocess.run(["git", "ls-files", "*.py", "*.sh"], cwd=REPO, capture_output=True, text=True).stdout.split()
    malos = []
    for rel in archivos:
        if rel.startswith("tests/"):
            continue
        for n, linea in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"connectors|LIB_ADQUISICION|(?:ANALYSIS|DATAFW)_DIR\s*/\s*[\"']connectors", linea):
                malos.append(f"{rel}:{n}: {linea.strip()[:80]}")
    assert not malos, "\n".join(malos)
