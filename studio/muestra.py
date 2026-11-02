#!/usr/bin/env python3
"""studio/muestra.py — una biblioteca de muestra con libros ficticios, para las pruebas y las capturas de Biblioteca Studio.

Nunca la biblioteca real (`../CLAUDE.md`: las bases reales son intocables en las pruebas). En una carpeta temporal crea:
una biblioteca Calibre mínima con `calibredb add` (si `calibredb` está instalado y responde; con `unshare -rn` para no
chocar con un Calibre abierto, como `tests/calibre`), una `zotero.sqlite` mínima con tres ítems enlazados a esos libros
por la ruta del adjunto, con sus metadatos editoriales, su lectura de KOReader y las portadas que genera el propio
Calibre (`calibre-debug`, una sola vez: la biblioteca hecha queda como plantilla en la caché y las demás se copian),
un repo de datos de muestra (los ledgers, dos fichas canónicas, la zona de entrada y un
`fuentes.yml`) y el índice (`lib/indice.py`, el mismo código) en un `XDG_STATE_HOME` temporal. Devuelve las variables
de entorno con las que la ventana (`core/env` las respeta) y `lib/indice.py` ven esa muestra y no la real.

    from muestra import crear
    m = crear(Path(carpeta))            # m.entorno: CALIBRE_DB, ZOTERO_DB, BIBLIOTECA_DIR, XDG_STATE_HOME, BIBLIOTECA_STUDIO_DATOS…
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent

# ocho libros ficticios: título, autor «Nombre Apellido» (Calibre lo invierte), clave de Zotero (o ninguna), clave para citar
LIBROS = [
    ("Economía de las ciudades pequeñas", "Rosa Quispe", "QUISPE01", "quispeEconomiaCiudades2021"),
    ("Métodos cuantitativos para las ciencias sociales", "Julián Paredes", "PAREDE02", "paredesMetodosCuantitativos2019"),
    ("Historia del presupuesto público", "Marta Huamán", "HUAMAN03", ""),
    ("Teoría del crecimiento regional", "Aurelio Ccente", "", ""),
    ("Manual de redacción académica", "Inés Valverde", "VALVER05", "valverdeManualRedaccion2020"),
    ("Estadística para economistas", "Tomás Arango", "", ""),
    ("Instituciones y desarrollo local", "Carla Mendoza", "MENDOZ07", "mendozaInstitucionesDesarrollo2022"),
    ("Finanzas municipales", "Pedro Sulca", "", ""),
]

# lo editorial de cada libro (por título): año, editorial, serie y número, etiquetas, identificadores, idioma, tipo,
# páginas y la lectura en KOReader (fracción leída, estado, minutos, última lectura); algunos vacíos a propósito: las
# bandejas (sin tipo, sin portada) y los filtros tienen que tener qué mostrar
META = {
    "Economía de las ciudades pequeñas": dict(año=2021, editorial="Fondo Editorial de Muestra", serie="Desarrollo local", indice=1,
        etiquetas=["economía urbana", "desarrollo"], ids={"isbn": "9786120000011"}, idioma="spa", tipo="book", paginas=212,
        ko=(0.42, "reading", 185, "2026-10-30"), descripcion="<p>Un libro de muestra sobre la economía de las ciudades pequeñas.</p>"),
    "Métodos cuantitativos para las ciencias sociales": dict(año=2019, editorial="Editorial Universitaria de Muestra", serie="Métodos",
        indice=3, etiquetas=["métodos", "estadística"], ids={"isbn": "9786120000028"}, idioma="spa", tipo="book", paginas=388,
        ko=(1.0, "complete", 940, "2026-09-12")),
    "Historia del presupuesto público": dict(año=1998, editorial="Fondo Editorial de Muestra", serie="", etiquetas=["finanzas públicas", "historia"],
        ids={"doi": "10.1000/muestra.presupuesto"}, idioma="spa", tipo="book", paginas=154),
    "Teoría del crecimiento regional": dict(año=1987, editorial="Ediciones de Muestra", serie="Desarrollo local", indice=2,
        etiquetas=["crecimiento", "desarrollo"], ids={}, idioma="spa", tipo="", paginas=0, portada=False),
    "Manual de redacción académica": dict(año=2020, editorial="Editorial Universitaria de Muestra", serie="Métodos", indice=1,
        etiquetas=["redacción"], ids={"isbn": "9786120000059"}, idioma="spa", tipo="book", paginas=120, ko=(0.08, "reading", 22, "2026-11-01")),
    "Estadística para economistas": dict(año=2015, editorial="Ediciones de Muestra", serie="Métodos", indice=2,
        etiquetas=["estadística"], ids={}, idioma="spa", tipo="", paginas=0),
    "Instituciones y desarrollo local": dict(año=2022, editorial="Fondo Editorial de Muestra", serie="Desarrollo local", indice=3,
        etiquetas=["instituciones", "desarrollo"], ids={"isbn": "9786120000073"}, idioma="spa", tipo="report", paginas=96),
    "Finanzas municipales": dict(año=2011, editorial="Ediciones de Muestra", serie="", etiquetas=["finanzas públicas"],
        ids={"norma": "Ley de muestra 0001"}, idioma="spa", tipo="statute", paginas=48),
}

# lo que corre DENTRO de calibre-debug (la API de Calibre) sobre la biblioteca de MUESTRA recién creada: las columnas
# personalizadas, los metadatos y las portadas que el propio Calibre genera (create_cover). Nunca la biblioteca real.
_ENRIQUECER = r"""
import json, random, sys
from datetime import datetime, timezone
from calibre.gui2 import ensure_app
ensure_app()
from calibre.db.backend import DB
from calibre.library import db as abrir
from calibre.ebooks.covers import create_cover
biblioteca, plan = sys.argv[-2], json.load(open(sys.argv[-1], encoding="utf-8"))
d = abrir(biblioteca).new_api
for etiqueta, tipo in (("item_type", "text"), ("clasificador", "text"), ("pages", "int"), ("ko_progfloat", "float"),
                       ("ko_status", "text"), ("ko_tiempo", "int"), ("ko_lastmod", "datetime")):
    if etiqueta not in d.field_metadata.custom_field_keys():
        d.create_custom_column(etiqueta, etiqueta, tipo, False)
