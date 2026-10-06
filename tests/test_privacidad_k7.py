"""tests/test_privacidad_k7.py — privacidad del repo público (ola 2a, K7; RQ-SEC-01, RQ-BIB-04, P227).

Objetivo: ningún correo en lo rastreado (el contacto de Crossref llega por la variable CROSSREF_MAILTO)
  y ninguna ficha de catalogación con `proyecto:` como ruta (normativa 1.10: se relaciona por id).
Límite: la lista `PERMITIDOS` son identificadores técnicos con forma de correo que no son de nadie.
"""
from __future__ import annotations

import re
import subprocess

import calibre_apoyo as ap

PERMITIDOS = {"zoterostyle@polygon.org"}   # id del complemento Ethereal Style de Zotero, no un correo
CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")   # ERE: git grep -E


def test_sin_correos_en_lo_rastreado():
    r = subprocess.run(["git", "-C", str(ap.REPO), "grep", "-nIE", CORREO.pattern], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr                     # 1 = nada hallado; otro = patrón roto
    assert r.returncode == 1 or "zoterostyle@polygon.org" in r.stdout   # el patrón sí encuentra lo que debe
    hallados = [l for l in r.stdout.splitlines()
                if not {m.group(0) for m in CORREO.finditer(l)} <= PERMITIDOS]
    assert hallados == [], "\n".join(hallados)


def test_fichas_con_proyecto_por_id():
    fichas = (ap.REPO / "script_catalogacion_biblioteca" / "fichas").glob("*.md")
    malas = [f.name for f in fichas
             if re.search(r"^proyecto:\s*\S*/", f.read_text(encoding="utf-8", errors="replace"), re.M)]
    assert malas == []
