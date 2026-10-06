"""tests/test_calibre_caracterizacion.py — caracterización de los tres sincronizadores vivos (ola 2, K1; R-2).

Objetivo: fijar lo que hacen hoy `script_ecosistema_lectura`, `script_koreader_estudio` y
  `script_sincronizar_zotero` antes de tocar su código (Feathers 2002, calibre_id 10437): el árbol de
  trabajo debe producir, sobre las mismas copias, el mismo reporte y el mismo cambio en las bases que la
  referencia de git (`calibre_apoyo.REFERENCIA`).
Método: para cada suite y modo (simulación y `--aplicar`), dos corridas aisladas desde la misma foto de
  las bases reales; se comparan las filas del reporte y el delta semántico de metadata.db y zotero.sqlite.
  `sincronizar_zotero` se corre además sobre una copia «perturbada» (títulos, ISBN, valoración, adjuntos,
  creadores, etiquetas, idioma, tipo y espejo desfasados a propósito) para ejercitar cada camino de
  escritura, que en la foto real del día suele estar vacío.
Límite: la perturbación del relleno de la fecha (`pubdate`) va aparte (prueba siguiente) porque la
  referencia falla ahí (ver su docstring).
"""
from __future__ import annotations

import sqlite3

import pytest

import calibre_apoyo as ap

pytestmark = pytest.mark.caracterizacion

SUITES = {
    "ecosistema_lectura": ("script_ecosistema_lectura", "reportes", "sync_*.tsv"),
    "koreader_estudio": ("script_koreader_estudio", "reportes", "sync_*.tsv"),
    "sincronizar_zotero": ("script_sincronizar_zotero", "reportes", "sync_*.tsv"),
}


def _cal_rw(db):
    """Conexión de prueba a la COPIA de Calibre con las funciones que piden sus disparadores."""
    c = sqlite3.connect(db)
    c.create_function("title_sort", 1, lambda s: s)
    c.create_function("uuid4", 0, lambda: "00000000-0000-0000-0000-000000000000")
    return c


def _col(c, label):
    return c.execute("select id from custom_columns where label = ?", (label,)).fetchone()[0]


def _enlazados(cal, zot):
    """[(libro, clave, itemID)] de los libros con #zotero_key que existe en Zotero, por id."""
    n = _col(cal, "zotero_key")
    claves = dict(zot.execute("select key, itemID from items"))
    return [(b, k.strip(), claves[k.strip()])
            for b, k in cal.execute(f"select book, value from custom_column_{n} order by book")
            if k and k.strip() in claves]


def _valor(zot, texto):
    r = zot.execute("select valueID from itemDataValues where value = ?", (texto,)).fetchone()
    if r:
        return r[0]
    return zot.execute("insert into itemDataValues(value) values (?)", (texto,)).lastrowid


def _campo(zot, item, campo, texto):
    fid = zot.execute("select fieldID from fields where fieldName = ?", (campo,)).fetchone()[0]
    vid = _valor(zot, texto)
    zot.execute("delete from itemData where itemID = ? and fieldID = ?", (item, fid))
    zot.execute("insert into itemData(itemID, fieldID, valueID) values (?,?,?)", (item, fid, vid))


