"""biblioteca_app/controladores/ajustes.py — «Configurar Biblioteca Studio…»: la terminal de «Abrir terminal en el repo»
y si el panel inferior se abre solo al correr una operación, en QSettings."""

from __future__ import annotations

from gui_comun.qt import QObject, QSettings, Property, Signal, Slot


class Ajustes(QObject):
    cambiado = Signal()
    guardado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._s = QSettings()

    def _terminal_get(self) -> str:
        return str(self._s.value("sistema/terminal", "konsole") or "konsole")

    def _terminal_set(self, v: str) -> None:
        v = (v or "").strip() or "konsole"
        if v != self._terminal_get():
            self._s.setValue("sistema/terminal", v)
            self.cambiado.emit()

    terminal = Property(str, _terminal_get, _terminal_set, notify=cambiado)

    def _abrir_get(self) -> bool:
        return str(self._s.value("ventana/abrirInferior", "true")).lower() in ("true", "1")

    def _abrir_set(self, v: bool) -> None:
        if bool(v) != self._abrir_get():
            self._s.setValue("ventana/abrirInferior", "true" if v else "false")
            self.cambiado.emit()

    abrirInferior = Property(bool, _abrir_get, _abrir_set, notify=cambiado)

    @Slot()
    def guardar(self) -> None:
        self._s.sync()
        self.cambiado.emit()
        self.guardado.emit()
