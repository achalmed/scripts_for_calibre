"""tests/calibre_apoyo.py — utilidades de las pruebas de scripts_for_calibre (ola 2, K1).

Objetivo: correr las suites sobre COPIAS de metadata.db y zotero.sqlite en un directorio temporal y
  comparar lo que hacen con lo que hacía la referencia (un commit de git), sin tocar jamás las bases
  reales (R-6 de la ola 2).
Método:
  - las bases reales se leen solo con `mode=ro` y se copian con la API de respaldo de SQLite;
  - la biblioteca se reproduce como «espejo»: carpetas reales y un enlace simbólico por archivo de libro,
    sin `metadata.opf` (Calibre los reescribe y un enlace los escribiría en la biblioteca real);
  - cada corrida tiene su propio HOME, XDG_* y candado, y un `ps`/`pgrep` falso que dice «Calibre y
    Zotero cerrados», para que las pruebas no dependan de las apps del autor ni las esperen;
  - el árbol de referencia sale de `git archive <ref>` y el actual de `git ls-files`, ambos copiados al
    temporal con `core` enlazado al lado: los respaldos y reportes de las corridas quedan en el temporal.
  - lo que se compara es el «delta semántico» de cada base (antes → después), con las fechas volátiles
    (ahora()) reducidas a «cambió».
Límite: KOReader se lee de una copia de su carpeta de configuración; las columnas compuestas no se
  comparan (son plantillas de Calibre, no datos).
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO.parent
CORE = DOCS / "core"
REFERENCIA = os.environ.get("CALIBRE_REF_CARACTERIZACION", "467c8a7")   # main antes de la ola 2a (2026-10-05)

sys.path.insert(0, str(CORE))
import env as core_env  # noqa: E402  (rutas reales, solo para leerlas)

REAL_BIBLIOTECA = Path(core_env.BIBLIOTECA_DIR)
REAL_CALIBRE_DB = Path(core_env.CALIBRE_DB)
REAL_ZOTERO_DB = Path(core_env.ZOTERO_DB)
REAL_KOREADER = Path(core_env.KOREADER_STATS).parent.parent   # ~/.config/koreader


# ------------------------------------------------------------------ copias
def copiar_base(origen: Path, destino: Path) -> None:
    """Copia consistente de una base SQLite abriendo el origen en solo lectura."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def espejo_biblioteca(destino: Path, db: Path) -> Path:
    """Biblioteca espejo en `destino`: carpetas reales, enlaces a los archivos de libro, `db` como metadata.db."""
    destino.mkdir(parents=True, exist_ok=True)
    for raiz, dirs, files in os.walk(REAL_BIBLIOTECA):
        rel = Path(raiz).relative_to(REAL_BIBLIOTECA)
        if rel == Path("."):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".") and not f.startswith("metadata")]
        (destino / rel).mkdir(exist_ok=True)
        for f in files:
            if f == "metadata.opf":
                continue
            os.symlink(Path(raiz) / f, destino / rel / f)
    shutil.copyfile(db, destino / "metadata.db")
    return destino


def copiar_koreader(destino: Path) -> Path:
    """Copia de lo que leen las suites de KOReader: estadísticas, sidecars por hash e historial."""
    destino.mkdir(parents=True, exist_ok=True)
    stats = REAL_KOREADER / "settings" / "statistics.sqlite3"
    if stats.exists():
        copiar_base(stats, destino / "settings" / "statistics.sqlite3")
    if (REAL_KOREADER / "hashdocsettings").is_dir():
        shutil.copytree(REAL_KOREADER / "hashdocsettings", destino / "hashdocsettings", symlinks=True)
    if (REAL_KOREADER / "history.lua").exists():
        shutil.copyfile(REAL_KOREADER / "history.lua", destino / "history.lua")
    return destino


def arbol_referencia(destino: Path, ref: str = REFERENCIA) -> Path:
    """El árbol del repo en `ref`, en destino/scripts_for_calibre, con `core` enlazado al lado."""
    destino.mkdir(parents=True, exist_ok=True)
    arbol = destino / "scripts_for_calibre"
    arbol.mkdir()
    archivo = subprocess.run(["git", "-C", str(REPO), "archive", ref], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(arbol)], input=archivo, check=True)
    # Las suites tomaron nombres por función en la fase E de la ola 2: en la referencia, cada nombre nuevo es un
    # enlace a su carpeta vieja, y las pruebas usan las mismas rutas para las dos versiones.
    for viejo, nuevo in NOMBRES_ANTERIORES.items():
        if (arbol / viejo).is_dir() and not (arbol / nuevo).exists():
            os.symlink(viejo, arbol / nuevo)
    os.symlink(CORE, destino / "core")
    return arbol


# carpeta en la referencia (467c8a7) → carpeta hoy (fase E de la ola 2)
NOMBRES_ANTERIORES = {"script_catalogacion_biblioteca": "catalogacion", "script_ecosistema_lectura": "lectura",
                      "script_koreader_estudio": "koreader", "script_sincronizar_zotero": "sincronizar-zotero",
                      "script_metadatos_calibre": "metadatos-pdf", "script_verificar_metadatos": "verificacion"}


