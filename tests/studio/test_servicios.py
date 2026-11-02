"""tests/studio/test_servicios.py — los servicios y los modelos de Biblioteca Studio, sin Qt: el catálogo de operaciones
(cada una corre un programa que existe, simular nunca lleva --aplicar, lo que escribe en una base lo declara), la puerta
(candado, respaldos, timers), las lecturas de la muestra (índice, ledgers, entrada, fichas, manifiestos, coherencia) y
las filas de las tablas."""
from __future__ import annotations

import fcntl
import json
from pathlib import Path

from conftest import REPO

from biblioteca_app import modelos as mod  # noqa: E402
from biblioteca_app.servicios import datos, operaciones as ops, puerta  # noqa: E402


# --- el catálogo de operaciones ------------------------------------------------------------------------------------

def test_cada_operacion_corre_un_programa_que_existe():
    ids = [o.id for o in ops.todas()]
    assert len(ids) == len(set(ids)), "ids de operación repetidos"
    for o in ops.todas():
        assert o.programa().is_file(), f"{o.id}: no existe {o.orden[0]}"
        assert ops.etapa_de(o.id) in ops.NOMBRES_ETAPAS
    assert ops.NOMBRES_ETAPAS == ("libros", "adquirir", "entrada", "catalogar", "fichas", "manifiestos", "sincronizar", "puerta", "tareas")
    assert ops.etapa("puerta").operaciones == ()


def test_simular_nunca_aplica_y_aplicar_lleva_su_bandera():
    for o in ops.todas():
        valor = "x" if o.entrada else ""
        assert "--aplicar" not in o.argv(False, valor), o.id
        if o.aplicar:
            assert o.argv(True, valor)[-len(o.aplicar):] == list(o.aplicar), o.id
        assert o.verbo == ("Simular" if o.escribe else "Ejecutar")


def test_lo_que_escribe_en_una_base_lo_declara():
    for i in ("catalogar", "catalogacion", "koreader", "zotero_calibre", "notas", "migracion", "todo", "lectura", "enlazar_zotero", "metadatos_pdf"):
        assert "calibre" in ops.operacion(i).bases, i
    assert "zotero" in ops.operacion("zotero_calibre").bases
    for i in ("verificacion", "fuentes", "estado", "timers_verificar"):
        assert not ops.operacion(i).escribe, i


def test_la_orden_es_la_de_la_terminal_relativa_al_repo():
    o = ops.operacion("localizar")
    assert o.argv(False, 'openalex "Teoría general"', python="/usr/bin/python3")[-2:] == ["openalex", "Teoría general"]
    assert o.texto_orden(False, "congreso 'Ley 1'", python="/usr/bin/python3") == "/usr/bin/python3 main.py localizar congreso 'Ley 1'"
    assert ops.operacion("catalogar").texto_orden(True) == "bash ingesta/main.sh catalogar --aplicar"
    assert ops.operacion("enlazar_zotero").texto_orden(False) == "bash lectura/main.sh --enlazar --ris"
    assert ops.operacion("fichas_validar").valor_inicial() == "catalogacion/fichas"
    assert ops.relativa_al_repo(str(ops.REPO / "catalogacion" / "fichas")) == "catalogacion/fichas"
    assert ops.relativa_al_repo("/otra/carpeta") == "/otra/carpeta"


# --- la puerta -------------------------------------------------------------------------------------------------------

def test_candado_ocupado_y_respaldos(tmp_path):
    candado = tmp_path / "calibre.lock"
    assert puerta.candado_ocupado(candado) is False                      # no existe
    candado.write_text("")
    assert puerta.candado_ocupado(candado) is False
    with open(candado) as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert puerta.candado_ocupado(candado) is True
    assert puerta.respaldos(tmp_path / "no") == []
    (tmp_path / "puerta" / "koreader" / "calibre").mkdir(parents=True)
    (tmp_path / "puerta" / "koreader" / "calibre" / "metadata_1.db").write_bytes(b"x")
    filas = puerta.respaldos(tmp_path / "puerta")
    assert filas[0]["suite"] == "koreader" and filas[0]["n"] == 1 and filas[0]["ultimo"] != "—"


def test_timers_devuelve_las_tres_unidades():
    filas = puerta.timers()
    assert [f["unidad"] for f in filas] == [u + ".timer" for u in puerta.UNIDADES]
    for f in filas:
        assert set(f) >= {"activo", "proxima", "ultima", "resultado", "nivel"}


# --- las lecturas de la muestra --------------------------------------------------------------------------------------

def test_indice_y_libros(muestra):
    indice = datos.leer_indice(muestra.indice)
    lista = datos.libros(indice)
    assert len(lista) == 8 and all(d["id"].isdigit() for d in lista)
    assert datos.antiguedad_indice(indice).startswith("hace")
    assert datos.leer_indice(muestra.raiz / "no.json") == {"libros": {}, "biblioteca": "", "generado": "", "notas": ""}
    con_zotero = [d for d in lista if d["zotero_key"]]
    assert len(con_zotero) == 5 and sum(bool(d["clave"]) for d in con_zotero) == 4
    assert sum(bool(d["fichas"]) for d in lista) == 2


