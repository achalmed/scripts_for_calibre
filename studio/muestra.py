#!/usr/bin/env python3
"""studio/muestra.py — una biblioteca de muestra con libros ficticios, para las pruebas y las capturas de Biblioteca Studio.

Nunca la biblioteca real (`../CLAUDE.md`: las bases reales son intocables en las pruebas). En una carpeta temporal crea:
una biblioteca Calibre mínima con `calibredb add` (si `calibredb` está instalado y responde; con `unshare -rn` para no
chocar con un Calibre abierto, como `tests/calibre`), una `zotero.sqlite` mínima con tres ítems enlazados a esos libros
por la ruta del adjunto, un repo de datos de muestra (los ledgers, dos fichas canónicas, la zona de entrada y un
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
        r = _calibredb(["add", "--with-library", str(biblioteca)] + sorted(str(p) for p in pdfs.glob("*.pdf")), config)
        con_calibre = r.returncode == 0 and (biblioteca / "metadata.db").is_file()
        if not con_calibre:
            print("muestra: calibredb no pudo crear la biblioteca:", (r.stderr or r.stdout)[-800:], file=sys.stderr)
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
