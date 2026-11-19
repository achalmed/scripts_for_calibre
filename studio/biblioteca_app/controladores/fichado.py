"""biblioteca_app/controladores/fichado.py — fichar el libro de la ficha editorial con su PDF al lado y estudiarlo por partes con los prompts del ecosistema (decisiones §9.4 y §9.5).

Objetivo: desde la ficha de un libro, «Nueva ficha» (textual, paráfrasis o fuente) en el escrito que se elija, viendo el
  PDF, y «Estudiar con la IA»: copiar el prompt de una mirada sobre unas hojas del libro y pegar la respuesta del chat,
  cuyas fichas propuestas (cotejadas en su hoja) se llevan al escrito una por una.
Método: todo pasa por `lib/consulta.py` (cargado por su ruta, como «Usado en»), en hilos: `escritos` y `usos` (los que ya
  usan el libro, primero), `formulario`, `nueva_ficha` (simula; escribe con `aplicar` tras la revisión del diálogo, solo
  en `fuentes/fichas/` del escrito y, si el libro aún no es su fuente, su `fuentes.yml` y su `references.bib`),
  `miradas`, `prompt_obra` (al portapapeles) y `pegar_obra`. El PDF lo pinta el visor de gui-comun (`VisorPdf`).
La ficha de obra de Yachay (decisiones §9.13): la de la persona sobre la obra, una por libro, que la base de lectura trae
  de Yachay; la del escrito es su copia para ese escrito. «Nueva ficha» de obra se rellena con ella, y al guardar la del
  escrito la ventana ofrece llevarla de vuelta: `simularYachay` dice qué se enviaría y con qué versión, y `llevarAYachay`
  la envía tras confirmar, siempre por la CLI de la base (`lectura_base/main.py ficha-a-yachay`, la que tiene el token y
  el único escritor de la base). Un 409 no pisa: vuelve la versión actual y la persona elige llevar la suya sobre ella o
  quedarse con la de Yachay (`quedarseConYachay`: la sincronía de Yachay, `main.py sincronizar --origen yachay --aplicar`).
  Las llamadas a la CLI van por `CanalYachay`, que las pruebas reemplazan: nada contra el Yachay real.
Corregir (decisiones §9.13, nota del 2026-11-19): `leerFicha` abre una ficha que ya existe en un escrito con su huella
  (`corregible`) y `corregir` la reescribe por `lib/consulta.py guardar_ficha` (simula; escribe con `aplicar` y la huella con
  que se abrió: si cambió en disco, `ficha_cambiada` con la de ahora, y no pisa). La de obra corregida ofrece la misma vuelta
  a Yachay. `simularYachayDe` y `llevarAYachayDe` llevan el libro explícito: los usa «Corregir…» de la ficha de obra en
  Yachay, que no pasa por un escrito ni prepara el PDF.
Límite: no es una puerta: nunca escribe en Calibre ni en Zotero, ni llama a ningún modelo. Las capturas y las pruebas, sobre
  `studio/muestra.py` (WRITING_DIR de la muestra).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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


class CanalYachay:
    """La ficha de obra en Yachay por la CLI de la base de lectura (el token lo lee ella, del llavero)."""

    def _correr(self, argv: list[str], entrada: str = "", tiempo: int = 120) -> tuple[dict, int, str]:
        r = subprocess.run([sys.executable, str(datos.REPO / "lectura_base" / "main.py"), *argv], input=entrada,
                           capture_output=True, text=True, timeout=tiempo)
        try:
            salida = json.loads(r.stdout) if r.stdout.strip() else {}
        except ValueError:
            salida = {}
        error = (r.stderr or "").strip().splitlines()[-1:] or [""]
        return salida if isinstance(salida, dict) else {}, r.returncode, error[0].replace("[ERROR] ", "")

    def ficha_a_yachay(self, calibre_id: int, respuestas: dict, aplicar: bool, sobre: int | None = None) -> dict:
        argv = ["ficha-a-yachay", str(int(calibre_id)), "-", "--json"] + (["--aplicar"] if aplicar else []) \
            + (["--sobre", str(int(sobre))] if sobre is not None else [])
        r, codigo, error = self._correr(argv, json.dumps(respuestas, ensure_ascii=False))
        if codigo not in (0, 4) or not r:
            return {"error": error or f"la CLI salió con {codigo}", "sinCanal": codigo == 3}
        return r

    def sincronizar_yachay(self) -> dict:
        r, codigo, error = self._correr(["sincronizar", "--origen", "yachay", "--aplicar", "--json"], tiempo=300)
        return {"ok": codigo == 0, "error": "" if codigo == 0 else (error or f"la CLI salió con {codigo}")}


class Fichado(QObject):
    cambiado = Signal()
    revisada = Signal("QVariantMap")                 # lo que escribiría una ficha (simulación) o lo que escribió
    promptObra = Signal("QVariantMap")               # el prompt de la mirada (ya en el portapapeles) o {error}
    pegadoObra = Signal("QVariantMap")               # lo pegado, leído: {ok, errores, avisos, estudio, fichas}
    yachay = Signal("QVariantMap")                   # la ficha de obra en Yachay: lo que se enviaría, lo enviado o el 409
    corregible = Signal("QVariantMap")               # una ficha del escrito para corregirla (sus secciones y su huella) o {error}
    aviso = Signal(str, str)
    _listo = Signal(str, "QVariant")                 # (qué, dato) desde los hilos

    def __init__(self, libros, consola, cache: Path, parent=None, canal: CanalYachay | None = None):
        super().__init__(parent)
        self.libros, self.consola = libros, consola
        self.canal = canal or CanalYachay()
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
                self.consola.registrar("ok", f"Ficha {'corregida' if r.get('correccion') else 'guardada'}: {r.get('ruta') or r.get('archivo')}")
                self.libros._pedir_usos()                 # «Usado en» suma el escrito
            self.revisada.emit(r)
        elif que == "prompt":
            if r.get("prompt"):
                QGuiApplication.clipboard().setText(r["prompt"])
            self.promptObra.emit(r)
        elif que == "pegar":
            self.pegadoObra.emit(r)
        elif que == "ficha":
            self.corregible.emit(r)
        elif que == "yachay":
            if r.get("escrita"):
                self.consola.registrar("ok", f"Ficha de obra del libro {r.get('calibre_id')} llevada a Yachay (versión {r.get('version')})")
            elif r.get("codigo") == "lectura_modificada":
                self.consola.registrar("warn", f"Yachay: la ficha de obra cambió allí (versión {r.get('version')}); no se envió nada")
            elif r.get("error"):
                self.consola.registrar("warn", f"Yachay: {r['error']}")
            self.yachay.emit(r)
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

    @Slot(str, str)
    def leerFicha(self, carpeta: str, archivo: str) -> None:
        """Una ficha que ya existe en el escrito `carpeta`, para corregirla (`corregible`): sus secciones, su página, su
        categoría, su uso y la huella con que se abrió (`lib/fichar.py leer`)."""
        nombre = Path(archivo).name

        def trabajo():
            c = _consulta()
            return {**c._fichar().leer(c._proyecto(carpeta), nombre), "carpeta": carpeta}
        self._en_hilo("ficha", trabajo)

    @Slot(str, str, str, "QVariantMap", bool)
    def corregir(self, carpeta: str, archivo: str, huella: str, campos: dict, aplicar: bool) -> None:
        """Corrige una ficha que ya existe con la huella con que se abrió (`lib/consulta.py guardar_ficha`): sin `aplicar`
        simula; con él escribe (`revisada`). Si cambió en disco: `{codigo: "ficha_cambiada", actual}`, sin escribir."""
        nombre, campos = Path(archivo).name, dict(campos)

        def trabajo():
            r = _consulta().guardar_ficha(carpeta, nombre, huella, campos, aplicar)
            return {**r, "aplicar": aplicar, "correccion": True}
        self._en_hilo("revisar", trabajo)

    # ------------------------------------------------------------------ la ficha de obra en Yachay (§9.13)
    @Slot("QVariantMap")
    def simularYachay(self, secciones: dict) -> None:
        """Qué se enviaría a la ficha de obra de Yachay de este libro y sobre qué versión (`yachay`, sin escribir)."""
        self.simularYachayDe(self._calibre_id, secciones)

    @Slot(int, "QVariantMap")
    def simularYachayDe(self, calibre_id: int, secciones: dict) -> None:
        """Lo mismo, del libro `calibre_id` (la de Yachay corregida sin pasar por un escrito)."""
        cid, respuestas = int(calibre_id), dict(secciones)
        self._en_hilo("yachay", lambda: {**self.canal.ficha_a_yachay(cid, respuestas, False), "accion": "simular"})

    @Slot("QVariantMap", int)
    def llevarAYachay(self, secciones: dict, sobre: int) -> None:
        """La envía (tras confirmar en la ventana); `sobre` ≥ 0 tras un 409: llevar la suya sobre esa versión."""
        self.llevarAYachayDe(self._calibre_id, secciones, sobre)

    @Slot(int, "QVariantMap", int)
    def llevarAYachayDe(self, calibre_id: int, secciones: dict, sobre: int) -> None:
        """Lo mismo, del libro `calibre_id`."""
        cid, respuestas = int(calibre_id), dict(secciones)
        sobre_v = int(sobre) if int(sobre) >= 0 else None
        self._en_hilo("yachay", lambda: {**self.canal.ficha_a_yachay(cid, respuestas, True, sobre_v), "accion": "llevar"})

    @Slot()
    def quedarseConYachay(self) -> None:
        """Ante un 409, la de Yachay: la sincronía de Yachay la trae a la base (nada se envía)."""
        self._en_hilo("yachay", lambda: {**self.canal.sincronizar_yachay(), "accion": "quedarse"})

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
