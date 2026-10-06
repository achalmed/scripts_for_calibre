"""Caracterización de `main.py verificar`, `manifiesto/` y `fichas/` (ola 2, F1), en seco y contra la copia.

`manifiesto/` es contrato con `datafw` y `escritura`, que cargan `manifiesto/lib/manifiesto.py` por ruta y
usan `cargar` y `ruta`; `manifiesto/main.py bib` es el otro contrato. Estas pruebas fijan esa interfaz.
"""
import json
import textwrap

from conftest import pdf_minimo, sha256


# ---------------------------------------------------------------- verificar (paso 00)
def test_verificar_existe_por_titulo(caja):
    libro = caja.un_libro()
    r = caja.py("main.py", "verificar", "--json", "--titulo", libro["titulo"])
    assert r.returncode == 0, r.stdout + r.stderr
    datos = json.loads(r.stdout)
    assert datos["resultado"] == "existe"
    assert libro["id"] in [c["calibre_id"] for c in datos["candidatos"]]


def test_verificar_no_existe_y_sin_argumentos(caja):
    r = caja.py("main.py", "verificar", "--titulo", "qwzx título que no existe en ninguna biblioteca kjhg")
    assert r.returncode == 1
    r = caja.py("main.py", "verificar")
    assert r.returncode == 2
    assert "indica una referencia" in r.stdout


def test_verificar_archivo_consulta_ledgers(caja):
    """Un archivo que no está en Calibre pero sí en el ledger de ingesta: «no existe» y la nota del ledger."""
    archivo = caja.base / "suelto.pdf"
    archivo.write_bytes(pdf_minimo("Archivo suelto de prueba"))
    led = caja.repo / "ingesta" / "ingesta.tsv"
    with open(led, "a", encoding="utf-8") as f:
        f.write("\t".join(["2026-10-05", sha256(archivo), "programa-prueba/suelto.pdf", "t", "a", "Report", "Informe",
                           "2026", "", "", "99999", "", "", "catalogado"]) + "\n")
    r = caja.py("main.py", "verificar", "--archivo", archivo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Ledgers: ingesta: calibre_id 99999 (catalogado)" in r.stdout


def test_fuentes_y_estado(caja):
    r = caja.py("main.py", "fuentes")
    assert r.returncode == 0, r.stderr
    assert "articulo" in r.stdout and "congreso" in r.stdout
    n = len((caja.repo / "fuentes_descargadas.tsv").read_text(encoding="utf-8").splitlines()) - 1
    r = caja.py("main.py", "estado")
    assert r.returncode == 0, r.stderr
    assert f"Fuentes documentales adquiridas: {n}" in r.stdout


# ---------------------------------------------------------------- manifiesto (contrato)
def _proyecto(caja, libro):
    raiz = caja.docs / "escritura" / "reports" / "2026-10-05-prueba" / "fuentes"
    raiz.mkdir(parents=True)
    (raiz / "fuentes.yml").write_text(textwrap.dedent(f"""\
        proyecto: 2026-10-05-prueba
        generado: 2026-10-05
        fuentes:
        - origen: doc.pdf
          calibre_id: {libro['id']}
          zotero_key: ''
          clave_bibtex: ''
          titulo: x
          autores: x
          serie: ''
          anexo: ''
          sha256: ''
          uso: ''
          nota: ''
        """), encoding="utf-8")
    return raiz


def test_manifiesto_cargado_por_ruta(caja):
    """Como lo cargan datafw (pipeline/lib_proc/fuentes.py) y escritura (reporting/entorno.py)."""
    libro = caja.libro_con_archivo()
    raiz = _proyecto(caja, libro)
    codigo = textwrap.dedent(f"""\
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location("fuentes_manifiesto", {str(caja.repo / 'manifiesto' / 'lib' / 'manifiesto.py')!r})
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        d = m.cargar({str(raiz)!r})
        print(len(d["fuentes"]), d["fuentes"][0]["calibre_id"])
        print(m.ruta({str(raiz)!r}, "doc.pdf"))
        print(m.ruta({str(raiz)!r}, "{libro['id']}"))
        print(m.raiz_de({str(raiz / 'otro.pdf')!r}))
        """)
    r = caja.correr("python3", "-c", codigo)
    assert r.returncode == 0, r.stderr
    lineas = r.stdout.splitlines()
    assert lineas[0] == f"1 {libro['id']}"
    assert lineas[1] == str(libro["archivo"]) == lineas[2]
    assert lineas[3] == str(raiz)


def test_manifiesto_verificar_ruta_y_bib_en_seco(caja):
    libro = caja.libro_con_archivo()
    raiz = _proyecto(caja, libro)
    r = caja.py("manifiesto/main.py", "verificar", raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    r = caja.py("manifiesto/main.py", "ruta", raiz, "doc.pdf")
    assert r.returncode == 0 and r.stdout.strip() == str(libro["archivo"])
    antes = (raiz / "fuentes.yml").read_bytes()
    r = caja.py("manifiesto/main.py", "bib", raiz.parent)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "@" in r.stdout and "simulación" in r.stdout
    assert not (raiz.parent / "references.bib").exists()
    assert (raiz / "fuentes.yml").read_bytes() == antes


def test_manifiesto_todo_simula(caja):
    libro = caja.libro_con_archivo()
    _proyecto(caja, libro)
    r = caja.py("manifiesto/main.py", "todo")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "simulación" in r.stdout


# ---------------------------------------------------------------- fichas
FICHA_BUENA = """\
---
tipo: ficha_parafrasis
calibre_id: {bid}
zotero_key:
clave_bibtex: prueba2026
proyecto: 2026-10-05-prueba
pagina: 1
categoria: Concepto/definición
uso: 2
verificacion:
  estado: pendiente
  metodo:
  fecha:
---

## Paráfrasis
Una paráfrasis de prueba.

## Origen literal
«Documento de prueba»

## Control de fidelidad
Pendiente.

## Encadenamiento
Proviene de [prueba2026-fuente.md](prueba2026-fuente.md).
"""


def test_fichas_validar_y_estado(caja):
    libro = caja.un_libro()
    carpeta = caja.docs / "escritura" / "reports" / "2026-10-05-prueba" / "fuentes" / "fichas"
    carpeta.mkdir(parents=True)
    (carpeta / "prueba2026-p001-parafrasis-prueba.md").write_text(FICHA_BUENA.format(bid=libro["id"]), encoding="utf-8")
    r = caja.py("fichas/main.py", "validar", carpeta)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 fichas · 1 cumplen" in r.stdout
    (carpeta / "prueba2026-p002-parafrasis-mala.md").write_text(FICHA_BUENA.format(bid=libro["id"]).split("## Paráfrasis")[0], encoding="utf-8")
    r = caja.py("fichas/main.py", "validar", carpeta)
    assert r.returncode == 1
    assert "1 con faltas" in r.stdout
    r = caja.py("fichas/main.py", "estado", carpeta)
    assert r.returncode in (0, 1)
