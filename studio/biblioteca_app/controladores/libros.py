"""biblioteca_app/controladores/libros.py — el catálogo bibliográfico (reingeniería B2–B8, `docs/reingenieria.md`): los
libros de Calibre con sus metadatos editoriales y su lectura en KOReader (`servicios/catalogo.py`, en solo lectura) unidos
al índice de `lib/indice.py` (claves de Zotero y para citar, fichas, nota); la búsqueda avanzada, los filtros por
colección, autor, década y tipo, el orden y la cuadrícula o la lista; las portadas en miniatura (`ProveedorPortadas`);
la ficha editorial del libro actual y lo que se hace con él (abrir el documento con su aplicación, mostrarlo en Dolphin,
abrir en Calibre y en Zotero, la nota, copiar la clave); y las bandejas de trabajo. El enlace `biblioteca-studio://libro/<id>`
de los complementos lo abre. La ventana no escribe: lo que cambia la biblioteca es una operación (la CLI de su suite)."""

from __future__ import annotations

from pathlib import Path

from gui_comun.modelos import ModeloFiltrado, ModeloLista
from gui_comun.qt import QObject, QSettings, Property, Signal, Slot

from biblioteca_app.servicios import catalogo as cat
from biblioteca_app.servicios import datos

ROLES = ("id", "titulo", "autores", "año", "serie", "tipo", "portada", "fuente", "zotero", "clave", "koProgreso", "koEstado",
         "fichas", "etiquetas", "seccion", "otro", "detalle", "nivel")
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


def fila(l: dict, seccion: str = "") -> dict:
    """Una tarjeta del catálogo (o de una bandeja)."""
    return {"id": l["id"], "titulo": l["titulo"], "autores": " · ".join(l["autores"]) or "sin autor", "año": str(l["año"] or ""),
            "serie": _serie(l), "tipo": l["tipo"], "portada": bool(l["portada"]), "fuente": f"image://portadas/{l['id']}" if l["portada"] else "",
            "zotero": bool(l["zotero_key"]), "clave": l["clave"], "koProgreso": -1.0 if l["ko_progreso"] is None else float(l["ko_progreso"]),
            "koEstado": l["ko_estado"], "fichas": len(l["fichas"]), "etiquetas": ", ".join(l["etiquetas"]), "seccion": seccion,
            "otro": False, "detalle": "", "nivel": ""}


