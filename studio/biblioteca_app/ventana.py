"""La ventana de Biblioteca Studio: el marco común de los studios (gui-comun) sobre las suites de este repo.

Inicio (cifras del índice, el estado de Calibre y Zotero y un buscador de libros), una página por grupo de acciones
(`acciones.PAGINAS`: Entrada, Adquirir, Catalogar y verificar, Sincronizar, Fichas y lecturas, Manifiestos), la
página de un libro (la abren los complementos con `biblioteca-studio://libro/<id>`) y la de la puerta. Cada acción
corre su CLI en la consola; «Aplicar» se apaga mientras esté abierta la aplicación en la que escribe.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from gui_comun.diseno import clase, icono_trazo, variante
from gui_comun.theming import aplicar_tema, disenador_de
from gui_comun.widgets.console_dock import ConsoleDock
from gui_comun.widgets.marco import montar_studio
from gui_comun.widgets.paleta import Comando
from gui_comun.widgets.tarjetas import (Cifra, ListaConVacio, Tarjeta, encabezado, pagina_desplazable,
                                        rejilla_pareja, seccion)
from gui_comun.workers.process_worker import ProcessWorker

from biblioteca_app.acciones import PAGINAS, REPO, abiertas, candado_ocupado

APP_VERSION = "1.0.0"
ACENTO = "sepia"
LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v16M8 4v16M12 5l4 15M17 4l3 16"/></svg>')
NOMBRE_BASE = {"calibre": "Calibre", "zotero": "Zotero"}


def _env():
    sys.path.insert(0, str(REPO / "lib"))
    from indice import _env as env  # noqa: E402  el mismo cargador de core/env que el índice
    return env()


def _hex(nombre: str) -> str:
    return "_hex_-" + nombre.encode("utf-8").hex()


class Ajustes:
    def __init__(self) -> None:
        from PySide6.QtCore import QSettings
        self.q = QSettings()

    def theme(self) -> str:
        return str(self.q.value("ui/tema", "sistema"))

    def set_theme(self, tema: str) -> None:
        self.q.setValue("ui/tema", tema)


class TarjetaAccion(Tarjeta):
    """Una acción: qué hace, lo que pide (si pide algo) y sus botones «Simular» y «Aplicar»."""

    def __init__(self, ventana, accion):
        super().__init__()
        self.ventana, self.a = ventana, accion
        titulo = QLabel(accion.titulo)
        titulo.setStyleSheet("font-weight: 600; font-size: 14px;")
        self.cuerpo.addWidget(titulo)
        desc = clase(QLabel(accion.descripcion), "tenue")
        desc.setWordWrap(True)
        self.cuerpo.addWidget(desc)
        self.valor = None
        if accion.entrada:
            fila = QHBoxLayout()
            self.valor = QLineEdit(str(REPO / accion.defecto) if accion.defecto else "")
            self.valor.setPlaceholderText(accion.etiqueta)
            fila.addWidget(self.valor, 1)
            if accion.entrada in ("carpeta", "archivo"):
                b = variante(QPushButton("…"), "fantasma")
                b.setFixedWidth(40)
                b.clicked.connect(self._elegir)
                fila.addWidget(b)
            self.cuerpo.addLayout(fila)
        botones = QHBoxLayout()
        self.aviso = clase(QLabel(""), "tenue")
        botones.addWidget(self.aviso, 1)
        if accion.aplicar is None:
            self.b_correr = variante(QPushButton("Ejecutar"), "primario")
            self.b_correr.clicked.connect(lambda: self._correr(False))
            botones.addWidget(self.b_correr)
            self.b_aplicar = None
        else:
            b_sim = QPushButton("Simular")
            b_sim.clicked.connect(lambda: self._correr(False))
            self.b_aplicar = variante(QPushButton("Aplicar"), "primario")
            self.b_aplicar.clicked.connect(lambda: self._correr(True))
            botones.addWidget(b_sim)
            botones.addWidget(self.b_aplicar)
        self.cuerpo.addLayout(botones)

    def refrescar(self, abiertas_ahora: set[str]) -> None:
        bloquean = [NOMBRE_BASE[b] for b in self.a.bases if b in abiertas_ahora]
        if self.b_aplicar is not None:
            self.b_aplicar.setEnabled(not bloquean)
            self.b_aplicar.setToolTip(f"Cierra {' y '.join(bloquean)} para aplicar" if bloquean else
                                      "Escribe por la puerta (candado y respaldo)")
        self.aviso.setText(f"Cierra {' y '.join(bloquean)} para aplicar" if bloquean else "")

    def _elegir(self) -> None:
        inicio = self.valor.text() or str(REPO)
        if self.a.entrada == "carpeta":
            ruta = QFileDialog.getExistingDirectory(self, self.a.etiqueta, inicio)
        else:
            ruta, _ = QFileDialog.getOpenFileName(self, self.a.etiqueta, inicio)
        if ruta:
            self.valor.setText(ruta)

    def _correr(self, aplicar: bool) -> None:
        valor = self.valor.text().strip() if self.valor else ""
        if self.a.entrada and not valor:
            self.ventana.marco.avisar("Falta un dato", f"Escribe {self.a.etiqueta}.", "aviso")
            return
        if aplicar and QMessageBox.question(self.ventana.ui, self.a.titulo, f"¿Aplicar «{self.a.titulo}»? Escribe por "
                                            "la puerta: candado y respaldo verificado antes de tocar nada.") != QMessageBox.Yes:
            return
        self.ventana.correr(self.a.argv(aplicar, valor), f"{self.a.titulo}{'' if aplicar else ' (simulación)'}"
                            if self.a.aplicar is not None else self.a.titulo)


class PaginaAcciones(QWidget):
    def __init__(self, ventana, pagina):
        super().__init__()
        contenido = QWidget()
        raiz = QVBoxLayout(contenido)
        raiz.setSpacing(12)
        raiz.addWidget(encabezado(pagina.nombre, pagina.para_que))
        rejilla = rejilla_pareja(2)
        self.tarjetas = []
        for i, a in enumerate(pagina.acciones):
            t = TarjetaAccion(ventana, a)
            self.tarjetas.append(t)
            rejilla.addWidget(t, i // 2, i % 2)
        raiz.addLayout(rejilla)
        raiz.addStretch(1)
        fuera = QVBoxLayout(self)
        fuera.setContentsMargins(0, 0, 0, 0)
        fuera.addWidget(pagina_desplazable(contenido))


class PaginaLibro(QWidget):
    """Un libro del índice: portada, datos, claves y sus fichas; abrirlo en Calibre, Zotero, el PDF o su nota."""

    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self.id = ""
        self.d: dict = {}
        contenido = QWidget()
        raiz = QVBoxLayout(contenido)
        raiz.setSpacing(14)
        cabeza = QHBoxLayout()
        atras = variante(QPushButton(icono_trazo("volver"), " Volver"), "fantasma")
        atras.clicked.connect(lambda: ventana.navigate("dashboard"))
        cabeza.addWidget(atras, 0, Qt.AlignTop)
        self.portada = QLabel()
        self.portada.setFixedSize(120, 170)
        self.portada.setAlignment(Qt.AlignCenter)
        cabeza.addWidget(self.portada, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        self.titulo = QLabel()
        self.titulo.setObjectName("tituloPagina")
        self.titulo.setWordWrap(True)
        self.autores = QLabel()
        self.autores.setObjectName("subtituloPagina")
        self.autores.setWordWrap(True)
        self.datos = clase(QLabel(), "suave")
        self.datos.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.datos.setWordWrap(True)
        for w in (self.titulo, self.autores, self.datos):
            textos.addWidget(w)
        botones = QGridLayout()                  # en rejilla de tres: en una fila no caben en una ventana estrecha
        botones.setHorizontalSpacing(8)
        botones.setVerticalSpacing(8)
        for i, (texto, icono, accion) in enumerate((
                ("Abrir en Calibre", "libro", self._calibre), ("Abrir en Zotero", "abrir", self._zotero),
                ("Abrir el archivo", "documento", self._archivo), ("Nota de lectura", "texto", self._nota),
                ("Copiar la clave", "receta", self._copiar))):
            b = QPushButton(icono_trazo(icono), f" {texto}")
            b.clicked.connect(accion)
            botones.addWidget(b, i // 3, i % 3)
        botones.setColumnStretch(3, 1)
        textos.addLayout(botones)
        textos.addStretch(1)
        cabeza.addLayout(textos, 1)
        raiz.addLayout(cabeza)
        caja = Tarjeta("Fichas que lo citan · doble clic para abrir")
        self.fichas = ListaConVacio("Ninguna ficha cita este libro.")
        self.fichas.lista.itemDoubleClicked.connect(
            lambda it: QDesktopServices.openUrl(QUrl.fromLocalFile(str(REPO / it.text()))))
        caja.cuerpo.addWidget(self.fichas, 1)
        caja.setMinimumHeight(200)
        raiz.addWidget(caja, 1)
        fuera = QVBoxLayout(self)
        fuera.setContentsMargins(0, 0, 0, 0)
        fuera.addWidget(pagina_desplazable(contenido))

    def mostrar(self, libro_id: str) -> bool:
        d = self.ventana.indice.get("libros", {}).get(str(libro_id))
        if not d:
            return False
        self.id, self.d = str(libro_id), d
        self.titulo.setText(d["titulo"])
        self.autores.setText(" · ".join(d["autores"]) or "sin autor")
        nota = Path(d["nota"]) if d.get("nota") else None
        self.datos.setText(f"Calibre {self.id} · Zotero {d['zotero_key'] or '—'} · clave {d['clave'] or '—'}\n"
                           f"Nota de lectura: {'sí' if nota and nota.is_file() else 'todavía no'} · "
                           f"{len(d['fichas'])} ficha(s)")
        portada = Path(self.ventana.indice["biblioteca"]) / d["carpeta"] / "cover.jpg"
        pix = QPixmap(str(portada)) if portada.is_file() else QPixmap()
        if not pix.isNull():
            self.portada.setPixmap(pix.scaled(QSize(120, 170), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.portada.setPixmap(icono_trazo("libro").pixmap(64, 64))
        self.fichas.lista.clear()
        for f in d["fichas"]:
            self.fichas.lista.addItem(QListWidgetItem(icono_trazo("documento"), f))
        self.fichas.actualizar()
        return True

    def _calibre(self) -> None:
        nombre = Path(self.ventana.indice["biblioteca"]).name
        QDesktopServices.openUrl(QUrl(f"calibre://show-book/{_hex(nombre)}/{self.id}"))

    def _zotero(self) -> None:
        if self.d.get("zotero_key"):
            QDesktopServices.openUrl(QUrl(f"zotero://select/library/items/{self.d['zotero_key']}"))
        else:
            self.ventana.marco.avisar("Sin clave de Zotero", "Este libro todavía no está enlazado.", "aviso")

    def _archivo(self) -> None:
        if self.d.get("formatos"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.ventana.indice["biblioteca"]) / self.d["formatos"][0])))

    def _nota(self) -> None:
        nota = Path(self.d.get("nota") or "")
        if nota.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(nota)))
        else:
            self.ventana.marco.avisar("Todavía no hay nota de lectura", "La crean el complemento de KOReader o Zotero "
                                      "Integration (Obsidian, Ctrl+R).", "info")

    def _copiar(self) -> None:
        if self.d.get("clave"):
            QGuiApplication.clipboard().setText(self.d["clave"])
            self.ventana.marco.avisar("Clave copiada", self.d["clave"], "ok")


class Ventana:
    """Envoltorio de la QMainWindow con la forma que `gui_comun.widgets.marco.montar_studio` espera."""

    def __init__(self) -> None:
        app = QApplication.instance()
        self.settings = Ajustes()
        disenador = disenador_de(app) or aplicar_tema(app, self.settings.theme(), acento=ACENTO)
        self.env = _env()
        self.indice = self._leer_indice()
        self.ui = QMainWindow()
        self.ui.setWindowTitle(f"Biblioteca Studio {APP_VERSION}")
        central = QWidget()
        fila = QHBoxLayout(central)
        self.ui.sidebar = QListWidget()
        self.ui.stack = QStackedWidget()
        fila.addWidget(self.ui.sidebar)
        fila.addWidget(self.ui.stack, 1)
        self.ui.setCentralWidget(central)
        self.ui.statusbar = self.ui.statusBar()
        self.console = ConsoleDock(self.ui)
        self.ui.addDockWidget(Qt.BottomDockWidgetArea, self.console)
        self._workers: list = []

        self.controllers: dict[str, SimpleNamespace] = {}
        self._page_order: list[str] = []
        self.paginas_acciones: list[PaginaAcciones] = []
        self._pagina("dashboard", "Inicio", "inicio", self._crear_inicio())
        for p in PAGINAS:
            w = PaginaAcciones(self, p)
            self.paginas_acciones.append(w)
            self._pagina(p.id, p.nombre, p.icono, w)
        self._pagina("puerta", "Puerta", "candado", self._crear_puerta())
        self.libro = PaginaLibro(self)
        self.ui.stack.addWidget(self.libro)
        self.ui.sidebar.currentRowChanged.connect(self._al_cambiar)
        self.ui.sidebar.setCurrentRow(0)

        self.marco = montar_studio(self, nombre="Biblioteca Studio", subtitulo="Calibre · Zotero · KOReader",
                                   logo_svg=LOGO, disenador=disenador, primarios={}, peligro=())
        for p in PAGINAS:
            for a in p.acciones:
                self.marco.comandos_extra.append(
                    Comando(a.titulo, lambda pid=p.id: self.navigate(pid), grupo=p.nombre, icono=icono_trazo(p.icono),
                            palabras=a.descripcion))
        self.reloj = QTimer(self.ui, interval=4000, timeout=self._refrescar_estado)
        self.reloj.start()
        self._refrescar_estado()

    # ----------------------------------------------------------------------------------------------- páginas
    def _crear_inicio(self) -> QWidget:
        contenido = QWidget()
        raiz = QVBoxLayout(contenido)
        raiz.setSpacing(14)
        raiz.addWidget(encabezado("Inicio", "Una sola biblioteca: Calibre guarda los archivos, Zotero manda en citas y "
                                            "metadatos, KOReader lleva la lectura. Aquí se ven las tres."))
        libros = list(self.indice.get("libros", {}).values())
        cifras = rejilla_pareja(4)
        self.cifras = [Cifra("Libros en Calibre", f"{len(libros):,}".replace(",", " "), "según el índice"),
                       Cifra("Enlazados con Zotero", f"{sum(bool(d['zotero_key']) for d in libros):,}".replace(",", " "),
                             "con su clave para citar"),
                       Cifra("Con ficha", f"{sum(bool(d['fichas']) for d in libros):,}".replace(",", " "),
                             "del Método Documental"),
                       Cifra("Índice", (self.indice.get("generado") or "—")[:10], "lo que leen los complementos")]
        for i, c in enumerate(self.cifras):
            cifras.addWidget(c, 0, i)
        raiz.addLayout(cifras)
        self.estado = Tarjeta("Ahora mismo")
        self.lbl_estado = QLabel()
        self.lbl_estado.setWordWrap(True)
        self.estado.cuerpo.addWidget(self.lbl_estado)
        raiz.addWidget(self.estado)
        raiz.addSpacing(4)
        raiz.addWidget(seccion("Buscar un libro"))
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Título, autor, clave para citar o número de Calibre…")
        self.buscador.setClearButtonEnabled(True)
        clase(self.buscador, "busqueda")
        self.buscador.textChanged.connect(self._buscar)
        raiz.addWidget(self.buscador)
        self.resultados = ListaConVacio("Escribe para buscar entre los libros de la biblioteca.")
        self.resultados.lista.itemActivated.connect(lambda it: self.abrir_libro(it.data(Qt.UserRole)))
        self.resultados.lista.itemDoubleClicked.connect(lambda it: self.abrir_libro(it.data(Qt.UserRole)))
        caja = Tarjeta()
        caja.cuerpo.addWidget(self.resultados, 1)
        caja.setMinimumHeight(260)
        raiz.addWidget(caja, 1)
        return pagina_desplazable(contenido)

    def _crear_puerta(self) -> QWidget:
        contenido = QWidget()
        raiz = QVBoxLayout(contenido)
        raiz.setSpacing(14)
        raiz.addWidget(encabezado("Puerta", "Una sola puerta escribe en Calibre y en Zotero: con la aplicación cerrada, "
                                            "con candado y con respaldo verificado. Aquí se ve su estado y cómo deshacer."))
        self.lbl_puerta = QLabel()
        self.lbl_puerta.setWordWrap(True)
        t = Tarjeta("Candados y aplicaciones")
        t.cuerpo.addWidget(self.lbl_puerta)
        raiz.addWidget(t)
        resp = Tarjeta("Respaldos de cada escritura · doble clic para abrir la carpeta")
        self.respaldos = ListaConVacio("Sin respaldos todavía (el disco de respaldos puede no estar montado).")
        self.respaldos.lista.itemDoubleClicked.connect(
            lambda it: QDesktopServices.openUrl(QUrl.fromLocalFile(it.data(Qt.UserRole))))
        resp.cuerpo.addWidget(self.respaldos, 1)
        deshacer = clase(QLabel("Para deshacer una escritura: cierra la aplicación y copia su respaldo sobre la base "
                                "(metadata.db o zotero.sqlite). La guía del repo lo detalla (CLAUDE.md, «Deshacer una "
                                "escritura»)."), "tenue")
        deshacer.setWordWrap(True)
        resp.cuerpo.addWidget(deshacer)
        resp.setMinimumHeight(260)
        raiz.addWidget(resp, 1)
        timers = Tarjeta("Tareas automáticas")
        self.lbl_timers = clase(QLabel(), "suave")
        self.lbl_timers.setWordWrap(True)
        self.lbl_timers.setTextInteractionFlags(Qt.TextSelectableByMouse)
        timers.cuerpo.addWidget(self.lbl_timers)
        raiz.addWidget(timers)
        return pagina_desplazable(contenido)

    # ----------------------------------------------------------------------------------------------------- API
    def show(self) -> None:
        self.ui.show()

    def navigate(self, page_id: str) -> None:
        if page_id in self._page_order:
            self.ui.sidebar.setCurrentRow(self._page_order.index(page_id))

    def abrir_libro(self, libro_id) -> None:
        if self.libro.mostrar(str(libro_id)):
            self.ui.stack.setCurrentWidget(self.libro)
            self.ui.show()
            self.ui.raise_()
            self.ui.activateWindow()
        else:
            self.marco.avisar(f"No está el libro {libro_id}", "Actualiza el índice (Sincronizar).", "aviso")

    def abrir_url(self, url: str) -> None:
        """`biblioteca-studio://libro/<id>`: lo que piden los complementos de Calibre, KOReader y Zotero."""
        partes = url.split("://", 1)[-1].strip("/").split("/")
        if len(partes) >= 2 and partes[0] == "libro":
            self.abrir_libro(partes[1])

    def correr(self, argv: list[str], nombre: str) -> None:
        worker = ProcessWorker(argv, cwd=str(REPO), description=nombre)
        self.console.attach_process_worker(worker, nombre)
        self.console.show()                   # aquí lo que importa es el informe: la consola se abre sola
        worker.finished_with_code.connect(lambda _c: self._refrescar_estado())
        if argv[-1:] == ["--aplicar"] and "indice.py" in argv[1]:
            worker.finished_with_code.connect(lambda _c: self._recargar_indice())
        self._workers.append(worker)
        worker.start()

    def run_function_worker(self, worker, nombre: str) -> None:   # lo pide el marco
        self.console.attach_function_worker(worker, nombre)
        self._workers.append(worker)
        worker.start()

    # -------------------------------------------------------------------------------------------------- privado
    def _leer_indice(self) -> dict:
        sys.path.insert(0, str(REPO / "lib"))
        from indice import ruta_indice
        ruta = ruta_indice()
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"libros": {}, "biblioteca": str(self.env.BIBLIOTECA_DIR)}

    def _recargar_indice(self) -> None:
        self.indice = self._leer_indice()
        self._buscar(self.buscador.text())
        self.marco.avisar("Índice actualizado", f"{len(self.indice.get('libros', {}))} libros", "ok")

    def _buscar(self, texto: str) -> None:
        texto = texto.strip().lower()
        lista = self.resultados.lista
        lista.clear()
        if len(texto) >= 2:
            for b, d in self.indice.get("libros", {}).items():
                if texto == b or texto in d["titulo"].lower() or texto in d["clave"].lower() or \
                        any(texto in a.lower() for a in d["autores"]):
                    item = QListWidgetItem(icono_trazo("libro"), f"{d['titulo']}\n{' · '.join(d['autores'][:2])} · "
                                           f"Calibre {b}" + (f" · {d['clave']}" if d["clave"] else ""))
                    item.setData(Qt.UserRole, b)
                    lista.addItem(item)
                    if lista.count() >= 60:
                        break
        self.resultados.vacio.setText("Ningún libro coincide." if len(texto) >= 2 else
                                      "Escribe para buscar entre los libros de la biblioteca.")
        self.resultados.actualizar()

    def _refrescar_estado(self) -> None:
        ahora = abiertas()
        for p in self.paginas_acciones:
            for t in p.tarjetas:
                t.refrescar(ahora)
        apps = " · ".join(f"{n}: {'abierto (no se aplica en él)' if b in ahora else 'cerrado'}"
                          for b, n in NOMBRE_BASE.items())
        candados = " · ".join(f"candado de {n}: {'ocupado' if candado_ocupado(getattr(self.env, 'LOCK_' + b.upper(), '')) else 'libre'}"
                              for b, n in NOMBRE_BASE.items())
        self.lbl_estado.setText(f"{apps}\n{candados}")
        self.lbl_puerta.setText(f"{apps}\n{candados}")

    def _pintar_puerta(self) -> None:
        base = Path(getattr(self.env, "RESPALDOS_DIR", "")) / "biblioteca" / "puerta"
        self.respaldos.lista.clear()
        if base.is_dir():
            for d in sorted(base.iterdir()):
                archivos = sorted((p for p in d.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime)
                ultimo = archivos[-1] if archivos else None
                from datetime import datetime
                cuando = datetime.fromtimestamp(ultimo.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if ultimo else "—"
                item = QListWidgetItem(icono_trazo("carpeta"), f"{d.name}\n{len(archivos)} respaldo(s) · el último: {cuando}")
                item.setData(Qt.UserRole, str(d))
                self.respaldos.lista.addItem(item)
        self.respaldos.actualizar()
        try:
            salida = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--no-pager"], capture_output=True,
                                    text=True, timeout=5).stdout
            filas = [l for l in salida.splitlines() if any(k in l for k in ("koreader", "ecosistema", "biblioteca"))]
            self.lbl_timers.setText("\n".join(filas) or "Ninguna tarea automática de la biblioteca instalada "
                                    "(systemd/instalar.sh).")
        except (OSError, subprocess.SubprocessError):
            self.lbl_timers.setText("No se pudo consultar systemd.")

    def _pagina(self, id_: str, nombre: str, icono: str, widget) -> None:
        self.controllers[id_] = SimpleNamespace(widget=widget)
        self._page_order.append(id_)
        self.ui.stack.addWidget(widget)
        self.ui.sidebar.addItem(QListWidgetItem(icono_trazo(icono), nombre))

    def _al_cambiar(self, fila: int) -> None:
        self.ui.stack.setCurrentIndex(fila)
        if self._page_order[fila] == "puerta":
            self._pintar_puerta()

    def _open_preferences(self) -> None:
        self.navigate("puerta")

    def _about(self) -> None:
        QMessageBox.about(self.ui, "Acerca de Biblioteca Studio",
                          f"<b>Biblioteca Studio</b> {APP_VERSION}<br><br>La biblioteca del ecosistema: Calibre, Zotero "
                          "y KOReader con el Método Documental (adquirir, ingerir, catalogar, fichar, citar).<br><br>"
                          "Cada botón corre una suite de <code>scripts-biblioteca</code>; la escritura pasa por una sola "
                          "puerta, con la aplicación cerrada, candado y respaldo.<br><br>Edison Achalma")
