"""biblioteca_app/controladores/espacio.py — lo transversal: la vista activa (las nueve etapas de `operaciones.ETAPAS`),
el filtro de Libros, el resumen y el contexto de la barra de estado, el título de la ventana y las acciones sobre una
ruta (abrir con el sistema, Dolphin, terminal, portapapeles). Se recuerda la última vista en QSettings."""

from __future__ import annotations

import os
import shutil
import subprocess

from gui_comun.qt import QGuiApplication, QObject, QSettings, Property, Signal, Slot

from biblioteca_app.servicios import operaciones as ops

NOMBRES_VISTAS = ops.NOMBRES_ETAPAS


class Espacio(QObject):
    vistaCambiada = Signal()
    resumenCambiado = Signal()
    contextoCambiado = Signal()
    aviso = Signal(str, str)                 # texto, tipo (informacion · positivo · aviso · error)

    def __init__(self, consola, ajustes=None, parent=None):
        super().__init__(parent)
        self.consola, self.ajustes = consola, ajustes
        self._s = QSettings()
        self._vista = str(self._s.value("vista", NOMBRES_VISTAS[0]) or NOMBRES_VISTAS[0])
        if self._vista not in NOMBRES_VISTAS:
            self._vista = NOMBRES_VISTAS[0]
        self._resumen = ""
        self._contexto = ""

    # ------------------------------------------------------------- vista
    @Property("QVariantList", constant=True)
    def vistas(self) -> list:
        return [{"nombre": e.id, "texto": e.nombre, "icono": e.icono, "paraQue": e.para_que} for e in ops.ETAPAS]

    @Property(str, notify=vistaCambiada)
    def vista(self) -> str:
        return self._vista

    @Property(int, notify=vistaCambiada)
    def indiceVista(self) -> int:
        return NOMBRES_VISTAS.index(self._vista)

    @Property(str, notify=vistaCambiada)
    def textoVista(self) -> str:
        return ops.etapa(self._vista).nombre

    @Property(str, notify=vistaCambiada)
    def paraQue(self) -> str:
        return ops.etapa(self._vista).para_que

    @Slot(str)
    def fijarVista(self, nombre: str) -> None:
        if nombre in NOMBRES_VISTAS and nombre != self._vista:
            self._vista = nombre
            self._s.setValue("vista", nombre)
            self.vistaCambiada.emit()

    @Slot(int)
    def fijarVistaPorIndice(self, i: int) -> None:
        if 0 <= i < len(NOMBRES_VISTAS):
            self.fijarVista(NOMBRES_VISTAS[i])

    # ------------------------------------------------------ barra de estado
    @Property(str, notify=resumenCambiado)
    def resumen(self) -> str:
        return self._resumen

    @Slot(str)
    def fijarResumen(self, texto: str) -> None:
        if texto != self._resumen:
            self._resumen = texto
            self.resumenCambiado.emit()

    @Property(str, notify=contextoCambiado)
    def contexto(self) -> str:
        return self._contexto

    @Slot(str)
    def fijarContexto(self, texto: str) -> None:
        if texto != self._contexto:
            self._contexto = texto
            self.contextoCambiado.emit()

    # ------------------------------------------------------- sobre una ruta
    @Slot(str)
    def abrir(self, ruta: str) -> None:
        """Un archivo o carpeta con la aplicación del sistema (xdg-open)."""
        if ruta and os.path.exists(ruta):
            subprocess.Popen(["xdg-open", ruta])
            self.consola.registrar("info", f"Abierto con el sistema: {ruta}")
        else:
            self.aviso.emit(f"No existe: {ruta or '(nada seleccionado)'}", "aviso")

    @Slot(str)
    def abrirEnlace(self, url: str) -> None:
        """Un enlace (`calibre://`, `zotero://`) con el escritorio."""
        subprocess.Popen(["xdg-open", url])
        self.consola.registrar("info", f"Enlace: {url}")

    @Slot(str)
    def abrirDolphin(self, ruta: str) -> None:
        carpeta = ruta if os.path.isdir(ruta) else os.path.dirname(ruta)
        if os.path.isdir(carpeta):
            subprocess.Popen(["xdg-open", carpeta])
        else:
            self.aviso.emit(f"No existe la carpeta: {carpeta}", "aviso")

    def _terminal(self) -> str:
        preferido = (self.ajustes.terminal if self.ajustes is not None else "konsole") or "konsole"
        for candidato in (preferido, "konsole", "x-terminal-emulator"):
            if shutil.which(candidato):
                return candidato
        return ""

    @Slot(str)
    def abrirTerminal(self, ruta: str) -> None:
        carpeta = ruta if os.path.isdir(ruta) else os.path.dirname(ruta)
        if not os.path.isdir(carpeta):
            return
        terminal = self._terminal()
        if terminal == "konsole":
            subprocess.Popen(["konsole", "--workdir", carpeta])
        elif terminal:
            subprocess.Popen([terminal], cwd=carpeta)
        else:
            self.aviso.emit("No se encontró un emulador de terminal (konsole).", "aviso")

    @Slot(str)
    def copiar(self, texto: str) -> None:
        if texto:
            QGuiApplication.clipboard().setText(texto)
            self.consola.registrar("info", f"Copiado: {texto}")

    # --------------------------------------------------------------- paleta
    def entradas_paleta(self, _texto: str) -> list[dict]:
        return [{"nombre": f"ir.{e.id}", "texto": f"Ir a {e.nombre}", "grupo": "Vistas", "icono": e.icono,
                 "ejecutar": lambda n=e.id: self.fijarVista(n)} for e in ops.ETAPAS]
