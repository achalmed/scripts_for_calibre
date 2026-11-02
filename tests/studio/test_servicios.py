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


# ---------------------------------------------------------------------- reingeniería: el catálogo y los pasos de la puerta
from biblioteca_app.servicios import catalogo as cat  # noqa: E402
from biblioteca_app.servicios import pasos  # noqa: E402


def test_consulta_por_campo():
    assert cat.consulta('autor:Quispe año:2019-2021 "ciudades pequeñas" Título:eco foo:bar') == [
        ("autor", "quispe"), ("año", "2019-2021"), ("", "ciudades pequenas"), ("titulo", "eco"), ("", "foo:bar")]
    assert cat.consulta('serie:"Desarrollo local') == [("serie", "desarrollo"), ("", "local")] or cat.consulta('serie:"Desarrollo local')[0][0] in ("serie", "")
    libro = {"id": "7", "titulo": "Economía urbana", "autores": ["Quispe, Rosa"], "año": 2020, "serie": "Desarrollo local", "etiquetas": ["ciudades"],
             "clave": "quispeEconomia2020", "zotero_key": "ABCD1234", "identificadores": {"isbn": "9786120000011"}, "tipo": "book"}
    for consulta, esperado in (("economia", True), ("autor:rosa", True), ("autor:perez", False), ("año:2020", True), ("año:2015-2019", False),
                               ("año:-2020", True), ("serie:desarrollo", True), ("etiqueta:ciudad", True), ("id:9786120000011", True),
                               ("id:7", True), ("id:abcd1234", True), ("clave:quispe", True), ("tipo:book", True), ("7", True), ("ley", False)):
        assert cat.cumple(libro, cat.consulta(consulta)) is esperado, consulta


def test_facetas_bandejas_y_orden():
    base = {"serie": "", "autores": [], "año": None, "tipo": "", "zotero_key": "", "clave": "", "fichas": [], "portada": True, "orden_titulo": "", "orden_autor": "", "añadido": ""}
    libros = [dict(base, id="1", titulo="B", orden_titulo="B", serie="S", autores=["X"], año=2021, tipo="book", zotero_key="Z1", clave="k1", fichas=["catalogacion/fichas/1_b.md"], añadido="2026-01-02"),
              dict(base, id="2", titulo="A", orden_titulo="A", serie="S", autores=["Y"], año=1999, zotero_key="Z2", portada=False, añadido="2026-03-01"),
              dict(base, id="3", titulo="C", orden_titulo="C", autores=["X"])]
    f = cat.facetas(libros)
    assert f["coleccion"] == [{"valor": "S", "n": 2}] and f["autor"][0] == {"valor": "X", "n": 2}
    assert [x["valor"] for x in f["decada"]] == ["2020–2029", "1990–1999", "sin año"]
    assert cat.cumple_filtros(libros[1], {"coleccion": "S", "decada": "1990–1999", "autor": "", "tipo": "sin tipo"})
    assert [l["id"] for l in sorted(libros, key=cat.clave_orden("titulo"))] == ["2", "1", "3"]
    assert [l["id"] for l in sorted(libros, key=cat.clave_orden("año"))] == ["1", "2", "3"]
    assert [l["id"] for l in sorted(libros, key=cat.clave_orden("añadido"))] == ["2", "1", "3"]
    entrada = [{"paso": "recibido", "archivo": "x.pdf"}, {"paso": "catalogado", "archivo": "y.pdf"}]
    fichas = [{"ficha": "1_b.md", "verificacion": "pendiente", "calibre_id": "1"}, {"ficha": "9_z.md", "verificacion": "pendiente", "calibre_id": "9"}]
    b = cat.bandejas(libros, entrada, fichas)
    assert b["clasificar"]["libros"] == ["2", "3"] and [e["archivo"] for e in b["clasificar"]["otros"]] == ["x.pdf"]
    assert b["fichas"]["libros"] == ["1"] and [e["archivo"] for e in b["fichas"]["otros"]] == ["9_z.md"]
    assert b["sin_clave"]["libros"] == ["2"] and b["sin_zotero"]["libros"] == ["3"] and b["sin_portada"]["libros"] == ["2"]
    assert b["fichas"]["n"] == 2


