"""Privacidad y rutas (ola 2, F5; RQ-SEC-01, RQ-RUT-01; P239, P240, P248).

- Ningún archivo rastreado lleva la carpeta de inicio de la máquina ni un correo (condición de A1 para publicar).
- Los ledgers guardan rutas relativas a DOCS_ROOT; las relativas que no empiezan por una carpeta de la raíz
  siguen siendo las de la zona de entrada (o del CIL histórico), como antes.
- Nada del código carga el envoltorio lib_comun ni escribe en meta/reparaciones (retirada).
- El correo de contacto de Unpaywall sale del entorno.
"""
import csv
import importlib.util
import re
import subprocess
import tarfile

from conftest import REPO

CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]")
HOME = "/" + "home" + "/"          # partido: el patrón no se cuenta a sí mismo
# identificadores públicos que tienen forma de correo y no lo son (el id del complemento Ethereal Style de Zotero)
NO_CORREOS = {"zoterostyle@polygon.org"}


def _rastreados():
    return subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()


def test_ningun_archivo_rastreado_lleva_home_ni_correo():
    hallazgos = []
    for rel in _rastreados():
        p = REPO / rel
        if rel.startswith("tests/") or not p.is_file() or p.is_symlink():
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if HOME in texto:
            hallazgos.append(f"{rel}: ruta de la carpeta de inicio")
        for m in CORREO.finditer(texto):
            if m.group(0) in NO_CORREOS:
                continue
            hallazgos.append(f"{rel}: correo {m.group(0)[:3]}…")
    assert not hallazgos, "\n".join(hallazgos[:20])


def test_codigo_sin_lib_comun_ni_reparaciones():
    malos = []
    for rel in _rastreados():
        if rel.endswith((".py", ".sh")) and not rel.startswith("tests/"):
            # Path.home() solo como respaldo de una variable XDG (el estado de usuario), nunca para una ruta de datos
            texto = "\n".join(l for l in (REPO / rel).read_text(encoding="utf-8").splitlines() if "XDG_" not in l)
            for patron in ("lib_comun", "LIB_COMUN", "reparaciones", "$HOME/Documents", "Path.home()"):
                if patron in texto:
                    malos.append(f"{rel}: {patron}")
    assert not malos, "\n".join(malos)


def _rutas():
    spec = importlib.util.spec_from_file_location("rutas", REPO / "lib" / "rutas.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_rutas_relativas_a_docs_root(tmp_path):
    R = _rutas()
    docs = tmp_path / "Documents"
    (docs / "datafw" / "data").mkdir(parents=True)
    entrada = docs / "scripts-biblioteca" / "entrada"
    entrada.mkdir(parents=True)
    assert R.a_texto(docs / "datafw" / "data" / "x.pdf", docs) == "datafw/data/x.pdf"
    assert R.a_texto("/otra/parte/x.pdf", docs) == "/otra/parte/x.pdf"     # fuera de la raíz: se queda absoluta
    assert R.resolver("datafw/data/x.pdf", entrada, docs) == docs / "datafw" / "data" / "x.pdf"
    assert R.resolver("programa-2026/x.pdf", entrada, docs) == entrada / "programa-2026" / "x.pdf"
    assert R.resolver("02_investigacion/marco_legal/x.pdf", entrada, docs) == entrada / "02_investigacion/marco_legal/x.pdf"
    assert R.resolver("/abs/x.pdf", entrada, docs).as_posix() == "/abs/x.pdf"
    assert R.resolver("", entrada, docs) is None


def test_ledgers_sin_rutas_absolutas_de_la_raiz():
    for nombre in ("ingesta/ingesta.tsv", "ingesta/pendientes.tsv"):
        with open(REPO / nombre, encoding="utf-8", newline="") as f:
            for fila in csv.DictReader(f, delimiter="\t"):
                for col in ("origen", "ruta_calibre"):
                    assert not (fila.get(col) or "").startswith("/"), f"{nombre}: {col} absoluta"


def test_archivar_resuelve_rutas_relativas(caja):
    """Una fila del ledger con origen y ruta_calibre relativas a DOCS_ROOT se archiva (en simulación) como antes."""
    libro = caja.libro_con_archivo()
    origen = caja.docs / "03 writing" / "reports" / "2026-10-05-prueba" / "fuentes" / "doc.pdf"
    origen.parent.mkdir(parents=True)
    origen.write_bytes(libro["archivo"].read_bytes())
    led = caja.repo / "ingesta" / "ingesta.tsv"
    with open(led, "a", encoding="utf-8") as f:
        f.write("\t".join(["2026-10-05", "0" * 64, str(origen.relative_to(caja.docs)), "t", "a", "Report", "Informe",
                           "2026", "", "", str(libro["id"]), str(libro["archivo"].relative_to(caja.docs)), "", "catalogado"]) + "\n")
    r = caja.ingesta("archivar")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SIM  03 writing/reports/2026-10-05-prueba/fuentes/doc.pdf → manifiesto →" in r.stdout
    assert "[archivar] 1 documento(s) · simulación" in r.stdout


def test_correo_de_unpaywall_desde_el_entorno(caja):
    codigo = ("import importlib.util as u; s = u.spec_from_file_location('c', 'fuentes/articulo/config.py');"
              " m = u.module_from_spec(s); s.loader.exec_module(m); print(repr(m.EMAIL))")
    assert caja.correr("python3", "-c", codigo).stdout.strip() == "''"
    r = caja.correr("python3", "-c", codigo, env={"FUENTES_CORREO_CONTACTO": "contacto@ejemplo.org"})
    assert r.stdout.strip() == "'contacto@ejemplo.org'"


def test_fichas_grafia_respalda_fuera_del_repo(caja):
    carpeta = caja.docs / "03 writing" / "reports" / "2026-10-05-prueba" / "fuentes" / "fichas"
    carpeta.mkdir(parents=True)
    ficha = carpeta / "prueba2026-fuente.md"
    ficha.write_text("---\ntipo: ficha-fuente\ncalibre-id: 1\n---\n\ncuerpo\n", encoding="utf-8")
    r = caja.py("fichas/main.py", "grafia", carpeta, "--aplicar")
    assert r.returncode == 0, r.stdout + r.stderr
    tars = list((caja.respaldos / "biblioteca" / "fuentes" / "fichas").rglob("respaldo.tar.gz"))
    assert len(tars) == 1 and (tars[0].parent / "UNDO.sh").is_file()
    with tarfile.open(tars[0]) as t:
        assert any(n.endswith("prueba2026-fuente.md") for n in t.getnames())
    assert not (caja.docs / "meta").exists()
