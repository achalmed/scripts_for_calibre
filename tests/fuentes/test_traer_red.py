"""tests/fuentes/test_traer_red.py — el primer caso real de `main.py traer`: la Ley 28077, la Ley 28322 y el D.S.
005-2002-EF (las modificatorias y el reglamento de la Ley de Canon), traídos de verdad a la COPIA de la biblioteca.

Objetivo: el flujo entero con las fuentes oficiales (Congreso y gob.pe), sin tocar la biblioteca real.
Método: `main.py traer --aplicar --json` en la caja de arena, una norma tras otra; después, el RIS de las tres.
Límite: usa la red (se salta sin `TRAER_RED=1`); las fichas de gob.pe pueden cambiar con el tiempo.
"""
import json
import os

import pytest

from conftest import saltar_si_calibre

pytestmark = pytest.mark.skipif(os.environ.get("TRAER_RED") != "1", reason="usa la red: TRAER_RED=1 para correrla")

CANON = [("Ley 28077", "ley_28077", "Congreso de la República"),
         ("Ley 28322", "ley_28322", "Congreso de la República"),
         ("D.S. 005-2002-EF", "decreto_supremo_005-2002-ef", "Ministerio de Economía y Finanzas")]


def test_las_tres_normas_del_canon_en_la_copia(caja, sin_calibre_abierto):
    hechos = []
    for cita, norma, emisor in CANON:
        r = caja.py("main.py", "traer", cita, "--json", timeout=600)
        p = json.loads(r.stdout)
        assert p["estado"] == "por-traer", (cita, p.get("mensaje"))
        assert p["metadatos"]["serie"] == "Marco legal 06 - Presupuesto", cita
        r = caja.py("main.py", "traer", cita, "--aplicar", "--json", timeout=900)
        saltar_si_calibre(r)
        p = json.loads(r.stdout)
        assert r.returncode == 0 and p["estado"] == "catalogada", (cita, p.get("mensaje"), p.get("salida"))
        assert p["metadatos"]["autores"] == emisor and p["norma"] == norma
        ris = open(p["ris"], encoding="utf-8").read()
        assert "TY  - STAT" in ris and f"calibre:{p['calibre_id']}" in ris
        hechos.append((cita, p["calibre_id"], p["metadatos"]["titulo"], p["metadatos"]["fecha"], p["ris"]))
    print("\n" + "\n".join(f"{c}: libro {i} «{t}» ({f})" for c, i, t, f, _ in hechos))
    # los índices de la serie no chocan: cada una toma el siguiente libre
    assert len({i for _, i, *_ in hechos}) == 3
