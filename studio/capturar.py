#!/usr/bin/python3
"""studio/capturar.py — una captura de Biblioteca Studio para la documentación sobre la BIBLIOTECA DE MUESTRA (`muestra.py`:
libros ficticios, una zotero.sqlite mínima, ledgers y fichas de muestra) creada en una carpeta temporal fuera de la
carpeta de inicio, con HOME, configuración, caché y estado temporales (ninguna ruta de la máquina ni la carpeta de
inicio aparece en pantalla; regla «repo público»), el esquema de color que se pida, la vista, la operación, la pestaña
de detalles y, si se pide, la paleta de órdenes. Nunca la biblioteca real.

    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-oscuro.png --esquema ~/Documents/lliphi/generado/esquema/LliphiOscuro.colors --vista entrada --operacion catalogar --pestana 3
    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-claro.png --esquema ~/Documents/lliphi/generado/esquema/LliphiClaro.colors --vista libros --pestana 0
    /usr/bin/python3 studio/capturar.py salida.png --paleta "catalogar"

Antes de capturar corre de verdad una operación que solo lee la muestra («Validar las fichas» sobre sus fichas): la
salida del panel inferior y el plan son reales.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(AQUI))


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura de Biblioteca Studio sobre la biblioteca de muestra")
    parser.add_argument("salida")
    parser.add_argument("--esquema", help="archivo .colors de KDE (relanza con XDG_CONFIG_HOME temporal)")
    parser.add_argument("--vista", default="libros", help="libros · adquirir · entrada · catalogar · fichas · manifiestos · sincronizar · puerta · tareas")
    parser.add_argument("--filtro", default="todos", help="en Libros: todos · sin_zotero · sin_clave · sin_ficha · sin_nota")
    parser.add_argument("--operacion", default="", help="la operación elegida (id del catálogo); por omisión la de la vista")
    parser.add_argument("--fila", type=int, default=0, help="la fila seleccionada de la tabla (−1 ninguna)")
    parser.add_argument("--pestana", type=int, default=-1, help="pestaña de detalles (0 Resumen · 1 Fichas · 2 Elemento · 3 Operación · 4 Plan · 5 Registro); −1 la de la vista")
    parser.add_argument("--sin-correr", action="store_true", help="no corre la operación de muestra antes de capturar")
    parser.add_argument("--paleta", default=None, help="abre la paleta de órdenes con este texto")
    parser.add_argument("--ancho", type=int, default=1280)
    parser.add_argument("--alto", type=int, default=800)
    args = parser.parse_args()

    if "BIBLIOTECA_STUDIO_CAPTURA" not in os.environ:      # primera pasada: la muestra, el entorno temporal (y esquema), y relanzar
        from biblioteca_app import aplicacion  # noqa: F401  (localiza gui_comun)
        from gui_comun.galeria.esquema import entorno_con_esquema
        import muestra
        carpeta = Path(tempfile.mkdtemp(prefix="biblioteca-studio-captura-", dir="/tmp"))   # fuera de la carpeta de inicio: ninguna ruta de la máquina en pantalla
        hogar = carpeta / "hogar"
        (hogar / ".config").mkdir(parents=True)
        config_usuario = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        for nombre in ("kdeglobals", "kcminputrc", "Kvantum", "fontconfig"):      # el aspecto del usuario, copiado; sus preferencias no
            origen = config_usuario / nombre
            if origen.is_dir():
                shutil.copytree(origen, hogar / ".config" / nombre, dirs_exist_ok=True)
            elif origen.is_file():
                shutil.copy2(origen, hogar / ".config" / nombre)
        if args.esquema:
            env = entorno_con_esquema(Path(args.esquema).expanduser(), hogar / ".config")
        else:
            env = dict(os.environ, XDG_CONFIG_HOME=str(hogar / ".config"))
        m = muestra.crear(carpeta / "muestra")
        (carpeta / "muestra" / "core").symlink_to(REPO.parent / "core")      # DOCS_ROOT = la muestra: las rutas se ven relativas a ella
        env.update(m.entorno)
        env.update({"HOME": str(hogar), "XDG_CACHE_HOME": str(hogar / ".cache"), "XDG_DATA_HOME": str(Path.home() / ".local" / "share"),
                    "DOCS_ROOT": str(carpeta / "muestra"), "BIBLIOTECA_STUDIO_CAPTURA": str(carpeta), "QT_QPA_PLATFORM": "offscreen"})
        env.setdefault("QT_QPA_PLATFORMTHEME", "kde")     # sin pantalla, la paleta de Qt también lee el kdeglobals temporal
        orden = [sys.executable, str(AQUI / "capturar.py")] + [a for a in sys.argv[1:] if not a.startswith("--esquema") and a != args.esquema]
        codigo = subprocess.run(orden, env=env).returncode
        shutil.rmtree(carpeta, ignore_errors=True)
        return codigo

    from biblioteca_app import aplicacion
    from gui_comun.nucleo import Aplicacion
    from gui_comun.qt import QTimer

    app = Aplicacion(aplicacion.APP_ID, aplicacion.NOMBRE, version=aplicacion.APP_VERSION, nombre_ajustes=aplicacion.APP_NAME)
    piezas = aplicacion.construir(app, vigilar_puerta=False)
    espacio, libros, operaciones, tareas, interfaz = piezas["espacio"], piezas["libros"], piezas["operaciones"], piezas["tareas"], piezas["interfaz"]
    if not app.cargar(aplicacion.QML_DIR / "Main.qml"):
        return 1
    raiz = app.motor.rootObjects()[0]
    raiz.setProperty("width", args.ancho)
    raiz.setProperty("height", args.alto)
    repo_muestra = Path(os.environ["BIBLIOTECA_STUDIO_DATOS"])

    pendientes = [] if args.sin_correr else [("fichas_validar", str(repo_muestra / "catalogacion" / "fichas"))]

    def correr_siguiente():
        if tareas.activa:
            QTimer.singleShot(150, correr_siguiente)
            return
        if pendientes:
            id_, valor = pendientes.pop(0)
            operaciones.fijar(id_)
            if valor:
                operaciones.fijarValor(valor)
            operaciones.simular()
            QTimer.singleShot(150, correr_siguiente)
            return
        QTimer.singleShot(300, listo)

    def listo():
        espacio.fijarVista(args.vista)
        if args.vista == "libros":
            libros.fijarFiltro(args.filtro)
        if args.operacion:
            operaciones.fijar(args.operacion)
        raiz.setProperty("mostrarDetalles", True)
        raiz.setProperty("mostrarInferior", True)
        inferior = raiz.property("inferior")
        if inferior is not None:
            inferior.setProperty("pestanaActual", 0)
        if args.fila >= 0:
            QTimer.singleShot(300, lambda: interfaz.pedir.emit("seleccionar_fila", {"fila": args.fila}))
        if args.pestana >= 0:
            QTimer.singleShot(600, lambda: interfaz.pedir.emit("pestana", {"indice": args.pestana}))
        if args.paleta is not None:
            QTimer.singleShot(900, lambda: interfaz.pedir.emit("paleta", {"texto": args.paleta}))
        app.capturar(args.salida, espera_ms=2200)

    QTimer.singleShot(400, correr_siguiente)
    codigo = app.app.exec()
    app.cerrar()
    print("CAPTURA", args.salida)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