def perturbar(c: "Corrida", fecha: bool = False) -> None:  # noqa: F821
    """Desfasa a propósito una muestra fija de pares, igual en las dos corridas."""
    cal, zot = _cal_rw(c.calibre), sqlite3.connect(c.zotero)
    pares = _enlazados(cal, zot)
    tomar = iter(pares)

    def siguiente(cond=lambda b, k, i: True):
        for b, k, i in tomar:
            if cond(b, k, i):
                return b, k, i
        raise AssertionError("la foto no tiene pares suficientes para perturbar")

    def z_tiene(i, campo):
        return zot.execute("select 1 from itemData d join fields f on f.fieldID = d.fieldID "
                           "where d.itemID = ? and f.fieldName = ?", (i, campo)).fetchone()

    if fecha:
        for _ in range(3):   # año vacío en Calibre y presente en Zotero → relleno de pubdate
            b, k, i = siguiente(lambda b, k, i: z_tiene(i, "date"))
            cal.execute("update books set pubdate = '0101-01-01 00:00:00+00:00' where id = ?", (b,))
    else:
        for _ in range(3):   # título distinto en Zotero → calibre->zotero
            b, k, i = siguiente()
            _campo(zot, i, "title", "Título perturbado por la prueba")
        for _ in range(3):   # ISBN solo en Zotero → relleno en Calibre
            b, k, i = siguiente(lambda b, k, i: z_tiene(i, "ISBN") and cal.execute(
                "select 1 from identifiers where book = ? and type = 'isbn'", (b,)).fetchone())
            cal.execute("delete from identifiers where book = ? and type = 'isbn'", (b,))
        for _ in range(2):   # estrellas en Zotero y Calibre sin valoración → relleno de rating
            b, k, i = siguiente(lambda b, k, i: not cal.execute(
                "select 1 from books_ratings_link where book = ?", (b,)).fetchone())
            t = zot.execute("select tagID from tags where name = '⭐⭐⭐'").fetchone()
            tid = t[0] if t else zot.execute("insert into tags(name) values ('⭐⭐⭐')").lastrowid
            zot.execute("insert or ignore into itemTags(itemID, tagID, type) values (?,?,0)", (i, tid))
        for _ in range(2):   # adjunto con ruta rota → reparar
            b, k, i = siguiente(lambda b, k, i: zot.execute(
                "select 1 from itemAttachments where parentItemID = ? and linkMode = 2 "
                "and path like 'attachments:%'", (i,)).fetchone())
            zot.execute("update itemAttachments set path = 'attachments:Ruta rota (0)/no-existe.pdf' "
                        "where parentItemID = ? and linkMode = 2", (i,))
        for _ in range(2):   # sin creadores en Zotero → calibre->zotero
            b, k, i = siguiente()
            zot.execute("delete from itemCreators where itemID = ?", (i,))
        for _ in range(2):   # etiquetas manuales borradas en Zotero
            b, k, i = siguiente(lambda b, k, i: cal.execute(
                "select 1 from books_tags_link where book = ?", (b,)).fetchone())
            zot.execute("delete from itemTags where itemID = ? and type = 0", (i,))
        for _ in range(2):   # idioma fuera de ISO en Zotero → normalizar
            b, k, i = siguiente(lambda b, k, i: cal.execute(
                "select 1 from books_languages_link where book = ?", (b,)).fetchone())
            _campo(zot, i, "language", "Idioma perturbado")
        n39 = _col(cal, "item_type")
        rep = cal.execute(f"select id from custom_column_{n39} where value = 'Report'").fetchone()[0]
        for _ in range(1):   # tipo distinto en Calibre → cambio de tipo en Zotero
            b, k, i = siguiente(lambda b, k, i: cal.execute(
                f"select 1 from books_custom_column_{n39}_link l join custom_column_{n39} v "
                f"on v.id = l.value where l.book = ? and v.value = 'Book'", (b,)).fetchone())
            cal.execute(f"update books_custom_column_{n39}_link set value = ? where book = ?", (rep, b))
        n25 = _col(cal, "zotero_title")
        for _ in range(3):   # espejo vacío en Calibre → se repuebla
            b, k, i = siguiente()
            cal.execute(f"delete from custom_column_{n25} where book = ?", (b,))
    cal.commit()
    zot.commit()
    cal.close()
    zot.close()


