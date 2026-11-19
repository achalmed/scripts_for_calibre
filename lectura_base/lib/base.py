"""lectura_base/lib/base.py — la base de lectura de Biblioteca Studio (decisiones §9.6): el ÚNICO escritor de `lectura.sqlite`.

Una sola base donde se juntan, con su origen, los subrayados, resaltados y notas de KOReader, Zotero, Okular, el lector
de Yachay y Ñawinchay, y las sesiones, el progreso y el tiempo de lectura de cada libro. Vive fuera del repo y fuera de toda base de
Calibre o de Zotero: `$XDG_DATA_HOME/biblioteca/lectura.sqlite` (o `LECTURA_DB`). Esta conexión se niega a abrir una
ruta dentro de la biblioteca o de la carpeta de Zotero, o igual a `CALIBRE_DB` o `ZOTERO_DB`: esas solo las escribe la
puerta (`lib/escribir*`).

El modelo:
- `anotaciones`: una por pasaje subrayado, venga de donde venga (libro por `calibre_id` y MD5 parcial de KOReader; hoja
  del PDF; página o capítulo que se cita; texto; rectángulos como fracciones de la hoja [[hoja, x, y, ancho, alto]] con el
  origen arriba a la izquierda, como Yachay; color; tipo; intención; nota; fechas; huella) y, desde el esquema 3, su
  `posicion` en un libro de flujo (EPUB): los xpointers `pos0` y `pos1` de KOReader (fin exclusivo) y el pasaje con su
  contexto (`cita`, el TextQuoteSelector de la W3C). Con ella, lo anotado en un EPUB vuelve a KOReader en su lugar.
- `presencias`: dónde vive cada anotación (origen y su identificador en esa herramienta). Un mismo subrayado hecho en
  KOReader y en Zotero es UNA anotación con dos presencias: así no se duplica al cruzar orígenes.
- `sesiones` (KOReader trae cada página con su hora) y `progreso` (por libro y por origen: hoja, fracción, estado,
  segundos). Los relojes no se copian entre sí: cada origen guarda su tiempo y las estadísticas los suman.
- `cambios`: la cola que llenan los disparadores en cada alta, cambio o baja; un consumidor (Yachay por su API, otro
  studio) lee desde su número y guarda su cursor en `cursores`.
- `fichas_obra` (esquema 2, 2026-11-19, decisiones §9.13): la ficha de obra de la persona sobre un libro, como la da Yachay
  (las seis respuestas, los temas, el signo, si la dio por leída y su `version`, que viaja como `version_base` en la
  vuelta). Una por libro y origen: Yachay da a cada persona solo las suyas y una por `calibre_id`.

Conciliar (`importar`): una lectura de un origen se compara con la base. Lo ya visto (misma presencia) se actualiza si
cambió en el origen y es más nuevo; lo nuevo se une a una anotación de otro origen si es el mismo pasaje (la misma huella,
o el texto casi igual en la misma hoja o la vecina, o los rectángulos solapados); si no, es una anotación nueva. Lo que un
origen leyó entero y ya no trae queda «ausente» en ese origen; una anotación ausente en todos queda «borrada» (borrar en
una herramienta no borra en las otras: eso lo decide el autor, §9.7).

Quién escribe: los adaptadores de `sincronizar` (los `LEIDOS`: KOReader, Zotero, Okular y Yachay se leen desde aquí) y los
clientes que traen su propia lectura (`CLIENTES`: Ñawinchay, el lector del ecosistema, llama a `importar` con lo de su
diario). Todos pasan por `importar`, el único escritor; la conexión espera hasta `ESPERA_MS` si otro está escribiendo.

Simular es la regla: `importar(..., aplicar=False)` concilia sobre una copia en memoria y devuelve el plan; con
`aplicar=True`, antes de escribir, un respaldo verificado (`lib/escribir.respaldar`).
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lectura_base.lib import texto as tx

REPO = Path(__file__).resolve().parents[2]
ESQUEMA = 3          # 2 (2026-11-19): `fichas_obra`; 3 (2026-11-19): `anotaciones.posicion`. Ambas aditivas
LEIDOS = ("koreader", "zotero", "okular", "yachay")     # los que `sincronizar` lee desde aquí
CLIENTES = ("nawinchay",)                                # los que traen su lectura y llaman a `importar` (§9.14)
ORIGENES = LEIDOS + CLIENTES
NOMBRES = {"koreader": "KOReader", "zotero": "Zotero", "okular": "Okular", "yachay": "Yachay", "nawinchay": "Ñawinchay",
           "base": "Biblioteca Studio"}
ESPERA_MS = 5000     # busy_timeout: un cliente que vuelca mientras corre el ciclo espera en vez de fallar

SQL_ESQUEMA = """
CREATE TABLE IF NOT EXISTS libros (
    calibre_id INTEGER PRIMARY KEY,
    md5 TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL DEFAULT '',
    autores TEXT NOT NULL DEFAULT '',
    actualizado TEXT
);
CREATE INDEX IF NOT EXISTS libros_md5 ON libros(md5);

CREATE TABLE IF NOT EXISTS anotaciones (
    id INTEGER PRIMARY KEY,
    uid TEXT NOT NULL UNIQUE,
    calibre_id INTEGER,
    md5 TEXT NOT NULL DEFAULT '',
    hoja INTEGER,
    pagina TEXT NOT NULL DEFAULT '',
    capitulo TEXT NOT NULL DEFAULT '',
    texto TEXT NOT NULL DEFAULT '',
    texto_normal TEXT NOT NULL DEFAULT '',
    rects TEXT NOT NULL DEFAULT '[]',
    color TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'resaltado',
    intencion TEXT NOT NULL DEFAULT '',
    nota TEXT NOT NULL DEFAULT '',
    creada TEXT NOT NULL DEFAULT '',
    modificada TEXT NOT NULL DEFAULT '',
    huella TEXT NOT NULL,
    borrada TEXT,
    origen_ultimo TEXT NOT NULL DEFAULT '',
    posicion TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS anotaciones_libro ON anotaciones(calibre_id, hoja);
CREATE INDEX IF NOT EXISTS anotaciones_md5 ON anotaciones(md5);
CREATE INDEX IF NOT EXISTS anotaciones_huella ON anotaciones(huella);

CREATE TABLE IF NOT EXISTS presencias (
    id INTEGER PRIMARY KEY,
    anotacion_id INTEGER NOT NULL REFERENCES anotaciones(id) ON DELETE CASCADE,
    origen TEXT NOT NULL,
    origen_id TEXT NOT NULL,
    huella_origen TEXT NOT NULL DEFAULT '',
    visto TEXT,
    ausente TEXT,
    UNIQUE (origen, origen_id)
);
CREATE INDEX IF NOT EXISTS presencias_anotacion ON presencias(anotacion_id);

CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY,
    calibre_id INTEGER,
    md5 TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL,
    origen_id TEXT NOT NULL,
    inicio INTEGER NOT NULL,
    fin INTEGER NOT NULL,
    segundos INTEGER NOT NULL,
    paginas INTEGER NOT NULL DEFAULT 0,
    desde INTEGER,
    hasta INTEGER,
    UNIQUE (origen, origen_id)
);
CREATE INDEX IF NOT EXISTS sesiones_libro ON sesiones(calibre_id, inicio);
CREATE INDEX IF NOT EXISTS sesiones_inicio ON sesiones(inicio);

