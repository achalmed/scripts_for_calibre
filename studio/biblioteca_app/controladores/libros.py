"""biblioteca_app/controladores/libros.py — el catálogo bibliográfico (reingeniería B2–B8, `docs/reingenieria.md`): los
libros de Calibre con sus metadatos editoriales y su lectura en KOReader (`servicios/catalogo.py`, en solo lectura) unidos
al índice de `lib/indice.py` (claves de Zotero y para citar, fichas, nota); la búsqueda avanzada, los filtros por
colección, autor, década y tipo, el orden y la cuadrícula o la lista; las portadas en miniatura (`gui_comun.miniaturas.ProveedorMiniaturas`);
la ficha editorial del libro actual y lo que se hace con él (abrir el documento con su aplicación, mostrarlo en Dolphin,
abrir en Calibre y en Zotero, la nota, copiar la clave); y las bandejas de trabajo. El enlace `biblioteca-studio://libro/<id>`
de los complementos lo abre. La ventana no escribe: lo que cambia la biblioteca es una operación (la CLI de su suite).
2026-11-22 (pedido del autor): el orden por colección e índice de serie, agrupar la lista con títulos (colección, autor,
tipo, década), el orden de cada grupo de filtros (más libros, nombre, recientes) y, además de metadata.db, el vigilante
mira el índice (lo reescribe el timer cada 30 min) y `zotero.sqlite`: si Zotero cambió, el índice se rehace solo (solo lee las
bases y escribe el JSON); lo que va de Zotero a Calibre sigue siendo la operación «Zotero ⇄ Calibre», por la puerta."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from gui_comun.modelos import ModeloFiltrado, ModeloLista
from gui_comun.qt import QFileSystemWatcher, QObject, QSettings, QTimer, Property, Signal, Slot

from biblioteca_app.servicios import catalogo as cat
from biblioteca_app.servicios import datos

ROLES = ("id", "titulo", "autores", "año", "serie", "tipo", "portada", "fuente", "zotero", "clave", "koProgreso", "koEstado",
         "fichas", "etiquetas", "seccion", "otro", "detalle", "nivel", "grupo", "paginas")
FILTROS = (("coleccion", "Colección"), ("autor", "Autor"), ("decada", "Año"), ("tipo", "Tipo"))
TEXTO_KO = {"reading": "leyendo", "complete": "terminado", "abandoned": "abandonado"}


def _hex(nombre: str) -> str:
    return "_hex_-" + nombre.encode("utf-8").hex()


def _bytes(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024
    return ""


def _serie(l: dict) -> str:
    if not l["serie"]:
        return ""
    i = l["serie_indice"]
    return f"{l['serie']} [{i:g}]" if i is not None else l["serie"]


def fila(l: dict, seccion: str = "", grupo: str = "") -> dict:
    """Una tarjeta del catálogo (o de una bandeja); `grupo`, el título de su grupo en la lista agrupada."""
    return {"id": l["id"], "titulo": l["titulo"], "autores": " · ".join(l["autores"]) or "sin autor", "año": str(l["año"] or ""),
            "serie": _serie(l), "tipo": l["tipo"], "portada": bool(l["portada"]), "fuente": f"image://portadas/{l['id']}" if l["portada"] else "",
            "zotero": bool(l["zotero_key"]), "clave": l["clave"], "koProgreso": -1.0 if l["ko_progreso"] is None else float(l["ko_progreso"]),
            "koEstado": l["ko_estado"], "fichas": len(l["fichas"]), "etiquetas": ", ".join(l["etiquetas"]), "seccion": seccion,
            "otro": False, "detalle": "", "nivel": "", "grupo": grupo, "paginas": l.get("paginas") or 0}


ESPERA_DB_MS = 1500
ESPERA_ZOTERO_MS = 20_000              # Zotero escribe a ráfagas mientras se edita: el índice se rehace cuando se calma
ENTRE_INDICES_S = 120                  # y no más de una vez cada dos minutos (Zotero también escribe al sincronizar)


def firma(ruta: Path) -> tuple:
    """(mtime en ns, tamaño) de un archivo, y los de su diario de SQLite si existen; () si no está."""
    partes = []
    for r in (ruta, ruta.with_name(ruta.name + "-wal"), ruta.with_name(ruta.name + "-journal")):
        try:
            st = os.stat(r)
        except OSError:
            continue
        partes.append((r.name, st.st_mtime_ns, st.st_size))
    return tuple(partes)



def texto_ids(d: dict) -> str:
    """«DOI resuelto en Crossref (2026-11-18)» o «DOI que no existe»: lo que el índice dice del identificador del libro (C12.5)."""
    v = d.get("verificacion_ids") or {}
    partes = []
    for tipo, nombre in (("doi", "DOI"), ("isbn", "ISBN")):
        e = v.get(tipo)
        if not d.get(tipo) or not e or e == "sin_identificador":
            continue
        partes.append({"existe": f"{nombre} resuelto", "no_existe": f"{nombre} que no existe", "discrepa": f"{nombre} de otro título: revísalo",
                       "mal_formado": f"{nombre} mal formado", "no_hallado": f"{nombre} no hallado en Open Library",
                       "sin_consultar": f"{nombre} sin consultar"}.get(e, e))
    return (" · ".join(partes) + (f" ({v['fecha']})" if v.get("fecha") else "")) if partes else ""

class Libros(QObject):
    cambiado = Signal()                 # el catálogo, las facetas, las bandejas y los contadores
    filtroCambiado = Signal()           # la búsqueda, los filtros, el orden o la forma (cuadrícula · lista)
    actualCambiado = Signal()           # el libro de la ficha
    bandejaCambiada = Signal()
    facetasCambiadas = Signal()         # las cuentas de los filtros (cambian con la búsqueda)
    vigilarCambiado = Signal()
    seleccionar = Signal(int)           # QML: lleva la cuadrícula a ese índice visible
    aviso = Signal(str, str)
    usosCambiados = Signal()            # los escritos que usan el libro de la ficha (decisiones §9.1)
    _usosListos = Signal(str, "QVariantList")
    _leido = Signal(object)             # la relectura en segundo plano terminó (llega al hilo de la ventana)
    _indiceListo = Signal(int, str)     # el índice rehecho en un hilo (código, última línea)
    sincroniaCambiada = Signal()

    def __init__(self, espacio, consola, env, ruta_indice: Path | None = None, escritorio=None, repo: Path = datos.REPO,
                 portadas=None, parent=None):
        super().__init__(parent)
        self.espacio, self.consola, self.env, self.escritorio, self.repo = espacio, consola, env, escritorio, Path(repo)
        self.portadas = portadas
        self._ruta_indice = ruta_indice
        self._s = QSettings()
        self._indice: dict = {"libros": {}}
        self._libros: list[dict] = []
        self._por_id: dict[str, dict] = {}
        self._planos: dict[str, dict] = {}      # los campos de la búsqueda ya normalizados, por id (catalogo.planos)
        self._coinciden: set[str] | None = None  # los ids que cumplen la búsqueda; None = sin búsqueda
        self._leyendo = False                   # una relectura en segundo plano en curso
        self._releer_otra = False               # y otra pedida mientras tanto
        self._leido.connect(self._aplicar)
        self._inmutable = False
        self._error = ""
        self._usos: list = []
        self._usos_de = ""
        self._usosListos.connect(self._poner_usos)
        self._busqueda = ""
        self._terminos: list = []
        self._filtros = {k: "" for k, _t in FILTROS}
        self._orden = str(self._s.value("catalogo/orden", "titulo") or "titulo")
        self._agrupar = str(self._s.value("catalogo/agrupar", "") or "")
        if self._agrupar not in dict(cat.AGRUPAR):
            self._agrupar = ""
        try:
            self._orden_facetas = {k: v for k, v in json.loads(str(self._s.value("catalogo/orden_facetas", "{}") or "{}")).items()
                                   if v in dict(cat.ORDENES_FACETA)}
        except (ValueError, AttributeError):
            self._orden_facetas = {}
        self._lista = str(self._s.value("catalogo/forma", "cuadricula") or "cuadricula") == "lista"
        self._facetas: dict = {}
        self._bandejas: dict = {}
        self._bandeja = ""
        self._entrada: list[dict] = []
        self._fichas_meta: list[dict] = []
        self._actual: dict = {}
        self._filas = ModeloLista(ROLES, parent=self)
        self._modelo = ModeloFiltrado(self._filas, parent=self)
        self._modelo.aceptar_con(self._acepta)
        self._bandeja_filas = ModeloLista(ROLES, parent=self)
        # el vigilante de metadata.db (solo mira: la firma del archivo; releer es leer en solo lectura, como F6)
        self._db: Path | None = None
        self._firma_db: tuple = ()
        self._vigilar = str(self._s.value("catalogo/vigilar", "true")).lower() in ("true", "1")
        self._vigilante = QFileSystemWatcher(self)
        self._vigilante.fileChanged.connect(self._db_cambio)
        self._vigilante.directoryChanged.connect(self._db_cambio)
        self._espera_db = QTimer(self)
        self._espera_db.setSingleShot(True)
        self._espera_db.setInterval(ESPERA_DB_MS)
        self._espera_db.timeout.connect(self._releer_si_cambio)
        # Zotero (solo se mira la firma de zotero.sqlite): si cambió después del índice, el índice se rehace en un hilo
        self._zotero: Path | None = None
        self._firma_zotero: tuple = ()
        self._rehaciendo = False
        self._ultimo_indice = ""
        self._rehecho_en = float("-inf")
        self._espera_zotero = QTimer(self)
        self._espera_zotero.setSingleShot(True)
        self._espera_zotero.setInterval(ESPERA_ZOTERO_MS)
        self._espera_zotero.timeout.connect(self._zotero_calmo)
        self._indiceListo.connect(self._indice_listo)
        self.recargar()

    modelo = Property(QObject, lambda self: self._modelo, constant=True)
    bandejaModelo = Property(QObject, lambda self: self._bandeja_filas, constant=True)

    # ------------------------------------------------------------------ leer
    @Slot()
    def recargar(self) -> None:
        """Relee el índice y Calibre (en solo lectura), la entrada y las fichas: tras «Actualizar el índice», F6 o una aplicación."""
        self._aplicar(self._leer())

    def recargar_en_segundo_plano(self) -> None:
        """La misma relectura, fuera del hilo de la ventana (la pide el vigilante de metadata.db: Calibre o la
        sincronización de KOReader escriben a cualquier hora, y releer 4775 libros y la zona de entrada toma 1 a 2 s)."""
        if self._leyendo:
            self._releer_otra = True
            return
        import threading
        self._leyendo, self._releer_otra = True, False

        def trabajo():
            try:
                r = self._leer()
            except Exception as e:                  # noqa: BLE001  se informa en la ventana, no tumba el hilo
                r = {"fallo": str(e)}
            self._leido.emit(r)
        threading.Thread(target=trabajo, name="catalogo", daemon=True).start()

    def _leer(self) -> dict:
        """Todo lo que la relectura necesita, sin tocar la ventana (corre también en un hilo)."""
        indice = datos.leer_indice(self._ruta_indice)
        biblioteca = Path(indice.get("biblioteca") or self.env.BIBLIOTECA_DIR)
        db = Path(getattr(self.env, "CALIBRE_DB", "") or biblioteca / "metadata.db")
        r = {"indice": indice, "db": db, "firma": firma(db), "error": ""}
        try:
            leido = cat.leer(db, indice, biblioteca)
            r["libros"], r["inmutable"] = leido["libros"], leido["inmutable"]
        except Exception as e:      # noqa: BLE001  una base que no se puede leer no tumba la ventana
            r["libros"], r["inmutable"], r["error"] = [], False, f"No se pudo leer la biblioteca de Calibre: {e}"
        r["planos"] = {l["id"]: cat.planos(l) for l in r["libros"]}
        try:
            r["entrada"] = datos.entrada(self.repo, Path(self.env.DOCS_ROOT))
            r["fichas"] = datos.fichas(self.repo)
        except OSError:
            r["entrada"], r["fichas"] = [], []
        r["bandejas"] = cat.bandejas(r["libros"], r["entrada"], r["fichas"])
        return r

    def _aplicar(self, r: dict) -> None:
        """Pone lo leído en los modelos (en el hilo de la ventana)."""
        en_hilo, self._leyendo = self._leyendo, False
        if "fallo" in r:
            self.consola.registrar("error", f"No se pudo releer el catálogo: {r['fallo']}")
        else:
            self._indice, self._db, self._firma_db = r["indice"], r["db"], r["firma"]
            self._firma_indice = firma(self._ruta_indice_actual())
            self._vigilar_db()
            self._libros, self._inmutable, self._error = r["libros"], r["inmutable"], r["error"]
            if self._error:
                self.consola.registrar("error", self._error)
            self._por_id = {l["id"]: l for l in self._libros}
            self._planos = r["planos"]
            if self.portadas is not None:
                self.portadas.fijar_rutas({l["id"]: l["ruta_portada"] for l in self._libros if l["portada"]})
            self._entrada, self._fichas_meta, self._bandejas = r["entrada"], r["fichas"], r["bandejas"]
            self._pintar()
            self._pintar_bandeja()
            self.cambiado.emit()
            if self._actual:
                self._fijar(self._por_id.get(self._actual["id"], {}))
        if en_hilo and self._releer_otra:
            self.recargar_en_segundo_plano()

    # ------------------------------------------------------------------ el vigilante de metadata.db
    def _ruta_indice_actual(self) -> Path:
        return self._ruta_indice or datos.ruta_indice()

    def _vigilar_db(self) -> None:
        """Vigila metadata.db y su carpeta (Calibre puede reemplazar el archivo o escribir su diario al lado), el índice
        (lo reescriben el timer de cada 30 min y Ctrl+R) y zotero.sqlite (solo su firma)."""
        actuales = set(self._vigilante.files()) | set(self._vigilante.directories())
        if actuales:
            self._vigilante.removePaths(list(actuales))
        zotero = Path(getattr(self.env, "ZOTERO_DB", "") or "")
        self._zotero = zotero if str(zotero) not in ("", ".") and zotero.is_file() else None
        if self._zotero is not None and not self._firma_zotero:
            self._firma_zotero = firma(self._zotero)
        if not self._vigilar or self._db is None:
            return
        indice = self._ruta_indice_actual()
        rutas = [str(r) for r in (self._db, self._db.parent, indice) if r.exists()]
        if self._zotero is not None:
            rutas.append(str(self._zotero))
        if rutas:
            self._vigilante.addPaths(rutas)

    def _db_cambio(self, ruta: str = "") -> None:
        if not self._vigilar:
            return
        if self._zotero is not None and ruta == str(self._zotero):
            self._espera_zotero.start()         # Zotero: el índice se rehace cuando deja de escribir
            self.sincroniaCambiada.emit()
            return
        self._espera_db.start()                 # Calibre escribe en ráfagas: se relee cuando se calma

    def _releer_si_cambio(self) -> None:
        indice = self._ruta_indice_actual()
        if self._vigilar and indice.exists() and str(indice) not in self._vigilante.files():
            self._vigilante.addPath(str(indice))         # reescrito (os.replace): se vuelve a vigilar
        firma_indice = firma(indice)
        if self._db is None or (firma(self._db) == self._firma_db and firma_indice == getattr(self, "_firma_indice", ())):
            if self._db is not None and str(self._db) not in self._vigilante.files() and self._db.exists():
                self._vigilante.addPath(str(self._db))   # reemplazado por uno nuevo: se vuelve a vigilar
            return
        self.consola.registrar("info", "metadata.db o el índice cambiaron (Calibre, una suite o el timer): el catálogo se relee en solo lectura.")
        self.recargar_en_segundo_plano()

    # ------------------------------------------------------------------ Zotero: el índice se rehace solo
    def _zotero_calmo(self) -> None:
        if self._zotero is None or not self._vigilar:
            return
        if str(self._zotero) not in self._vigilante.files() and self._zotero.exists():
            self._vigilante.addPath(str(self._zotero))
        f = firma(self._zotero)
        if f == self._firma_zotero:
            return
        import time
        falta = self._rehecho_en + ENTRE_INDICES_S - time.monotonic()
        if falta > 0:                           # se rehízo hace poco: se mira otra vez cuando toque
            QTimer.singleShot(int(falta * 1000) + 50, self._zotero_calmo)
            return
        self._firma_zotero = f
        self._rehecho_en = time.monotonic()
        self.rehacerIndice()

    @Slot()
    def rehacerIndice(self) -> None:
        """`lib/indice.py --aplicar` en un hilo: relee Calibre y Zotero en solo lectura (claves de Zotero y para citar) y
        reescribe el JSON; el vigilante del índice relee el catálogo. No toca ninguna base: no pasa por la puerta."""
        if self._rehaciendo:
            return
        self._rehaciendo = True
        self.sincroniaCambiada.emit()
        orden = [sys.executable or "python3", str(datos.REPO / "lib" / "indice.py"), "--aplicar"]

        def trabajo():
            try:
                r = subprocess.run(orden, capture_output=True, text=True, timeout=300, check=False)
                salida = (r.stdout if r.returncode == 0 else (r.stderr or r.stdout)) or ""
                self._indiceListo.emit(r.returncode, (salida.strip().splitlines() or [""])[-1])
            except (OSError, subprocess.TimeoutExpired) as e:
                self._indiceListo.emit(1, str(e))
        threading.Thread(target=trabajo, name="indice", daemon=True).start()

    def _indice_listo(self, codigo: int, linea: str) -> None:
        self._rehaciendo = False
        if codigo == 0:
            from datetime import datetime
            self._ultimo_indice = datetime.now().strftime("%H:%M")
            self.consola.registrar("info", f"Zotero cambió: índice rehecho ({linea})")
            self.recargar_en_segundo_plano()
        else:
            self.consola.registrar("warn", f"No se pudo rehacer el índice tras un cambio en Zotero: {linea}")
        self.sincroniaCambiada.emit()

    @Property(bool, notify=sincroniaCambiada)
    def rehaciendoIndice(self) -> bool:
        return self._rehaciendo

    @Property(str, notify=sincroniaCambiada)
    def estadoSincronia(self) -> str:
        """Lo que dice el botón «Sincronizar» del catálogo: qué se sigue solo y cuándo se rehízo el índice."""
        if not self._vigilar:
            return "Vigilancia apagada: el catálogo se relee con F6 y el índice con Ctrl+R"
        partes = ["Calibre: al momento", "Zotero: claves al momento; metadatos con «Zotero ⇄ Calibre» (04:30, o ahora)"]
        if self._rehaciendo:
            partes.append("rehaciendo el índice…")
        elif self._ultimo_indice:
            partes.append(f"índice rehecho a las {self._ultimo_indice}")
        return " · ".join(partes)

    def _vigilar_set(self, v: bool) -> None:
        self._vigilar = bool(v)
        self._s.setValue("catalogo/vigilar", "true" if self._vigilar else "false")
        self._vigilar_db()
        self.vigilarCambiado.emit()

    vigilar = Property(bool, lambda self: self._vigilar, _vigilar_set, notify=vigilarCambiado)

    def _pintar(self, facetas: bool = True) -> None:
        """Las filas en su orden (y, si se agrupa, por grupo y dentro en ese orden); el proxy las filtra al recibirlas (no
        hace falta otra pasada). Las facetas no dependen del orden: cambiar el orden no las recuenta."""
        if facetas:
            self._buscar_ids()
        orden = sorted(self._libros, key=cat.clave_orden(self._orden))
        if self._agrupar:
            orden = sorted(orden, key=cat.clave_grupo(self._agrupar))       # estable: dentro de cada grupo sigue el orden
        self._filas.poner([fila(l, grupo=cat.grupo_de(l, self._agrupar)) for l in orden])
        if facetas:
            self._contar_facetas()

    def _buscar_ids(self) -> None:
        """Los ids que cumplen la búsqueda, una vez por búsqueda (el filtro de cada fila solo mira el conjunto)."""
        if self._terminos:
            self._coinciden = {l["id"] for l in self._libros if cat.cumple(l, self._terminos, self._planos.get(l["id"]))}
        else:
            self._coinciden = None

    def _contar_facetas(self) -> None:
        """Las facetas se cuentan sobre lo que cumple la búsqueda (no los filtros: se ve cuánto da cada uno)."""
        buscados = self._libros if self._coinciden is None else [l for l in self._libros if l["id"] in self._coinciden]
        self._facetas = cat.facetas(buscados, ordenes=self._orden_facetas)
        self.facetasCambiadas.emit()

    def _recalcular(self) -> None:
        """Tras cambiar la búsqueda: el conjunto, el filtro (una pasada) y las facetas."""
        self._buscar_ids()
        self._modelo.aceptar_con(self._acepta)
        self._contar_facetas()

    def _acepta(self, i: int) -> bool:
        bid = self._filas.fila(i).get("id", "")
        l = self._por_id.get(bid)
        return bool(l) and (self._coinciden is None or bid in self._coinciden) and cat.cumple_filtros(l, self._filtros)

    @property
    def indice(self) -> dict:
        return self._indice

    @property
    def libros(self) -> list[dict]:
        return self._libros

    @Property(int, notify=cambiado)
    def total(self) -> int:
        return len(self._libros)

    @Property(int, notify=filtroCambiado)
    def visibles(self) -> int:
        return self._modelo.rowCount()

    @Property(bool, notify=cambiado)
    def hayIndice(self) -> bool:
        return bool(self._indice.get("libros"))

    @Property(bool, notify=cambiado)
    def inmutable(self) -> bool:
        return self._inmutable

    @Property(str, notify=cambiado)
    def error(self) -> str:
        return self._error

    @Property(str, notify=cambiado)
    def generado(self) -> str:
        return datos.antiguedad_indice(self._indice)

    @Property("QVariantMap", notify=cambiado)
    def contadores(self) -> dict:
        b = self._bandejas
        return {"todos": len(self._libros), **{k: v["n"] for k, v in b.items()},
                "con_portada": sum(l["portada"] for l in self._libros), "leyendo": sum(l["ko_estado"] == "reading" for l in self._libros)}

    @Property(str, notify=cambiado)
    def resumen(self) -> str:
        c = self.contadores
        if not self._libros:
            return self._error or "Sin libros: falta la biblioteca de Calibre o el índice (Ctrl+R)"
        return (f"{c['todos']} libros · {c.get('sin_zotero', 0)} sin Zotero · {c.get('sin_clave', 0)} sin clave para citar · "
                f"{c.get('fichas', 0)} con la ficha incompleta · {c['leyendo']} leyéndose en KOReader"
                + (" · Calibre ocupado: lo último confirmado" if self._inmutable else ""))

    # ------------------------------------------------------- búsqueda, filtros, orden y forma
    @Property(str, notify=filtroCambiado)
    def busqueda(self) -> str:
        return self._busqueda

    @Slot(str)
    def buscar(self, texto: str) -> None:
        texto = (texto or "").strip()
        if texto != self._busqueda:
            self._busqueda, self._terminos = texto, cat.consulta(texto)
            self._recalcular()
            self.filtroCambiado.emit()

    @Property("QVariantMap", notify=filtroCambiado)
    def filtros(self) -> dict:
        return dict(self._filtros)

    @Property("QVariantList", constant=True)
    def nombresFiltros(self) -> list:
        return [{"clave": k, "titulo": t} for k, t in FILTROS]

    @Slot(str, str)
    def fijarFiltro(self, clave: str, valor: str) -> None:
        if clave in self._filtros and self._filtros[clave] != valor:
            self._filtros[clave] = valor
            self._modelo.aceptar_con(self._acepta)
            self.filtroCambiado.emit()

    @Slot()
    def limpiarFiltros(self) -> None:
        cambio = any(self._filtros.values()) or self._busqueda
        self._filtros = {k: "" for k in self._filtros}
        self._busqueda, self._terminos = "", []
        if cambio:
            self._recalcular()
            self.filtroCambiado.emit()

    @Property(bool, notify=filtroCambiado)
    def hayFiltros(self) -> bool:
        return bool(self._busqueda or any(self._filtros.values()))

    @Property("QVariantMap", notify=facetasCambiadas)
    def facetas(self) -> dict:
        return dict(self._facetas)

    @Property("QVariantList", constant=True)
    def ordenes(self) -> list:
        return [{"clave": k, "titulo": t} for k, t in cat.ORDENES]

    @Property(str, notify=filtroCambiado)
    def orden(self) -> str:
        return self._orden

    @Slot(str)
    def fijarOrden(self, orden: str) -> None:
        if orden in dict(cat.ORDENES) and orden != self._orden:
            self._orden = orden
            self._s.setValue("catalogo/orden", orden)
            self._pintar(facetas=False)
            self.filtroCambiado.emit()

    @Property("QVariantList", constant=True)
    def agrupaciones(self) -> list:
        return [{"clave": k, "titulo": t} for k, t in cat.AGRUPAR]

    @Property(str, notify=filtroCambiado)
    def agrupar(self) -> str:
        return self._agrupar

    @Slot(str)
    def fijarAgrupar(self, clave: str) -> None:
        """Agrupa la lista con títulos (colección, autor, tipo, década); en la cuadrícula no hay títulos: pasa a la lista."""
        if clave in dict(cat.AGRUPAR) and clave != self._agrupar:
            self._agrupar = clave
            self._s.setValue("catalogo/agrupar", clave)
            self._pintar(facetas=False)
            if clave and not self._lista:
                self.enLista = True
            self.filtroCambiado.emit()

    @Property("QVariantList", constant=True)
    def ordenesFaceta(self) -> list:
        return [{"clave": k, "titulo": t} for k, t in cat.ORDENES_FACETA]

    @Property("QVariantMap", notify=facetasCambiadas)
    def ordenFacetas(self) -> dict:
        return {k: self._orden_facetas.get(k, "n") for k, _t in FILTROS}

    @Slot(str, str)
    def fijarOrdenFaceta(self, grupo: str, orden: str) -> None:
        """El orden de los valores de un grupo de filtros (p. ej., las colecciones por nombre); se recuerda."""
        if grupo in self._filtros and orden in dict(cat.ORDENES_FACETA) and self._orden_facetas.get(grupo, "n") != orden:
            self._orden_facetas[grupo] = orden
            self._s.setValue("catalogo/orden_facetas", json.dumps(self._orden_facetas))
            self._contar_facetas()

    def _lista_get(self) -> bool:
        return self._lista

    def _lista_set(self, v: bool) -> None:
        if bool(v) != self._lista:
            self._lista = bool(v)
            self._s.setValue("catalogo/forma", "lista" if v else "cuadricula")
            self.filtroCambiado.emit()

    enLista = Property(bool, _lista_get, _lista_set, notify=filtroCambiado)

    @Slot()
    def alternarForma(self) -> None:
        self.enLista = not self._lista

    # --------------------------------------------------------------------- bandejas
    @Property("QVariantList", notify=cambiado)
    def bandejas(self) -> list:
        return [{"clave": k, "titulo": t, "icono": i, "descripcion": d, "etapa": e, "operacion": o, "n": self._bandejas.get(k, {}).get("n", 0)}
                for k, t, i, d, e, o in cat.BANDEJAS]

    @Property(str, notify=bandejaCambiada)
    def bandeja(self) -> str:
        return self._bandeja

    @Property("QVariantMap", notify=bandejaCambiada)
    def bandejaInfo(self) -> dict:
        return next((b for b in self.bandejas if b["clave"] == self._bandeja), {})

    @Slot(str)
    def fijarBandeja(self, clave: str) -> None:
        clave = clave if clave in self._bandejas else ""
        if clave != self._bandeja:
            self._bandeja = clave
            self._pintar_bandeja()
            self.bandejaCambiada.emit()

    def _pintar_bandeja(self) -> None:
        b = self._bandejas.get(self._bandeja, {})
        filas = []
        for e in b.get("otros", []):
            filas.append({"id": "", "titulo": e.get("titulo") or e.get("archivo", ""), "autores": e.get("autores", "") or "—", "año": "",
                          "serie": "", "tipo": e.get("tipo", ""), "portada": False, "fuente": "", "zotero": False, "clave": "", "koProgreso": -1.0,
                          "koEstado": "", "fichas": 0, "etiquetas": "", "seccion": e.get("seccion", ""), "otro": True,
                          "detalle": f"{e.get('origen', '')} · {e.get('paso', '')}" + (f" · confianza {e['confianza']}" if e.get("confianza") else ""),
                          "nivel": e.get("nivel", ""), "grupo": "", "paginas": 0})
        libros = sorted((self._por_id[i] for i in b.get("libros", []) if i in self._por_id), key=cat.clave_orden("titulo"))
        filas += [fila(l, "En Calibre") for l in libros]
        self._bandeja_filas.poner(filas)

    # --------------------------------------------------------------------- el libro de la ficha
    def _fijar(self, l: dict) -> None:
        self._actual = dict(l) if l else {}
        self.actualCambiado.emit()
        self._pedir_usos()

    # --------------------------------------------------------------------- en qué escritos se usa (§9.1)
    def _pedir_usos(self) -> None:
        """Los escritos de escritura que declaran el libro o tienen fichas de él (lib/consulta.py, en un hilo)."""
        import threading
        bid = str(self._actual.get("id") or "")
        self._usos, self._usos_de = [], bid
        self.usosCambiados.emit()
        if not bid.isdigit():
            return

        def trabajo():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("biblioteca_consulta", datos.REPO / "lib" / "consulta.py")
                consulta = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(consulta)
                r = consulta.usos(int(bid))
            except Exception as e:                         # sin escritura o con un fuentes.yml roto: sin usos, con aviso
                self.consola.registrar("warn", f"Usos del libro {bid}: {e}")
                r = []
            self._usosListos.emit(bid, r)
        threading.Thread(target=trabajo, name="usos", daemon=True).start()

    def _poner_usos(self, bid: str, usos: list) -> None:
        if bid == self._usos_de:
            self._usos = list(usos)
            self.usosCambiados.emit()

    @Property("QVariantList", notify=usosCambiados)
    def usos(self) -> list:
        return self._usos

    @Slot(str)
    def abrirEnLatex(self, principal: str) -> None:
        """El escrito en LaTeX Studio (latex-studio/studio/main.py junto a la raíz de los documentos)."""
        import subprocess
        main = Path(os.environ.get("LATEX_STUDIO_DIR") or Path(self.env.DOCS_ROOT) / "latex-studio") / "studio" / "main.py"
        if not main.is_file() or not principal:
            self.aviso.emit("No encuentro LaTeX Studio (latex-studio/studio/main.py)", "aviso")
            return
        subprocess.Popen(["/usr/bin/python3", str(main), principal], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str)
    def fijarId(self, libro_id: str) -> None:
        self._fijar(self._por_id.get(str(libro_id), {}))

    @Slot(int)
    def fijarFila(self, fila_visible: int) -> None:
        """El libro de esa posición visible del catálogo (cuadrícula o lista)."""
        if 0 <= fila_visible < self._modelo.rowCount():
            self.fijarId(self._filas.fila(self._modelo.filaOrigen(fila_visible)).get("id", ""))
        else:
            self._fijar({})

    @Slot(str, result=int)
    def filaDe(self, libro_id: str) -> int:
        for i, f in enumerate(self._filas.todas()):
            if f.get("id") == str(libro_id):
                return self._modelo.filaVisible(i)
        return -1

    @Slot(str, result=bool)
    def irA(self, libro_id: str) -> bool:
        """Abre el libro en el catálogo (quita lo que lo oculte): lo que piden los complementos y la paleta."""
        libro_id = str(libro_id)
        if libro_id not in self._por_id:
            self.aviso.emit(f"El libro {libro_id} no está en la biblioteca: Actualizar el índice (Ctrl+R).", "aviso")
            return False
        self.espacio.fijarArea("catalogo")
        if self.filaDe(libro_id) < 0:
            self.limpiarFiltros()
        self.fijarId(libro_id)
        self.seleccionar.emit(self.filaDe(libro_id))
        return True

    @Slot(str, result=bool)
    def abrirUrl(self, url: str) -> bool:
        """`biblioteca-studio://libro/<id>`: lo que piden los complementos de Calibre, KOReader y Zotero."""
        partes = url.split("://", 1)[-1].strip("/").split("/")
        if len(partes) >= 2 and partes[0] == "libro":
            return self.irA(partes[1])
        return False

    @Property(bool, notify=actualCambiado)
    def hayActual(self) -> bool:
        return bool(self._actual)

    @Property(str, notify=actualCambiado)
    def id(self) -> str:
        return str(self._actual.get("id", ""))

    @Property(str, notify=actualCambiado)
    def titulo(self) -> str:
        return self._actual.get("titulo", "")

    @Property(str, notify=actualCambiado)
    def autores(self) -> str:
        return " · ".join(self._actual.get("autores") or []) or "sin autor"

    @Property(str, notify=actualCambiado)
    def zoteroKey(self) -> str:
        return self._actual.get("zotero_key") or ""

    @Property(str, notify=actualCambiado)
    def clave(self) -> str:
        return self._actual.get("clave") or ""

    @Property(int, notify=actualCambiado)
    def nFichas(self) -> int:
        return len(self._actual.get("fichas") or [])

    @Property("QVariantMap", notify=actualCambiado)
    def ficha(self) -> dict:
        """La ficha editorial del libro actual, ya redactada para QML."""
        l = self._actual
        if not l:
            return {}
        estados = {f["ficha"]: f.get("verificacion", "pendiente") for f in self._fichas_meta}
        imprenta = [x for x in (l["editorial"], str(l["año"] or ""), ", ".join(l["idiomas"]), f"{l['paginas']} págs." if l["paginas"] else "") if x]
        ids = [{"tipo": k.upper() if k in ("isbn", "doi", "issn") else k, "valor": v} for k, v in sorted(l["identificadores"].items())]
        ko = l["ko_estado"]
        lectura = ""
        if l["ko_progreso"] is not None or ko:
            lectura = TEXTO_KO.get(ko, ko or "abierto")
            if l["ko_progreso"] is not None:
                lectura += f" · {l['ko_progreso'] * 100:.0f} %"
            if l["ko_minutos"]:
                lectura += f" · {l['ko_minutos'] // 60} h {l['ko_minutos'] % 60:02d} min"
            if l["ko_ultima"]:
                lectura += f" · última lectura {l['ko_ultima']}"
        nota = l["nota"]
        return {
            "id": l["id"], "titulo": l["titulo"], "autores": l["autores"], "año": str(l["año"] or ""), "imprenta": " · ".join(imprenta), "serie": _serie(l),
            "tipo": l["tipo"], "etiquetas": l["etiquetas"], "identificadores": ids, "descripcion": l["descripcion"],
            "portada": l["portada"], "fuente": f"image://portadas/{l['id']}/grande" if l["portada"] else "",
            "clave": l["clave"], "zotero": bool(l["zotero_key"]), "zoteroKey": l["zotero_key"],
            "koreader": lectura, "koProgreso": -1.0 if l["ko_progreso"] is None else float(l["ko_progreso"]), "koEstado": ko,
            "fichas": [{"nombre": Path(f).name, "ruta": str(self.repo / f) if not Path(f).is_absolute() else f,
                        "verificacion": estados.get(Path(f).name, "pendiente")} for f in l["fichas"]],
            "nota": nota, "hayNota": bool(nota) and Path(nota).is_file(), "notaEnlazada": l["nota_enlazada"],
            "formatos": [{"formato": f["formato"], "nombre": f["nombre"], "tamano": _bytes(f["bytes"]) if f["bytes"] else ""} for f in l["formatos"]],
            "carpeta": l["carpeta"], "añadido": l["añadido"], "ids": texto_ids(self._indice.get("libros", {}).get(str(l["id"])) or {}),
            "porqueIds": "Una referencia inventada tiene un DOI que no existe o que es de otra obra: se resuelve antes de entregar. · ICMJE (2025); Jergas y Baethge (2015)",
        }

    def _biblioteca(self) -> Path:
        return Path(self._indice.get("biblioteca") or self.env.BIBLIOTECA_DIR)

    def ruta_archivo(self) -> str:
        formatos = self._actual.get("formatos") or []
        return str(self._biblioteca() / self._actual["carpeta"] / formatos[0]["nombre"]) if formatos and self._actual.get("carpeta") else ""

    @Property(str, notify=actualCambiado)
    def rutaArchivo(self) -> str:
        return self.ruta_archivo()

    @Property(str, notify=actualCambiado)
    def rutaCarpeta(self) -> str:
        return str(self._biblioteca() / self._actual["carpeta"]) if self._actual.get("carpeta") else ""

    @Property(bool, notify=actualCambiado)
    def hayNota(self) -> bool:
        return bool(self._actual.get("nota")) and Path(self._actual["nota"]).is_file()

    # ----------------------------------------------------------- acciones sobre el libro
    @Slot()
    def abrirCalibre(self) -> None:
        if self._actual:
            self.espacio.abrirEnlace(f"calibre://show-book/{_hex(self._biblioteca().name)}/{self.id}")

    @Slot()
    def abrirZotero(self) -> None:
        if self.zoteroKey:
            self.espacio.abrirEnlace(f"zotero://select/library/items/{self.zoteroKey}")
        elif self._actual:
            self.aviso.emit("Este libro todavía no está enlazado con Zotero (bandeja «Sin Zotero»).", "aviso")

    def _escritorio(self, metodo: str, ruta: str) -> None:
        if self.escritorio is not None:
            getattr(self.escritorio, metodo)(ruta)
        elif metodo == "mostrarEnDolphin":
            self.espacio.abrirDolphin(ruta)
        else:
            self.espacio.abrir(ruta)

    @Slot()
    def abrirArchivo(self) -> None:
        ruta = self.ruta_archivo()
        if ruta:
            self._escritorio("abrirConAplicacion", ruta)
        elif self._actual:
            self.aviso.emit("Este libro no tiene ningún archivo en Calibre.", "aviso")

    @Slot()
    def mostrarEnDolphin(self) -> None:
        ruta = self.ruta_archivo() or self.rutaCarpeta
        if ruta:
            self._escritorio("mostrarEnDolphin", ruta)

    @Slot()
    def abrirNota(self) -> None:
        if self.hayNota:
            self._escritorio("abrirConAplicacion", self._actual["nota"])
        elif self._actual:
            self.aviso.emit("Todavía no hay nota de lectura: la crean el complemento de KOReader o Zotero Integration (Obsidian).", "informacion")

    @Slot()
    def copiarClave(self) -> None:
        if self.clave:
            self.espacio.copiar(self.clave)
            self.aviso.emit(f"Clave copiada: {self.clave}", "positivo")
        elif self._actual:
            self.aviso.emit("Este libro no tiene clave para citar (Zotero manda: enlázalo primero).", "aviso")

    @Slot()
    def copiarCita(self) -> None:
        """«Citar en LaTeX» (decisiones §9.9): «\\parencite{clave}» al portapapeles, lista para pegar en LaTeX Studio."""
        if self.clave:
            cita = f"\\parencite{{{self.clave}}}"
            self.espacio.copiar(cita)
            self.aviso.emit(f"Copiado: {cita}. Pégalo en LaTeX Studio.", "positivo")
        elif self._actual:
            self.aviso.emit("Este libro no tiene clave para citar (Zotero manda: enlázalo primero).", "aviso")

    @Slot(str)
    def abrirFicha(self, ruta: str) -> None:
        if ruta:
            self._escritorio("abrirConAplicacion", ruta)

    # --------------------------------------------------------------------------- paleta
    def entradas_paleta(self, texto: str) -> list[dict]:
        """«Libro: …» para la paleta (solo cuando hay algo escrito: la biblioteca tiene miles), con la misma búsqueda."""
        t = texto.strip()
        if len(t) < 2:
            return []
        terminos = cat.consulta(t)
        salida = []
        for l in self._libros:
            if cat.cumple(l, terminos, self._planos.get(l["id"])):
                salida.append({"nombre": f"libro.{l['id']}", "texto": f"Libro: {l['titulo']}", "grupo": "Catálogo", "icono": "folder-book",
                               "ejecutar": lambda i=l["id"]: self.irA(i)})
                if len(salida) >= 40:
                    break
        return salida
