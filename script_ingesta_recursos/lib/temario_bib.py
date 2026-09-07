#!/usr/bin/env python3
"""temario_bib.py CURSO_DIR CALIBRE_ID TITULO AUTOR RUTA_ORIGINAL [NOTA] — añade una entrada a `bibliografia:` del temario.yml."""
import sys, yaml, pathlib
cdir, cid, titulo, autor, ruta = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
nota = sys.argv[6] if len(sys.argv) > 6 else ""
ty = cdir / "temario.yml"
if not ty.exists():
    sys.exit(3)
txt = ty.read_text(encoding="utf-8"); comentarios = [l for l in txt.split("\n")[:3] if l.startswith("#")]
t = yaml.safe_load(txt) or {}
bib = t.setdefault("bibliografia", []) or []
if not any(b.get("calibre_id") == cid for b in bib):
    e = {"calibre_id": cid, "titulo": titulo, "autor": autor, "origen": ruta}
    if nota: e["nota"] = nota
    bib.append(e)
t["bibliografia"] = bib
ty.write_text("\n".join(comentarios) + "\n" + yaml.safe_dump(t, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
