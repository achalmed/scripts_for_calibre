"""tests/conftest.py — la caja de arena de las pruebas de scripts_for_fuentes (ola 2, F1).

Objetivo: correr las suites tal como se usan (procesos, `main.sh`/`main.py`) sin tocar nada real.
Método: cada prueba recibe una copia del workspace en miniatura bajo `tmp_path`:
  Documents/core/                 env, shell-lib y py-common copiados del core real
  Documents/scripts_for_fuentes/  el árbol de trabajo de este repo (sin fichas provisionales, respaldos ni entrada/)
  Documents/scripts-biblioteca/  solo lo que ingesta lee o escribe: fichas y resumen de la catalogación
  Documents/biblioteca/metadata.db  copia de la base real hecha con la API de respaldo de sqlite, en solo lectura
y un entorno limpio (HOME, XDG_*, CALIBRE_CONFIG_DIRECTORY, LOCK_*, RESPALDOS_DIR) que apunta dentro de la caja.
Límite: la base real se lee una vez por sesión (`mode=ro`); nunca se escribe. Los libros de la copia no tienen
archivo salvo los que una prueba fabrique con `libro_con_archivo`.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

BASETEMP = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pytest" / "scripts-biblioteca-fuentes" / "basetemp"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """El temporal de la caja de arena va al disco (XDG_CACHE_HOME), no a /tmp: /tmp es tmpfs (RAM). Solo si nadie
    pidió otro --basetemp y la corrida es de estas pruebas."""
    if config.option.basetemp:
        return
    aqui = Path(__file__).resolve().parent
    args = [Path(a.split("::")[0]).resolve() for a in (config.args or [])]
    if args and all(aqui in a.parents or a == aqui for a in args):
        BASETEMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(BASETEMP)

REPO = Path(__file__).resolve().parents[2]
NOMBRE_REPO = "scripts-biblioteca"   # la caja usa ya el nombre de destino de la fusión
DOCS_REAL = REPO.parent
CORE_REAL = DOCS_REAL / "core"

# Lo que no entra en la caja: estado local, respaldos y lo que no es código ni ledger.
_EXCLUIR = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache", "backups", "reportes",
                                  "salida_ris", "logs", "tests")


def _db_real() -> Path:
    """La base real según core/env (sin cargar env.sh: basta la regla de env.py)."""
    v = os.environ.get("CALIBRE_DB")
    if v:
        return Path(v)
    return Path(os.environ.get("BIBLIOTECA_DIR") or DOCS_REAL / "biblioteca") / "metadata.db"


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pdf_minimo(texto: str = "Documento de prueba") -> bytes:
    """Un PDF de una página con texto extraíble (pdftotext lo lee); offsets del xref calculados."""
    flujo = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(salida)


@pytest.fixture(scope="session")
def plantilla(tmp_path_factory) -> Path:
    """La caja de arena de referencia, construida una vez por sesión; cada prueba trabaja en una copia."""
    base = tmp_path_factory.mktemp("plantilla")
    docs = base / "Documents"
    # core: solo lo que cargan las suites
    for parte in ("env.sh", "env.py"):
        (docs / "core").mkdir(parents=True, exist_ok=True)
        shutil.copy2(CORE_REAL / parte, docs / "core" / parte)
    for parte in ("shell-lib", "py-common"):
        shutil.copytree(CORE_REAL / parte, docs / "core" / parte, ignore=_EXCLUIR)
    # este repo, sin estado local
    # el repo fusionado (ola 2, fase E), sin el registro real de la catalogación (650 fichas): la caja lleva uno vacío
    def _ignorar(carpeta, nombres):
        fuera = set(_EXCLUIR(carpeta, nombres))
        if Path(carpeta).resolve() == (REPO / "catalogacion").resolve():
            fuera |= {"fichas", "resumen_catalogacion.tsv"}
        return fuera
    shutil.copytree(REPO, docs / NOMBRE_REPO, ignore=_ignorar, symlinks=True)
    fichas = docs / NOMBRE_REPO / "ingesta" / "fichas"
    if fichas.exists():
        shutil.rmtree(fichas)
    fichas.mkdir()
    entrada = docs / NOMBRE_REPO / "entrada"
    if entrada.exists():
        shutil.rmtree(entrada)
    entrada.mkdir()
    (docs / NOMBRE_REPO / "logs").mkdir(exist_ok=True)
    # catalogación (el registro canónico, en el mismo repo desde la fusión): solo cabecera y carpeta
    cat = docs / NOMBRE_REPO / "catalogacion"
    (cat / "fichas").mkdir(parents=True)
    (cat / "resumen_catalogacion.tsv").write_text(
        "id\tautores\ttitulo\ttipo_zotero\tclasificador\teditorial\tfecha\tidentificador\tidioma\ttags\tconfianza\tnota\n",
        encoding="utf-8")
    # Ni el envoltorio lib_comun (retirado en la fusión) ni la red de 02 analysis (F4) entran en la caja:
    # las pruebas demuestran que este repo ya no los necesita.
    # raíces de entrada que ingesta recorre
    for d in ("02 analysis/data/raw", "03 writing/reports", "10 Class/docencia/cursos", "prompts"):
        (docs / d).mkdir(parents=True, exist_ok=True)
    # la base: copia consistente leída en solo lectura
    real = _db_real()
    if not real.exists():
        pytest.skip(f"no hay base de Calibre que copiar ({real})")
    (docs / "biblioteca").mkdir()
    origen = sqlite3.connect(f"file:{real}?mode=ro", uri=True)
    destino = sqlite3.connect(docs / "biblioteca" / "metadata.db")
    with destino:
        origen.backup(destino)
    origen.close(); destino.close()
    return base


@pytest.fixture
def caja(plantilla, tmp_path) -> "Caja":
    base = tmp_path / "caja"
    shutil.copytree(plantilla, base, symlinks=True)
    return Caja(base)


class Caja:
    """Una copia de la caja de arena con su entorno y atajos para correr las suites."""

    def __init__(self, base: Path):
        self.base = base
        self.docs = base / "Documents"
        self.repo = self.docs / NOMBRE_REPO
        self.biblioteca = self.docs / "biblioteca"
        self.db = self.biblioteca / "metadata.db"
        self.respaldos = base / "respaldos"
        # los respaldos de la puerta única (ola 2, fase E) van al estado de usuario: <estado>/biblioteca/respaldos/<suite>/
        self.respaldos_puerta = base / "estado" / "biblioteca" / "respaldos"
        self.lock_calibre = base / "estado" / "biblioteca" / "calibre.lock"
        home = base / "home"
        home.mkdir(exist_ok=True)
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "USER": os.environ.get("USER", "prueba"),
            "HOME": str(home),
            "DOCS_ROOT": str(self.docs),
            "SCRIPTS_BIBLIOTECA": str(self.repo), "SCRIPTS_CALIBRE": str(self.repo), "SCRIPTS_FUENTES": str(self.repo),
            "BIBLIOTECA_DIR": str(self.biblioteca),
            "CALIBRE_DB": str(self.db),
            "ZOTERO_DIR": str(base / "Zotero"),
            "ZOTERO_DB": str(base / "Zotero" / "zotero.sqlite"),
            "ARCHDISK_DIR": str(base / "archdisk"),
            "RESPALDOS_DIR": str(self.respaldos),
            "LOCK_CALIBRE": str(self.lock_calibre),
            "LOCK_ZOTERO": str(base / "estado" / "biblioteca" / "zotero.lock"),
            "XDG_STATE_HOME": str(base / "estado"),
            "XDG_CACHE_HOME": str(base / "cache"),
            "XDG_CONFIG_HOME": str(base / "config"),
            "CALIBRE_CONFIG_DIRECTORY": str(base / "config" / "calibre"),
            "NO_COLOR": "1",
        }
        # salvaguarda: nada del entorno apunta fuera de la caja
        for k in ("DOCS_ROOT", "BIBLIOTECA_DIR", "CALIBRE_DB", "LOCK_CALIBRE", "RESPALDOS_DIR", "HOME"):
            assert self.env[k].startswith(str(base)), k
        assert self.db.resolve() != _db_real().resolve()

    def correr(self, *args, cwd=None, entrada=None, env=None, timeout=300) -> subprocess.CompletedProcess:
        e = dict(self.env)
        if env:
            e.update(env)
        return subprocess.run([str(a) for a in args], cwd=cwd or self.repo, env=e, input=entrada,
                              capture_output=True, text=True, timeout=timeout)

    def ingesta(self, *args, **kw):
        return self.correr("bash", self.repo / "ingesta" / "main.sh", *args, **kw)

    def py(self, script, *args, **kw):
        return self.correr("python3", self.repo / script, *args, **kw)

    # ---- datos de la caja
    def un_libro(self) -> dict:
        """El primer libro con formato PDF de la copia: id, título, ruta del archivo (que no existe aún)."""
        c = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        bid, titulo, path, nombre = c.execute(
            "select b.id, b.title, b.path, d.name from books b join data d on d.book=b.id "
            "where d.format='PDF' order by b.id limit 1").fetchone()
        c.close()
        return {"id": bid, "titulo": titulo, "archivo": self.biblioteca / path / f"{nombre}.pdf"}

    def libro_con_archivo(self) -> dict:
        libro = self.un_libro()
        libro["archivo"].parent.mkdir(parents=True, exist_ok=True)
        libro["archivo"].write_bytes(pdf_minimo(libro["titulo"][:40].encode("ascii", "ignore").decode()))
        return libro

    def max_id(self) -> int:
        c = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        n = c.execute("select max(id) from books").fetchone()[0]
        c.close()
        return n

    def huella_db(self) -> str:
        return sha256(self.db)


def calibre_abierto() -> bool:
    """Lo mismo que core/shell-lib/detectar_apps.sh: un proceso cuyo nombre empieza por «calibre»."""
    out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
    return any(l.strip().lower().startswith("calibre") for l in out.splitlines())


@pytest.fixture
def sin_calibre_abierto():
    if calibre_abierto():
        pytest.skip("Calibre está abierto en la máquina: la prueba de escritura en la copia se salta")


class CandadoOcupado:
    """Toma el candado de la caja como lo haría otra herramienta (flock en otro descriptor)."""

    def __init__(self, ruta: Path):
        self.ruta = ruta

    def __enter__(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.fd = open(self.ruta, "w")
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.fd.close()


def saltar_si_calibre(r: subprocess.CompletedProcess) -> None:
    """Si la puerta respondió 75 porque apareció un proceso calibre* ajeno durante la prueba (otro agente, un timer),
    la prueba no mide lo que quería: se salta en vez de fallar."""
    if r.returncode == 75 and calibre_abierto():
        pytest.skip("un proceso calibre* ajeno apareció durante la prueba (la puerta respondió 75, que es lo correcto)")
