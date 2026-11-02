"""biblioteca_app/controladores/puerta.py — el estado de la puerta visto desde la ventana: si Calibre y Zotero corren y
si los candados están ocupados (cada 4 s, como la ventana de 1.x), y lo que eso significa para Aplicar. Solo lee."""

from __future__ import annotations

from gui_comun.qt import QObject, QTimer, Property, Signal, Slot

from biblioteca_app.servicios import puerta as svc

INTERVALO_MS = 4000


class Puerta(QObject):
    cambiado = Signal()

    def __init__(self, env, parent=None, vigilar: bool = True):
        super().__init__(parent)
        self.env = env
        self._abiertas: set[str] = set()
        self._ocupados: set[str] = set()
        self._reloj = QTimer(self)
        self._reloj.setInterval(INTERVALO_MS)
        self._reloj.timeout.connect(self.refrescar)
        self.refrescar()
        if vigilar:
            self._reloj.start()

    @Slot()
    def refrescar(self) -> None:
        abiertas = svc.abiertas()
        ocupados = {b for b in svc.NOMBRE_BASE if svc.candado_ocupado(getattr(self.env, "LOCK_" + b.upper(), ""))}
        if abiertas != self._abiertas or ocupados != self._ocupados:
            self._abiertas, self._ocupados = abiertas, ocupados
            self.cambiado.emit()

    @Property(bool, notify=cambiado)
    def calibreAbierto(self) -> bool:
        return "calibre" in self._abiertas

    @Property(bool, notify=cambiado)
    def zoteroAbierto(self) -> bool:
        return "zotero" in self._abiertas

    @Property(bool, notify=cambiado)
    def candadoCalibre(self) -> bool:
        return "calibre" in self._ocupados

    @Property(bool, notify=cambiado)
    def candadoZotero(self) -> bool:
        return "zotero" in self._ocupados

    @Property(str, notify=cambiado)
    def contexto(self) -> str:
        """«Calibre cerrado · Zotero abierto · candados libres» (la barra de estado)."""
        if not self._abiertas:
            apps = "Calibre y Zotero cerrados"
        elif self._abiertas == set(svc.NOMBRE_BASE):
            apps = "Calibre y Zotero abiertos"
        else:
            apps = " · ".join(f"{n} {'abierto' if b in self._abiertas else 'cerrado'}" for b, n in svc.NOMBRE_BASE.items())
        if not self._ocupados:
            candados = "candados libres"
        else:
            candados = "candado de " + " y ".join(svc.NOMBRE_BASE[b] for b in sorted(self._ocupados)) + " ocupado"
        return f"{apps} · {candados}"

    @Slot(str, result=str)
    def impedimento(self, bases: str) -> str:
        """Por qué no se puede aplicar una operación que escribe en esas bases («calibre,zotero»); vacío si se puede."""
        motivos = []
        for b in [x for x in bases.split(",") if x]:
            if b in self._abiertas:
                motivos.append(f"{svc.NOMBRE_BASE[b]} está abierto: ciérralo para aplicar")
            if b in self._ocupados:
                motivos.append(f"el candado de {svc.NOMBRE_BASE[b]} está ocupado (otra suite escribe)")
        return "; ".join(motivos)

    @Slot(str, result=str)
    def estadoDe(self, bases: str) -> str:
        """«Calibre cerrado · candado libre» de las bases que toca una operación (el diálogo de Aplicar)."""
        partes = []
        for b in [x for x in bases.split(",") if x]:
            partes.append(f"{svc.NOMBRE_BASE[b]} {'abierto' if b in self._abiertas else 'cerrado'} · candado "
                          f"{'ocupado' if b in self._ocupados else 'libre'}")
        return " · ".join(partes) or "no escribe en ninguna base"