def test_entrada_cruza_la_zona_con_los_ledgers(muestra):
    filas = {f["archivo"]: f for f in datos.entrada(muestra.repo, muestra.raiz)}
    assert filas["ley_31143.pdf"]["paso"] == "catalogado" and filas["ley_31143.pdf"]["calibre_id"]
    assert filas["articulo_muestra.pdf"]["paso"] == "identificado" and filas["articulo_muestra.pdf"]["confianza"] == "media"
    assert filas["informe_sin_identificar.pdf"]["paso"] == "recibido"
    assert filas["tesis_borrador.pdf"]["paso"] == "identificado" and filas["tesis_borrador.pdf"]["origen"] == "proyecto-muestra/tesis_borrador.pdf"
    assert filas["no_existe.pdf"]["paso"] == "sin archivo" and filas["no_existe.pdf"]["existe"] is False
    assert "fuentes.yml" not in filas


def test_descargas_catalogacion_fichas_y_manifiestos(muestra):
    d = datos.descargas(muestra.repo)
    assert [x["estado"] for x in d] == ["error", "descargado", "descargado"]       # la más reciente primero
    c = datos.catalogacion(muestra.repo)
    assert len(c) == 4 and [x["ficha"] for x in c] == ["sí", "sí", "no", "no"]
    f = datos.fichas(muestra.repo)
    assert len(f) == 2 and f[0]["verificacion"] == "verificada_script" and f[0]["nivel"] == "positivo" and f[1]["verificacion"] == "pendiente"
    assert f[0]["titulo"].startswith("Economía") and f[0]["proyecto"] == "muestra" and f[0]["calibre_id"] == "1"
    env = datos.cargar_env()
    m = datos.manifiestos(type("E", (), {"DOCS_ROOT": muestra.raiz, "DATAFW_DIR": muestra.raiz / "datafw", "WRITING_DIR": muestra.raiz / "escritura"})(), muestra.repo)
    assert len(m) == 1 and m[0]["proyecto"] == "proyecto-muestra" and m[0]["entradas"] == 2 and m[0]["sin_libro"] == 1 and m[0]["nivel"] == "negativo"
    assert m[0]["carpeta"] == "repo/entrada/proyecto-muestra"
    assert env is not None


def test_coherencia_sin_correr_nada(muestra):
    indice = datos.leer_indice(muestra.indice)
    comps = {c["comprobacion"]: c for c in datos.coherencia(indice, datos.fichas(muestra.repo), datos.catalogacion(muestra.repo))}
    assert comps["Libros sin clave de Zotero"]["cuantos"] == 3 and comps["Libros sin clave de Zotero"]["nivel"] == "negativo"
    assert comps["Libros sin clave para citar"]["cuantos"] == 1
    assert comps["Notas de lectura sin enlazar"]["cuantos"] == 1 and comps["Notas de lectura sin enlazar"]["operacion"] == "notas"
    assert comps["Fichas sin libro en el índice"]["cuantos"] == 0 and comps["Fichas sin libro en el índice"]["resultado"] == "en orden"
    assert comps["Filas de catalogación sin ficha"]["cuantos"] == 2
    assert comps["Índice de libros"]["nivel"] == "positivo" and "8 libros" in comps["Índice de libros"]["resultado"]
    assert len(comps["Libros sin clave de Zotero"]["afectados"]) == 3


# --- las filas de las tablas ----------------------------------------------------------------------------------------

def test_filas_y_contadores_de_libros(muestra):
    lista = datos.libros(datos.leer_indice(muestra.indice))
    f = mod.fila_libro(lista[0])
    assert f["titulo"] and f["id"] == "1" and f["clave"] != "—" and f["fichas"] == "1" and f["nivel"] == "positivo" and f["crudo"]["id"] == 1
    c = mod.contar_libros(lista)
    assert c == {"todos": 8, "sin_zotero": 3, "sin_clave": 1, "sin_ficha": 6, "sin_nota": 8}
    assert mod.resumen_libros(c) == "8 libros · 3 sin Zotero · 1 sin clave para citar · 6 sin ficha · 8 sin nota"
    assert mod.resumen_libros({"todos": 0}).startswith("Sin índice")
    assert [x[0] for x in mod.FILTROS_LIBROS] == ["todos", "sin_zotero", "sin_clave", "sin_ficha", "sin_nota"]


def test_campos_elemento_y_filas_de_etapa():
    campos = mod.campos_elemento({"archivo": "a.pdf", "paso": "recibido", "nivel": "neutro", "ruta": "/x/a.pdf", "crudo": {}}, mod.COLUMNAS["entrada"])
    assert campos[0] == {"etiqueta": "Archivo", "valor": "a.pdf"} and campos[1]["valor"] == "recibido"
    assert {c["etiqueta"] for c in campos} >= {"Ruta"} and all(c["etiqueta"] != "Nivel" for c in campos)
    assert mod.fila_manifiesto({"proyecto": "p", "entradas": 3, "sin_libro": 0})["sin_libro"] == "—"
    assert mod.fila_coherencia({"comprobacion": "x", "cuantos": 2, "nivel": "negativo", "resultado": "2"}, "Op")["resuelve"] == "Op"
    assert mod.fila_tarea({"unidad": "u", "activo": "no instalado"})["habilitado"] is False
    assert json.dumps(mod.COLUMNAS)                      # serializable: lo que QML recibe