CREATE TABLE IF NOT EXISTS progreso (
    id INTEGER PRIMARY KEY,
    clave TEXT NOT NULL,
    calibre_id INTEGER,
    md5 TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL,
    hoja INTEGER,
    hojas INTEGER,
    fraccion REAL,
    estado TEXT NOT NULL DEFAULT '',
    segundos INTEGER NOT NULL DEFAULT 0,
    primera TEXT NOT NULL DEFAULT '',
    ultima TEXT NOT NULL DEFAULT '',
    UNIQUE (origen, clave)
);

CREATE TABLE IF NOT EXISTS cambios (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    tabla TEXT NOT NULL,
    fila INTEGER NOT NULL,
    uid TEXT NOT NULL DEFAULT '',
    operacion TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT '',
    calibre_id INTEGER
);
CREATE TABLE IF NOT EXISTS cursores (
    consumidor TEXT PRIMARY KEY,
    seq INTEGER NOT NULL DEFAULT 0,
    momento TEXT
);
CREATE TABLE IF NOT EXISTS corridas (
    id INTEGER PRIMARY KEY,
    momento TEXT NOT NULL,
    origen TEXT NOT NULL,
    resumen TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS fichas_obra (
    id INTEGER PRIMARY KEY,
    origen TEXT NOT NULL DEFAULT 'yachay',
    origen_id TEXT NOT NULL DEFAULT '',
    calibre_id INTEGER NOT NULL,
    ficha TEXT NOT NULL DEFAULT '{}',
    secciones TEXT NOT NULL DEFAULT '{}',
    escritas INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 6,
    leida INTEGER NOT NULL DEFAULT 0,
    leida_en TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 0,
    creada TEXT NOT NULL DEFAULT '',
    modificada TEXT NOT NULL DEFAULT '',
    visto TEXT,
    baja TEXT,
    UNIQUE (origen, calibre_id)
);
CREATE INDEX IF NOT EXISTS fichas_obra_origen_id ON fichas_obra(origen, origen_id);

CREATE TRIGGER IF NOT EXISTS anotaciones_alta AFTER INSERT ON anotaciones BEGIN
    INSERT INTO cambios(tabla, fila, uid, operacion, origen, calibre_id)
    VALUES ('anotaciones', NEW.id, NEW.uid, 'alta', NEW.origen_ultimo, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS anotaciones_cambio AFTER UPDATE ON anotaciones
WHEN NEW.texto IS NOT OLD.texto OR NEW.nota IS NOT OLD.nota OR NEW.color IS NOT OLD.color OR NEW.rects IS NOT OLD.rects
  OR NEW.hoja IS NOT OLD.hoja OR NEW.pagina IS NOT OLD.pagina OR NEW.intencion IS NOT OLD.intencion
  OR NEW.tipo IS NOT OLD.tipo OR NEW.borrada IS NOT OLD.borrada OR NEW.calibre_id IS NOT OLD.calibre_id BEGIN
    INSERT INTO cambios(tabla, fila, uid, operacion, origen, calibre_id)
    VALUES ('anotaciones', NEW.id, NEW.uid,
            CASE WHEN NEW.borrada IS NOT NULL AND OLD.borrada IS NULL THEN 'baja'
                 WHEN NEW.borrada IS NULL AND OLD.borrada IS NOT NULL THEN 'alta' ELSE 'cambio' END,
            NEW.origen_ultimo, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS presencias_alta AFTER INSERT ON presencias BEGIN
    INSERT INTO cambios(tabla, fila, uid, operacion, origen, calibre_id)
    SELECT 'presencias', NEW.id, a.uid, 'alta', NEW.origen, a.calibre_id FROM anotaciones a WHERE a.id = NEW.anotacion_id;
END;
CREATE TRIGGER IF NOT EXISTS sesiones_alta AFTER INSERT ON sesiones BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id) VALUES ('sesiones', NEW.id, 'alta', NEW.origen, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS sesiones_cambio AFTER UPDATE ON sesiones WHEN NEW.segundos IS NOT OLD.segundos OR NEW.fin IS NOT OLD.fin BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id) VALUES ('sesiones', NEW.id, 'cambio', NEW.origen, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS progreso_alta AFTER INSERT ON progreso BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id) VALUES ('progreso', NEW.id, 'alta', NEW.origen, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS fichas_obra_alta AFTER INSERT ON fichas_obra BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id) VALUES ('fichas_obra', NEW.id, 'alta', NEW.origen, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS fichas_obra_cambio AFTER UPDATE ON fichas_obra
WHEN NEW.ficha IS NOT OLD.ficha OR NEW.version IS NOT OLD.version OR NEW.leida IS NOT OLD.leida OR NEW.baja IS NOT OLD.baja BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id)
    VALUES ('fichas_obra', NEW.id, CASE WHEN NEW.baja IS NOT NULL AND OLD.baja IS NULL THEN 'baja' ELSE 'cambio' END,
            NEW.origen, NEW.calibre_id);
END;
CREATE TRIGGER IF NOT EXISTS progreso_cambio AFTER UPDATE ON progreso
WHEN NEW.hoja IS NOT OLD.hoja OR NEW.fraccion IS NOT OLD.fraccion OR NEW.estado IS NOT OLD.estado OR NEW.segundos IS NOT OLD.segundos BEGIN
    INSERT INTO cambios(tabla, fila, operacion, origen, calibre_id) VALUES ('progreso', NEW.id, 'cambio', NEW.origen, NEW.calibre_id);
END;
"""


# --------------------------------------------------------------------------------------------------- dónde vive y quién la abre
def ruta_base() -> Path:
    """`LECTURA_DB` si viene en el entorno; si no, `$XDG_DATA_HOME/biblioteca/lectura.sqlite` (datos del usuario: lo
    hecho solo en Yachay o en la base no está en ninguna otra parte; por eso no va a la caché ni al estado)."""
    if os.environ.get("LECTURA_DB"):
        return Path(os.environ["LECTURA_DB"]).expanduser()
    datos = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return datos / "biblioteca" / "lectura.sqlite"


class RutaProhibida(RuntimeError):
    """Se intentó abrir como base de lectura una base de Calibre o de Zotero."""


def env(nombre: str) -> str:
    """Una ruta del espacio de trabajo: la variable del entorno o, si no está, la de core/env.py (normativa 5.1); «» si
    ninguno la da. Así los adaptadores no escriben la carpeta de inicio del usuario como literal."""
    return _env_core((nombre,))[nombre]


def _env_core(claves=("CALIBRE_DB", "ZOTERO_DB", "BIBLIOTECA_DIR", "ZOTERO_DIR")) -> dict:
    """Las rutas de core/env.py (sin fallar si no está): por omisión CALIBRE_DB, ZOTERO_DB, BIBLIOTECA_DIR y ZOTERO_DIR."""
    salida = {k: os.environ.get(k, "") for k in claves}
    if all(salida.values()):
        return salida
    try:
        d = REPO
        while d != d.parent and not (d / "core" / "env.py").is_file():
            d = d.parent
        import importlib.util
        s = importlib.util.spec_from_file_location("core_env_lectura", d / "core" / "env.py")
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        for k in salida:
            salida[k] = salida[k] or str(getattr(m, k, "") or "")
    except Exception:  # noqa: BLE001 — sin core/env, valen las del entorno
        pass
    return salida


def comprobar_ruta(ruta: Path) -> Path:
    """La ruta, resuelta, si puede ser la base de lectura; `RutaProhibida` si es (o está dentro de) la biblioteca de
    Calibre o la carpeta de Zotero."""
    real = Path(os.path.realpath(ruta))
    e = _env_core()
    for k in ("CALIBRE_DB", "ZOTERO_DB"):
        if e[k] and real == Path(os.path.realpath(e[k])):
            raise RutaProhibida(f"{real} es {k}: solo la escribe la puerta (lib/escribir*)")
    for k in ("BIBLIOTECA_DIR", "ZOTERO_DIR"):
        if e[k]:
            carpeta = Path(os.path.realpath(e[k]))
            if real == carpeta or carpeta in real.parents:
                raise RutaProhibida(f"{real} está dentro de {k} ({carpeta}): la base de lectura vive fuera")
    return real


def conectar(ruta: Path | None = None, escribir: bool = False) -> sqlite3.Connection:
    """La conexión a la base: de solo lectura por omisión (lo que usan la ventana y las consultas); de escritura solo aquí,
    tras comprobar la ruta, y con el esquema creado o al día."""
    ruta = Path(ruta or ruta_base())
    if not escribir:
        c = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True, timeout=ESPERA_MS / 1000)
        c.row_factory = sqlite3.Row
        return c
    real = comprobar_ruta(ruta)
    real.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(real, timeout=ESPERA_MS / 1000)
    preparar(c)
    return c


def preparar(c: sqlite3.Connection) -> None:
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute(f"PRAGMA busy_timeout = {ESPERA_MS}")
    c.executescript(SQL_ESQUEMA)
    columnas = {f[1] for f in c.execute("PRAGMA table_info(anotaciones)")}
    if "posicion" not in columnas:          # esquema 3 sobre una base anterior: la columna, con su valor por omisión
        c.execute("ALTER TABLE anotaciones ADD COLUMN posicion TEXT NOT NULL DEFAULT '{}'")
    if int(c.execute("PRAGMA user_version").fetchone()[0]) < ESQUEMA:
        c.execute(f"PRAGMA user_version = {ESQUEMA}")
    c.commit()


def memoria() -> sqlite3.Connection:
    """Una base en memoria: donde se simula y donde los adaptadores copian lo que leen (nunca un archivo)."""
    return sqlite3.connect(":memory:")


def en_memoria(ruta: Path | None = None) -> sqlite3.Connection:
    """Una copia en memoria de la base (vacía si aún no existe): sobre ella se simula."""
    ruta = Path(ruta or ruta_base())
    m = memoria()
    if ruta.is_file():
        origen = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)
        origen.backup(m)
        origen.close()
    preparar(m)
    return m


def respaldar(ruta: Path | None = None) -> Path | None:
    """Respaldo verificado de la base antes de aplicar (la misma función de la puerta: copia por la API de SQLite,
    quick_check y rotación), en `<raíz de respaldos de la puerta>/lectura/`. Nada que respaldar si aún no existe."""
    ruta = Path(ruta or ruta_base())
    if not ruta.is_file():
        return None
    sys.path.insert(0, str(REPO / "lib"))
    import escribir  # noqa: E402  (lib/escribir.py: respaldar y la raíz de respaldos)
    return escribir.respaldar(ruta, escribir.raiz_respaldos() / "lectura", "lectura", int(os.environ.get("LECTURA_CONSERVAR", 5)))


# --------------------------------------------------------------------------------------------------------------------- fechas
def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso(valor, local: bool = True) -> str:
    """Una fecha de una herramienta como ISO en UTC («2026-03-11T17:31:04Z»): KOReader y Okular dan la hora local sin
    zona (`local=True`); Zotero, UTC sin zona (`local=False`); un número es segundos desde 1970. Vacío si no se entiende."""
    if valor in (None, ""):
        return ""
    try:
        if isinstance(valor, (int, float)):
            d = datetime.fromtimestamp(float(valor), timezone.utc)
        else:
            v = str(valor).strip().replace(" ", "T")
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.astimezone() if local else d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OSError, OverflowError):
        return ""


# ------------------------------------------------------------------------------------------------------ lo que trae un origen
@dataclass
class Lectura:
    """Lo que un adaptador leyó de su herramienta, ya en la forma de la base.

    `anotaciones`: [{origen_id, calibre_id, md5, hoja, pagina, capitulo, texto, rects, color, tipo, intencion, nota, creada,
    modificada, posicion}] (`posicion`, opcional: {pos0, pos1, cita} en un EPUB, ver `posicion_limpia`); `sesiones`: [{origen_id, calibre_id, md5, inicio, fin, segundos, paginas, desde, hasta}]; `progreso`:
    [{calibre_id, md5, hoja, hojas, fraccion, estado, segundos, primera, ultima}]; `libros`: {calibre_id: {md5, titulo,
    autores}}; `fichas_obra`: [{origen_id, calibre_id, ficha, secciones, escritas, total, leida, leida_en,
    version, creada, modificada}] (Yachay; `bajas_fichas`, las que quitó); `alcance`: las claves de libro (`clave_libro`) que se leyeron enteras (lo que falta de ellas queda ausente;
    `None`: nada se marca ausente); `avisos`: lo que no se pudo leer; `bajas`: lo que el origen avisa que quitó. Un registro
    con `uid_base` es una anotación que la base le dio a ese origen (Yachay devuelve su `uid` como `origen_id`)."""
    origen: str
    anotaciones: list[dict] = field(default_factory=list)
    sesiones: list[dict] = field(default_factory=list)
    progreso: list[dict] = field(default_factory=list)
    libros: dict[int, dict] = field(default_factory=dict)
    alcance: set[str] | None = field(default_factory=set)
    avisos: list[str] = field(default_factory=list)
    bajas: list[str] = field(default_factory=list)       # origen_id que el origen dice haber quitado (Yachay)
    fichas_obra: list[dict] = field(default_factory=list)    # la ficha de obra de cada libro (Yachay, §9.13)
    bajas_fichas: list[str] = field(default_factory=list)    # el id de Yachay de las fichas de obra que quitó


def clave_libro(calibre_id, md5: str = "") -> str:
    return f"c{int(calibre_id)}" if calibre_id not in (None, "") else f"m{md5 or ''}"


@dataclass
class Plan:
    """Lo que hizo (o haría, al simular) una conciliación."""
    origen: str
    leidas: int = 0
    altas: list[dict] = field(default_factory=list)       # anotaciones nuevas
    uniones: list[dict] = field(default_factory=list)     # el mismo pasaje que ya estaba (de otro origen)
    cambios: list[dict] = field(default_factory=list)     # cambió en el origen
    ausentes: list[dict] = field(default_factory=list)    # el origen ya no la tiene
    borradas: list[dict] = field(default_factory=list)    # ya no está en ningún origen
    sesiones: dict = field(default_factory=lambda: {"altas": 0, "cambios": 0})
    progreso: dict = field(default_factory=lambda: {"altas": 0, "cambios": 0})
    fichas_obra: dict = field(default_factory=lambda: {"altas": 0, "cambios": 0, "bajas": 0})
    posiciones: int = 0                                   # anotaciones que ganaron su posición en el EPUB
    avisos: list[str] = field(default_factory=list)

    def resumen(self) -> dict:
        return {"origen": self.origen, "leidas": self.leidas, "altas": len(self.altas), "uniones": len(self.uniones),
                "cambios": len(self.cambios), "ausentes": len(self.ausentes), "borradas": len(self.borradas),
                "sesiones": dict(self.sesiones), "progreso": dict(self.progreso), "fichas_obra": dict(self.fichas_obra),
                "posiciones": self.posiciones, "avisos": list(self.avisos)}

    def vacio(self) -> bool:
        return not (self.altas or self.uniones or self.cambios or self.ausentes or self.borradas or self.posiciones
                    or any(self.sesiones.values()) or any(self.progreso.values()) or any(self.fichas_obra.values()))


# --------------------------------------------------------------------------------------------------------------- conciliar
CAMPOS = ("hoja", "pagina", "capitulo", "texto", "rects", "color", "tipo", "intencion", "nota")
UMBRAL_TEXTO = 0.9          # dos textos de la misma hoja (o la vecina) que se parecen así son el mismo pasaje
UMBRAL_TEXTO_SIN_HOJA = 0.95
UMBRAL_SOLAPE = 0.5


XPOINTER = "/body/DocFragment["


def posicion_limpia(p) -> dict:
    """La posición de un pasaje en un libro de flujo, en su forma: `pos0` y `pos1` (xpointers de crengine, como los
    guarda KOReader: «/body/DocFragment[9]/body/p[1]/text().28», fin exclusivo) y `cita` ({exacto, prefijo, sufijo},
    el pasaje con su contexto, que lo vuelve a encontrar si el libro cambió). Lo demás se descarta; {} si no hay nada."""
    if isinstance(p, str):
        try:
            p = json.loads(p or "{}")
        except ValueError:
            p = {}
    p = p if isinstance(p, dict) else {}
    salida = {}
    if all(isinstance(p.get(k), str) and p[k].startswith(XPOINTER) for k in ("pos0", "pos1")):
        salida["pos0"], salida["pos1"] = p["pos0"], p["pos1"]
    cita = p.get("cita") if isinstance(p.get("cita"), dict) else {}
    cita = {k: str(cita.get(k) or "")[:2000 if k == "exacto" else 64] for k in ("exacto", "prefijo", "sufijo") if cita.get(k)}
    if cita.get("exacto"):
        salida["cita"] = cita
    return salida


def _normalizar(r: dict) -> dict:
    """Un registro de un adaptador con todos sus campos y en su forma (texto limpio, rects en JSON, color en hex)."""
    rects = r.get("rects") or []
    salida = {
        "origen_id": str(r["origen_id"]),
        "calibre_id": int(r["calibre_id"]) if r.get("calibre_id") not in (None, "") else None,
        "md5": str(r.get("md5") or ""),
        "hoja": int(r["hoja"]) if r.get("hoja") not in (None, "") else None,
        "pagina": str(r.get("pagina") or ""),
        "capitulo": str(r.get("capitulo") or "").strip(),
        "texto": tx.limpiar(r.get("texto") or ""),
        "rects": json.dumps([[int(x[0]), *(round(float(v), 5) for v in x[1:5])] for x in rects], separators=(",", ":")),
        "color": tx.color(r.get("color") or ""),
        "tipo": str(r.get("tipo") or "resaltado"),
        "intencion": str(r.get("intencion") or ""),
        "nota": str(r.get("nota") or "").strip(),
        "creada": str(r.get("creada") or ""),
        "modificada": str(r.get("modificada") or r.get("creada") or ""),
    }
    salida["uid_base"] = str(r.get("uid_base") or "")
    salida["posicion"] = json.dumps(posicion_limpia(r.get("posicion")), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    salida["texto_normal"] = tx.normal(salida["texto"])
    salida["huella"] = tx.huella(clave_libro(salida["calibre_id"], salida["md5"]), salida["hoja"], salida["texto_normal"],
                                 salida["nota"], json.loads(salida["rects"]))
    salida["huella_origen"] = tx.huella("origen", salida["hoja"], "|".join(str(salida[k]) for k in CAMPOS), salida["modificada"])
    return salida


def _mismo_libro(fila, r: dict) -> bool:
    if r["calibre_id"] is not None and fila["calibre_id"] is not None:
        return int(fila["calibre_id"]) == r["calibre_id"]
    return bool(r["md5"]) and fila["md5"] == r["md5"]


def _puntaje(fila, r: dict) -> float:
    """Cuánto se parece un registro nuevo a una anotación ya guardada (0: nada; ≥ 1: el mismo pasaje)."""
    if fila["huella"] == r["huella"]:
        return 2.0
    h1, h2 = fila["hoja"], r["hoja"]
    if h1 is not None and h2 is not None and abs(int(h1) - h2) > 1:
        return 0.0
    if fila["texto_normal"] and r["texto_normal"]:
        p = tx.parecido(fila["texto_normal"], r["texto_normal"])
        umbral = UMBRAL_TEXTO if (h1 is not None and h2 is not None) else UMBRAL_TEXTO_SIN_HOJA
        if p >= umbral:
            return 1.0 + p
    if h1 is not None and h1 == h2:
        s = tx.solape(json.loads(fila["rects"] or "[]"), json.loads(r["rects"]))
        if s >= UMBRAL_SOLAPE:
            return 1.0 + s
        if not fila["texto_normal"] and not r["texto_normal"] and fila["nota"] and tx.normal(fila["nota"]) == tx.normal(r["nota"]):
            return 1.5
    return 0.0


def _candidata(c: sqlite3.Connection, origen: str, r: dict):
    """La anotación de otro origen que es el mismo pasaje que `r`, o None. Nunca une dos de un mismo origen: si una
    herramienta tiene dos subrayados iguales, son dos."""
    if r["calibre_id"] is not None:
        filas = c.execute("SELECT * FROM anotaciones WHERE (calibre_id = ? OR (calibre_id IS NULL AND md5 = ? AND md5 != '')) "
                          "AND id NOT IN (SELECT anotacion_id FROM presencias WHERE origen = ?)",
                          (r["calibre_id"], r["md5"], origen)).fetchall()
    elif r["md5"]:
        filas = c.execute("SELECT * FROM anotaciones WHERE md5 = ? AND id NOT IN (SELECT anotacion_id FROM presencias WHERE origen = ?)",
                          (r["md5"], origen)).fetchall()
    else:
        return None
    mejor, puntos = None, 0.0
    for f in filas:
        if not _mismo_libro(f, r):
            continue
        p = _puntaje(f, r)
        if p > puntos:
            mejor, puntos = f, p
    return mejor if puntos >= 1.0 else None


def _vista(fila_o_registro, **extra) -> dict:
    d = dict(fila_o_registro)
    salida = {k: d.get(k) for k in ("uid", "calibre_id", "hoja", "pagina", "texto", "nota", "color") if k in d}
    salida["texto"] = (salida.get("texto") or "")[:120]
    salida.update(extra)
    return salida


def _anotacion_de(c, anotacion_id: int):
    return c.execute("SELECT * FROM anotaciones WHERE id = ?", (anotacion_id,)).fetchone()


def _actualizar(c, fila, r: dict, origen: str) -> bool:
    """Lleva a la anotación lo que cambió en el origen, si el origen es más nuevo (o la anotación no tiene fecha). Un
    campo vacío en el origen no borra lo que la base ya sabe (como en Calibre ⇄ Zotero)."""
    if fila["modificada"] and r["modificada"] and r["modificada"] < fila["modificada"]:
        return False
    nuevos = {}
    for k in ("texto", "rects", "color", "tipo", "intencion", "pagina", "capitulo", "posicion"):
        vacio = r[k] in ("", "[]", "{}")
        if not vacio and r[k] != fila[k]:
            nuevos[k] = r[k]
    if r["nota"] != fila["nota"]:                  # la nota sí se puede vaciar: borrarla es una edición
        nuevos["nota"] = r["nota"]
    if r["hoja"] is not None and fila["hoja"] is None:
        nuevos["hoja"] = r["hoja"]
    if r["calibre_id"] is not None and fila["calibre_id"] is None:
        nuevos["calibre_id"] = r["calibre_id"]
    if not nuevos:
        return False
    if "texto" in nuevos:
        nuevos["texto_normal"] = r["texto_normal"]
    nuevos.update(modificada=r["modificada"] or ahora(), origen_ultimo=origen)
    asignar = ", ".join(f"{k} = ?" for k in nuevos)
    c.execute(f"UPDATE anotaciones SET {asignar} WHERE id = ?", (*nuevos.values(), fila["id"]))
    return True


def _rellenar(c, fila, r: dict, origen: str) -> None:
    """Al unir el mismo pasaje de otro origen: solo se completa lo que la anotación no tenía (el texto que Okular no
    guarda, la hoja que un EPUB no trae, la nota, la intención de Yachay); nada de lo que ya tiene se pisa."""
    nuevos = {}
    for k in ("texto", "pagina", "capitulo", "color", "intencion", "nota"):
        if not fila[k] and r[k]:
            nuevos[k] = r[k]
    if (fila["rects"] in ("", "[]")) and r["rects"] != "[]":
        nuevos["rects"] = r["rects"]
    if fila["posicion"] in ("", "{}") and r["posicion"] != "{}":
        nuevos["posicion"] = r["posicion"]
    for k in ("hoja", "calibre_id"):
        if fila[k] is None and r[k] is not None:
            nuevos[k] = r[k]
    if not fila["md5"] and r["md5"]:
        nuevos["md5"] = r["md5"]
    if "texto" in nuevos:
        nuevos["texto_normal"] = r["texto_normal"]
    if nuevos:
        nuevos["origen_ultimo"] = origen
        c.execute(f"UPDATE anotaciones SET {', '.join(f'{k} = ?' for k in nuevos)} WHERE id = ?", (*nuevos.values(), fila["id"]))


def _ausente(c, presencia_id: int, anotacion_id: int, origen: str, momento: str, plan: Plan) -> None:
    """Una presencia que el origen ya no tiene; si era la última, la anotación queda borrada (en la base: no se borra en
    las otras herramientas)."""
    c.execute("UPDATE presencias SET ausente = ? WHERE id = ?", (momento, presencia_id))
    fila = _anotacion_de(c, anotacion_id)
    plan.ausentes.append(_vista(fila))
    quedan = c.execute("SELECT count(*) FROM presencias WHERE anotacion_id = ? AND ausente IS NULL", (anotacion_id,)).fetchone()[0]
    if not quedan and fila["borrada"] is None:
        c.execute("UPDATE anotaciones SET borrada = ?, origen_ultimo = ? WHERE id = ?", (momento, origen, anotacion_id))
        plan.borradas.append(_vista(fila))


def _conciliar(c: sqlite3.Connection, lectura: Lectura, plan: Plan) -> None:
    origen, momento = lectura.origen, ahora()
    vistos: set[int] = set()
    for crudo in lectura.anotaciones:
        r = _normalizar(crudo)
        plan.leidas += 1
        p = c.execute("SELECT * FROM presencias WHERE origen = ? AND origen_id = ?", (origen, r["origen_id"])).fetchone()
        if p is not None:
            vistos.add(p["id"])
            fila = _anotacion_de(c, p["anotacion_id"])
            if p["huella_origen"] and p["huella_origen"] != r["huella_origen"] and _actualizar(c, fila, r, origen):
                plan.cambios.append(_vista(r, uid=fila["uid"]))
            elif fila["posicion"] in ("", "{}") and r["posicion"] != "{}":
                # lo ya visto antes del esquema 3 (los EPUB de KOReader) gana su posición sin contar como edición
                c.execute("UPDATE anotaciones SET posicion = ? WHERE id = ?", (r["posicion"], fila["id"]))
                plan.posiciones += 1
            if fila["borrada"] is not None:
                c.execute("UPDATE anotaciones SET borrada = NULL, origen_ultimo = ? WHERE id = ?", (origen, fila["id"]))
            c.execute("UPDATE presencias SET huella_origen = ?, visto = ?, ausente = NULL WHERE id = ?",
                      (r["huella_origen"], momento, p["id"]))
            continue
        fila = c.execute("SELECT * FROM anotaciones WHERE uid = ?", (r["uid_base"],)).fetchone() if r["uid_base"] else None
        fila = fila if fila is not None else _candidata(c, origen, r)
        if fila is not None:
            _rellenar(c, fila, r, origen)
            if fila["borrada"] is not None:
                c.execute("UPDATE anotaciones SET borrada = NULL, origen_ultimo = ? WHERE id = ?", (origen, fila["id"]))
            anotacion_id, uid = fila["id"], fila["uid"]
            plan.uniones.append(_vista(r, uid=uid, con=[x["origen"] for x in c.execute(
                "SELECT origen FROM presencias WHERE anotacion_id = ?", (anotacion_id,))]))
        else:
            uid = secrets.token_hex(8)
            cur = c.execute(
                "INSERT INTO anotaciones(uid, calibre_id, md5, hoja, pagina, capitulo, texto, texto_normal, rects, color, tipo, "
                "intencion, nota, creada, modificada, huella, origen_ultimo, posicion) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uid, r["calibre_id"], r["md5"], r["hoja"], r["pagina"], r["capitulo"], r["texto"], r["texto_normal"], r["rects"],
                 r["color"], r["tipo"], r["intencion"], r["nota"], r["creada"], r["modificada"], r["huella"], origen, r["posicion"]))
            anotacion_id = cur.lastrowid
            plan.altas.append(_vista(r, uid=uid))
        cur = c.execute("INSERT INTO presencias(anotacion_id, origen, origen_id, huella_origen, visto) VALUES (?,?,?,?,?)",
                        (anotacion_id, origen, r["origen_id"], r["huella_origen"], momento))
        vistos.add(cur.lastrowid)

    # lo que el origen avisó que quitó, y lo que leyó entero y ya no trae
    for origen_id in lectura.bajas:
        p = c.execute("SELECT id, anotacion_id FROM presencias WHERE origen = ? AND origen_id = ? AND ausente IS NULL",
                      (origen, str(origen_id))).fetchone()
        if p is not None:
            _ausente(c, p["id"], p["anotacion_id"], origen, momento, plan)
    if lectura.alcance:
        for p in c.execute("SELECT p.id, p.anotacion_id, a.calibre_id, a.md5 FROM presencias p JOIN anotaciones a ON a.id = p.anotacion_id "
                           "WHERE p.origen = ? AND p.ausente IS NULL", (origen,)).fetchall():
            if p["id"] in vistos or clave_libro(p["calibre_id"], p["md5"]) not in lectura.alcance:
                continue
            _ausente(c, p["id"], p["anotacion_id"], origen, momento, plan)

    for s in lectura.sesiones:
        previa = c.execute("SELECT id, segundos, fin, paginas FROM sesiones WHERE origen = ? AND origen_id = ?",
                           (origen, str(s["origen_id"]))).fetchone()
        valores = (s.get("calibre_id"), s.get("md5") or "", int(s["inicio"]), int(s["fin"]), int(s["segundos"]),
                   int(s.get("paginas") or 0), s.get("desde"), s.get("hasta"))
        if previa is None:
            c.execute("INSERT INTO sesiones(calibre_id, md5, inicio, fin, segundos, paginas, desde, hasta, origen, origen_id) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)", (*valores, origen, str(s["origen_id"])))
            plan.sesiones["altas"] += 1
        elif (previa["segundos"], previa["fin"], previa["paginas"]) != (valores[4], valores[3], valores[5]):
            c.execute("UPDATE sesiones SET calibre_id = ?, md5 = ?, inicio = ?, fin = ?, segundos = ?, paginas = ?, desde = ?, hasta = ? "
                      "WHERE id = ?", (*valores, previa["id"]))
            plan.sesiones["cambios"] += 1

    for g in lectura.progreso:
        clave = clave_libro(g.get("calibre_id"), g.get("md5") or "")
        valores = {"calibre_id": g.get("calibre_id"), "md5": g.get("md5") or "", "hoja": g.get("hoja"), "hojas": g.get("hojas"),
                   "fraccion": round(float(g["fraccion"]), 4) if g.get("fraccion") is not None else None,
                   "estado": g.get("estado") or "", "segundos": int(g.get("segundos") or 0),
                   "primera": g.get("primera") or "", "ultima": g.get("ultima") or ""}
        previa = c.execute("SELECT * FROM progreso WHERE origen = ? AND clave = ?", (origen, clave)).fetchone()
        if previa is None:
            c.execute(f"INSERT INTO progreso(origen, clave, {', '.join(valores)}) VALUES (?, ?, {', '.join('?' * len(valores))})",
                      (origen, clave, *valores.values()))
            plan.progreso["altas"] += 1
        elif any(previa[k] != v for k, v in valores.items()):
            c.execute(f"UPDATE progreso SET {', '.join(f'{k} = ?' for k in valores)} WHERE id = ?", (*valores.values(), previa["id"]))
            plan.progreso["cambios"] += 1

    _conciliar_fichas(c, lectura, plan, momento)

    for calibre_id, d in lectura.libros.items():
        c.execute("INSERT INTO libros(calibre_id, md5, titulo, autores, actualizado) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(calibre_id) DO UPDATE SET md5 = CASE WHEN excluded.md5 != '' THEN excluded.md5 ELSE libros.md5 END, "
                  "titulo = CASE WHEN excluded.titulo != '' THEN excluded.titulo ELSE libros.titulo END, "
                  "autores = CASE WHEN excluded.autores != '' THEN excluded.autores ELSE libros.autores END, actualizado = excluded.actualizado",
                  (int(calibre_id), d.get("md5") or "", d.get("titulo") or "", d.get("autores") or "", momento))
        if d.get("md5"):                       # lo que solo traía el MD5 ya sabe su libro
            c.execute("UPDATE anotaciones SET calibre_id = ?, origen_ultimo = ? WHERE calibre_id IS NULL AND md5 = ?",
                      (int(calibre_id), origen, d["md5"]))
            c.execute("UPDATE sesiones SET calibre_id = ? WHERE calibre_id IS NULL AND md5 = ?", (int(calibre_id), d["md5"]))
    plan.avisos += lectura.avisos
    c.execute("INSERT INTO corridas(momento, origen, resumen) VALUES (?,?,?)", (momento, origen, json.dumps(plan.resumen(), ensure_ascii=False)))


# ----------------------------------------------------------------------------------------- la ficha de obra (§9.13)
CAMPOS_OBRA = ("pregunta", "metodo", "datos", "hallazgo", "limites", "uso")
# los títulos de las seis en la norma de fichas (`GUIAS_OBRA` de `lib/fichar.py`, los mismos que Yachay da en `secciones`)
TITULOS_OBRA = {"pregunta": "Pregunta", "metodo": "Método", "datos": "Datos", "hallazgo": "Hallazgo", "limites": "Límites",
                "uso": "Uso que le daré"}
SIGNOS = ("", "positivo", "negativo", "nulo", "mixto", "no_aplica")


def ficha_limpia(f: dict | None) -> dict:
    """La ficha de obra en su forma: las seis respuestas como texto, los temas como lista y el signo en su vocabulario
    (el de `lectura_obra.limpiar_ficha` de Yachay; lo que no lo es queda vacío)."""
    f = f if isinstance(f, dict) else {}
    salida = {k: str(f.get(k) or "").strip() for k in CAMPOS_OBRA}
    temas = f.get("temas") or []
    if isinstance(temas, str):
        temas = [x for x in (t.strip() for t in temas.replace(";", ",").split(",")) if x]
    salida["temas"] = [str(x).strip() for x in temas if str(x).strip()]
    signo = str(f.get("signo") or "")
    salida["signo"] = signo if signo in SIGNOS else ""
    return salida


def _registro_ficha(d: dict) -> dict:
    ficha = ficha_limpia(d.get("ficha"))
    escritas = d.get("escritas")
    return {"origen_id": str(d.get("origen_id") or d.get("id") or ""), "calibre_id": int(d["calibre_id"]),
            "ficha": json.dumps(ficha, ensure_ascii=False, sort_keys=True),
            "secciones": json.dumps(d.get("secciones") or {TITULOS_OBRA[k]: ficha[k] for k in CAMPOS_OBRA},
                                    ensure_ascii=False, sort_keys=True),
            "escritas": int(escritas if escritas is not None else sum(1 for k in CAMPOS_OBRA if ficha[k])),
            "total": int(d.get("total") or len(CAMPOS_OBRA)), "leida": 1 if d.get("leida") or d.get("leida_en") else 0,
            "leida_en": str(d.get("leida_en") or ""), "version": int(d.get("version") or 0),
            "creada": str(d.get("creada") or d.get("creado_en") or ""),
            "modificada": str(d.get("modificada") or d.get("actualizado_en") or "")}


def _conciliar_fichas(c: sqlite3.Connection, lectura: Lectura, plan: Plan, momento: str) -> None:
    """La ficha de obra de cada libro: se guarda tal como la dio el origen si su versión es otra (o es nueva); una baja la
    marca. Una por libro y origen: Yachay da a cada persona las suyas, una por `calibre_id`."""
    for crudo in lectura.fichas_obra:
        if crudo.get("calibre_id") in (None, ""):
            continue
        r = _registro_ficha(crudo)
        previa = c.execute("SELECT * FROM fichas_obra WHERE origen = ? AND calibre_id = ?", (lectura.origen, r["calibre_id"])).fetchone()
        if previa is None:
            c.execute(f"INSERT INTO fichas_obra(origen, visto, {', '.join(r)}) VALUES (?, ?, {', '.join('?' * len(r))})",
                      (lectura.origen, momento, *r.values()))
            plan.fichas_obra["altas"] += 1
            continue
        if previa["baja"] is None and all(previa[k] == v for k, v in r.items()):
            c.execute("UPDATE fichas_obra SET visto = ? WHERE id = ?", (momento, previa["id"]))
            continue
        c.execute(f"UPDATE fichas_obra SET {', '.join(f'{k} = ?' for k in r)}, visto = ?, baja = NULL WHERE id = ?",
                  (*r.values(), momento, previa["id"]))
        plan.fichas_obra["cambios"] += 1
    for origen_id in lectura.bajas_fichas:
        f = c.execute("SELECT id FROM fichas_obra WHERE origen = ? AND origen_id = ? AND baja IS NULL",
                      (lectura.origen, str(origen_id))).fetchone()
        if f is not None:
            c.execute("UPDATE fichas_obra SET baja = ? WHERE id = ?", (momento, f["id"]))
            plan.fichas_obra["bajas"] += 1


def ficha_obra_publica(f) -> dict:
    """Una fila de `fichas_obra` como la leen la ventana y la CLI."""
    d = {k: f[k] for k in f.keys() if k not in ("ficha", "secciones")}
    d["ficha"] = ficha_limpia(json.loads(f["ficha"] or "{}"))
    d["secciones"] = json.loads(f["secciones"] or "{}")
    d["leida"] = bool(f["leida"])
    return d


def ficha_obra(calibre_id: int, origen: str = "yachay", ruta: Path | None = None) -> dict | None:
    """La ficha de obra del libro en la base (solo lee); None si no hay o si el origen la quitó."""
    with lector(ruta) as c:
        if c is None:
            return None
        f = c.execute("SELECT * FROM fichas_obra WHERE origen = ? AND calibre_id = ? AND baja IS NULL",
                      (origen, int(calibre_id))).fetchone()
        return ficha_obra_publica(f) if f is not None else None


def guardar_ficha_obra(registro: dict, origen: str = "yachay", aplicar: bool = False, ruta: Path | None = None) -> Plan:
    """Lo que el origen respondió al escribirle la ficha (la vuelta) o lo que la persona eligió quedarse de él (un 409), en
    la base, para que muestre la versión nueva sin esperar a la próxima lectura. Es la conciliación de una sola ficha:
    simula sin `aplicar`; con él, tras el respaldo verificado. El `origen_id` que el origen no devuelva se conserva."""
    previa = ficha_obra(int(registro["calibre_id"]), origen, ruta)
    if previa and not str(registro.get("origen_id") or registro.get("id") or ""):
        registro = {**registro, "origen_id": previa["origen_id"]}
    return importar([Lectura(origen, alcance=None, fichas_obra=[registro])], aplicar=aplicar, ruta=ruta)[0]


def importar(lecturas: list[Lectura], aplicar: bool = False, ruta: Path | None = None) -> list[Plan]:
    """Concilia las lecturas (en orden) con la base. Sin `aplicar`, sobre una copia en memoria: nada se escribe."""
    ruta = Path(ruta or ruta_base())
    planes = []
    if aplicar:
        respaldar(ruta)
        c = conectar(ruta, escribir=True)
    else:
        c = en_memoria(ruta)
    try:
        for lectura in lecturas:
            plan = Plan(lectura.origen)
            with c:
                _conciliar(c, lectura, plan)
            planes.append(plan)
    finally:
        c.close()
    return planes


# ---------------------------------------------------------------------------------------------- lo que se escribió en otro lado
def registrar_presencias(nuevas: list[dict], origen: str, aplicar: bool = False, ruta: Path | None = None) -> int:
    """Tras escribir anotaciones de la base en una herramienta (exportar), apunta dónde quedaron: [{uid, origen_id}].
    Así la próxima lectura de esa herramienta las reconoce como la misma anotación y no las duplica."""
    if not nuevas:
        return 0
    if aplicar:
        respaldar(ruta)
    c = conectar(ruta, escribir=True) if aplicar else en_memoria(ruta)
    n = 0
    try:
        with c:
            for x in nuevas:
                fila = c.execute("SELECT id FROM anotaciones WHERE uid = ?", (x["uid"],)).fetchone()
                if fila is None:
                    continue
                c.execute("INSERT OR IGNORE INTO presencias(anotacion_id, origen, origen_id, visto) VALUES (?,?,?,?)",
                          (fila["id"], origen, str(x["origen_id"]), ahora()))
                n += 1
    finally:
        c.close()
    return n


# ------------------------------------------------------------------------------------------------------- la cola de cambios
def cambios_desde(seq: int = 0, limite: int = 500, ruta: Path | None = None) -> dict:
    """Los cambios posteriores a `seq` con el estado actual de cada fila: {cambios: [...], hasta: último seq}. Solo lee."""
    ruta = Path(ruta or ruta_base())
    if not ruta.is_file():
        return {"cambios": [], "hasta": int(seq)}
    with conectar(ruta) as c:
        filas = c.execute("SELECT * FROM cambios WHERE seq > ? ORDER BY seq LIMIT ?", (int(seq), int(limite))).fetchall()
        salida = []
        for f in filas:
            d = dict(f)
            if f["tabla"] in ("anotaciones", "presencias") and f["uid"]:
                a = c.execute("SELECT * FROM anotaciones WHERE uid = ?", (f["uid"],)).fetchone()
                if a is not None:
                    d["anotacion"] = anotacion_publica(c, a)
            elif f["tabla"] in ("sesiones", "progreso"):
                fila = c.execute(f"SELECT * FROM {f['tabla']} WHERE id = ?", (f["fila"],)).fetchone()
                d["datos"] = dict(fila) if fila is not None else None
            elif f["tabla"] == "fichas_obra":
                fila = c.execute("SELECT * FROM fichas_obra WHERE id = ?", (f["fila"],)).fetchone()
                d["datos"] = ficha_obra_publica(fila) if fila is not None else None
            salida.append(d)
    return {"cambios": salida, "hasta": salida[-1]["seq"] if salida else int(seq)}


def anotacion_publica(c, a) -> dict:
    """Una anotación como la ven los consumidores: sus campos, sus rectángulos como lista y dónde vive."""
    d = {k: a[k] for k in a.keys() if k not in ("id", "texto_normal")}
    d["rects"] = json.loads(a["rects"] or "[]")
    d["posicion"] = posicion_limpia(a["posicion"]) if "posicion" in a.keys() else {}
    d["origenes"] = [{"origen": p["origen"], "origen_id": p["origen_id"], "ausente": p["ausente"]}
                     for p in c.execute("SELECT origen, origen_id, ausente FROM presencias WHERE anotacion_id = ? ORDER BY id", (a["id"],))]
    return d


def leer_cursor(consumidor: str, ruta: Path | None = None):
    """El cursor de un consumidor: el `seq` de la cola que ya leyó (entero), o el cursor que otro sistema le dio (Yachay)."""
    ruta = Path(ruta or ruta_base())
    if not ruta.is_file():
        return 0
    with conectar(ruta) as c:
        f = c.execute("SELECT seq FROM cursores WHERE consumidor = ?", (consumidor,)).fetchone()
    if not f:
        return 0
    v = f["seq"]
    return int(v) if str(v).lstrip("-").isdigit() else v


def guardar_cursor(consumidor: str, seq, ruta: Path | None = None) -> None:
    c = conectar(ruta, escribir=True)
    try:
        with c:
            c.execute("INSERT INTO cursores(consumidor, seq, momento) VALUES (?,?,?) ON CONFLICT(consumidor) "
                      "DO UPDATE SET seq = excluded.seq, momento = excluded.momento",
                      (consumidor, int(seq) if str(seq).lstrip("-").isdigit() else str(seq), ahora()))
    finally:
        c.close()


@contextmanager
def lector(ruta: Path | None = None):
    """Conexión de solo lectura (None si la base aún no existe): lo que usan las consultas y la ventana."""
    ruta = Path(ruta or ruta_base())
    if not ruta.is_file():
        yield None
        return
    c = conectar(ruta)
    try:
        yield c
    finally:
        c.close()
