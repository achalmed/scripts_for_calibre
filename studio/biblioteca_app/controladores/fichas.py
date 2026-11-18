"""biblioteca_app/controladores/fichas.py — el área «Fichas» (rediseño del 2026-11-18, decisiones §9.9): todas las fichas de
los escritos y las fichas canónicas, filtradas en lista (Todas, Textuales, Paráfrasis, Por revisar, con su cuenta), y el
«Repaso para estudiantes».

Objetivo: ver de un vistazo lo fichado en todos los escritos, saber qué falta cotejar y estudiarlo sin mirar.
Método: las fichas de los escritos salen de `lib/consulta.py` (`escritos` y `fichas`, el lector único de la norma), en un
  hilo; las canónicas, de `catalogacion/fichas/` (`servicios.datos.fichas`, lo mismo que la etapa Fichas). El repaso es el
  sistema Leitner de cinco cajas de `lib/repaso.py` (su base propia, `REPASO_DB`): la tarjeta muestra la pregunta (la
  categoría o el tema de la ficha y su obra), «Mostrar la ficha» revela la cita, «La sabía» la sube de caja y «Repasar
  luego» la baja a la 1. Entran al repaso las textuales, las paráfrasis y las síntesis que tienen texto.
Límite: solo lee las fichas; lo único que escribe es la base del repaso, por su único escritor. «Nueva ficha» y «Estudiar
  con la IA» son los diálogos de la ficha editorial (§9.4 y §9.5), sobre el libro de la ficha elegida.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from datetime import date
from pathlib import Path

from gui_comun.qt import QGuiApplication, QObject, Property, Signal, Slot

from biblioteca_app.servicios import datos

TIPOS = {"textual": "Textual", "parafrasis": "Paráfrasis", "sintesis": "Síntesis", "fuente": "Fuente", "catalogacion": "Catalogación"}
FILTROS = (("todas", "Todas"), ("textual", "Textuales"), ("parafrasis", "Paráfrasis"), ("revisar", "Por revisar"))
DE_REPASO = ("textual", "parafrasis", "sintesis")


def _repaso():
    """`lib/repaso.py`, cargado por su ruta (el único escritor de la base del repaso)."""
    if "biblioteca_repaso" in sys.modules:
        return sys.modules["biblioteca_repaso"]
    spec = importlib.util.spec_from_file_location("biblioteca_repaso", datos.REPO / "lib" / "repaso.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["biblioteca_repaso"] = m
    spec.loader.exec_module(m)
    return m


def cotejo(estado: str) -> str:
    """Lo que dice el estado de verificación de una ficha, en palabras."""
    if estado.startswith("verificada"):
        return "cotejada con el PDF" if estado == "verificada_script" else "revisada por el autor"
    return {"observada": "no coincide con el PDF", "pendiente": "sin cotejar"}.get(estado, "")


def por_revisar(f: dict) -> bool:
    return f["tipo"] in ("textual", "parafrasis", "sintesis", "catalogacion") and not f["verificacion"].startswith("verificada")


def tema_de_nombre(nombre: str, tipo: str) -> str:
    """«clave-p012-textual-escala-urbana» → «escala urbana» (el frontmatter no guarda el tema: lo lleva el nombre, sin
    tildes; sirve para buscar, no para mostrarlo)."""
    marca = f"-{tipo}-"
    return nombre.split(marca, 1)[1].replace("-", " ") if marca in nombre else ""


def leer_todas(repo: Path, titulos: dict) -> tuple[list[dict], list[dict]]:
    """(fichas, escritos): las de cada escrito de escritura y las canónicas, con lo que la ventana pinta. `titulos` es
    {calibre_id: título} del catálogo."""
    from biblioteca_app.controladores.fichado import _consulta
    c = _consulta()
    escritos = c.escritos()
    salida = []
    for e in escritos:
        try:
            lista = c.fichas(e["carpeta"])
        except (SystemExit, OSError, ValueError):
            continue
        for f in lista:
            tipo = f["tipo"] or "fuente"
            cid = str(f.get("calibre_id") or "")
            cita = (f.get("parafrasis") or f["texto"]) if tipo == "parafrasis" else f["texto"]   # de una paráfrasis, la paráfrasis
            salida.append({"clave": f"{e['proyecto']}/{f['nombre']}", "tipo": tipo, "tipoTexto": TIPOS.get(tipo, tipo),
                           "cita": cita, "literal": f["texto"], "obra": titulos.get(cid) or f.get("clave") or "sin obra", "calibreId": cid,
                           "pagina": f["pagina"], "categoria": f["categoria"], "tema": f.get("tema") or "", "temaNombre": tema_de_nombre(f["nombre"], tipo),
                           "verificacion": f["verificacion"] or "", "escrito": e["titulo"], "principal": e.get("principal") or "",
                           "insertar": f["insertar"], "archivo": f["archivo"]})
    for f in datos.fichas(repo):
        cid = str(f.get("calibre_id") or "")
        salida.append({"clave": f"catalogacion/{Path(f['ruta']).stem}", "tipo": "catalogacion", "tipoTexto": TIPOS["catalogacion"],
                       "cita": "", "literal": "", "obra": titulos.get(cid) or f.get("titulo") or f["ficha"], "calibreId": cid, "pagina": "",
                       "categoria": "", "tema": "", "temaNombre": "", "verificacion": f.get("verificacion") or "", "escrito": "",
                       "principal": "", "insertar": "", "archivo": f["ruta"]})
    for f in salida:
        f["cotejo"] = cotejo(f["verificacion"]) if f["tipo"] != "fuente" else ""      # la de fuente no se coteja
        f["porRevisar"] = por_revisar(f)
        f["detalle"] = " · ".join(x for x in (f["obra"] if f["cita"] else "", f"p. {f['pagina']}" if f["pagina"] else "", f["tipoTexto"],
                                              f["categoria"], f["cotejo"], f["escrito"]) if x)
    return salida, escritos



def pregunta_de(f: dict) -> str:
    """La pista de recuperación de una ficha (§9.9): una pregunta que se responde sin mirar, no un rótulo. Con tema,
    «¿Qué sostiene la obra sobre «tema»?» (en una textual, «con sus palabras»); sin tema, la categoría como guía."""
    tema = (f.get("tema") or "").strip()
    textual = (f.get("tipoTexto") or "").lower().startswith("textual")
    if tema:
        return f"¿Qué dice la obra, con sus palabras, sobre «{tema}»?" if textual else f"¿Qué sostiene la obra sobre «{tema}»?"
    guia = (f.get("categoria") or f.get("tipoTexto") or "esta ficha").strip()
    return f"{guia}: ¿qué sostiene la obra en esta página?"

class Fichas(QObject):
    cambiado = Signal()                 # la lista, los filtros y sus cuentas
    repasoCambiado = Signal()           # la tarjeta del repaso y lo que queda hoy
    aviso = Signal(str, str)
    _listas = Signal("QVariantList", "QVariantList")

    def __init__(self, libros, consola, repo: Path = datos.REPO, parent=None, en_hilo: bool = True):
        super().__init__(parent)
        self.libros, self.consola, self.repo = libros, consola, Path(repo)
        self._en_hilo = en_hilo
        self._todas: list[dict] = []
        self._escritos: list[dict] = []
        self._filtro = "todas"
        self._busqueda = ""
        self._modo = "lista"
        self._cargando = False
        self._actual = ""
        self._cola: list[str] = []
        self._mostrada = False
        self._proxima: int | None = None
        self._listas.connect(self._poner)
        self.recargar()

    # ------------------------------------------------------------------ leer
    @Slot()
    def recargar(self) -> None:
        """Relee las fichas de los escritos y las canónicas (en un hilo: recorre todo escritura/)."""
        titulos = {str(l["id"]): l["titulo"] for l in getattr(self.libros, "_libros", [])}
        self._cargando = True
        self.cambiado.emit()

        def trabajo():
            try:
                fichas, escritos = leer_todas(self.repo, titulos)
            except Exception as e:  # noqa: BLE001 — sin escritura o con una ficha rota: se dice, no se cae
                self.consola.registrar("warn", f"Fichas: {e}")
                fichas, escritos = [], []
            self._listas.emit(fichas, escritos)
        if self._en_hilo:
            threading.Thread(target=trabajo, name="fichas", daemon=True).start()
        else:
            trabajo()

    def _poner(self, fichas: list, escritos: list) -> None:
        self._todas, self._escritos = [dict(f) for f in fichas], [dict(e) for e in escritos]
        self._cargando = False
        self._armar_cola()
        self.cambiado.emit()

    @Property(bool, notify=cambiado)
    def cargando(self) -> bool:
        return self._cargando

    @Property(bool, notify=cambiado)
    def leidas(self) -> bool:
        """Ya se leyeron una vez (Inicio no cuenta lo que aún no sabe)."""
        return not self._cargando and (bool(self._todas) or bool(self._escritos))

    def escritos(self) -> list[dict]:
        return self._escritos

    def todas(self) -> list[dict]:
        return self._todas

    # ------------------------------------------------------------------ la lista y sus filtros
    def _cumple(self, f: dict, filtro: str) -> bool:
        if filtro == "revisar":
            return f["porRevisar"]
        return filtro == "todas" or f["tipo"] == filtro

    @Property("QVariantList", notify=cambiado)
    def filtros(self) -> list:
        return [{"clave": k, "texto": t, "n": sum(1 for f in self._todas if self._cumple(f, k))} for k, t in FILTROS]

    @Property(str, notify=cambiado)
    def filtro(self) -> str:
        return self._filtro

    @Slot(str)
    def fijarFiltro(self, clave: str) -> None:
        if clave in dict(FILTROS) and (clave != self._filtro or self._modo != "lista"):
            self._filtro, self._modo = clave, "lista"
            self.cambiado.emit()

    @Slot(str)
    def buscar(self, texto: str) -> None:
        texto = (texto or "").strip().lower()
        if texto != self._busqueda:
            self._busqueda = texto
            self.cambiado.emit()

    @Property(str, notify=cambiado)
    def busqueda(self) -> str:
        return self._busqueda

    @Property("QVariantList", notify=cambiado)
    def lista(self) -> list:
        palabras = self._busqueda.split()
        salida = []
        for f in self._todas:
            if not self._cumple(f, self._filtro):
                continue
            heno = " ".join((f["cita"], f["obra"], f["categoria"], f["tema"], f["temaNombre"], f["escrito"])).lower()
            if all(p in heno for p in palabras):
                salida.append(f)
        return salida

    @Property(int, notify=cambiado)
    def porRevisar(self) -> int:
        return sum(1 for f in self._todas if f["porRevisar"])

    @Property(str, notify=cambiado)
    def actual(self) -> str:
        return self._actual

    @Slot(str)
    def elegir(self, clave: str) -> None:
        """La ficha elegida: su libro pasa a ser el del catálogo (lo que «Nueva ficha» y «Estudiar con la IA» usan)."""
        self._actual = clave
        f = next((x for x in self._todas if x["clave"] == clave), None)
        if f and f["calibreId"] and self.libros is not None:
            self.libros.fijarId(f["calibreId"])
        self.cambiado.emit()

    @Slot(str)
    def abrirEnLatex(self, principal: str) -> None:
        if self.libros is not None:
            self.libros.abrirEnLatex(principal)

    @Slot(str)
    def abrirArchivo(self, ruta: str) -> None:
        if ruta and self.libros is not None:
            self.libros.abrirFicha(ruta)

    @Slot(str)
    def copiar(self, texto: str) -> None:
        if texto:
            QGuiApplication.clipboard().setText(texto)
            self.aviso.emit("Copiado: pégalo en LaTeX Studio.", "positivo")

    # ------------------------------------------------------------------ el repaso (Leitner, §9.9)
    def _de_repaso(self) -> list[dict]:
        return [f for f in self._todas if f["tipo"] in DE_REPASO and f["cita"]]

    def _armar_cola(self, hoy: date | None = None) -> None:
        r = _repaso()
        claves = [f["clave"] for f in self._de_repaso()]
        try:
            self._cola = r.para_hoy(claves, hoy=hoy)
            self._proxima = r.proxima(claves, hoy=hoy)
        except Exception as e:  # noqa: BLE001 — una base del repaso ilegible: sin repaso, con aviso
            self.consola.registrar("warn", f"Repaso: {e}")
            self._cola, self._proxima = [], None
        self._mostrada = False
        self.repasoCambiado.emit()

    @Property(str, notify=cambiado)
    def modo(self) -> str:
        return self._modo

    @Slot(str)
    def fijarModo(self, modo: str) -> None:
        if modo in ("lista", "repaso") and modo != self._modo:
            self._modo = modo
            self.cambiado.emit()

    @Property(int, notify=repasoCambiado)
    def paraHoy(self) -> int:
        return len(self._cola)

    @Property(str, notify=repasoCambiado)
    def resumenRepaso(self) -> str:
        """«2 por repasar hoy · próximas en 3 días» (lo que se sabe; sin fichas de repaso, nada)."""
        partes = []
        if self._de_repaso():
            partes.append(f"{len(self._cola)} por repasar hoy")
        if self._proxima is not None:
            partes.append(f"próximas en {self._proxima} día" + ("" if self._proxima == 1 else "s"))
        return " · ".join(partes)

    @Property("QVariantMap", notify=repasoCambiado)
    def tarjeta(self) -> dict:
        """La ficha que toca: la pregunta (categoría o tema, y la obra), su cita (oculta hasta «Mostrar») y su caja."""
        if not self._cola:
            return {"hay": False}
        clave = self._cola[0]
        f = next((x for x in self._todas if x["clave"] == clave), None)
        if f is None:
            return {"hay": False}
        e = _repaso().estado([clave]).get(clave)
        return {"hay": True, "clave": clave, "pregunta": pregunta_de(f), "tema": f["categoria"] if f["tema"] else "",
                "obra": f["obra"] + (f", p. {f['pagina']}" if f["pagina"] else ""), "cita": f["cita"], "tipo": f["tipoTexto"],
                "caja": e["caja"] if e else 1, "nueva": e is None, "escrito": f["escrito"]}

    @Property(bool, notify=repasoCambiado)
    def mostrada(self) -> bool:
        return self._mostrada

    @Slot()
    def mostrar(self) -> None:
        if self._cola and not self._mostrada:
            self._mostrada = True
            self.repasoCambiado.emit()

    @Slot(bool)
    def responder(self, sabia: bool) -> None:
        """«La sabía» (sube una caja) o «Repasar luego» (vuelve a la caja 1); se escribe en la base del repaso."""
        if not self._cola:
            return
        clave = self._cola[0]
        try:
            r = _repaso().responder(clave, bool(sabia), aplicar=True)
        except Exception as e:  # noqa: BLE001 — se dice en la ventana
            self.aviso.emit(f"No se pudo guardar el repaso: {e}", "error")
            return
        dias = (date.fromisoformat(r["proxima"]) - date.today()).days
        self.consola.registrar("info", f"Repaso: {clave} → caja {r['caja']} (vuelve en {dias} días)")
        self._armar_cola()
