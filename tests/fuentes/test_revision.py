"""tests/fuentes/test_revision.py — la revisión de literatura de un escrito: el tipo, la bitácora, el cribado en dos fases y el
diagrama PRISMA 2020 (FLUJO_DE_CONOCIMIENTO C2.1, C2.2 y C2.3; decisiones §9.10).

Sobre un escrito de prueba en un temporal: nada toca escritura ni las bases. El diagrama se compila con LuaLaTeX si está.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RIS = """TY  - JOUR
TI  - Pobreza y empleo en el Perú
AU  - Pérez, Ana
PY  - 2020
DO  - 10.1000/abc
AB  - Un resumen.
ER  -
TY  - JOUR
TI  - Pobreza y empleo en el Perú
AU  - Pérez, Ana
PY  - 2020
DO  - https://doi.org/10.1000/ABC
ER  -
TY  - JOUR
TI  - Ingresos laborales y pobreza
PY  - 2021
ER  -
"""


def _cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def rev(tmp_path):
    d = tmp_path / "escritura" / "reports" / "2026-11-18-revision"
    (d / "fuentes").mkdir(parents=True)
    (d / "proyecto.yaml").write_text("titulo: Revisión de muestra\n", encoding="utf-8")
    sys.modules.pop("biblioteca_revision", None)
    return d, _cargar("biblioteca_revision", REPO / "lib" / "revision.py"), _cargar("t_prisma", REPO / "lib" / "prisma.py")


def _armar(m, d):
    r, h = m.leer(d)
    r = m.declarar(r, "sistematica", "¿Qué explica la pobreza?", ["Perú, 2015-2025"], ["Sin datos"])
    r, b = m.buscar(r, "Scopus", 'TITLE-ABS-KEY(pobreza AND empleo)', 3, "2015-2025; artículos", "2026-11-18")
    r, n = m.importar(r, b["id"], RIS)
    return r, h, n


def test_la_bitacora_registra_la_busqueda_y_marca_duplicados(rev):
    d, m, _p = rev
    r, h, n = _armar(m, d)
    assert n == {"importados": 3, "duplicados": 1}, "el mismo DOI, con otra grafía, es un duplicado"
    b = r["busquedas"][0]
    assert b == {"id": "b1", "clase": "base", "base": "Scopus", "cadena": "TITLE-ABS-KEY(pobreza AND empleo)",
                 "filtros": "2015-2025; artículos", "fecha": "2026-11-18", "resultados": 3, "nota": ""}
    assert r["registros"][1]["duplicado_de"] == "r0001" and r["registros"][0]["resumen"] == "Un resumen."
    s = m.escribir(d, r, h, aplicar=False)
    assert not m.ruta(d).exists() and "+tipo: sistematica" in s["diff"], "simular no escribe"
    w = m.escribir(d, r, h, aplicar=True)
    texto = m.ruta(d).read_text(encoding="utf-8")
    assert texto.startswith("# fuentes/revision.yml") and "cadena: TITLE-ABS-KEY(pobreza AND empleo)" in texto
    assert m.leer(d)[0]["registros"] == r["registros"], "lo escrito se lee igual"
    with pytest.raises(m.Cambiada):
        m.escribir(d, r, h, aplicar=True)                       # la huella vieja ya no vale
    assert m.escribir(d, r, w["huella"], aplicar=True)["escrito"]


def test_la_busqueda_exige_lo_que_pide_prisma_s(rev):
    _d, m, _p = rev
    r = m.vacia()
    with pytest.raises(ValueError, match="cadena"):
        m.buscar(r, "Scopus", "", 10)
    with pytest.raises(ValueError, match="número"):
        m.buscar(r, "Scopus", "x", "muchos")
    r, b = m.buscar(r, "Búsqueda de citas", "", 2, clase="citas")
    assert b["clase"] == "citas", "en otros métodos la cadena puede faltar"


def test_el_cribado_en_dos_fases(rev):
    d, m, _p = rev
    r, _h, _n = _armar(m, d)
    with pytest.raises(ValueError, match="copia"):
        m.cribar(r, "r0002", 1, "incluir")
    with pytest.raises(ValueError, match="solo pasa"):
        m.cribar(r, "r0001", 2, "incluir")
    r, _ = m.cribar(r, "r0001", 1, "incluir")
    r, _ = m.cribar(r, "r0003", 1, "excluir", "otro tema")
    with pytest.raises(ValueError, match="motivo"):
        m.cribar(r, "r0001", 2, "excluir")
    r, x = m.cribar(r, "r0001", 2, "recuperar")
    assert x["recuperado"] is True and x["fase2"] == ""
    r, x = m.cribar(r, "r0001", 2, "excluir", "Otra población")
    c = m.cuentas(r)["bases"]
    assert (c["identificados"], c["duplicados"], c["cribados"], c["excluidos_titulo"], c["buscados"], c["evaluados"],
            c["excluidos_texto"], c["incluidos"]) == (3, 1, 2, 1, 1, 1, 1, 0)
    assert c["motivos"] == {"Otra población": 1}
    r, _ = m.cribar(r, "r0001", 2, "incluir")
    assert m.cuentas(r)["incluidos"] == 1 and m.cuentas(r)["cuadra"]


def test_las_cuentas_avisan_si_no_cuadran(rev):
    d, m, _p = rev
    r, _h, _n = _armar(m, d)
    r["busquedas"][0]["resultados"] = 120
    c = m.cuentas(r)
    assert not c["cuadra"] and any("120 resultados y hay 3 registros" in a for a in c["avisos"])
    r["eliminados"]["otras_razones"] = 117                       # el ajuste manual, con su nota
    r["busquedas"][0]["resultados"] = 3
    assert not m.cuentas(r)["cuadra"]


def test_los_requisitos_dependen_del_tipo(rev):
    d, m, _p = rev
    r, _h, _n = _armar(m, d)
    req = {x["clave"]: x for x in m.requisitos(r)}
    assert set(req) == {"pregunta", "criterios", "bitacora", "cribado", "prisma"}
    assert req["bitacora"]["cumple"] and not req["cribado"]["cumple"] and "por cribar" in req["cribado"]["detalle"]
    assert req["pregunta"]["fuente"] == "Grant y Booth (2009); Snyder (2019)"
    narrativa = {x["clave"]: x for x in m.requisitos(m.declarar(r, "narrativa"))}
    assert "prisma" not in narrativa and narrativa["bitacora"]["exigencia"] == "recomendado"
    with pytest.raises(ValueError, match="tipo de revisión"):
        m.declarar(r, "inventada")
    assert m.requisitos(m.vacia()) == [], "sin tipo declarado no hay requisitos"


@pytest.mark.skipif(not shutil.which("lualatex"), reason="sin LuaLaTeX")
def test_el_diagrama_sale_de_la_bitacora_y_sabe_si_quedo_viejo(rev):
    d, m, p = rev
    r, h, _n = _armar(m, d)
    r, _ = m.cribar(r, "r0001", 1, "incluir")
    r, _ = m.buscar(r, "Búsqueda de citas", "", 1, clase="citas")
    m.escribir(d, r, h, aplicar=True)
    sim = p.generar(d)
    assert not sim["escrito"] and not (d / "fuentes" / "prisma.pdf").exists()
    assert "Registros cribados" in p.tikz(sim["cuentas"]) and "otros métodos" in p.tikz(sim["cuentas"])
    g = p.generar(d, aplicar=True)
    assert g["escrito"] and (d / "fuentes" / "prisma.pdf").read_bytes()[:4] == b"%PDF"
    assert p.al_dia(d) is True
    r2, h2 = m.leer(d)
    r2, _ = m.cribar(r2, "r0003", 1, "excluir")
    m.escribir(d, r2, h2, aplicar=True)
    assert p.al_dia(d) is False, "la bitácora cambió: el diagrama quedó viejo"
    v = m.ver(d)
    assert v["prisma"]["al_dia"] is False and v["prisma"]["pdf"]
    assert any(x["clave"] == "prisma" and not x["cumple"] and "otras cifras" in x["detalle"] for x in v["requisitos"])


def test_sin_busquedas_no_hay_diagrama(rev):
    d, _m, p = rev
    with pytest.raises(ValueError, match="no tiene búsquedas"):
        p.generar(d)


def test_bibtex_tambien_se_importa(rev):
    _d, m, _p = rev
    regs = m.leer_exportacion("@article{a1,\n  title = {Un artículo},\n  author = {Pérez, Ana and Soto, Luis},\n  year = {2019},\n"
                              "  doi = {10.1/x}\n}\n")
    assert regs == [{"titulo": "Un artículo", "autores": "Pérez, Ana; Soto, Luis", "anio": "2019", "doi": "10.1/x", "resumen": ""}]
