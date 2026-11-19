"""tests/fuentes/test_catalogar_ia.py — catalogar con un chat (decisiones §9.15, `lib/catalogar_ia.py`).

Sobre un repo de prueba en un temporal (los dos registros) y una metadata.db mínima con los vocabularios cerrados (nunca la
biblioteca real): el prompt rellena su «4 Entrada» y pide el bloque de vuelta; lo pegado se comprueba sin IA; guardar simula
por defecto, no escribe con problemas y, con `aplicar`, reescribe solo la fila de la obra y conserva las demás tal cual.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
HOY = dt.date(2026, 11, 19)
SHA = "c" * 64

PENDIENTES = ("sha256\torigen\tautores\ttitulo\ttipo_zotero\tclasificador\titem_type\teditorial\tfecha\tidentificador\tidioma\ttags\t"
              "confianza\tnota\tficha\tserie\tserie_index\n"
              f"{'a' * 64}\totro.pdf\tINEI\tOtro documento\tReport\tInforme\tReport\t\t2018\t\tSpanish\testadistica\talta\t\t\t\t\n"
              f"{SHA}\tproyecto/acunaascencio2024incidence.pdf\tOIT\tInternational Journal of Energy Economics and\tReport\tInforme\t"
              "report\tOIT\t2023\t\tSpanish\tdocumento_oficial\talta\t\tc29c7460_x.md\t\t0\n")
RESUMEN = ("id\tautores\ttitulo\ttipo_zotero\tclasificador\teditorial\tfecha\tidentificador\tidioma\ttags\tconfianza\tnota\n"
           "9894\tClara, Penalver & Sara, Sanchez\tCuentos para educar con inteligencia emocional\tBook\tLibro\tPenguin\t2014\t"
           "isbn:9788448843809\tSpanish\tpedagogia, aprendizaje\talta\tEdicion digital\n"
           "9895\tLuis M., Benavides\tCuentos para ser humano\tBook\tLibro\t\t2012\t\tSpanish\tpedagogia\talta\t\n")

RESPUESTA = """Es un artículo de revista.