def arbol_actual(destino: Path) -> Path:
    """El árbol de trabajo (rastreado y nuevo no ignorado), sin las fichas, en destino/scripts_for_calibre."""
    destino.mkdir(parents=True, exist_ok=True)
    arbol = destino / "scripts_for_calibre"
    salida = subprocess.run(["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "-z"],
                            check=True, capture_output=True).stdout.decode()
    for rel in filter(None, salida.split("\0")):
        if rel.startswith("catalogacion/fichas/"):
            continue
        origen = REPO / rel
        if not origen.exists() and not origen.is_symlink():
            continue   # borrado en el árbol de trabajo y aún rastreado
        p = arbol / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_symlink():
            os.symlink(os.readlink(origen), p)
        else:
            shutil.copy2(origen, p)
    os.symlink(CORE, destino / "core")
    return arbol


# ------------------------------------------------------------------ entorno
FALSO_PS = "#!/bin/sh\n# ps falso de las pruebas: ningún proceso de Calibre ni de Zotero.\necho COMMAND\necho bash\n"
FALSO_PGREP = "#!/bin/sh\n# pgrep falso de las pruebas: nada coincide.\nexit 1\n"


def entorno(corrida: Path, biblioteca: Path, zotero_db: Path, koreader: Path) -> dict:
    """Entorno mínimo de una corrida: todo lo que escribe cae dentro de `corrida`."""
    bin_falso = corrida / "bin"
    bin_falso.mkdir(parents=True, exist_ok=True)
    for nombre, texto in (("ps", FALSO_PS), ("pgrep", FALSO_PGREP)):
        p = bin_falso / nombre
        p.write_text(texto)
        p.chmod(0o755)
    home = corrida / "home"
    home.mkdir(exist_ok=True)
    (corrida / "tmp").mkdir(exist_ok=True)
    e = {
        "TMPDIR": str(corrida / "tmp"),          # los temporales de Calibre y de las suites, al disco, no a /tmp
        "PATH": f"{bin_falso}:{os.environ['PATH']}",
        "HOME": str(home),
        "USER": os.environ.get("USER", "prueba"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TZ": os.environ.get("TZ", "America/Lima"),
        "XDG_STATE_HOME": str(corrida / "estado"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "BIBLIOTECA_DIR": str(biblioteca),
        "CALIBRE_DB": str(biblioteca / "metadata.db"),
        "ZOTERO_DIR": str(zotero_db.parent),
        "ZOTERO_DB": str(zotero_db),
        "QEL_ZOTERO_DB": str(zotero_db),
        "QKO_KOREADER_CONFIG": str(koreader),
        "KOREADER_STATS": str(koreader / "settings" / "statistics.sqlite3"),
        "KOREADER_RESPALDO_DIR": str(corrida / "koreader-respaldo"),
        "RESPALDOS_DIR": str(corrida / "respaldos-externos"),
        "LOCK_CALIBRE": str(corrida / "estado" / "calibre.lock"),
        "LOCK_ZOTERO": str(corrida / "estado" / "zotero.lock"),
    }
    reales = {str(REAL_CALIBRE_DB), str(REAL_ZOTERO_DB), str(REAL_BIBLIOTECA)}
    assert not reales & set(e.values()), "el entorno de prueba apunta a una base real"
    return e


def _aislar() -> list[str]:
    """`unshare -rn` si se puede: Calibre se excluye entre procesos con un socket abstracto por usuario
    («Another calibre program… is running»); en un espacio de red propio, una prueba no choca con un
    timer real ni la referencia con el árbol actual."""
    global _AISLAR
    if _AISLAR is None:
        ok = shutil.which("unshare") and subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0
        _AISLAR = ["unshare", "-rn"] if ok else []
    return _AISLAR


_AISLAR = None


def correr(arbol: Path, suite: str, args: list[str], e: dict, timeout: int = 240):
    return subprocess.run([*_aislar(), str(arbol / suite / "main.sh"), *args], env=e, capture_output=True,
                          text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def lanzar(arbol: Path, suite: str, args: list[str], e: dict, salida: Path):
    """Como `correr`, pero en segundo plano (la referencia y el árbol actual corren a la vez)."""
    fh = open(salida, "w")
    return subprocess.Popen([*_aislar(), str(arbol / suite / "main.sh"), *args], env=e, stdout=fh,
                            stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL), fh


def ultimo(carpeta: Path, patron: str) -> Path | None:
    cand = sorted(carpeta.glob(patron), key=lambda p: p.stat().st_mtime)
    return cand[-1] if cand else None


# ------------------------------------------------------------------ volcados semánticos
def _ro(db: Path):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def _fecha(v):
    """Fechas de Calibre (texto ISO con o sin zona) a ISO UTC al segundo; lo demás, igual."""
    if not isinstance(v, str) or len(v) < 10 or v[4] != "-":
        return v
    try:
        d = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return v
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def volcado_calibre(db: Path) -> dict:
    """{(libro, campo): valor} con lo que las suites pueden escribir; fechas normalizadas."""
    c = _ro(db)
    v = {}
    for bid, title, pubdate, sidx, path in c.execute("select id, title, pubdate, series_index, path from books"):
        v[(bid, "title")] = title
        v[(bid, "pubdate")] = _fecha(pubdate)
        v[(bid, "series_index")] = sidx
        v[(bid, "path")] = path
    for bid, nombres in c.execute("select l.book, group_concat(a.name, ' & ') from books_authors_link l "
                                  "join authors a on a.id = l.author group by l.book order by l.id"):
        v[(bid, "authors")] = nombres
    consultas = {
        "tags": "select l.book, t.name from books_tags_link l join tags t on t.id = l.tag",
        "publisher": "select l.book, p.name from books_publishers_link l join publishers p on p.id = l.publisher",
        "series": "select l.book, s.name from books_series_link l join series s on s.id = l.series",
        "languages": "select l.book, g.lang_code from books_languages_link l join languages g on g.id = l.lang_code",
        "rating": "select l.book, r.rating from books_ratings_link l join ratings r on r.id = l.rating",
        "identifiers": "select book, type || ':' || val from identifiers",
        "comments": "select book, text from comments",
        "formats": "select book, format || ':' || name from data",
    }
    for campo, sql in consultas.items():
        acum = {}
        for bid, x in c.execute(sql):
            acum.setdefault(bid, []).append(str(x))
        for bid, xs in acum.items():
            v[(bid, campo)] = " | ".join(sorted(xs))
    for num, label, tipo, norm in c.execute("select id, label, datatype, normalized from custom_columns"):
        if tipo == "composite":
            continue
        if norm:
            sql = (f"select l.book, x.value from books_custom_column_{num}_link l "
                   f"join custom_column_{num} x on x.id = l.value")
        else:
            sql = f"select book, value from custom_column_{num}"
        acum = {}
        for bid, x in c.execute(sql):
            acum.setdefault(bid, []).append(_fecha(x) if tipo == "datetime" else x)
        for bid, xs in acum.items():
            v[(bid, "#" + label)] = xs[0] if len(xs) == 1 else tuple(sorted(map(str, xs)))
    c.close()
    return v


def volcado_zotero(db: Path) -> dict:
    """{(clave, campo): valor} de ítems, campos, creadores, etiquetas y adjuntos."""
    c = _ro(db)
    v = {}
    clave = {}
    for iid, key, tipo, synced, dmod, cdmod in c.execute(
            "select i.itemID, i.key, t.typeName, i.synced, i.dateModified, i.clientDateModified "
            "from items i join itemTypes t on t.itemTypeID = i.itemTypeID"):
        clave[iid] = key
        v[(key, "tipo")] = tipo
        v[(key, "synced")] = synced
        v[(key, "dateModified")] = dmod
        v[(key, "clientDateModified")] = cdmod
    for iid, campo, valor in c.execute(
            "select d.itemID, f.fieldName, x.value from itemData d join fields f on f.fieldID = d.fieldID "
            "join itemDataValues x on x.valueID = d.valueID"):
        v[(clave[iid], "f:" + campo)] = valor
    acum = {}
    for iid, orden, ctipo, fn, ln, fm in c.execute(
            "select ic.itemID, ic.orderIndex, ic.creatorTypeID, c.firstName, c.lastName, c.fieldMode "
            "from itemCreators ic join creators c on c.creatorID = ic.creatorID order by ic.itemID, ic.orderIndex"):
        acum.setdefault(iid, []).append((orden, ctipo, fn, ln, fm))
    for iid, xs in acum.items():
        v[(clave[iid], "creadores")] = tuple(xs)
    acum = {}
    for iid, nombre, tipo in c.execute("select it.itemID, t.name, it.type from itemTags it join tags t on t.tagID = it.tagID"):
        acum.setdefault(iid, []).append((nombre, tipo))
    for iid, xs in acum.items():
        v[(clave[iid], "etiquetas")] = tuple(sorted(xs))
    for iid, padre, modo, ruta in c.execute("select itemID, parentItemID, linkMode, path from itemAttachments"):
        v[(clave[iid], "adjunto")] = (clave.get(padre), modo, ruta)
    for (iid,) in c.execute("select itemID from deletedItems"):
        v[(clave[iid], "borrado")] = True
    c.close()
    return v


VOLATILES = {"#ko_lastsync", "#zotero_date_modified", "dateModified", "clientDateModified"}   # se escriben con ahora()


def delta(antes: dict, despues: dict) -> dict:
    """Cambios entre dos volcados; los campos volátiles solo dicen «cambió»."""
    d = {}
    for k in set(antes) | set(despues):
        a, b = antes.get(k), despues.get(k)
        if a != b:
            d[k] = "cambió" if k[1] in VOLATILES else (a, b)
    return d
