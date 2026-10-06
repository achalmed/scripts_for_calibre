"""La ingesta de cursos: caracterizada en F1 sobre `ingesta_cursos/main.sh` y fundida en F3 en
`ingesta/main.sh cursos` (ola 2), que comparte ledger, catalogación y puerta con el resto de `ingesta`.

Prueba de salida de F3: `ingesta cursos --dry-run` anuncia exactamente lo que anunciaba el `main.sh` viejo
(las líneas `[simular]` y el recuento, fijados en F1), y además ya no escribe informes al simular.
"""
import csv

from conftest import pdf_minimo


def _curso(caja):
    curso = caja.docs / "docencia" / "contenido" / "cursos" / "curso-prueba"
    (curso / "05-recursos" / "lecturas").mkdir(parents=True)
    (curso / "curso.yml").write_text("curso: curso-prueba\nbibliografia: []\n", encoding="utf-8")
    pdf = curso / "05-recursos" / "lecturas" / "lectura_de_prueba.pdf"
    pdf.write_bytes(pdf_minimo("Lectura de prueba del curso"))
    return curso, pdf


def cursos(caja, *args):
    return caja.ingesta("cursos", *args)


def test_escanear_propone_ingestar(caja):
    _curso(caja)
    r = cursos(caja, "--escanear")
    assert r.returncode == 0, r.stdout + r.stderr
    tsvs = sorted((caja.repo / "ingesta" / "reportes" / "cursos").glob("candidatos_*.tsv"))
    assert len(tsvs) == 1
    filas = list(csv.DictReader(open(tsvs[0], encoding="utf-8"), delimiter="\t"))
    assert [(f["decision"], f["clase"], f["autor"]) for f in filas] == [("ingestar", "lectura", "Unknown")]
    assert filas[0]["ruta"] == "docencia/contenido/cursos/curso-prueba/05-recursos/lecturas/lectura_de_prueba.pdf"


def test_simular_anuncia_sin_escribir_en_calibre(caja):
    curso, pdf = _curso(caja)
    libro = caja.un_libro()
    tsv = caja.base / "candidatos.tsv"
    ruta = str(pdf.relative_to(caja.docs))
    tsv.write_text("decision\tclase\tpaginas\tMB\tautor\ttitulo\tcurso\truta\tduplicado_id\n"
                   f"ingestar\tlectura\t1\t0\tUnknown\tLectura de prueba\tcurso-prueba\t{ruta}\t\n"
                   f"duplicado\tlectura\t1\t0\tUnknown\tOtra lectura\tcurso-prueba\t{ruta}\t{libro['id']}\n"
                   f"omitir\tplantilla\t1\t0\tUnknown\tNada\tcurso-prueba\t{ruta}\t\n", encoding="utf-8")
    antes = caja.huella_db()
    r = cursos(caja, "--dry-run", "--tsv", tsv)
    assert r.returncode == 0, r.stdout + r.stderr
    salida = r.stdout + r.stderr
    assert f'[simular] calibredb add -t "Lectura de prueba" -a "Unknown" "{ruta}"' in salida
    assert f"[simular] duplicado de id={libro['id']}: enlazar temario y retirar {ruta}" in salida
    assert "filas=2 · añadidos=0 · duplicados enlazados=0" in salida
    assert caja.huella_db() == antes
    assert pdf.exists()
    assert "bibliografia: []" in (curso / "curso.yml").read_text(encoding="utf-8")
    assert not (caja.repo / "ingesta" / "reportes").exists()      # simular no deja informes (antes sí)
    assert not (caja.repo / "ingesta_cursos").exists()            # la sub-suite vieja salió del árbol


def test_sin_tsv_sale_3(caja):
    r = cursos(caja)
    assert r.returncode == 3
    assert "--escanear" in r.stdout + r.stderr


def test_aplicar_en_la_copia_por_la_puerta(caja, sin_calibre_abierto):
    import yaml
    from conftest import saltar_si_calibre
    curso, pdf = _curso(caja)
    ruta = str(pdf.relative_to(caja.docs))
    tsv = caja.base / "candidatos.tsv"
    tsv.write_text("decision\tclase\tpaginas\tMB\tautor\ttitulo\tcurso\truta\tduplicado_id\n"
                   f"ingestar\tlectura\t1\t0\tUnknown\tLectura de prueba\tcurso-prueba\t{ruta}\t\n", encoding="utf-8")
    ultimo = caja.max_id()
    r = cursos(caja, "--aplicar", "--tsv", tsv)
    saltar_si_calibre(r)
    assert r.returncode == 0, r.stdout + r.stderr
    assert caja.max_id() == ultimo + 1
    bib = yaml.safe_load((curso / "curso.yml").read_text(encoding="utf-8"))["bibliografia"]
    assert bib == [{"calibre_id": ultimo + 1, "titulo": "Lectura de prueba", "autor": "Unknown", "origen": ruta}]
    assert not pdf.exists()
    assert (caja.respaldos / "biblioteca" / "fuentes" / "originales-cursos" / ruta).is_file()
    assert list((caja.respaldos_puerta / "ingesta" / "calibre").glob("metadata_*.db"))