d.close()
d = abrir(biblioteca).new_api
fecha = lambda t: datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
for libro, m in plan.items():
    b = int(libro)
    if m.get("año"):
        d.set_field("pubdate", {b: fecha(f"{m['año']}-06-01")})
    for campo, valor in (("publisher", m.get("editorial")), ("comments", m.get("descripcion"))):
        if valor:
            d.set_field(campo, {b: valor})
    if m.get("serie"):
        d.set_field("series", {b: m["serie"]})
        d.set_field("series_index", {b: float(m.get("indice") or 1)})
    if m.get("etiquetas"):
        d.set_field("tags", {b: m["etiquetas"]})
    if m.get("ids"):
        d.set_field("identifiers", {b: m["ids"]})
    if m.get("idioma"):
        d.set_field("languages", {b: [m["idioma"]]})
    if m.get("tipo"):
        d.set_field("#item_type", {b: m["tipo"]})
    if m.get("paginas"):
        d.set_field("#pages", {b: int(m["paginas"])})
    if m.get("ko"):
        p, estado, minutos, ultima = m["ko"]
        d.set_field("#ko_progfloat", {b: float(p)})
        d.set_field("#ko_status", {b: estado})
        d.set_field("#ko_tiempo", {b: int(minutos)})
        d.set_field("#ko_lastmod", {b: fecha(ultima)})
    if m.get("portada", True):
        random.seed(b)                    # estilo y colores distintos por libro, pero siempre los mismos
        d.set_cover({b: create_cover(m["titulo"], m["autores"], series=m.get("serie") or None, series_index=m.get("indice") or 1)})
    else:
        d.set_cover({b: None})            # calibredb add sacó una del PDF en blanco: este libro va sin portada
