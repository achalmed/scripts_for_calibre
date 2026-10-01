"""verificar.py — salud de la biblioteca entera tras la campaña de grafías (solo lee).

    python3 verificar.py [<biblioteca> <zotero.sqlite>]      (por defecto, los de core/env.py)

Cuenta: formatos de Calibre cuyo archivo no existe, enlaces `attachments:` de Zotero (linkMode 2) cuyo
archivo no existe, y carpetas de autor vacías. Se corre antes y después: las cifras deben ser iguales o
menores; un enlace roto nuevo es un fallo de la campaña.
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "core"))
import env  # noqa: E402

bib = Path(sys.argv[1] if len(sys.argv) > 2 else env.BIBLIOTECA_DIR)
zot = Path(sys.argv[2] if len(sys.argv) > 2 else env.ZOTERO_DB)
c = sqlite3.connect(f"file:{bib / 'metadata.db'}?mode=ro", uri=True)
faltan = [f"{p}/{n}.{f.lower()}" for p, n, f in c.execute(
    "select b.path, d.name, d.format from data d join books b on b.id = d.book")
    if not (bib / p / f"{n}.{f.lower()}").exists()]
z = sqlite3.connect(f"file:{zot}?mode=ro", uri=True)
rotos = [p for (p,) in z.execute("select path from itemAttachments where linkMode = 2 and path like 'attachments:%'")
         if not (bib / p[len("attachments:"):]).exists()]
vacias = [d.name for d in bib.iterdir() if d.is_dir() and not any(d.iterdir())]
print(f"formatos sin archivo: {len(faltan)} · enlaces Zotero rotos: {len(rotos)} · carpetas de autor vacías: {len(vacias)}")
for x in rotos[:10]:
    print("  roto:", x)
