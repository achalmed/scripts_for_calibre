"""biblioteca_app/controladores/catalogado.py — catalogar con un chat desde Método › Entrada y Método › Catalogar
(decisiones §9.15): copiar el prompt del paso 02 de la fila elegida, pegar lo que respondió el chat, ver los cambios
comprobados sin IA y guardarlos en su registro.

Método: todo pasa por `lib/catalogar_ia.py` (cargado por su ruta), en hilos: `prompt` (al portapapeles), `leer` (los cambios,
  los problemas y los avisos) y `guardar` (solo con lo leído sin problemas; reescribe la fila de `ingesta/pendientes.tsv` o
  de `catalogacion/resumen_catalogacion.tsv`). Después relee la etapa y elige su operación («Catalogar en Calibre» o
  «Aplicar la catalogación»), que se simula con F5 y se aplica con Ctrl+Intro, por la puerta, como siempre.
Límite: no es una puerta: nunca escribe en Calibre ni en Zotero, ni llama a ningún modelo. Las pruebas, sobre
  `studio/muestra.py`.
"""
from __future__ import annotations

import importlib.util
import sys
import threading

from gui_comun.qt import QGuiApplication, QObject, Property, Signal, Slot

from biblioteca_app.servicios import datos

OPERACION = {"entrada": "catalogar", "catalogar": "catalogacion"}


def _modulo():
    nombre = "biblioteca_catalogar_ia"
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, datos.REPO / "lib" / "catalogar_ia.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = m
    spec.loader.exec_module(m)
    return m


class Catalogado(QObject):
    cambiado = Signal()
    prompt = Signal("QVariantMap")          # {prompt (ya en el portapapeles), aviso} o {error}
    revisado = Signal("QVariantMap")        # {ok, cambios, problemas, avisos} o {error}
    guardado = Signal("QVariantMap")        # lo de revisado + {escrito, ruta} o {error}
    aviso = Signal(str, str)
    _listo = Signal(str, "QVariant")

    def __init__(self, etapas, operaciones, consola, parent=None):
        super().__init__(parent)
        self.etapas, self.operaciones, self.consola = etapas, operaciones, consola
        self._vista, self._clave, self._titulo, self._archivo = "", "", "", ""
        self._ocupado = False
        self._listo.connect(self._poner)

    # ------------------------------------------------------------------ propiedades
    @Property(str, notify=cambiado)
    def vista(self) -> str:
        return self._vista

    @Property(str, notify=cambiado)
    def clave(self) -> str:
        return self._clave

    @Property(str, notify=cambiado)
    def titulo(self) -> str:
        return self._titulo

    @Property(str, notify=cambiado)
    def archivo(self) -> str:
        return self._archivo

    @Property(bool, notify=cambiado)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(str, notify=cambiado)
    def operacion(self) -> str:
        """El título de la operación que aplica lo guardado."""
        from biblioteca_app.servicios import operaciones as ops
        o = ops.operacion(OPERACION.get(self._vista, ""))
        return o.titulo if o else ""

    @Slot(str, result=bool)
    def admite(self, vista: str) -> bool:
        return vista in OPERACION

    # ------------------------------------------------------------------ la fila
    @Slot(str, int, result=bool)
    def elegir(self, vista: str, fila: int) -> bool:
        """La fila visible `fila` de la tabla de `vista` (Entrada o Catalogar); falso si no se puede catalogar con un chat."""
        modelo, tabla = self.etapas.modeloDe(vista), self.etapas.tablaDe(vista)
        if vista not in OPERACION or modelo is None or fila < 0 or fila >= modelo.rowCount():
            return False
        f = tabla.fila(modelo.filaOrigen(fila))
        if vista == "entrada":
            if f.get("paso") != "identificado":
                self.aviso.emit("Solo un archivo identificado (con su fila en pendientes.tsv) se cataloga con un chat: "
                                + ("ya está en Calibre; se corrige en Catalogar." if f.get("paso") == "catalogado" else "corre antes «Identificar»."), "aviso")
                return False
            clave, archivo = f.get("ruta", ""), f.get("archivo", "")
        else:
            clave, archivo = str(f.get("id", "")), ""
        self._vista, self._clave, self._titulo, self._archivo = vista, clave, f.get("titulo", "") or archivo, archivo
        self.cambiado.emit()
        return True

    # ------------------------------------------------------------------ hilos
    def _en_hilo(self, que: str, trabajo) -> None:
        self._ocupado = True
        self.cambiado.emit()

        def correr():
            try:
                r = trabajo()
            except (ValueError, LookupError, OSError) as e:
                r = {"error": str(e)}
            except Exception as e:  # noqa: BLE001 — se dice en la ventana, no se cae
                r = {"error": f"{type(e).__name__}: {e}"}
            self._listo.emit(que, r)
        threading.Thread(target=correr, name=f"catalogado-{que}", daemon=True).start()

    def _poner(self, que: str, r) -> None:
        self._ocupado = False
        self.cambiado.emit()
        if que == "prompt":
            if r.get("prompt"):
                QGuiApplication.clipboard().setText(r["prompt"])
                self.consola.registrar("info", f"Catalogar con un chat: prompt del paso 02 copiado ({len(r['prompt'])} caracteres) para «{self._titulo}»")
            self.prompt.emit(r)
        elif que == "revisar":
            self.revisado.emit(r)
        elif que == "guardar":
            if r.get("escrito"):
                self.consola.registrar("ok", f"Catalogación guardada en {r.get('ruta')}: {len(r.get('cambios', []))} campos de «{self._titulo}»")
                self.etapas.recargar(self._vista)
                self.operaciones.fijar(OPERACION[self._vista])
            self.guardado.emit(r)

    # ------------------------------------------------------------------ lo que pide la ventana
    @Slot()
    def copiarPrompt(self) -> None:
        if not self._clave or self._ocupado:
            return
        vista, clave, repo = self._vista, self._clave, self.etapas.repo
        self._en_hilo("prompt", lambda: _modulo().prompt(vista, clave, repo))

    @Slot(str)
    def revisar(self, pegado: str) -> None:
        if not self._clave or self._ocupado:
            return
        vista, clave, repo = self._vista, self._clave, self.etapas.repo
        self._en_hilo("revisar", lambda: _modulo().leer(vista, clave, pegado, repo))

    @Slot(str)
    def guardar(self, pegado: str) -> None:
        if not self._clave or self._ocupado:
            return
        vista, clave, repo = self._vista, self._clave, self.etapas.repo
        self._en_hilo("guardar", lambda: _modulo().guardar(vista, clave, pegado, aplicar=True, repo=repo))
