"""biblioteca_app/controladores/espacio.py — lo transversal: el área (reingeniería B1: Catálogo, Bandejas, Método
Documental, Coherencia), la vista activa (la etapa de `operaciones.ETAPAS` cuyas operaciones se ofrecen), el resumen y
el contexto de la barra de estado y las acciones sobre una ruta (abrir con el sistema, Dolphin, terminal,
portapapeles). Se recuerdan el área y la vista en QSettings."""

from __future__ import annotations

import os
import shutil
import subprocess

from gui_comun.qt import QGuiApplication, QObject, QSettings, Property, Signal, Slot

from biblioteca_app.servicios import operaciones as ops

NOMBRES_VISTAS = ops.NOMBRES_ETAPAS
AREAS = (("catalogo", "Catálogo", "view-preview"), ("bandejas", "Bandejas", "mail-folder-inbox"),
         ("metodo", "Método Documental", "view-process-tree"), ("coherencia", "Coherencia", "folder-sync"))
NOMBRES_AREAS = tuple(a for a, _t, _i in AREAS)
VISTAS_DE = {"catalogo": ("libros",), "metodo": ("adquirir", "entrada", "catalogar", "fichas", "manifiestos"),
             "coherencia": ("sincronizar", "puerta", "tareas")}


class Espacio(QObject):
    vistaCambiada = Signal()
    areaCambiada = Signal()
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
        self._area = str(self._s.value("area", "catalogo") or "catalogo")
        if self._area not in NOMBRES_AREAS:
            self._area = "catalogo"
        self._resumen = ""
        self._contexto = ""

    # ------------------------------------------------------------- área
    @Property("QVariantList", constant=True)
    def areas(self) -> list:
        return [{"nombre": a, "texto": t, "icono": i} for a, t, i in AREAS]

    @Property(str, notify=areaCambiada)
    def area(self) -> str:
        return self._area

    @Property(int, notify=areaCambiada)
    def indiceArea(self) -> int:
        return NOMBRES_AREAS.index(self._area)

    @Property(str, notify=areaCambiada)
    def textoArea(self) -> str:
        return dict((a, t) for a, t, _i in AREAS)[self._area]

    @Slot(str)
    def fijarArea(self, area: str) -> None:
        """Cambia de área; la vista (las operaciones que se ofrecen) pasa a una del área si no lo era ya."""
        if area not in NOMBRES_AREAS:
            return
        vistas = VISTAS_DE.get(area)
        if vistas and self._vista not in vistas:
            guardada = str(self._s.value(f"vista/{area}", vistas[0]) or vistas[0])
            self._fijar_vista(guardada if guardada in vistas else vistas[0], mover_area=False)
        if area != self._area:
            self._area = area
            self._s.setValue("area", area)
            self.areaCambiada.emit()

    @Slot(int)
    def fijarAreaPorIndice(self, i: int) -> None:
        if 0 <= i < len(NOMBRES_AREAS):
            self.fijarArea(NOMBRES_AREAS[i])

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
        """La etapa activa; el área la sigue (una operación elegida desde el menú lleva a su etapa)."""
        self._fijar_vista(nombre, mover_area=True)

    def _fijar_vista(self, nombre: str, mover_area: bool) -> None:
        if nombre not in NOMBRES_VISTAS:
            return
        if nombre != self._vista:
            self._vista = nombre
            self._s.setValue("vista", nombre)
            area = next((a for a, vs in VISTAS_DE.items() if nombre in vs), "")
            if area:
                self._s.setValue(f"vista/{area}", nombre)
            self.vistaCambiada.emit()
        if mover_area:
            area = next((a for a, vs in VISTAS_DE.items() if nombre in vs), "")
            if area and area != self._area and self._area != "bandejas":
                self._area = area
                self._s.setValue("area", area)
                self.areaCambiada.emit()

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
        areas = [{"nombre": f"ir.area.{a}", "texto": f"Ir a {t}", "grupo": "Áreas", "icono": i,
                  "ejecutar": lambda n=a: self.fijarArea(n)} for a, t, i in AREAS]
        return areas + [{"nombre": f"ir.{e.id}", "texto": f"Ir a {e.nombre}", "grupo": "Etapas", "icono": e.icono,
                         "ejecutar": lambda n=e.id: (self.fijarVista(n), self.fijarArea(next((a for a, vs in VISTAS_DE.items() if n in vs), "catalogo")))}
                        for e in ops.ETAPAS]