def _comparar(arboles, corrida, nombre, args, perturbacion=None, exigir_exito=True):
    """Corre referencia y árbol actual a la vez sobre copias idénticas y compara reporte y deltas."""
    suite, sub, patron = SUITES[nombre]
    estado = {}
    for impl in ("ref", "act"):
        c = corrida(impl)
        if perturbacion:
            perturbacion(c)
        carpeta = arboles[impl] / suite / sub
        previos = set(carpeta.glob(patron)) if carpeta.exists() else set()
        antes = (ap.volcado_calibre(c.calibre), ap.volcado_zotero(c.zotero))
        proc, fh = ap.lanzar(arboles[impl], suite, args, c.env, c.raiz / "salida.txt")
        estado[impl] = (c, carpeta, previos, antes, proc, fh)
    medidas = {}
    for impl, (c, carpeta, previos, antes, proc, fh) in estado.items():
        codigo = proc.wait(timeout=300)
        fh.close()
        texto = (c.raiz / "salida.txt").read_text(errors="replace")
        nuevos = sorted(set(carpeta.glob(patron)) - previos)
        medidas[impl] = {
            "salida": codigo,
            "texto": texto,
            "reporte": sorted(nuevos[-1].read_text(encoding="utf-8").splitlines()) if nuevos else None,
            "calibre": ap.delta(antes[0], ap.volcado_calibre(c.calibre)),
            "zotero": ap.delta(antes[1], ap.volcado_zotero(c.zotero)),
        }
        if exigir_exito:
            assert codigo == 0, f"{impl}: salida {codigo}\n{texto[-4000:]}"
    if exigir_exito:
        for clave in ("reporte", "calibre", "zotero"):
            assert medidas["act"][clave] == medidas["ref"][clave], \
                f"{nombre} {args}: «{clave}» difiere de la referencia"
    return medidas


@pytest.mark.parametrize("nombre", list(SUITES))
def test_simulacion_igual_a_la_referencia(arboles, corrida, nombre):
    m = _comparar(arboles, corrida, nombre, [])
    assert m["act"]["reporte"] is not None, "la simulación no dejó reporte"
    # en simulación nada se escribe (salvo lo volátil que Calibre toque al abrir la base)
    assert {k for k, v in m["act"]["calibre"].items() if v != "cambió"} == set()
    assert m["act"]["zotero"] == {}


@pytest.mark.parametrize("nombre", list(SUITES))
def test_aplicar_igual_a_la_referencia(arboles, corrida, nombre):
    _comparar(arboles, corrida, nombre, ["--aplicar"])


def test_sincronizar_zotero_perturbado_igual_a_la_referencia(arboles, corrida):
    m = _comparar(arboles, corrida, "sincronizar_zotero", ["--aplicar"], perturbar)
    campos = {k[1] for k in m["act"]["calibre"]} | {k[1] for k in m["act"]["zotero"]}
    # cada camino de escritura quedó ejercitado
    for esperado in ("identifiers", "rating", "#zotero_title", "f:title", "creadores", "etiquetas",
                     "adjunto", "f:language", "tipo"):
        assert esperado in campos, f"la perturbación no ejercitó «{esperado}»"



@pytest.mark.xfail(strict=True, reason="defecto de la referencia que K3 corrige: el relleno de pubdate por SQL "
                   "directo choca con el disparador books_update_trg (title_sort) después de escribir Zotero")
def test_sincronizar_zotero_relleno_de_fecha(arboles, corrida):
    """Calibre sin año y Zotero con año: la referencia escribe Zotero, falla con «no such function:
    title_sort» y deja Calibre sin tocar (ni la fecha, ni el espejo, ni los demás rellenos). Lo esperado
    tras K3: el mismo cambio en Zotero y, además, la fecha rellenada en Calibre, con salida 0."""
    m = _comparar(arboles, corrida, "sincronizar_zotero", ["--aplicar"],
                  lambda c: perturbar(c, fecha=True), exigir_exito=False)
    ref, act = m["ref"], m["act"]
    assert ref["salida"] != 0 and "title_sort" in ref["texto"]      # el defecto, fijado
    assert act["salida"] == 0, act["texto"][-3000:]
    assert act["zotero"] == ref["zotero"]
    fechas = {k: v for k, v in act["calibre"].items() if k[1] == "pubdate"}
    assert len(fechas) == 3 and all(v[1].endswith("-01-01T00:00:00+00:00") for v in fechas.values())
