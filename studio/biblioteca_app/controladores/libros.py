"""biblioteca_app/controladores/libros.py — la vista Libros: la tabla del índice (`lib/indice.py`, el JSON; nunca las
bases), sus filtros de coherencia (Todos · Sin Zotero · Sin clave para citar · Sin ficha · Sin nota enlazada), el libro
actual con sus detalles (Resumen, las fichas que lo citan) y lo que se hace con él: abrir en Calibre, en Zotero, el
archivo, la nota; copiar la clave. El enlace `biblioteca-studio://libro/<id>` de los complementos lo selecciona."""

from __future__ import annotations

import os
from pathlib import Path

from gui_comun.modelos import ModeloFiltrado, ModeloTabla
from gui_comun.qt import QObject, QUrl, Property, Signal, Slot

from biblioteca_app import modelos as mod
from biblioteca_app.servicios import datos


def _hex(nombre: str) -> str:
    return "_hex_-" + nombre.encode("utf-8").hex()


class Libros(QObject):
    cambiado = Signal()                 # el índice y los contadores
    actualCambiado = Signal()           # el libro actual
    filtroCambiado = Signal()
    seleccionar = Signal(int)           # QML: selecciona esa fila visible de la tabla
    aviso = Signal(str, str)

    def __init__(self, espacio, consola, env, ruta_indice: Path | None = None, parent=None):
        super().__init__(parent)
        self.espacio, self.consola, self.env = espacio, consola, env
        self._ruta_indice = ruta_indice
        self._tabla = ModeloTabla(mod.COLUMNAS["libros"], parent=self)
        self._modelo = ModeloFiltrado(self._tabla, parent=self)
        self._fichas = ModeloTabla(mod.COLUMNAS_FICHAS_LIBRO, parent=self)
        self._indice: dict = {"libros": {}}
        self._lista: list[dict] = []
        self._contadores: dict = {}
        self._filtro = "todos"
        self._actual: dict = {}
        self._modelo.aceptar_con(self._acepta)
        self.recargar()

    modelo = Property(QObject, lambda self: self._modelo, constant=True)
    fichasModelo = Property(QObject, lambda self: self._fichas, constant=True)

    # ------------------------------------------------------------- el índice
    @Slot()
    def recargar(self) -> None:
        """Relee el JSON del índice (tras «Actualizar el índice» o F6)."""
        self._indice = datos.leer_indice(self._ruta_indice)
        self._lista = datos.libros(self._indice)
        self._tabla.poner([mod.fila_libro(d) for d in self._lista])
        self._contadores = mod.contar_libros(self._lista)
        self.cambiado.emit()
        if self._actual:
            self._fijar_libro(self._indice["libros"].get(self._actual.get("id", ""), {}) and {"id": self._actual["id"], **self._indice["libros"][self._actual["id"]]})

    @property
    def indice(self) -> dict:
        return self._indice

    @Property(int, notify=cambiado)
    def total(self) -> int:
        return len(self._lista)

    @Property(bool, notify=cambiado)
    def hayIndice(self) -> bool:
        return bool(self._lista)

    @Property(str, notify=cambiado)
    def generado(self) -> str:
        return datos.antiguedad_indice(self._indice)

    @Property("QVariantMap", notify=cambiado)
    def contadores(self) -> dict:
        return dict(self._contadores)

    @Property(str, notify=cambiado)
    def resumen(self) -> str:
        return mod.resumen_libros(self._contadores)

    @Property("QVariantList", notify=cambiado)
    def filasNavegacion(self) -> list:
        return [{"nombre": "libros" if f == "todos" else f"libros.{f}", "texto": t, "icono": mod.ICONO_LIBRO if f == "todos" else "",
                 "contador": self._contadores.get(f, 0)} for f, t in mod.FILTROS_LIBROS]

    # --------------------------------------------------------------- filtro
    def _acepta(self, fila_origen: int) -> bool:
        return mod.cumple_filtro(self._tabla.fila(fila_origen).get("datos", {}), self._filtro)

    @Property(str, notify=filtroCambiado)
    def filtro(self) -> str:
        return self._filtro

    @Property(str, notify=filtroCambiado)
    def textoFiltro(self) -> str:
        return dict(mod.FILTROS_LIBROS).get(self._filtro, "Todos")

    @Slot(str)
    def fijarFiltro(self, filtro: str) -> None:
        filtro = filtro if filtro in dict(mod.FILTROS_LIBROS) else "todos"
        if filtro != self._filtro:
            self._filtro = filtro
            self._modelo.aceptar_con(self._acepta)
            self.filtroCambiado.emit()

    # --------------------------------------------------------- libro actual
    @Slot(int)
    def fijarFila(self, fila: int) -> None:
        if fila < 0 or fila >= self._modelo.rowCount():
            self._fijar_libro({})
            return
        self._fijar_libro(self._tabla.fila(self._modelo.filaOrigen(fila)).get("datos", {}))

    def _fijar_libro(self, d: dict) -> None:
        self._actual = dict(d) if d else {}
        fichas = self._actual.get("fichas") or []
        self._fichas.poner([{"ficha": f, "ruta": str(datos.REPO / f), "icono": "document-edit-verify", "habilitado": True} for f in fichas])
        self.actualCambiado.emit()

    @Slot(str, result=int)
    def filaDe(self, libro_id: str) -> int:
        """La fila visible del libro con ese `calibre_id`; −1 si no está (o el filtro lo oculta)."""
        for i, f in enumerate(self._tabla.todas()):
            if f.get("id") == str(libro_id):
                return self._modelo.filaVisible(i)
        return -1

    @Slot(str, result=bool)
    def irA(self, libro_id: str) -> bool:
        """Selecciona el libro en la vista Libros (filtro Todos): lo que piden los complementos y la paleta."""
        libro_id = str(libro_id)
        if libro_id not in self._indice.get("libros", {}):
            self.aviso.emit(f"El libro {libro_id} no está en el índice: Actualizar el índice (Ctrl+R).", "aviso")
            return False
        self.espacio.fijarVista("libros")
        self.fijarFiltro("todos")
        fila = self.filaDe(libro_id)
        self.fijarFila(fila)
        self.seleccionar.emit(fila)
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

    @Property(str, notify=actualCambiado)
    def carpeta(self) -> str:
        return self._actual.get("carpeta") or ""

    @Property("QVariantList", notify=actualCambiado)
    def formatos(self) -> list:
        return [os.path.basename(f) for f in self._actual.get("formatos") or []]

    def _biblioteca(self) -> Path:
        return Path(self._indice.get("biblioteca") or self.env.BIBLIOTECA_DIR)

    def ruta_archivo(self) -> str:
        formatos = self._actual.get("formatos") or []
        return str(self._biblioteca() / formatos[0]) if formatos else ""

    @Property(str, notify=actualCambiado)
    def rutaArchivo(self) -> str:
        return self.ruta_archivo()

    @Property(str, notify=actualCambiado)
    def rutaCarpeta(self) -> str:
        return str(self._biblioteca() / self._actual["carpeta"]) if self._actual.get("carpeta") else ""

    @Property(str, notify=actualCambiado)
    def portada(self) -> str:
        p = self._biblioteca() / self._actual.get("carpeta", "") / "cover.jpg" if self._actual.get("carpeta") else None
        return QUrl.fromLocalFile(str(p)).toString() if p and p.is_file() else ""

    @Property(str, notify=actualCambiado)
    def nota(self) -> str:
        return self._actual.get("apuntes") or self._actual.get("nota") or ""

    @Property(bool, notify=actualCambiado)
    def hayNota(self) -> bool:
        return bool(self.nota) and Path(self.nota).is_file()

    @Property(bool, notify=actualCambiado)
    def notaEnlazada(self) -> bool:
        return bool(self._actual.get("apuntes"))

    @Property(int, notify=actualCambiado)
    def nFichas(self) -> int:
        return len(self._actual.get("fichas") or [])

    # ----------------------------------------------------------- acciones
    @Slot()
    def abrirCalibre(self) -> None:
        if self._actual:
            self.espacio.abrirEnlace(f"calibre://show-book/{_hex(self._biblioteca().name)}/{self.id}")

    @Slot()
    def abrirZotero(self) -> None:
        if self.zoteroKey:
            self.espacio.abrirEnlace(f"zotero://select/library/items/{self.zoteroKey}")
        elif self._actual:
            self.aviso.emit("Este libro todavía no está enlazado con Zotero («Enlazar con Zotero lo que falta»).", "aviso")

    @Slot()
    def abrirArchivo(self) -> None:
        ruta = self.ruta_archivo()
        if ruta:
            self.espacio.abrir(ruta)
        elif self._actual:
            self.aviso.emit("Este libro no tiene ningún archivo en Calibre.", "aviso")

    @Slot()
    def abrirNota(self) -> None:
        if self.hayNota:
            self.espacio.abrir(self.nota)
        elif self._actual:
            self.aviso.emit("Todavía no hay nota de lectura: la crean el complemento de KOReader o Zotero Integration (Obsidian, Ctrl+R).", "informacion")

    @Slot()
    def copiarClave(self) -> None:
        if self.clave:
            self.espacio.copiar(self.clave)
            self.aviso.emit(f"Clave copiada: {self.clave}", "positivo")
        elif self._actual:
            self.aviso.emit("Este libro no tiene clave para citar (Zotero manda: enlázalo primero).", "aviso")

    @Slot(int)
    def abrirFicha(self, fila: int) -> None:
        if 0 <= fila < self._fichas.filas:
            self.espacio.abrir(self._fichas.fila(fila)["ruta"])

    # --------------------------------------------------------------- paleta
    def entradas_paleta(self, texto: str) -> list[dict]:
        """«Libro: …» para la paleta (solo cuando hay algo escrito: el índice tiene miles)."""
        t = texto.strip().lower()
        if len(t) < 2:
            return []
        salida = []
        for d in self._lista:
            if t in d.get("titulo", "").lower() or t in (d.get("clave") or "").lower() or t == d["id"] or any(t in a.lower() for a in d.get("autores") or []):
                salida.append({"nombre": f"libro.{d['id']}", "texto": f"Libro: {d['titulo']}", "grupo": "Libros", "icono": mod.ICONO_LIBRO,
                               "ejecutar": lambda i=d["id"]: self.irA(i)})
                if len(salida) >= 40:
                    break
        return salida
