"""tests/fuentes/test_traer.py — `main.py traer`: los pasos 00 a 03 de una norma, sobre la caja de arena.

Objetivo: que traer una norma simule sin escribir, que con `--aplicar` la catalogue en la COPIA de la biblioteca como
  norma (Statute, Normativa, `norma:`, serie, fecha completa) por la puerta y deje su RIS de tipo statute, y que con la
  puerta ocupada salga 75 sin descargar nada.
Método: un guion corre `lib/traer.py` dentro de la caja con las fuentes reemplazadas (sin red): la ficha de gob.pe es
  la del 2026-11-15 de la Ley 28077 y el PDF, uno mínimo. La prueba con red de las tres normas del canon está en
  `test_traer_red.py` (se salta sin `TRAER_RED=1`).
Límite: no importa el RIS en Zotero (eso lo hace Zotero, a mano).
"""
import json
import sqlite3

from conftest import CandadoOcupado, pdf_minimo, saltar_si_calibre

FICHA = {"cita": "Ley 28077", "tipo": "ley", "numero": "28077", "norma": "ley_28077",
         "url": "https://www.leyes.congreso.gob.pe/Documentos/Leyes/28077.pdf", "fuente": "gob.pe", "rotulo": "Ley N.° 28077",
         "titulo": "Ley N.° 28077. Ley que modifica diversos Artículos de la Ley N.° 27506, Ley de Canon",
         "sumilla": "Ley que modifica diversos Artículos de la Ley N.° 27506, Ley de Canon", "fecha": "2003-09-04",
         "emisor": "Congreso de la República", "pagina": "https://www.gob.pe/institucion/mef/normas-legales/229450-28077"}

GUION = r"""
import hashlib, json, shutil, sys
sys.path.insert(0, ".")
import config
from lib import comun, traer
import fuentes.gobpe.localizar as g, fuentes.congreso.localizar as c
ficha, pdf, modo = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3]
g.localizar = lambda cita, cfg: ficha
c.localizar = lambda cita, cfg: {"url": ficha["url"], "fuente": "Congreso-Leyes"}
def descargar(url, destino, base, ext="pdf"):
    p = destino / f"{base}.{ext}"; shutil.copy(pdf, p)
    return p, hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size
comun.descargar = descargar
if modo == "plan":
    r = traer.plan(ficha["cita"]); codigo = 0
else:
    codigo, r = traer.aplicar(ficha["cita"])
print(json.dumps(r, ensure_ascii=False, default=str)); sys.exit(codigo)
"""


def _traer(caja, modo, ficha=FICHA):
    pdf = caja.base / "norma.pdf"
    pdf.write_bytes(pdf_minimo("Ley 28077 que modifica la Ley de Canon"))
    r = caja.correr("python3", "-c", GUION, json.dumps(ficha), pdf, modo)
    return r, (json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {})


def _libro(caja, bid):
    c = sqlite3.connect(f"file:{caja.db}?mode=ro", uri=True)
    cols = dict(c.execute("select label, id from custom_columns"))
    enum = lambda lab: c.execute(f"select v.value from books_custom_column_{cols[lab]}_link l join custom_column_{cols[lab]} v "  # noqa: E731
                                 f"on v.id = l.value where l.book = ?", (bid,)).fetchone()
    d = {"titulo": c.execute("select title from books where id=?", (bid,)).fetchone()[0],
         "pubdate": c.execute("select pubdate from books where id=?", (bid,)).fetchone()[0],
         "ids": dict(c.execute("select type, val from identifiers where book=?", (bid,))),
         "serie": (c.execute("select s.name from books_series_link l join series s on s.id=l.series where l.book=?", (bid,)).fetchone() or [""])[0],
         "item_type": (enum("item_type") or [""])[0], "clasificador": (enum("clasificador") or [""])[0]}
    c.close()
    return d


def test_simula_sin_escribir_y_propone_la_serie_de_la_ley_que_modifica(caja):
    antes = caja.huella_db()
    r, p = _traer(caja, "plan")
    assert r.returncode == 0, r.stderr
    assert p["estado"] == "por-traer" and [x["paso"] for x in p["pasos"]] == ["00", "01", "02", "03"]
    m = p["metadatos"]
    assert m["item_type"] == "Statute" and m["norma"] == "ley_28077" and m["fecha"] == "2003-09-04"
    assert m["serie"] == "Marco legal 06 - Presupuesto", "la serie de la Ley 27506, que la 28077 modifica"
    assert "documento_oficial" not in m["tags"] and "norma" in m["tags"]
    assert caja.huella_db() == antes and not any((caja.repo / "entrada").iterdir())


def test_una_que_ya_existe_no_se_trae(caja):
    r, p = _traer(caja, "plan", {**FICHA, "cita": "Ley 27506"})
    assert p["estado"] == "existe" and p["calibre_id"] == 10887


def test_aplicada_en_la_copia_queda_como_norma_con_su_ris(caja, sin_calibre_abierto):
    nuevo = caja.max_id() + 1
    r, p = _traer(caja, "aplicar")
    saltar_si_calibre(r)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert p["estado"] == "catalogada" and p["calibre_id"] == nuevo
    d = _libro(caja, nuevo)
    assert d["titulo"].startswith("Ley N.° 28077. Ley que modifica")
    assert d["ids"].get("norma") == "ley_28077" and d["ids"].get("url", "").endswith("28077.pdf")
    assert (d["item_type"], d["clasificador"]) == ("Statute", "Normativa")
    assert d["serie"] == "Marco legal 06 - Presupuesto" and d["pubdate"].startswith("2003-09-04")
    ris = open(p["ris"], encoding="utf-8").read()
    assert "TY  - STAT" in ris and "M1  - 28077" in ris and "DA  - 2003/09/04" in ris and "T2  -" not in ris
    led = (caja.repo / "ingesta" / "ingesta.tsv").read_text(encoding="utf-8")
    assert f"\t{nuevo}\t" in led
    # una segunda vez ya existe: no se duplica
    r2, p2 = _traer(caja, "aplicar")
    assert p2["estado"] == "existe" and p2["calibre_id"] == nuevo and caja.max_id() == nuevo


def test_con_la_biblioteca_ocupada_sale_75_sin_descargar(caja):
    antes = caja.huella_db()
    with CandadoOcupado(caja.lock_calibre):
        r, p = _traer(caja, "aplicar")
    assert r.returncode == 75 and p["estado"] == "puerta-cerrada" and p["mensaje"]
    assert caja.huella_db() == antes and not any((caja.repo / "entrada").iterdir())
