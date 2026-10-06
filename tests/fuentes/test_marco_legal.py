"""`manifiestos/marco_legal/`: el dato del marco legal y sus dos generadores (ola 2, F7).

El dato (parciales → `manifiesto.tsv` y `no_localizados.tsv`) es reproducible: regenerarlo en la caja de
arena da los mismos archivos que el repo. Sin `MARCO_LEGAL`, los dos generadores se niegan con 1.
"""
from conftest import REPO


def test_sin_marco_legal_se_niegan(caja):
    for guion in ("generar_manifiesto.sh", "generar_inventario.sh"):
        r = caja.correr("bash", caja.repo / "manifiestos" / "marco_legal" / guion)
        assert r.returncode == 1 and "MARCO_LEGAL no definida" in r.stderr


def test_el_manifiesto_se_regenera_identico(caja):
    ml = caja.repo / "manifiestos" / "marco_legal"
    r = caja.correr("bash", ml / "generar_manifiesto.sh", env={"MARCO_LEGAL": str(caja.base / "marco")})
    assert r.returncode == 0, r.stdout + r.stderr
    for nombre in ("manifiesto.tsv", "no_localizados.tsv"):
        assert (ml / nombre).read_bytes() == (REPO / "manifiestos" / "marco_legal" / nombre).read_bytes(), nombre


def test_el_inventario_se_escribe_fuera_del_repo(caja):
    destino = caja.base / "marco"
    destino.mkdir()
    r = caja.correr("bash", caja.repo / "manifiestos" / "marco_legal" / "generar_inventario.sh", env={"MARCO_LEGAL": str(destino)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert (destino / "INVENTARIO.md").is_file()
