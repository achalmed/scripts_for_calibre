#!/usr/bin/python3
"""
main.py — Punto de entrada de Biblioteca Studio. Sin lógica: la aplicación se arma en biblioteca_app/aplicacion.py.

Corre con el Python del sistema (/usr/bin/python3), cuyo Qt es el que trae Kirigami; el PySide6 de un entorno de pip
o de Anaconda no puede cargar los módulos QML de KDE. Cada operación es la CLI de una suite de este repo, que escribe
por la única puerta (lib/escribir.*); la ventana no escribe en ninguna base.

Uso:
    /usr/bin/python3 main.py                               # desde biblioteca-studio/studio/
    /usr/bin/python3 main.py biblioteca-studio://libro/48  # abre el libro (lo piden los complementos; una sola ventana)
    /usr/bin/python3 main.py --smoke                       # construye la interfaz y sale (prueba de humo)
    /usr/bin/python3 main.py --instalar-lanzador [-n]      # acceso directo del menú y el esquema biblioteca-studio://
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # el paquete del studio

from biblioteca_app.aplicacion import main                      # noqa: E402  (biblioteca_app localiza gui_comun al importarse)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
