"""biblioteca_app/aplicacion.py — arma Biblioteca Studio: la aplicación (gui_comun.nucleo), los controladores, el proveedor
de portadas, el registro de acciones (menú, paleta, atajos, estados de operación) y carga `qml/Main.qml` (VentanaBase;
reingeniería del 2026-11-02, `docs/reingenieria.md`).

Toda operación existe una sola vez, aquí, en `Acciones`. Ctrl+1–4 las áreas (Catálogo, Bandejas, Método Documental,
Coherencia), Ctrl+F buscar, Ctrl+G cuadrícula o lista, F9 los filtros. Las operaciones de las suites son acciones
`op.<id>` que eligen la operación actual (y llevan a su etapa); correrla es siempre «Simular» (F5, la orden sin
`--aplicar`) o «Aplicar» (Ctrl+Intro, con `--aplicar`, tras confirmar con la orden exacta, las bases y los pasos de la
puerta). Abrir el documento y mostrarlo en Dolphin son de `escritorio` de la base. Python no construye interfaz; la
ventana no escribe en ninguna base: toda corrida es la CLI de una suite, por la única puerta (`lib/escribir.*`).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from gui_comun.acciones import Acciones, StandardKey
from gui_comun.consola import Consola
from gui_comun.miniaturas import ProveedorMiniaturas
from gui_comun.nucleo import Aplicacion
from gui_comun.qt import QObject, QStandardPaths, Signal, Slot
from gui_comun.tareas import Tareas

from biblioteca_app.controladores.ajustes import Ajustes
from biblioteca_app.controladores.espacio import Espacio
from biblioteca_app.controladores.etapas import Etapas
from biblioteca_app.controladores.libros import Libros
from biblioteca_app.controladores.operaciones import Operaciones
from biblioteca_app.controladores.puerta import Puerta
from biblioteca_app.servicios import datos
from biblioteca_app.servicios import operaciones as ops
from biblioteca_app.controladores.espacio import AREAS, VISTAS_DE

AREA_DE = {v: a for a, vs in VISTAS_DE.items() for v in vs}

APP_DIR = Path(__file__).resolve().parent
QML_DIR = APP_DIR / "qml"
RECURSOS_DIR = APP_DIR / "recursos"
REPO = ops.REPO
APP_ID = "biblioteca-studio"
NOMBRE = "Biblioteca Studio"
APP_VERSION = "3.0.0"
ORG_NAME = "EdisonAchalma"
APP_NAME = "BibliotecaStudio"             # el applicationName de QSettings de 1.x: las preferencias se conservan
SOCKET = "biblioteca-studio"              # una sola ventana: el enlace de los complementos va a la abierta
DESCRIPCION = ("Un gestor bibliográfico sobre la biblioteca de Calibre: el catálogo con portadas, la búsqueda por campo y los filtros "
               "por colección, autor, año y tipo; la ficha editorial de cada libro con su clave para citar, su estado en Zotero y su "
               "lectura en KOReader; las bandejas de trabajo y las etapas del Método Documental. No escribe por su cuenta: cada "
               "operación es la CLI de su suite, que simula con F5 y aplica con Ctrl+Intro por la única puerta de escritura, cuyos "
               "seis pasos (aplicación cerrada, candado, respaldo verificado, aplicar, integridad, liberar) se ven en la ventana.")
ACENTO = "sepia"                          # el icono del lanzador: la única marca del studio


def datos_lanzador() -> dict:
    return dict(app_id=APP_ID, nombre=NOMBRE, comentario="Calibre, Zotero y KOReader con el Método Documental: adquirir, catalogar, "
                "sincronizar y citar", orden=["/usr/bin/python3", str(APP_DIR.parent / "main.py")],
                logo_svg=(RECURSOS_DIR / "marca.svg").read_text(encoding="utf-8"), acento=ACENTO, categorias="Office;",
                esquema="biblioteca-studio", palabras="calibre;zotero;koreader;biblioteca;libros;citas;fichas;")


class Interfaz(QObject):
    """Lo que Python pide a QML (abrir un diálogo, enfocar el filtro, seleccionar una fila, ir a una pestaña)."""

    pedir = Signal(str, "QVariantMap")

    @Slot(str)
    def abrir(self, nombre: str) -> None:
        self.pedir.emit(nombre, {})


def cache_portadas() -> Path:
    """La caché de las miniaturas de las portadas (`$XDG_CACHE_HOME/biblioteca-studio/portadas/`); nunca la biblioteca."""
    base = (QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
            or str(Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "biblioteca-studio"))
    return Path(base) / "portadas"


def construir(app: Aplicacion, cache: Path | None = None, vigilar_puerta: bool = True, ruta_indice: Path | None = None,
              repo_datos: Path | None = None) -> dict:
    """Crea controladores y acciones, y los expone al QML. Devuelve lo creado (para las pruebas y las capturas).

    `repo_datos` (o la variable `BIBLIOTECA_STUDIO_DATOS`): de dónde se leen los ledgers, las fichas y la zona de entrada
    que las tablas listan; por omisión, este repo. Las operaciones corren siempre las suites de este repo."""
    env = datos.cargar_env()
    repo_datos = repo_datos or (Path(os.environ["BIBLIOTECA_STUDIO_DATOS"]) if os.environ.get("BIBLIOTECA_STUDIO_DATOS") else datos.REPO)
    consola = Consola()
    tareas = Tareas(consola)
    interfaz = Interfaz()
    ajustes = Ajustes()
    espacio = Espacio(consola, ajustes)
    puerta = Puerta(env, vigilar=vigilar_puerta)
    portadas = ProveedorMiniaturas(cache_portadas(), anchos={"": 220, "grande": 520})   # gui-comun 3.1 (antes, la copia propia)
    app.motor.addImageProvider("portadas", portadas)        # image://portadas/<id>[/grande]: las miniaturas de cover.jpg (B3)
    escritorio = app.escritorio
    libros = Libros(espacio, consola, env, ruta_indice=ruta_indice, escritorio=escritorio, repo=repo_datos, portadas=portadas)
    etapas = Etapas(espacio, libros, env, consola, repo=repo_datos)
    operaciones = Operaciones(espacio, puerta, consola, tareas, env, cache=cache)
    acciones = Acciones()
    acciones.estandar(NOMBRE, paneles=False)
    pedir = lambda que, **datos_: (lambda *_: interfaz.pedir.emit(que, datos_))

    def objetivo() -> str:
        """La ruta sobre la que actúan Abrir, Abrir su carpeta y Copiar ruta: el libro actual en Libros; si no, el elemento."""
        if espacio.area in ("catalogo", "bandejas"):
            return libros.ruta_archivo() or libros.rutaCarpeta
        return etapas.elementoRuta

    # --- Archivo
    acciones.registrar("archivo.abrir", "&Abrir", "document-open", None, "Archivo", habilitada=False, operacion="lectura",
                       al_disparar=lambda *_: escritorio.abrirConAplicacion(objetivo()), descripcion="El documento del libro o el elemento seleccionado, con su aplicación")
    acciones.registrar("archivo.carpeta", "Mostrar en &Dolphin", "system-file-manager", "Ctrl+Shift+O", "Archivo", habilitada=False, operacion="lectura",
                       al_disparar=lambda *_: escritorio.mostrarEnDolphin(objetivo()), descripcion="El documento del libro o el elemento, señalado en su carpeta")
    acciones.registrar("archivo.copiar", "Copiar &ruta", "edit-copy", None, "Archivo", habilitada=False, al_disparar=lambda *_: espacio.copiar(objetivo()))
    acciones.registrar("archivo.entrada", "Abrir la zona de &entrada", "document-import", None, "Archivo", operacion="lectura",
                       al_disparar=lambda *_: escritorio.abrirCarpeta(str(REPO / "entrada")), descripcion="La carpeta entrada/ del repo en Dolphin: ahí se deja lo que hay que ingerir")
    acciones.registrar("archivo.terminal", "Abrir &terminal en el repo", "utilities-terminal", "Shift+F4", "Archivo",
                       al_disparar=lambda *_: espacio.abrirTerminal(str(REPO)), descripcion="Una terminal en biblioteca-studio/: las mismas órdenes que corre la ventana")
    # --- Editar
    acciones.registrar("editar.filtrar", "&Buscar", "edit-find", StandardKey.Find, "Editar", al_disparar=pedir("buscar"),
                       descripcion="En el catálogo, título:, autor:, año: (o 1990-2000), serie:, etiqueta:, id:, clave:; en una etapa, filtra su tabla")
    acciones.registrar("editar.todo", "Seleccionar &todo", "edit-select-all", StandardKey.SelectAll, "Editar", al_disparar=pedir("seleccionar_todo"))
    # --- Ver: las áreas, la forma del catálogo, los filtros y las etapas
    for i, (a, t, icono) in enumerate(AREAS, start=1):
        acciones.registrar(f"ver.area.{a}", f"&{i} {t}", icono, f"Ctrl+{i}", "Ver › Área", marcable=True, al_disparar=lambda *_, n=a: espacio.fijarArea(n))
    acciones.registrar("ver.forma", "Ver como &lista", "view-list-details", "Ctrl+G", "Ver", marcable=True, marcada=libros.enLista,
                       al_disparar=lambda *_: libros.alternarForma(), descripcion="El catálogo en cuadrícula de portadas o en lista compacta")
    acciones.registrar("ver.filtros", "Mostrar u ocultar los &filtros", "view-filter", "F9", "Ver", al_disparar=pedir("filtros"),
                       descripcion="Colección, autor, año y tipo, a la izquierda del catálogo")
    for e in ops.ETAPAS:
        if e.id != "libros":
            acciones.registrar(f"ver.vista.{e.id}", e.nombre, e.icono, None, "Ver › Etapa", marcable=True,
                               al_disparar=lambda *_, n=e.id: (espacio.fijarVista(n), espacio.fijarArea(AREA_DE.get(n, "metodo"))), descripcion=e.para_que)
    acciones.registrar("ver.releer", "&Releer", "view-refresh", "F6", "Ver", al_disparar=lambda *_: releer(), operacion="lectura",
                       descripcion="Vuelve a leer la biblioteca (solo lectura), los ledgers, las fichas, los respaldos o los timers; el índice no se regenera")
    acciones.registrar("ver.vigilar", "&Vigilar la biblioteca de Calibre", "view-refresh-symbolic", None, "Ver", marcable=True,
                       marcada=libros.vigilar, al_disparar=lambda marcada: setattr(libros, "vigilar", bool(marcada)), operacion="lectura",
                       descripcion="Relee el catálogo (en solo lectura) cuando metadata.db cambia: Calibre o una suite escribieron")
    acciones.registrar("ver.indice", "Actualizar el &índice", "folder-sync", "Ctrl+R", "Ver", al_disparar=lambda *_: actualizar_indice(), operacion="lectura",
                       descripcion="lib/indice.py --aplicar: relee Calibre y Zotero en solo lectura y reescribe el índice que leen la ventana y los complementos")
    # --- Método: elegir cada operación (un submenú por etapa), simular, aplicar, cancelar
    for e in ops.ETAPAS:
        for o in e.operaciones:
            acciones.registrar(f"op.{o.id}", o.titulo.replace("&", "&&"), e.icono, None, f"Método › {e.nombre}",
                               al_disparar=lambda *_, i=o.id: operaciones.fijar(i), descripcion=o.descripcion)
    acciones.registrar("op.simular", "&Simular", "system-run", StandardKey.Refresh, "Método", al_disparar=operaciones.simular, operacion="simulacion",
                       descripcion="Corre la operación elegida sin --aplicar: la suite simula y la salida queda en el panel inferior y en la pestaña Plan")
    acciones.registrar("op.aplicar", "&Aplicar…", "dialog-ok-apply", "Ctrl+Return", "Método", habilitada=False, al_disparar=pedir("aplicar"),
                       operacion="escritura", consecuencias=lambda: operaciones.textoConfirmacion,
                       descripcion="Muestra la orden exacta, las bases que toca y los pasos de la puerta; si confirmas, corre con --aplicar")
    acciones.registrar("op.cancelar", "&Cancelar la operación", "process-stop", None, "Método", habilitada=False, al_disparar=operaciones.cancelar,
                       descripcion="Detiene la corrida en curso y el proceso que lanzó")
    # --- Libro (el libro actual de la vista Libros)
    acciones.registrar("libro.calibre", "Abrir en &Calibre", "folder-book", None, "Libro", habilitada=False, al_disparar=libros.abrirCalibre,
                       descripcion="calibre://show-book: el libro en la ventana de Calibre")
    acciones.registrar("libro.zotero", "Abrir en &Zotero", "bookmarks", None, "Libro", habilitada=False, al_disparar=libros.abrirZotero,
                       descripcion="zotero://select: el ítem enlazado en Zotero")
    acciones.registrar("libro.archivo", "Abrir el &documento", "document-open", None, "Libro", habilitada=False, al_disparar=libros.abrirArchivo,
                       operacion="lectura", descripcion="El primer formato del libro con su aplicación")
    acciones.registrar("libro.dolphin", "Mostrar en &Dolphin", "system-file-manager", None, "Libro", habilitada=False, al_disparar=libros.mostrarEnDolphin,
                       operacion="lectura", descripcion="El documento del libro señalado en su carpeta de la biblioteca")
    acciones.registrar("libro.nota", "&Nota de lectura", "document-edit", None, "Libro", habilitada=False, al_disparar=libros.abrirNota,
                       descripcion="La nota enlazada en «apuntes» o la de Zotero Integration (notas/<clave>.md), si existe")
    acciones.registrar("libro.copiar_clave", "Copiar la c&lave para citar", "edit-copy", "Ctrl+Shift+C", "Libro", habilitada=False,
                       al_disparar=libros.copiarClave, descripcion="La clave de Better BibTeX del libro, al portapapeles")
    acciones.registrar("libro.fichas", "Abrir su &ficha", "document-edit-verify", None, "Libro", habilitada=False,
                       al_disparar=lambda *_: libros.abrirFicha(libros.ficha.get("fichas", [{}])[0].get("ruta", "")),
                       descripcion="La ficha canónica del libro (catalogacion/fichas/)")
    # --- Herramientas
    acciones.registrar("herr.lanzador", "Instalar el acceso &directo", "application-x-executable", None, "Herramientas",
                       al_disparar=lambda *_: instalar_lanzador(), operacion="instalacion",
                       consecuencias="Escribe el lanzador .desktop, el icono y el esquema biblioteca-studio:// en la configuración de tu usuario (studio/install.sh).",
                       descripcion="studio/install.sh: el acceso directo del menú y el esquema biblioteca-studio:// de los complementos")
    # --- Ayuda
    acciones.registrar("ayuda.manual", "&Manual de Biblioteca Studio", "help-contents", StandardKey.HelpContents, "Ayuda",
                       operacion="lectura", al_disparar=lambda *_: escritorio.abrirConAplicacion(str(REPO / "studio" / "README.md")))
    acciones.registrar("ayuda.metodo", "El &Método Documental", "help-about", None, "Ayuda", al_disparar=lambda *_: abrir_metodo(),
                       descripcion="prompts/00 metodo/METODO_DOCUMENTAL.md: los diez pasos que ejecutan las suites")
    acciones.registrar("ayuda.operacion", "Manual de la &suite de la operación", "help-hint", None, "Ayuda", al_disparar=lambda *_: abrir_readme_suite(),
                       descripcion="El README de la suite a la que pertenece la operación elegida")

    acciones.definir_menus([
        ("&Archivo", ["archivo.abrir", "archivo.carpeta", "archivo.copiar", "|", "archivo.entrada", "archivo.terminal", "|", "app.salir"]),
        ("&Editar", ["editar.filtrar", "editar.todo"]),
        ("&Ver", [f"ver.area.{a}" for a, _t, _i in AREAS] + ["|", "ver.forma", "ver.filtros", "|",
                  ("&Etapa", [f"ver.vista.{e.id}" for e in ops.ETAPAS if e.id != "libros"]), "|", "ver.releer", "ver.indice", "|", "ventana.pantalla_completa"]),
        ("&Método", ["op.simular", "op.aplicar", "op.cancelar", "|"]
                    + [(f"&{e.nombre}", [f"op.{o.id}" for o in e.operaciones]) for e in ops.ETAPAS if e.operaciones]),
        ("&Libro", ["libro.archivo", "libro.dolphin", "|", "libro.calibre", "libro.zotero", "libro.nota", "|", "libro.copiar_clave", "libro.fichas"]),
        ("&Herramientas", ["herr.lanzador", "|", "ventana.paleta"]),
        ("A&justes", ["app.ajustes"]),
        ("Ay&uda", ["ayuda.manual", "ayuda.metodo", "ayuda.operacion", "app.acerca"]),
    ])
    acciones.anadir_fuente(espacio.entradas_paleta)
    acciones.anadir_fuente(operaciones.entradas_paleta)
    acciones.anadir_fuente(libros.entradas_paleta)

    # ------------------------------------------------------------------------------------- lo que hacen las acciones compuestas
    def releer() -> None:
        if espacio.area in ("catalogo", "bandejas"):
            libros.recargar()
        else:
            etapas.recargar(espacio.vista)

    def actualizar_indice() -> None:
        """Ctrl+R: `lib/indice.py --aplicar` directamente (no toca ninguna base: solo escribe el JSON fuera del repo)."""
        if tareas.activa:
            espacio.aviso.emit("Hay una operación en curso (Esc la cancela).", "aviso")
            return
        operaciones.fijar("indice")
        operaciones.aplicar()

    def instalar_lanzador() -> None:
        if tareas.activa:
            return
        tareas.proceso("Instalando el acceso directo", ["bash", str(REPO / "studio" / "install.sh")], cwd=str(REPO))

    def abrir_metodo() -> None:
        ruta = Path(env.DOCS_ROOT) / "prompts" / "00 metodo" / "METODO_DOCUMENTAL.md"
        if ruta.is_file():
            escritorio.abrirConAplicacion(str(ruta))
        else:
            espacio.aviso.emit(f"No está el Método Documental en {ruta}", "aviso")

    def abrir_readme_suite() -> None:
        o = ops.operacion(operaciones.actual)
        if o is None:
            return
        carpeta = (REPO / o.orden[0]).parent
        readme = carpeta / "README.md"
        if not readme.is_file() or carpeta == REPO / "lib":
            readme = REPO / "README.md"
        escritorio.abrirConAplicacion(str(readme))

    # ------------------------------------------------------------------- disponibilidad según la vista, la selección y la tarea
    def vista_cambiada():
        v, a = espacio.vista, espacio.area
        for nombre in acciones.nombres():
            if nombre.startswith("ver.vista."):
                acciones.marcar(nombre, nombre == f"ver.vista.{v}" and a in ("metodo", "coherencia"))
            elif nombre.startswith("ver.area."):
                acciones.marcar(nombre, nombre == f"ver.area.{a}")
        disponibilidad()

    def disponibilidad():
        activa = tareas.activa
        en_libros = espacio.area in ("catalogo", "bandejas")
        hay_libro = en_libros and libros.hayActual
        hay_elemento = not en_libros and etapas.hayElemento and bool(etapas.elementoRuta)
        for nombre in ("archivo.abrir", "archivo.carpeta", "archivo.copiar"):
            acciones.habilitar(nombre, hay_libro or hay_elemento)
        acciones.habilitar("libro.calibre", hay_libro)
        acciones.habilitar("libro.zotero", hay_libro and bool(libros.zoteroKey))
        acciones.habilitar("libro.archivo", hay_libro and bool(libros.ruta_archivo()))
        acciones.habilitar("libro.dolphin", hay_libro and bool(libros.rutaCarpeta))
        acciones.marcar("ver.forma", libros.enLista)
        acciones.habilitar("libro.nota", hay_libro and libros.hayNota)
        acciones.habilitar("libro.copiar_clave", hay_libro and bool(libros.clave))
        acciones.habilitar("libro.fichas", hay_libro and libros.nFichas > 0)
        a = acciones.accion("op.simular")
        a.texto = f"&{operaciones.verbo}"
        acciones.habilitar("op.simular", operaciones.puedeSimular)
        b = acciones.accion("op.aplicar")
        b.visible = operaciones.escribe
        acciones.habilitar("op.aplicar", operaciones.puedeAplicar)
        acciones.habilitar("op.cancelar", operaciones.enCurso)
        acciones.habilitar("ver.releer", not activa)
        acciones.habilitar("ver.indice", not activa)
        acciones.habilitar("herr.lanzador", not activa)
        acciones.habilitar("ayuda.operacion", operaciones.hayOperacion)

    def barra_estado():
        espacio.fijarResumen(libros.resumen)
        espacio.fijarContexto(puerta.contexto + (f" · {operaciones.titulo}" if operaciones.hayOperacion else ""))

    def terminada(id_: str, aplicar: bool, codigo: int):
        if id_ == "indice" and aplicar and codigo == 0:
            libros.recargar()
        elif aplicar or id_ in ("recibir", "identificar", "descargar", "archivar", "todo", "timers_instalar"):
            etapas.recargarTodo()
            if aplicar:
                libros.recargar()          # lo aplicado puede cambiar la biblioteca y sus bandejas
        if id_ in ("timers_instalar", "timers_verificar"):
            etapas.recargar("tareas")

    espacio.vistaCambiada.connect(vista_cambiada)
    espacio.areaCambiada.connect(vista_cambiada)
    libros.filtroCambiado.connect(disponibilidad)
    libros.actualCambiado.connect(disponibilidad)
    libros.cambiado.connect(lambda: (disponibilidad(), barra_estado()))
    etapas.elementoCambiado.connect(disponibilidad)
    operaciones.cambiado.connect(lambda: (disponibilidad(), barra_estado()))
    operaciones.terminada.connect(terminada)
    puerta.cambiado.connect(barra_estado)
    tareas.cambiada.connect(disponibilidad)
    vista_cambiada()
    disponibilidad()
    barra_estado()

    piezas = dict(env=env, consola=consola, tareas=tareas, interfaz=interfaz, ajustes=ajustes, espacio=espacio, puerta=puerta,
                  libros=libros, etapas=etapas, operaciones=operaciones, acciones=acciones, portadas=portadas)
    for nombre, objeto in piezas.items():
        if nombre not in ("env", "portadas"):
            app.exponer(nombre, objeto)
    app.exponer("descripcionStudio", DESCRIPCION)
    app._piezas = piezas           # que vivan lo que la aplicación
    return piezas


def _enviar_a_la_abierta(urls: list[str]) -> bool:
    """Si ya hay una ventana, le pasa los enlaces y devuelve True (una sola instancia)."""
    from PySide6.QtNetwork import QLocalSocket
    otro = QLocalSocket()
    otro.connectToServer(SOCKET)
    if otro.waitForConnected(300):
        otro.write(json.dumps(urls).encode())
        otro.waitForBytesWritten(1000)
        return True
    return False


def _escuchar(app: Aplicacion, piezas: dict):
    """El servidor local que recibe los enlaces `biblioteca-studio://` de una segunda instancia."""
    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(SOCKET)
    escucha = QLocalServer()
    escucha.listen(SOCKET)

    def recibir():
        c = escucha.nextPendingConnection()
        c.waitForReadyRead(1000)
        try:
            lista = json.loads(bytes(c.readAll()).decode() or "[]")
        except ValueError:
            lista = []
        for u in lista:
            piezas["libros"].abrirUrl(u)
        ventana = app.ventana()
        if ventana is not None:
            ventana.show()
            ventana.raise_()
            ventana.requestActivate()

    escucha.newConnection.connect(recibir)
    return escucha


def main(argv: list[str]) -> int:
    from gui_comun import lanzador
    atendido = lanzador.desde_main(argv, **datos_lanzador())         # --instalar-lanzador / --quitar-lanzador
    if atendido is not None:
        return atendido
    urls = [a for a in argv if a.startswith("biblioteca-studio:")]
    humo = "--smoke" in argv
    if not humo and _enviar_a_la_abierta(urls):
        return 0
    app = Aplicacion(APP_ID, NOMBRE, version=APP_VERSION, organizacion=ORG_NAME, nombre_ajustes=APP_NAME)
    piezas = construir(app)
    if not app.cargar(QML_DIR / "Main.qml"):
        return 1
    escucha = None if humo else _escuchar(app, piezas)
    for u in urls:
        piezas["libros"].abrirUrl(u)
    if humo:
        from gui_comun.qt import QTimer
        QTimer.singleShot(0, app.app.quit)
    codigo = app.app.exec()
    if escucha is not None:
        escucha.close()
    app.cerrar()
    return codigo