d.close()
print("enriquecida", len(plan))
"""

_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\nxref\n0 4\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF\n")


@dataclass
class Muestra:
    raiz: Path
    biblioteca: Path
    calibre_db: Path
    zotero_db: Path
    repo: Path
    estado: Path
    indice: Path
    con_calibre: bool
    entorno: dict = field(default_factory=dict)


def hay_calibredb() -> bool:
    return shutil.which("calibredb") is not None


def _calibredb(args: list[str], config: Path, plazo: int = 120) -> subprocess.CompletedProcess:
    """`calibredb` con su configuración en un temporal (la del autor no se toca) y, si se puede, en su propio espacio de
    red (el socket abstracto de Calibre es por usuario: con la aplicación abierta, chocaría)."""
    env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=str(config), CALIBRE_TEMP_DIR=str(config / "tmp"), CALIBRE_NO_NATIVE_FILEDIALOGS="1")
    (config / "tmp").mkdir(parents=True, exist_ok=True)
    orden = ["calibredb"] + args
    if shutil.which("unshare"):
        prueba = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
        if prueba.returncode == 0:
            orden = ["unshare", "-rn"] + orden
    return subprocess.run(orden, capture_output=True, text=True, env=env, timeout=plazo)


def _plantilla() -> Path | None:
    """Dónde guardar la biblioteca de muestra ya hecha (crearla cuesta unos segundos de Calibre): en la caché del usuario,
    con la huella de este archivo (si la muestra cambia, se rehace). `BIBLIOTECA_MUESTRA_SIN_PLANTILLA=1` la desactiva."""
    if os.environ.get("BIBLIOTECA_MUESTRA_SIN_PLANTILLA"):
        return None
    import hashlib
    huella = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "biblioteca-studio-muestra" / huella


def _guardar_plantilla(biblioteca: Path, destino: Path) -> None:
    import tempfile
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".plantilla-", dir=destino.parent))
        shutil.copytree(biblioteca, tmp / "biblioteca")
        (tmp / "biblioteca").rename(destino)            # atómico: otra prueba nunca ve una plantilla a medias
        tmp.rmdir()
    except OSError:
        pass                                            # otra prueba la dejó primero: vale la suya


def _enriquecer(biblioteca: Path, config: Path) -> bool:
    """Los metadatos, las columnas y las portadas de la muestra por la API de Calibre (`calibre-debug`, una sola vez)."""
    if not shutil.which("calibre-debug"):
        return False
    plan = {}
    with sqlite3.connect(biblioteca.joinpath("metadata.db").resolve().as_uri() + "?mode=ro", uri=True) as c:
        for b, titulo in c.execute("select id, title from books"):
            autor = next((a for t, a, _z, _c in LIBROS if t == titulo), "")
            plan[str(b)] = dict(META.get(titulo, {}), titulo=titulo, autores=[autor] if autor else [])
    archivo = config / "enriquecer.json"
    guion = config / "enriquecer.py"
    archivo.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    guion.write_text(_ENRIQUECER, encoding="utf-8")
    env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=str(config), CALIBRE_TEMP_DIR=str(config / "tmp"), QT_QPA_PLATFORM="offscreen")
    orden = ["calibre-debug", str(guion), str(biblioteca), str(archivo)]
    if shutil.which("unshare") and subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0:
        orden = ["unshare", "-rn"] + orden
    r = subprocess.run(orden, capture_output=True, text=True, env=env, timeout=180)
    if r.returncode != 0:
        print("muestra: no se pudo enriquecer la biblioteca:", (r.stderr or r.stdout)[-800:], file=sys.stderr)
    return r.returncode == 0


def _zotero(db: Path, adjuntos: list[tuple[str, str, str]]) -> None:
    """Una zotero.sqlite mínima: items, fields, itemData, itemDataValues, itemAttachments (lo que lee `lib/indice.zotero`)."""
    c = sqlite3.connect(db)
    c.executescript("""
        create table items(itemID integer primary key, key text);
        create table fields(fieldID integer primary key, fieldName text);
        create table itemDataValues(valueID integer primary key, value text);
        create table itemData(itemID int, fieldID int, valueID int);
        create table itemAttachments(itemID int, parentItemID int, path text);
        insert into fields values (1, 'citationKey');
    """)
    n = 1
    for clave_zotero, clave_cita, ruta in adjuntos:
        c.execute("insert into items values (?, ?)", (n, clave_zotero))
        c.execute("insert into items values (?, ?)", (n + 1, f"ADJ{n:05d}"))
        if clave_cita:
            c.execute("insert into itemDataValues values (?, ?)", (n, clave_cita))
            c.execute("insert into itemData values (?, 1, ?)", (n, n))
        c.execute("insert into itemAttachments values (?, ?, ?)", (n + 1, n, f"attachments:{ruta}"))
        n += 2
    c.commit()
    c.close()


def _slug(texto: str) -> str:
    """Nombre en kebab ASCII, como las fichas canónicas (`<id>_<slug>.md`)."""
    import unicodedata
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "-".join(p for p in "".join(c if c.isalnum() else " " for c in plano.lower()).split())[:48]


def _repo_datos(repo: Path, libros: dict[int, dict]) -> None:
    """El repo de datos de muestra: los ledgers, dos fichas canónicas, la zona de entrada y un fuentes.yml."""
    (repo / "ingesta").mkdir(parents=True)
    (repo / "catalogacion" / "fichas").mkdir(parents=True)
    (repo / "entrada" / "proyecto-muestra").mkdir(parents=True)
    ids = sorted(libros)
    (repo / "fuentes_descargadas.tsv").write_text(
        "fecha\tsha256\tfuente\ttipo\treferencia\ttitulo\turl\torigen\tarchivo\tbytes\testado\n"
        "2026-10-30T09:12:00\t" + "a" * 64 + "\tcongreso\tnorma\tLey N.° 31143\tLey que regula la muestra\thttps://example.invalid/ley.pdf\t\tentrada/ley_31143.pdf\t1024\tdescargado\n"
        "2026-10-31T10:40:00\t" + "b" * 64 + "\tarticulo\tarticulo\t10.1000/muestra\tUn artículo de muestra\thttps://example.invalid/art.pdf\t\tentrada/articulo_muestra.pdf\t2048\tdescargado\n"
        "2026-11-01T08:05:00\t" + "c" * 64 + "\tcongreso\tnorma\tLey N.° 99999\t\thttps://example.invalid/no.pdf\t\t\t0\terror\n", encoding="utf-8")
    for nombre in ("ley_31143.pdf", "articulo_muestra.pdf", "informe_sin_identificar.pdf"):
        (repo / "entrada" / nombre).write_bytes(_PDF)
    (repo / "entrada" / "proyecto-muestra" / "tesis_borrador.pdf").write_bytes(_PDF)
    (repo / "ingesta" / "pendientes.tsv").write_text(
        "sha256\torigen\tautores\ttitulo\ttipo_zotero\tclasificador\titem_type\teditorial\tfecha\tidentificador\tidioma\ttags\tconfianza\tnota\tficha\tserie\tserie_index\n"
        + "a" * 64 + "\tley_31143.pdf\tCongreso de la República\tLey N.° 31143\tstatute\tnorma\tstatute\t\t2021\t\tes\tnormativa\talta\t\t\t\t\n"
        + "b" * 64 + "\tarticulo_muestra.pdf\tPérez, Ana\tUn artículo de muestra\tjournalArticle\tarticulo\tjournalArticle\t\t2024\t10.1000/muestra\tes\t\tmedia\t\t\t\t\n"
        + "d" * 64 + "\tproyecto-muestra/tesis_borrador.pdf\tUnknown\tTesis de muestra\tthesis\ttesis\tthesis\t\t2025\t\tes\t\tbaja\t\t\t\t\n"
        + "e" * 64 + "\tdatafw/data/raw/muestra/no_existe.pdf\tINEI\tCuestionario de muestra\treport\tinforme\treport\t\t2018\t\tes\t\tmedia\t\t\t\t\n", encoding="utf-8")
    (repo / "ingesta" / "ingesta.tsv").write_text(
        "fecha\tsha256\torigen\ttitulo\tautores\ttipo_zotero\tclasificador\tfecha_doc\teditorial\ttags\tcalibre_id\truta_calibre\tzotero_key\testado\n"
        + "2026-10-30\t" + "a" * 64 + f"\tley_31143.pdf\tLey N.° 31143\tCongreso de la República\tstatute\tnorma\t2021\t\tnormativa\t{ids[0]}\t\t\tcatalogado\n", encoding="utf-8")
    filas = ["id\tautores\ttitulo\ttipo_zotero\tclasificador\teditorial\tfecha\tidentificador\tidioma\ttags\tconfianza\tnota"]
    for i in ids[:4]:
        d = libros[i]
        filas.append(f"{i}\t{d['autores'][0]}\t{d['titulo']}\tbook\tlibro\t\t2021\t\tes\teconomia\talta\t")
    (repo / "catalogacion" / "resumen_catalogacion.tsv").write_text("\n".join(filas) + "\n", encoding="utf-8")
    for i, estado in ((ids[0], "verificada_script"), (ids[1], "pendiente")):
        d = libros[i]
        slug = _slug(d["titulo"])
        (repo / "catalogacion" / "fichas" / f"{i}_{slug}.md").write_text(
            f"---\ntipo: ficha_catalogacion\ncalibre_id: {i}\nzotero_key: {d['zotero_key']}\nclave_bibtex: {d['clave']}\nproyecto: muestra\n"
            f"verificacion:\n  estado: {estado}\n  metodo: texto\n  fecha: 2026-10-31\n---\n\n> Ficha de catalogación de «{d['titulo']}». "
            f"Generada para la muestra.\n\n## Origen\n\n`entrada/{slug}.pdf` · 12 págs\n\n## Zotero\n| Campo | Valor |\n|---|---|\n"
            f"| Title | {d['titulo']} |\n| Author | {d['autores'][0]} |\n\n## Calibre\n| Campo | Valor |\n|---|---|\n"
            f"| Title | {d['titulo']} |\n| Authors | {d['autores'][0]} |\n| Languages | spa |\n\n## Notas\n\nFicha de muestra.\n", encoding="utf-8")
    (repo / "entrada" / "proyecto-muestra" / "fuentes.yml").write_text(
        "proyecto: proyecto-muestra\ngenerado: '2026-11-01'\nfuentes:\n"
        f"- origen: ley_31143.pdf\n  calibre_id: {ids[0]}\n  zotero_key: {libros[ids[0]]['zotero_key']}\n  clave_bibtex: ''\n  titulo: {libros[ids[0]]['titulo']}\n"
        f"- origen: pendiente.pdf\n  calibre_id: ''\n  zotero_key: ''\n  clave_bibtex: ''\n  titulo: Una fuente sin libro\n", encoding="utf-8")


def crear(raiz: Path, con_calibre: bool | None = None) -> Muestra:
    """Crea la muestra en `raiz` (vacía o inexistente) y devuelve dónde quedó cada cosa y el entorno que la señala."""
    raiz = Path(raiz)
    raiz.mkdir(parents=True, exist_ok=True)
    biblioteca, config, repo, estado = raiz / "biblioteca", raiz / "calibre-config", raiz / "repo", raiz / "estado"
    biblioteca.mkdir()
    zotero_db = raiz / "zotero" / "zotero.sqlite"
    zotero_db.parent.mkdir()
    if con_calibre is None:
        con_calibre = hay_calibredb()
    libros: dict[int, dict] = {}
    if con_calibre:
        pdfs = raiz / "pdfs"
        pdfs.mkdir()
        for titulo, autor, _z, _c in LIBROS:
            (pdfs / f"{titulo} - {autor}.pdf").write_bytes(_PDF)
        plantilla = _plantilla()
        if plantilla is not None and (plantilla / "metadata.db").is_file():
            shutil.rmtree(biblioteca)
            shutil.copytree(plantilla, biblioteca)               # la misma biblioteca de muestra, ya enriquecida
        else:
            r = _calibredb(["add", "--with-library", str(biblioteca)] + sorted(str(p) for p in pdfs.glob("*.pdf")), config)
            con_calibre = r.returncode == 0 and (biblioteca / "metadata.db").is_file()
            if not con_calibre:
                print("muestra: calibredb no pudo crear la biblioteca:", (r.stderr or r.stdout)[-800:], file=sys.stderr)
            elif _enriquecer(biblioteca, config) and plantilla is not None:
                _guardar_plantilla(biblioteca, plantilla)
    if not con_calibre:
        _metadata_db_minima(biblioteca / "metadata.db")
    calibre_db = biblioteca / "metadata.db"
    with sqlite3.connect(calibre_db.resolve().as_uri() + "?mode=ro", uri=True) as c:
        for b, titulo, ruta in c.execute("select id, title, path from books order by id"):
            libros[b] = {"titulo": titulo, "carpeta": ruta}
        for b, nombre in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id=l.author"):
            libros[b].setdefault("autores", []).append(nombre.replace("|", ","))
        for b, fmt, nombre in c.execute("select book, format, name from data"):
            libros[b].setdefault("formatos", []).append(f"{nombre}.{fmt.lower()}")
    por_titulo = {d["titulo"]: b for b, d in libros.items()}
    adjuntos = []
    for titulo, _autor, clave_zotero, clave_cita in LIBROS:
        b = por_titulo.get(titulo)
        if b is None:
            continue
        libros[b].update(zotero_key=clave_zotero, clave=clave_cita)
        if clave_zotero:
            formatos = libros[b].get("formatos") or [f"{titulo}.pdf"]
            adjuntos.append((clave_zotero, clave_cita, f"{libros[b]['carpeta']}/{formatos[0]}"))
    _zotero(zotero_db, adjuntos)
    _repo_datos(repo, libros)
    estado.mkdir()
    (estado / "biblioteca").mkdir()
    entorno = {"CALIBRE_DB": str(calibre_db), "BIBLIOTECA_DIR": str(biblioteca), "ZOTERO_DB": str(zotero_db), "ZOTERO_DIR": str(zotero_db.parent),
               "XDG_STATE_HOME": str(estado), "BIBLIOTECA_STUDIO_DATOS": str(repo), "LOCK_CALIBRE": str(estado / "biblioteca" / "calibre.lock"),
               "LOCK_ZOTERO": str(estado / "biblioteca" / "zotero.lock"), "RESPALDOS_DIR": str(raiz / "respaldos"), "ARCHDISK_DIR": str(raiz / "no-montado"),
               "PUERTA_RESPALDOS": str(raiz / "respaldos" / "biblioteca" / "puerta"),
               "WRITING_DIR": str(raiz / "escritura"), "DATAFW_DIR": str(raiz / "datafw"), "NOTES_DIR": str(raiz / "notas")}
    (raiz / "notas").mkdir()
    indice = _indice(entorno, repo, libros, estado / "biblioteca" / "indice.json", raiz / "notas")
    _respaldos(raiz / "respaldos" / "biblioteca" / "puerta")
    return Muestra(raiz, biblioteca, calibre_db, zotero_db, repo, estado, indice, con_calibre, entorno)


def _metadata_db_minima(db: Path) -> None:
    """Sin calibredb: lo mínimo de metadata.db que lee `lib/indice.calibre` (books, authors, data, custom_columns)."""
    c = sqlite3.connect(db)
    c.executescript("""
        create table books(id integer primary key, title text, path text);
        create table authors(id integer primary key, name text);
        create table books_authors_link(id integer primary key, book int, author int);
        create table data(book int, format text, name text);
        create table custom_columns(id integer primary key, label text);
    """)
    for i, (titulo, autor, _z, _c) in enumerate(LIBROS, start=1):
        nombre, apellido = autor.split(" ", 1)
        carpeta = f"{apellido}, {nombre}/{titulo} ({i})"
        c.execute("insert into books values (?, ?, ?)", (i, titulo, carpeta))
        c.execute("insert into authors values (?, ?)", (i, f"{apellido}, {nombre}"))
        c.execute("insert into books_authors_link(book, author) values (?, ?)", (i, i))
        if i % 3 != 0:
            c.execute("insert into data values (?, 'PDF', ?)", (i, f"{titulo} - {autor}"))
    c.commit()
    c.close()


def _indice(entorno: dict, repo: Path, libros: dict, destino: Path, notas: Path) -> Path:
    """El índice con el mismo código que la ventana real (`lib/indice.construir`), sobre la muestra; las fichas y la nota
    de lectura se toman del repo de datos de muestra."""
    sys.path.insert(0, str(REPO / "lib"))
    import indice as ind  # noqa: E402
    env = SimpleNamespace(CALIBRE_DB=entorno["CALIBRE_DB"], ZOTERO_DB=entorno["ZOTERO_DB"], BIBLIOTECA_DIR=entorno["BIBLIOTECA_DIR"],
                          DOCS_ROOT=str(Path(entorno["NOTES_DIR"]).parent))
    d = ind.construir(env)
    fichas = {}
    for f in sorted((repo / "catalogacion" / "fichas").glob("*.md")):
        fichas.setdefault(f.name.split("_", 1)[0], []).append(f"catalogacion/fichas/{f.name}")
    for b, libro in d["libros"].items():
        libro["fichas"] = fichas.get(b, [])
        libro["nota"] = str(notas / f"{(libro['clave'] or f'calibre-{b}').lower()}.md")
    primero = next(iter(d["libros"].values()), None)
    if primero and primero.get("clave"):
        (notas / f"{primero['clave'].lower()}.md").write_text(f"# {primero['titulo']}\n\nNota de lectura de muestra.\n", encoding="utf-8")
    d["repo"] = str(repo)
    d["notas"] = str(notas)
    d["generado"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return destino


def _respaldos(raiz: Path) -> None:
    for suite in ("koreader", "sincronizar-zotero"):
        (raiz / suite / "calibre").mkdir(parents=True)
        (raiz / suite / "calibre" / "metadata_20261101_043000.db").write_bytes(b"respaldo de muestra")


if __name__ == "__main__":
    import tempfile
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="biblioteca-muestra-"))
    m = crear(destino)
    print(json.dumps({"raiz": str(m.raiz), "con_calibre": m.con_calibre, "libros": len(json.loads(m.indice.read_text())["libros"]), "entorno": m.entorno}, indent=1, ensure_ascii=False))
