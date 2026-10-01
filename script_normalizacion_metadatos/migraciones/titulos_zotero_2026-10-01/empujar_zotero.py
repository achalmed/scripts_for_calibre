"""empujar_zotero.py — iguala el título de cada ítem de Zotero al de su libro de Calibre (2026-10-01).

    python3 empujar_zotero.py [--aplicar]      (simula por defecto; con --aplicar, Zotero CERRADO)

Por qué: el sincronizador comparaba títulos con `norm()` (sin tildes ni mayúsculas), así que una corrección
de tildes o de mayúsculas en Calibre nunca llegaba a Zotero (133 ítems el 2026-10-01). En títulos manda Calibre
(MODELO_METADATOS §2). Solo se tocan los ítems cuyo título difiere SOLO en tildes y mayúsculas; si el texto es
otro, se reporta y no se toca. Respaldo de zotero.sqlite en backups/<esta carpeta>/ antes de escribir.
Escribe empujados.tsv (libro · clave · título de Zotero antes · título nuevo).
"""
import importlib.util
import os
import shutil
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[3] / "core"))
import env  # noqa: E402


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def sincronizador(zot, cal):
    for k, v in {"CALIBRE_DB": cal, "ZOTERO_DB": zot, "REPORT_TSV": os.devnull,
                 "REPORT_MD": os.devnull, "STATE_JSON": os.devnull}.items():
        os.environ.setdefault(k, v)
    ruta = AQUI.parents[2] / "script_sincronizar_zotero/lib/sincronizador.py"
    spec = importlib.util.spec_from_file_location("sincronizador", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    aplicar = "--aplicar" in argv
    cal, zot = str(Path(env.BIBLIOTECA_DIR) / "metadata.db"), str(env.ZOTERO_DB)
    c = sqlite3.connect(f"file:{cal}?mode=ro", uri=True)
    col = c.execute("select id from custom_columns where label = 'zotero_key'").fetchone()[0]
    libros = c.execute(f"select b.id, b.title, v.value from books b join custom_column_{col} v on v.book = b.id").fetchall()
    c.close()
    if aplicar:
        resp = AQUI.parents[1] / "backups" / AQUI.name
        resp.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zot, resp / f"zotero_empujar_{time.strftime('%Y%m%d_%H%M%S')}.sqlite")
    sinc = sincronizador(zot, cal)
    z = sqlite3.connect(zot if aplicar else f"file:{zot}?mode=ro", uri=not aplicar)
    cur = z.cursor()
    hechos, otros = [], []
    for libro, titulo, key in libros:
        r = cur.execute("select itemID from items where key = ?", (key,)).fetchone()
        if not r:
            continue
        actual = sinc.z_get_field(cur, r[0], "title") or ""
        if actual == titulo:
            continue
        if norm(actual) != norm(titulo):
            otros.append((libro, key, actual, titulo))
            continue
        if aplicar:
            sinc.z_set_field(cur, r[0], "title", titulo)
        hechos.append((libro, key, actual, titulo))
    if aplicar:
        z.commit()
        print("integridad:", z.execute("pragma integrity_check").fetchone()[0])
        with open(AQUI / "empujados.tsv", "w", encoding="utf-8") as f:
            for fila in hechos:
                f.write("\t".join(map(str, fila)) + "\n")
    z.close()
    print(f"{'escritos' if aplicar else 'se escribirían'}: {len(hechos)} títulos · texto distinto (no se tocan): {len(otros)}")
    for fila in otros[:20]:
        print("  distinto:", *fila, sep=" | ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
