"""biblioteca_app/controladores/fichado.py — fichar el libro de la ficha editorial con su PDF al lado y estudiarlo por partes con los prompts del ecosistema (decisiones §9.4 y §9.5).

Objetivo: desde la ficha de un libro, «Nueva ficha» (textual, paráfrasis o fuente) en el escrito que se elija, viendo el
  PDF, y «Estudiar con la IA»: copiar el prompt de una mirada sobre unas hojas del libro y pegar la respuesta del chat,
  cuyas fichas propuestas (cotejadas en su hoja) se llevan al escrito una por una.
Método: todo pasa por `lib/consulta.py` (cargado por su ruta, como «Usado en»), en hilos: `escritos` y `usos` (los que ya
  usan el libro, primero), `formulario`, `nueva_ficha` (simula; escribe con `aplicar` tras la revisión del diálogo, solo
  en `fuentes/fichas/` del escrito y, si el libro aún no es su fuente, su `fuentes.yml` y su `references.bib`),
  `miradas`, `prompt_obra` (al portapapeles) y `pegar_obra`. El PDF lo pinta el visor de gui-comun (`VisorPdf`).
Límite: no es una puerta: nunca escribe en Calibre ni en Zotero, ni llama a ningún modelo. Las capturas y las pruebas, sobre
  `studio/muestra.py` (WRITING_DIR de la muestra).
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

from gui_comun.qt import QGuiApplication, QObject, Property, Signal, Slot
from gui_comun.visor_pdf import VisorPdf

from biblioteca_app.servicios import datos


def _consulta():
    import sys
    if "biblioteca_consulta" in sys.modules:
        return sys.modules["biblioteca_consulta"]
    spec = importlib.util.spec_from_file_location("biblioteca_consulta", datos.REPO / "lib" / "consulta.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["biblioteca_consulta"] = m
    spec.loader.exec_module(m)
    return m


class Fichado(QObject):
    cambiado = Signal()
    revisada = Signal("QVariantMap")                 # lo que escribiría una ficha (simulación) o lo que escribió
    promptObra = Signal("QVariantMap")               # el prompt de la mirada (ya en el portapapeles) o {error}
    pegadoObra = Signal("QVariantMap")               # lo pegado, leído: {ok, errores, avisos, estudio, fichas}
    aviso = Signal(str, str)
    _listo = Signal(str, "QVariant")                 # (qué, dato) desde los hilos

    def __init__(self, libros, consola, cache: Path, parent=None):
        super().__init__(parent)
        self.libros, self.consola = libros, consola
        self._visor = VisorPdf(Path(cache), "BIBLIOTECA_STUDIO_VISOR", parent=self)
        self._escritos: list = []
        self._formulario: dict = {}
        self._miradas: list = []
        self._calibre_id = 0
        self._ocupado = False
        self._listo.connect(self._poner)

    # ------------------------------------------------------------------ propiedades
    visor = Property(QObject, lambda self: self._visor, constant=True)

    @Property("QVariantList", notify=cambiado)
    def escritos(self) -> list:
        return self._escritos

    @Property("QVariantMap", notify=cambiado)
    def formulario(self) -> dict:
        return self._formulario

    @Property("QVariantList", notify=cambiado)
    def miradas(self) -> list:
        return self._miradas

    @Property(bool, notify=cambiado)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(int, notify=cambiado)
    def calibreId(self) -> int:
        return self._calibre_id

    # ------------------------------------------------------------------ hilos
    def _en_hilo(self, que: str, trabajo) -> None:
        self._ocupado = True
        self.cambiado.emit()

        def correr():
            try:
                r = trabajo()
            except SystemExit as e:                       # _proyecto() de consulta: no es un escrito
                r = {"error": str(e).replace("[ERROR] ", "")}
            except (ValueError, LookupError, OSError) as e:
                r = {"error": str(e)}
            except Exception as e:  # noqa: BLE001 — se dice en la ventana, no se cae
                r = {"error": f"{type(e).__name__}: {e}"}
            self._listo.emit(que, r)
        threading.Thread(target=correr, name=f"fichado-{que}", daemon=True).start()

    def _poner(self, que: str, r) -> None:
        self._ocupado = False
        if que == "preparar":
            self._escritos, self._formulario, self._miradas, pdf = r.get("escritos", []), r.get("formulario", {}), r.get("miradas", []), r.get("pdf", "")
            if pdf:
                self._visor.abrir(pdf)
            if r.get("error"):
                self.consola.registrar("warn", f"Fichar: {r['error']}")
        elif que == "revisar":
            if r.get("escrito"):
                self.consola.registrar("ok", f"Ficha guardada: {r.get('ruta') or r.get('archivo')}")
                self.libros._pedir_usos()                 # «Usado en» suma el escrito
            self.revisada.emit(r)
        elif que == "prompt":
            if r.get("prompt"):
                QGuiApplication.clipboard().setText(r["prompt"])
            self.promptObra.emit(r)
        elif que == "pegar":
            self.pegadoObra.emit(r)
        self.cambiado.emit()

    # ------------------------------------------------------------------ lo que pide la ventana
    @Slot(int)
    def preparar(self, calibre_id: int) -> None:
        """Los escritos (los que ya usan el libro, primero), el formulario de fichas, las miradas y el PDF del libro."""
        self._calibre_id = int(calibre_id)

        def trabajo():
            c = _consulta()
            usos = {u["proyecto"]: u for u in c.usos(calibre_id)}
            escritos = [{**e, "usa": e["proyecto"] in usos, "fichas": usos.get(e["proyecto"], {}).get("fichas", 0)} for e in c.escritos()]
            escritos.sort(key=lambda e: (not e["usa"], e["proyecto"]))
            libro = c._indice()["libros"].get(str(calibre_id)) or {}
            biblioteca = Path(c._indice().get("biblioteca") or "")
            pdf = next((str(biblioteca / f) for f in libro.get("formatos", []) if f.lower().endswith(".pdf")), "")
            return {"escritos": escritos, "formulario": c._fichar().formulario(), "miradas": c._ayuda().miradas(), "pdf": pdf}
        self._en_hilo("preparar", trabajo)

    @Slot(str, "QVariantMap", bool)
    def revisar(self, carpeta: str, campos: dict, aplicar: bool) -> None:
        """Una ficha nueva del libro en el escrito `carpeta`: sin `aplicar` simula; con él escribe (`revisada`)."""
        campos = {**dict(campos), "calibre_id": self._calibre_id}

        def trabajo():
            return {**_consulta().nueva_ficha(carpeta, campos, aplicar), "aplicar": aplicar}
        self._en_hilo("revisar", trabajo)

    @Slot(str, int, int, str)
    def copiarPrompt(self, mirada: str, desde: int, hasta: int, proposito: str) -> None:
        """El prompt de la mirada sobre las hojas `desde`–`hasta` del libro, al portapapeles (`promptObra`)."""
        cid = self._calibre_id
        self._en_hilo("prompt", lambda: _consulta().prompt_obra(cid, mirada, desde, hasta, proposito))

    @Slot(str)
    def leerPegado(self, texto: str) -> None:
        """Lo que respondió el chat, leído sin IA: el estudio y sus fichas cotejadas (`pegadoObra`)."""
        cid = self._calibre_id
        self._en_hilo("pegar", lambda: _consulta().pegar_obra(cid, texto))
