#!/usr/bin/env python3
"""
main.py — Punto de entrada de Biblioteca Studio.

Orquestación mínima: crea la QApplication, aplica el tema guardado y abre la ventana. La lógica vive en
biblioteca_app/ y en gui_comun (el repo gui-comun); cada acción es una suite de este repo, que escribe por su puerta.

Uso:
    python3 studio/main.py                               # desde scripts-biblioteca/
    python3 studio/main.py biblioteca-studio://libro/48  # abre el libro (lo piden los complementos)
    python3 studio/main.py --smoke                       # construye la interfaz y sale (prueba de humo)
    python3 studio/main.py --instalar-lanzador [-n]      # acceso directo del menú y el esquema biblioteca-studio://
"""

import json
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(_AQUI))

import biblioteca_app  # noqa: F401  encuentra gui_comun

APP_ID = "biblioteca-studio"
SOCKET = "biblioteca-studio"


def datos_lanzador() -> dict:
    """El acceso directo en el menú de aplicaciones y el esquema de enlaces de los complementos."""
    from biblioteca_app.ventana import ACENTO, LOGO
    return dict(app_id=APP_ID, nombre="Biblioteca Studio", comentario="Calibre, Zotero y KOReader con el Método "
                "Documental: adquirir, catalogar, sincronizar y citar", orden=[sys.executable, str(_AQUI / "main.py")],
                logo_svg=LOGO, acento=ACENTO, categorias="Office;Education;", esquema="biblioteca-studio",
                palabras="calibre;zotero;koreader;biblioteca;libros;citas;fichas;")


def main() -> int:
    from gui_comun import lanzador
    atendido = lanzador.desde_main(sys.argv[1:], **datos_lanzador())   # --instalar-lanzador / --quitar-lanzador
    if atendido is not None:
        return atendido
    urls = [a for a in sys.argv[1:] if a.startswith("biblioteca-studio:")]
    smoke = "--smoke" in sys.argv
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    if not smoke:                          # una sola ventana: un enlace con la ventana abierta va a ella
        otro = QLocalSocket()
        otro.connectToServer(SOCKET)
        if otro.waitForConnected(300):
            otro.write(json.dumps(urls).encode())
            otro.waitForBytesWritten(1000)
            return 0
    from gui_comun.diseno import preparar_plataforma
    preparar_plataforma()                 # sin el plugin de Wayland, XWayland sin aviso
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    QApplication.setOrganizationName("EdisonAchalma")
    QApplication.setApplicationName("BibliotecaStudio")
    QApplication.setDesktopFileName(APP_ID)    # la ventana se agrupa con su acceso directo (Wayland)
    app = QApplication([sys.argv[0]])
    from biblioteca_app.ventana import Ventana
    ventana = Ventana()
    ventana.show()
    escucha = None
    if not smoke:
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
                ventana.abrir_url(u)
            ventana.ui.raise_()
            ventana.ui.activateWindow()

        escucha.newConnection.connect(recibir)
    for u in urls:
        ventana.abrir_url(u)
    if smoke:
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