```yaml
tipo: catalogacion
autores: "Edwin, Acuña Ascencio & María, Rojas"
titulo: "Incidence of energy poverty in Peru"
tipo_zotero: Journal Article
clasificador: artículo de revista
item_type: journal article
editorial: "EconJournals"
fecha: 2024
identificador: "doi:10.32479/ijeep.00000"
idioma: English
tags: [economia, energia, pobreza_nueva]
serie: ""
serie_index: ""
confianza: media
verificar: ["identificador: el DOI no se lee en la portada"]
nota: "Artículo de la revista IJEEP"
```
"""


def _cargar():
    spec = importlib.util.spec_from_file_location("catalogar_ia_prueba", REPO / "lib" / "catalogar_ia.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["catalogar_ia_prueba"] = m
    spec.loader.exec_module(m)
    return m


def _db(ruta: Path) -> None:
    con = sqlite3.connect(ruta)
    con.executescript("""
        create table custom_columns (id integer primary key, label text, display text);
        create table tags (id integer primary key, name text);
        create table books_tags_link (id integer primary key, book integer, tag integer);
        create table authors (id integer primary key, name text);
        create table custom_column_7 (id integer primary key, book integer, value text);
    """)
    con.execute("insert into custom_columns values (5, 'clasificador', ?)",
                (json.dumps({"enum_values": ["Libro", "Informe", "Artículo de revista", "Informe técnico"]}),))
    con.execute("insert into custom_columns values (6, 'item_type', ?)",
                (json.dumps({"enum_values": ["Book", "Report", "Journal Article"]}),))
    con.execute("insert into custom_columns values (7, 'zotero_key', '{}')")
    con.executemany("insert into tags (name) values (?)", [("economia",), ("energia",), ("pedagogia",), ("aprendizaje",), ("estadistica",)])
    con.executemany("insert into authors (name) values (?)", [("Edwin| Acuna Ascencio",), ("Clara| Penalver",)])
    con.execute("insert into custom_column_7 (book, value) values (9894, 'ABCD1234')")
    con.commit()
    con.close()


@pytest.fixture()
def mundo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "ingesta").mkdir(parents=True)
    (repo / "catalogacion").mkdir()
    (repo / "entrada" / "proyecto").mkdir(parents=True)
    (repo / "entrada" / "proyecto" / "acunaascencio2024incidence.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (repo / "ingesta" / "pendientes.tsv").write_text(PENDIENTES, encoding="utf-8")
    (repo / "catalogacion" / "resumen_catalogacion.tsv").write_text(RESUMEN, encoding="utf-8")
    db = tmp_path / "biblioteca" / "metadata.db"
    db.parent.mkdir()
    _db(db)
    prompts = tmp_path / "prompts"
    (prompts / "skills" / "fuentes-documentales" / "references").mkdir(parents=True)
    (prompts / "skills" / "fuentes-documentales" / "references" / "paso-02-catalogar.md").write_text(
        "---\ntitulo: 'Catalogar en Calibre'\nversion: '1.2.0'\n---\n# Paso 02\n\n## 4 Entrada\n\n- Archivo: [Inserta aquí]\n", encoding="utf-8")
    monkeypatch.delenv("BIBLIOTECA", raising=False)
    monkeypatch.delenv("QIR_BIBLIOTECA", raising=False)
    monkeypatch.setenv("CALIBRE_DB", str(db))
    monkeypatch.setenv("PROMPTS_DIR", str(prompts))
    return {"repo": repo, "m": _cargar(), "archivo": repo / "entrada" / "proyecto" / "acunaascencio2024incidence.pdf"}


def test_el_prompt_rellena_la_entrada_y_pide_el_bloque(mundo):
    m, repo = mundo["m"], mundo["repo"]
    r = m.prompt("entrada", str(mundo["archivo"]), repo)
    p = r["prompt"]
    assert r["fuente"]["version"] == "1.2.0" and r["titulo"] == "International Journal of Energy Economics and"
    assert "<entrada>" in p and "tipo: catalogacion" in p
    assert "acunaascencio2024incidence" in p and "clave de cita" in p           # el nombre del archivo es una clave de BibTeX
    assert "Informe técnico" in p and "Journal Article" in p and "economia" in p   # los vocabularios cerrados de Calibre
    assert "Carpeta de origen (serie): proyecto." in p
    assert m.prompt("entrada", SHA, repo)["titulo"] == r["titulo"]            # también por la huella
    with pytest.raises(LookupError):
        m.prompt("catalogar", "1", repo)


def test_leer_normaliza_comprueba_y_avisa(mundo):
    m, repo = mundo["m"], mundo["repo"]
    r = m.leer("entrada", SHA, RESPUESTA, repo, hoy=HOY)
    assert r["ok"], r["problemas"]
    c = r["campos"]
    assert c["clasificador"] == "Artículo de revista" and c["item_type"] == "Journal Article"   # la grafía del vocabulario
    assert c["tags"] == "economia, energia"                                                    # la nueva, fuera…
    assert "etiquetas propuestas: pobreza_nueva" in c["nota"]                                   # …y propuesta en la nota
    assert "por verificar: identificador" in c["nota"] and "revisada con un chat" in c["nota"]
    assert any("Acuna Ascencio" in a for a in r["avisos"])                                     # la grafía que ya existe
    assert {x["campo"] for x in r["cambios"]} >= {"autores", "titulo", "tipo_zotero", "clasificador"}


@pytest.mark.parametrize("cambio, problema", [
    ("clasificador: artículo de revista", "clasificador: Folleto raro", ),
    ("fecha: 2024", "fecha: 2031"),
    ('autores: "Edwin, Acuña Ascencio & María, Rojas"', "autores: Desconocido"),
    ("tipo_zotero: Journal Article", "tipo_zotero: Revista"),
    ('serie: ""', 'serie: "Energía - Perú"'),
])
def test_leer_rechaza_lo_que_no_cumple(mundo, cambio, problema):
    r = mundo["m"].leer("entrada", SHA, RESPUESTA.replace(cambio, problema), mundo["repo"], hoy=HOY)
    assert not r["ok"] and r["problemas"]


def test_sin_bloque_o_con_yaml_roto(mundo):
    m, repo = mundo["m"], mundo["repo"]
    assert "No hay un bloque" in m.leer("entrada", SHA, "Hola, no sé.", repo)["problemas"][0]
    roto = "```yaml\ntipo: catalogacion\ntitulo: [sin cerrar\n```"
    assert "no se puede leer" in m.leer("entrada", SHA, roto, repo)["problemas"][0]


def test_guardar_simula_y_luego_reescribe_solo_esa_fila(mundo):
    m, repo = mundo["m"], mundo["repo"]
    ruta = repo / "ingesta" / "pendientes.tsv"
    antes = ruta.read_text(encoding="utf-8")
    r = m.guardar("entrada", SHA, RESPUESTA, repo=repo, hoy=HOY)
    assert r["ok"] and not r["escrito"] and ruta.read_text(encoding="utf-8") == antes       # simula
    r = m.guardar("entrada", SHA, RESPUESTA.replace("fecha: 2024", "fecha: 2031"), aplicar=True, repo=repo, hoy=HOY)
    assert not r["escrito"] and ruta.read_text(encoding="utf-8") == antes                   # con problemas, no escribe
    r = m.guardar("entrada", SHA, RESPUESTA, aplicar=True, repo=repo, hoy=HOY)
    assert r["escrito"]
    nuevo = ruta.read_text(encoding="utf-8").splitlines()
    assert nuevo[0] == antes.splitlines()[0] and nuevo[1] == antes.splitlines()[1]          # la cabecera y la otra fila, intactas
    fila = dict(zip(nuevo[0].split("\t"), nuevo[2].split("\t")))
    assert fila["titulo"] == "Incidence of energy poverty in Peru" and fila["confianza"] == "media"
    assert fila["ficha"] == "c29c7460_x.md" and fila["sha256"] == SHA                     # lo que no se catalogó, igual


def test_catalogar_sin_columnas_de_serie_y_con_zotero(mundo):
    m, repo = mundo["m"], mundo["repo"]
    pegado = RESPUESTA.replace("Edwin, Acuña Ascencio & María, Rojas", "Clara, Peñalver & Sara, Sánchez")
    r = m.leer("catalogar", "9894", pegado, repo, hoy=HOY)
    assert r["ok"], r["problemas"]
    assert "item_type" not in r["campos"] and "serie" not in r["campos"]                     # el registro no tiene esas columnas
    assert any("no tiene columna" in a for a in r["avisos"])
    assert any("ya tiene ítem en Zotero" in a for a in r["avisos"])                          # título y autor de un libro con ítem
    assert any("«Clara, Penalver»" in a for a in r["avisos"])                               # la grafía sin tildes que ya existe
    ruta = repo / "catalogacion" / "resumen_catalogacion.tsv"
    m.guardar("catalogar", "9894", pegado, aplicar=True, repo=repo, hoy=HOY)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert lineas[2] == RESUMEN.splitlines()[2] and '"' not in lineas[1]                   # la otra fila igual; sin comillas (Bash)
    assert lineas[1].split("\t")[0] == "9894" and len(lineas[1].split("\t")) == 12