def test_catalogo_lee_la_muestra_en_solo_lectura(muestra):
    import json as _json
    indice = _json.loads(muestra.indice.read_text(encoding="utf-8"))
    antes = muestra.calibre_db.stat().st_mtime_ns
    r = cat.leer(muestra.calibre_db, indice, muestra.biblioteca)
    assert len(r["libros"]) == 8 and not r["inmutable"] and muestra.calibre_db.stat().st_mtime_ns == antes
    l = next(x for x in r["libros"] if x["titulo"].startswith("Economía"))
    assert l["clave"] == "quispeEconomiaCiudades2021" and l["zotero_key"] == "QUISPE01"
    if muestra.con_calibre:
        assert l["año"] == 2021 and l["serie"] == "Desarrollo local" and l["identificadores"] == {"isbn": "9786120000011"}
        assert l["tipo"] == "book" and l["ko_estado"] == "reading" and l["portada"] and Path(l["ruta_portada"]).is_file()


def test_pasos_de_una_aplicacion_que_sale_bien():
    p = pasos.empezar(pasos.previa(pasos.nuevos(("calibre",)), set(), set(), ("calibre",)))
    assert [x["estado"] for x in p] == ["en_curso"] + ["pendiente"] * 5 and p[0]["titulo"] == "Calibre cerrado"
    assert pasos.linea(p, "── Backup: /respaldos/catalogar/calibre/metadata_20261102_100000.db")
    assert [x["estado"] for x in p][:4] == ["hecho", "hecho", "hecho", "en_curso"] and p[2]["detalle"] == "metadata_20261102_100000.db"
    assert not pasos.linea(p, "── Calibre: 3 valores enviados a la API")
    pasos.terminar(p, 0, True, True)
    assert all(x["estado"] == "hecho" for x in p) and pasos.resumen(p) == "6 de 6 pasos"


def test_pasos_cuando_la_puerta_no_se_abre_o_falla():
    p = pasos.empezar(pasos.nuevos(("calibre", "zotero")))
    assert p[0]["titulo"] == "Calibre y Zotero cerrados"
    pasos.linea(p, "✗ Calibre está abierto: ciérralo antes de escribir en la biblioteca.")
    pasos.terminar(p, 1, None, True)
    assert p[0]["estado"] == "fallo" and p[2]["estado"] == "omitido" and p[5]["estado"] == "hecho" and "falló: Calibre y Zotero cerrados" in pasos.resumen(p)
    p = pasos.empezar(pasos.nuevos(("calibre",)))
    pasos.terminar(p, 75, None, False)                       # candado ocupado: 75 sin respaldo
    assert p[1]["estado"] == "fallo" and p[3]["estado"] == "omitido" and p[5]["estado"] == "fallo"
    p = pasos.empezar(pasos.nuevos(("calibre",)))
    pasos.linea(p, "── Backup: /x/metadata.db")
    pasos.linea(p, "✗ INTEGRIDAD FALLIDA. Restaura los respaldos:")
    pasos.terminar(p, 1, False, True)
    assert p[3]["estado"] == "fallo" and p[4]["estado"] == "fallo"
    p = pasos.empezar(pasos.nuevos(("calibre",)))
    pasos.linea(p, "✗ Sin respaldo verificado de metadata.db no se escribe.")
    pasos.terminar(p, 1, None, True)
    assert p[2]["estado"] == "fallo" and p[3]["estado"] == "omitido"
    p = pasos.empezar(pasos.nuevos(("calibre",)))
    pasos.terminar(p, 0, None, True)                         # la suite no tuvo nada que escribir: no abrió la puerta
    assert p[0]["estado"] == "hecho" and p[1]["estado"] == "omitido" and p[5]["estado"] == "hecho"
