"""tests/lectura_base/conftest.py — la fixture `mundo` (el mundo de juguete de `juguete_lectura.py`) y el temporal en el disco.

Las utilidades van en `juguete_lectura.py`, con nombre propio: un `from conftest import …` chocaría con el conftest de
`tests/calibre` cuando las dos carpetas corren juntas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parent
if str(AQUI) not in sys.path:
    sys.path.insert(0, str(AQUI))

from juguete_lectura import BASETEMP, REPO, Mundo, _calibre, _zotero, pdf_con_texto  # noqa: E402


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.basetemp:
        return
    args = [Path(a.split("::")[0]).resolve() for a in (config.args or [])]
    if args and all(REPO in a.parents or a == REPO for a in args):
        BASETEMP.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(BASETEMP)


@pytest.fixture
def mundo(tmp_path, monkeypatch) -> Mundo:
    from lectura_base.lib import biblioteca as bib
    raiz = tmp_path
    biblioteca = raiz / "biblioteca"
    c1 = "Quispe, Rosa/Economia de juguete (1)"
    c2 = "Paredes, Julian/Instituciones de juguete (2)"
    for carpeta, nombre in ((c1, "Economia de juguete"), (c2, "Instituciones de juguete")):
        (biblioteca / carpeta).mkdir(parents=True)
        (biblioteca / carpeta / f"{nombre}.pdf").write_bytes(pdf_con_texto())
    pdf1 = biblioteca / c1 / "Economia de juguete.pdf"
    pdf2 = biblioteca / c2 / "Instituciones de juguete.pdf"
    md5_1 = bib.md5_parcial(pdf1)
    calibre_db = biblioteca / "metadata.db"
    _calibre(calibre_db, [(1, "Economia de juguete", "Rosa Quispe", c1), (2, "Instituciones de juguete", "Julián Paredes", c2)],
             {1: md5_1})
    zotero_db = raiz / "Zotero" / "zotero.sqlite"
    zotero_db.parent.mkdir()
    _zotero(zotero_db, [(1, f"{c1}/Economia de juguete.pdf"), (2, f"{c2}/Instituciones de juguete.pdf")])
    koreader = raiz / "koreader"
    (koreader / "settings").mkdir(parents=True)
    docdata = raiz / "okular" / "docdata"
    docdata.mkdir(parents=True)
    estado = raiz / "estado"
    (estado / "biblioteca").mkdir(parents=True)
    entorno = {"CALIBRE_DB": calibre_db, "BIBLIOTECA_DIR": biblioteca, "ZOTERO_DB": zotero_db, "ZOTERO_DIR": zotero_db.parent,
               "KOREADER_DIR": koreader, "KOREADER_STATS": koreader / "settings" / "statistics.sqlite3",
               "OKULAR_DOCDATA": docdata, "LECTURA_DB": raiz / "datos" / "biblioteca" / "lectura.sqlite",
               "XDG_DATA_HOME": raiz / "datos", "XDG_STATE_HOME": estado, "XDG_CACHE_HOME": raiz / "cache",
               "PUERTA_RESPALDOS": raiz / "respaldos", "LOCK_CALIBRE": estado / "biblioteca" / "calibre.lock",
               "LOCK_ZOTERO": estado / "biblioteca" / "zotero.lock", "KOREADER_RESPALDO_DIR": raiz / "no-hay",
               "YACHAY_CLIENTE": raiz / "no-hay-cliente.py", "YACHAY_DIR": raiz / "no-hay-yachay"}
    for k, v in entorno.items():
        monkeypatch.setenv(k, str(v))
    for k in ("PUERTA_ZOTERO", "PUERTA_ZOTERO_DB", "PUERTA_CALIBRE", "PUERTA_BIBLIOTECA"):
        monkeypatch.delenv(k, raising=False)
    return Mundo(raiz, biblioteca, calibre_db, zotero_db, koreader, docdata, Path(entorno["LECTURA_DB"]), pdf1, pdf2, md5_1)