class Libros(QObject):
    cambiado = Signal()                 # el catálogo, las facetas, las bandejas y los contadores
    filtroCambiado = Signal()           # la búsqueda, los filtros, el orden o la forma (cuadrícula · lista)
    actualCambiado = Signal()           # el libro de la ficha
    bandejaCambiada = Signal()
    facetasCambiadas = Signal()         # las cuentas de los filtros (cambian con la búsqueda)
    seleccionar = Signal(int)           # QML: lleva la cuadrícula a ese índice visible
    aviso = Signal(str, str)

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
        self._inmutable = False
        self._error = ""
        self._busqueda = ""
        self._terminos: list = []
        self._filtros = {k: "" for k, _t in FILTROS}
        self._orden = str(self._s.value("catalogo/orden", "titulo") or "titulo")
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
        self.recargar()

    modelo = Property(QObject, lambda self: self._modelo, constant=True)
    bandejaModelo = Property(QObject, lambda self: self._bandeja_filas, constant=True)

    # ------------------------------------------------------------------ leer
    @Slot()
    def recargar(self) -> None:
        """Relee el índice y Calibre (en solo lectura), la entrada y las fichas: tras «Actualizar el índice», F6 o una aplicación."""
        self._indice = datos.leer_indice(self._ruta_indice)
        biblioteca = Path(self._indice.get("biblioteca") or self.env.BIBLIOTECA_DIR)
        db = Path(getattr(self.env, "CALIBRE_DB", "") or biblioteca / "metadata.db")
        try:
            leido = cat.leer(db, self._indice, biblioteca)
            self._libros, self._inmutable, self._error = leido["libros"], leido["inmutable"], ""
        except Exception as e:      # noqa: BLE001  una base que no se puede leer no tumba la ventana
            self._libros, self._inmutable, self._error = [], False, f"No se pudo leer la biblioteca de Calibre: {e}"
            self.consola.registrar("error", self._error)
        self._por_id = {l["id"]: l for l in self._libros}
        if self.portadas is not None:
            self.portadas.fijar_rutas({l["id"]: l["ruta_portada"] for l in self._libros if l["portada"]})
        try:
            self._entrada = datos.entrada(self.repo, Path(self.env.DOCS_ROOT))
            self._fichas_meta = datos.fichas(self.repo)
        except OSError:
            self._entrada, self._fichas_meta = [], []
        self._bandejas = cat.bandejas(self._libros, self._entrada, self._fichas_meta)
        self._pintar()
        self._pintar_bandeja()
        self.cambiado.emit()
        if self._actual:
            self._fijar(self._por_id.get(self._actual["id"], {}))

    def _pintar(self) -> None:
        orden = sorted(self._libros, key=cat.clave_orden(self._orden))
        self._filas.poner([fila(l) for l in orden])
        self._recalcular()

    def _recalcular(self) -> None:
        """Las facetas se cuentan sobre lo que cumple la búsqueda (no los filtros: se ve cuánto da cada uno)."""
        buscados = [l for l in self._libros if cat.cumple(l, self._terminos)] if self._terminos else self._libros
        self._facetas = cat.facetas(buscados)
        self._modelo.aceptar_con(self._acepta)
        self.facetasCambiadas.emit()

    def _acepta(self, i: int) -> bool:
        l = self._por_id.get(self._filas.fila(i).get("id", ""))
        return bool(l) and cat.cumple_filtros(l, self._filtros) and (not self._terminos or cat.cumple(l, self._terminos))

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
            self._pintar()
            self.filtroCambiado.emit()

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
                          "nivel": e.get("nivel", "")})
        libros = sorted((self._por_id[i] for i in b.get("libros", []) if i in self._por_id), key=cat.clave_orden("titulo"))
        filas += [fila(l, "En Calibre") for l in libros]
        self._bandeja_filas.poner(filas)

    # --------------------------------------------------------------------- el libro de la ficha
    def _fijar(self, l: dict) -> None:
        self._actual = dict(l) if l else {}
        self.actualCambiado.emit()

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
            "id": l["id"], "titulo": l["titulo"], "autores": l["autores"], "imprenta": " · ".join(imprenta), "serie": _serie(l),
            "tipo": l["tipo"], "etiquetas": l["etiquetas"], "identificadores": ids, "descripcion": l["descripcion"],
            "portada": l["portada"], "fuente": f"image://portadas/{l['id']}/grande" if l["portada"] else "",
            "clave": l["clave"], "zotero": bool(l["zotero_key"]), "zoteroKey": l["zotero_key"],
            "koreader": lectura, "koProgreso": -1.0 if l["ko_progreso"] is None else float(l["ko_progreso"]), "koEstado": ko,
            "fichas": [{"nombre": Path(f).name, "ruta": str(self.repo / f) if not Path(f).is_absolute() else f,
                        "verificacion": estados.get(Path(f).name, "pendiente")} for f in l["fichas"]],
            "nota": nota, "hayNota": bool(nota) and Path(nota).is_file(), "notaEnlazada": l["nota_enlazada"],
            "formatos": [{"formato": f["formato"], "nombre": f["nombre"], "tamano": _bytes(f["bytes"]) if f["bytes"] else ""} for f in l["formatos"]],
            "carpeta": l["carpeta"], "añadido": l["añadido"],
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
            if cat.cumple(l, terminos):
                salida.append({"nombre": f"libro.{l['id']}", "texto": f"Libro: {l['titulo']}", "grupo": "Catálogo", "icono": "folder-book",
                               "ejecutar": lambda i=l["id"]: self.irA(i)})
                if len(salida) >= 40:
                    break
        return salida
