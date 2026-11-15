"""migraciones/pasos/normas.py — NORMAS (2026-11-15): las normas de las series «Marco legal» que entraron como documento.

Las tandas del 2026-11-03 (altas 10844-10906, archivos `congreso_ley_…`, `pcm_ds_…`) catalogaron leyes y decretos como
`Document` / «Documento oficial»: la identificación no reconoce el número en un nombre con la sigla delante y, sin capa
de texto, cae en el documento (la Ley 27506, libro 10887, es una). Su RIS sale `GEN` y Zotero las tendría como
documento, sin número ni fecha de la norma. Esta campaña las deja como norma, como el resto de la biblioteca:

- `#item_type` → `Statute` y `#clasificador` → `Normativa`;
- la etiqueta `documento_oficial` sale y entran `norma` y `legislacion` si faltan (vocabulario cerrado);
- el identificador `norma:` se completa desde el título si falta (los demás identificadores se conservan).

Título, autor, fecha y serie no se tocan. Solo libros de una serie «Marco legal» cuyo título EMPIEZA por una norma
(«Ley N.° …», «Decreto Supremo N.° …», la Constitución): directivas, acuerdos, informes y dictámenes quedan como están.
"""
import importlib.util
import os
import re
from pathlib import Path

_PY = Path(os.environ.get("PY_COMMON") or Path(__file__).resolve().parents[3] / "core" / "py-common") / "biblioteca.py"
_s = importlib.util.spec_from_file_location("biblioteca_normas", _PY)
bib = importlib.util.module_from_spec(_s)
_s.loader.exec_module(bib)

ES_NORMA = re.compile(r"^(Ley N\.° \d|Ley Org[aá]nica N\.° \d|Decreto Supremo N\.° \d|Decreto Legislativo N\.° \d|Decreto Ley N\.° \d|"
                      r"Decreto de Urgencia N\.° \d|Resoluci[oó]n Legislativa N\.° \d|Texto Único Ordenado|Constituci[oó]n Pol[ií]tica)")
QUITAR, PONER = {"documento_oficial"}, {"norma", "legislacion"}


def _enum(c, col, etiqueta):
    t = f"custom_column_{col[etiqueta]}"
    return dict(c.execute(f"select l.book, v.value from books_{t}_link l join {t} v on v.id = l.value").fetchall())


def candidatos(c):
    col = dict(c.execute("select label, id from custom_columns").fetchall())
    item, clasif = _enum(c, col, "item_type"), _enum(c, col, "clasificador")
    filas = c.execute("select b.id, b.title, s.name from books b join books_series_link l on l.book = b.id "
                      "join series s on s.id = l.series where s.name like 'Marco legal%' order by b.id").fetchall()
    return [(b, t, s, item.get(b, ""), clasif.get(b, "")) for b, t, s in filas
            if ES_NORMA.match(t) and (item.get(b) != "Statute" or clasif.get(b) != "Normativa")]


def plan(c):
    etiquetas, ids = {}, {}
    for b, n in c.execute("select l.book, t.name from books_tags_link l join tags t on t.id = l.tag"):
        etiquetas.setdefault(b, set()).add(n)
    for b, tipo, val in c.execute("select book, type, val from identifiers"):
        ids.setdefault(b, {})[tipo] = val
    tipo, clase, tags, idents = {}, {}, {}, {}
    propuesta = [("libro", "título", "serie", "antes", "después", "etiquetas", "norma:")]
    for b, t, s, it, cl in candidatos(c):
        tipo[str(b)], clase[str(b)] = "Statute", "Normativa"
        nuevas = (etiquetas.get(b, set()) - QUITAR) | PONER
        if nuevas != etiquetas.get(b, set()):
            tags[str(b)] = sorted(nuevas)
        n = ids.get(b, {}).get("norma") or bib.norma_id(t)
        if n and ids.get(b, {}).get("norma") != n:
            idents[str(b)] = {**ids.get(b, {}), "norma": n}
        propuesta.append((b, t[:90], s, f"{it or '—'}/{cl or '—'}", "Statute/Normativa", ", ".join(sorted(nuevas)), n or "—"))
    campos = {"#item_type": tipo, "#clasificador": clase, "tags": tags}
    if idents:
        campos["identifiers"] = idents
    return ({"campos": campos},
            f"{len(tipo)} normas de «Marco legal» pasan a Statute/Normativa; {len(tags)} cambian de etiquetas; "
            f"{len(idents)} ganan su identificador norma:", propuesta)
