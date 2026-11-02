#!/usr/bin/python3
"""studio/capturar.py — una captura de Biblioteca Studio para la documentación sobre la BIBLIOTECA DE MUESTRA (`muestra.py`:
libros ficticios, una zotero.sqlite mínima, ledgers y fichas de muestra) creada en una carpeta temporal fuera de la
carpeta de inicio, con HOME, configuración, caché y estado temporales (ninguna ruta de la máquina ni la carpeta de
inicio aparece en pantalla; regla «repo público»), el esquema de color que se pida (con el tema de Kvantum a juego),
el área, el libro, la búsqueda, la bandeja, la etapa, la operación y, si se pide, la paleta de órdenes. Nunca la
biblioteca real: las portadas son las que la muestra genera con el propio Calibre.

    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-claro.png --esquema ~/Documents/lliphi/generado/esquema/LliphiClaro.colors --libro 1
    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-bandejas.png --area bandejas --bandeja clasificar --operacion catalogar
    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-metodo.png --area metodo --vista entrada --operacion catalogar --pestana 1
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
    parser.add_argument("--area", default="catalogo", help="catalogo · bandejas · metodo · coherencia")
    parser.add_argument("--vista", default="", help="la etapa: adquirir · entrada · catalogar · fichas · manifiestos · sincronizar · puerta · tareas")
    parser.add_argument("--libro", default="", help="el libro de la ficha editorial (su número de Calibre)")
    parser.add_argument("--buscar", default="", help="la búsqueda del catálogo (autor:… año:…)")
    parser.add_argument("--lista", action="store_true", help="el catálogo en lista compacta (no en cuadrícula)")
    parser.add_argument("--bandeja", default="", help="clasificar · fichas · sin_clave · sin_zotero · sin_portada")
    parser.add_argument("--operacion", default="", help="la operación elegida (id del catálogo)")
    parser.add_argument("--fila", type=int, default=0, help="en una etapa, la fila seleccionada de la tabla (−1 ninguna)")
    parser.add_argument("--pestana", type=int, default=-1, help="en una etapa, el lado: 0 Elemento · 1 Operación · 2 Plan · 3 Registro · 4 Salida")
    parser.add_argument("--dialogo", action="store_true", help="abre el diálogo de Aplicar de la operación (solo lo muestra: no aplica)")
    parser.add_argument("--sin-correr", action="store_true", help="no corre la operación de muestra antes de capturar")
    parser.add_argument("--paleta", default=None, help="abre la paleta de órdenes con este texto")
    parser.add_argument("--ancho", type=int, default=1440)
    parser.add_argument("--alto", type=int, default=900)
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
            # con QApplication (gui-comun 3.0) los campos los pinta el QStyle (Kvantum) con la paleta de su tema: el tema
            # de Kvantum va a juego con el esquema forzado (LliphiOscuro.colors → LliphiOscuro), o salen claros
            tema, kv = Path(args.esquema).stem, hogar / ".config" / "Kvantum"
            if (kv / tema).is_dir():
                (kv / "kvantum.kvconfig").write_text(f"[General]\ntheme={tema}\n", encoding="utf-8")
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
        libros.enLista = args.lista
        if args.vista:
            espacio.fijarVista(args.vista)
        if args.operacion:
            operaciones.fijar(args.operacion)
        espacio.fijarArea(args.area)
        if args.bandeja:
            libros.fijarBandeja(args.bandeja)
        if args.buscar:
            libros.buscar(args.buscar)
        if args.libro:
            libros.fijarId(args.libro)
        if args.area in ("metodo", "coherencia") and args.fila >= 0:
            QTimer.singleShot(300, lambda: interfaz.pedir.emit("seleccionar_fila", {"fila": args.fila}))
        if args.pestana >= 0:
            QTimer.singleShot(600, lambda: interfaz.pedir.emit("pestana", {"indice": args.pestana}))
        if args.paleta is not None:
            QTimer.singleShot(900, lambda: interfaz.pedir.emit("paleta", {"texto": args.paleta}))
        if args.dialogo:
            QTimer.singleShot(900, lambda: interfaz.pedir.emit("aplicar", {}))
        app.capturar(args.salida, espera_ms=2600)

    QTimer.singleShot(400, correr_siguiente)
    codigo = app.app.exec()
    app.cerrar()
    print("CAPTURA", args.salida)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
