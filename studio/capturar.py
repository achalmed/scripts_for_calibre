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
    /usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-inicio.png --area inicio
    /usr/bin/python3 studio/capturar.py salida.png --area fichas --repaso --mostrar      # el repaso Leitner, con la cita a la vista
    /usr/bin/python3 studio/capturar.py salida.png --libro 1 --ficha-obra               # «Nueva ficha» de obra rellena con la de Yachay (§9.13)
    /usr/bin/python3 studio/capturar.py salida.png --area metodo --vista catalogar --catalogar-ia   # catalogar con un chat (§9.15)
    /usr/bin/python3 studio/capturar.py salida.png --area metodo --vista catalogar --filtro-columna 5=alta --sin-panel
    /usr/bin/python3 studio/capturar.py salida.png --agrupar coleccion --orden serie --orden-colecciones nombre   # 2026-11-22

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


# lo que un chat devolvería con el prompt del paso 02 sobre la primera fila de Catalogar de la muestra (§9.15)
CATALOGACION_DE_MUESTRA = """Tipo Book: libro con ISBN y editorial.

```yaml
tipo: catalogacion
autores: "Rosa, Quispe Huamán"
titulo: "Economía de las ciudades pequeñas"
tipo_zotero: Book
clasificador: Libro
item_type: Book
editorial: "Fondo Editorial de Muestra"
fecha: 2021
identificador: "isbn:9786120000000"
idioma: Spanish
tags: [economia, economia_regional]
serie: ""
serie_index: ""
confianza: media
verificar: ["identificador: el ISBN no se lee en la página legal"]
nota: ""
```
"""

# lo que un chat devolvería con la mirada «Fichas textuales» sobre las hojas 2 y 3 del primer libro de la muestra
ESTUDIO_DE_MUESTRA = """```yaml
tipo: estudio-de-obra
version: 1
dimension: obra_fichas
titulo: "Dos fichas de los capítulos 1 y 2"
obra: "Economía de las ciudades pequeñas"
unidad: "caps. 1 y 2, pp. 12-13"
afirmaciones:
  - seccion: identificacion
    clase: H
    texto: "Los capítulos 1 y 2 tratan la escala urbana y el empleo local."
fichas:
  - tipo: textual_simple
    tema: "escala urbana"
    categoria: "Idea principal"
    cita: u2
    localizador: "p. 12"
    texto_citado: "Las ciudades pequeñas crecen cuando se integran a su región."
    comentario: "La tesis del capítulo 1."
  - tipo: parafrasis
    tema: "empleo y vías"
    categoria: "Argumento"
    cita: u2
    localizador: "p. 13"
    texto_citado: "El mercado de trabajo local depende de la conectividad vial"
    parafrasis: "El empleo de una ciudad pequeña sigue a sus caminos."
    comentario: "Fiel: no añade causas."
```"""


def sembrar_flujo(escrito: Path) -> None:
    """La revisión de muestra (tipo, bitácora, registros cribados y su diagrama PRISMA) y una ficha textual que propuso la
    IA, en el informe de muestra del temporal (decisiones §9.10). Nada fuera de la muestra."""
    import importlib.util

    def cargar(nombre):
        s = importlib.util.spec_from_file_location(f"muestra_{nombre}", REPO / "lib" / f"{nombre}.py")
        m = importlib.util.module_from_spec(s)
        sys.modules[f"biblioteca_{nombre}" if nombre == "revision" else f"muestra_{nombre}"] = m
        s.loader.exec_module(m)
        return m
    rv = cargar("revision")
    r, h = rv.leer(escrito)
    r = rv.declarar(r, "sistematica", "¿Cuánto explica la composición del empleo la recuperación incompleta de la pobreza?",
                    ["Perú, 2015-2025", "Estimaciones con microdatos de la ENAHO"], ["Sin método de descomposición", "Solo opinión"])
    r, b1 = rv.buscar(r, "Scopus", 'TITLE-ABS-KEY(("pobreza monetaria" OR "poverty") AND "Peru" AND (empleo OR employment))',
                      4, "2015-2025; artículos y documentos de trabajo; español e inglés", "2026-11-18")
    r, b2 = rv.buscar(r, "Repositorio del BCRP", "pobreza empleo descomposición", 2, "2015-2025", "2026-11-18")
    r, b3 = rv.buscar(r, "Búsqueda de citas", "", 1, "referencias de los incluidos", "2026-11-18", clase="citas")
    for bq, titulo, anio, doi in ((b1, "Pobreza y empleo informal en el Perú", "2021", "10.1000/muestra.1"),
                                  (b1, "Pobreza y empleo informal en el Perú", "2021", "10.1000/MUESTRA.1"),
                                  (b1, "Ingresos laborales y pobreza urbana", "2019", ""), (b1, "Turismo y crecimiento", "2018", ""),
                                  (b2, "Descomposición de la pobreza, 2019-2023", "2024", ""), (b2, "Empleo y pandemia", "2022", ""),
                                  (b3, "Un estudio citado por los incluidos", "2017", "")):
        r, _ = rv.registro(r, bq["id"], titulo, "Autora, Una", anio, doi)
    for rid, fase, decision, motivo in (("r0001", 1, "incluir", ""), ("r0003", 1, "incluir", ""), ("r0004", 1, "excluir", "otro tema"),
                                        ("r0005", 1, "incluir", ""), ("r0006", 1, "incluir", ""), ("r0007", 1, "incluir", ""),
                                        ("r0001", 2, "incluir", ""), ("r0003", 2, "excluir", "sin descomposición"),
                                        ("r0005", 2, "incluir", ""), ("r0006", 2, "no_recuperado", ""), ("r0007", 2, "incluir", "")):
        r, _ = rv.cribar(r, rid, fase, decision, motivo)
    rv.escribir(escrito, r, h, aplicar=True)
    cargar("prisma").generar(escrito, aplicar=True)
    fichar = cargar("fichar")
    fichar._verificar = lambda meta, _c, _r: {"estado": "verificada_script", "metodo": "texto", "fecha": "2026-11-18", "detalle": "", "pagina_pdf": None}
    fichar.registrar_ia = lambda *a, **k: {"registro": "ia/registro.yml", "total": 1}
    import yaml
    f = (yaml.safe_load((escrito / "fuentes" / "fuentes.yml").read_text(encoding="utf-8")) or {}).get("fuentes") or []
    if f:
        entrada = {"clave": f[0]["clave_bibtex"], "calibre_id": f[0]["calibre_id"], "zotero_key": f[0].get("zotero_key") or ""}
        fichar.guardar(escrito, {"tipo": "textual", "pagina": "14", "categoria": "Hallazgo", "tema": "integracion regional",
                                 "origen": {"autor": "llm", "herramienta": "Un chat de IA externo, con la mirada «Fichas textuales» de Biblioteca Studio"},
                                 "secciones": {"Cita exacta": "Las ciudades pequeñas crecen cuando se integran a su región."}},
                       entrada, aplicar=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura de Biblioteca Studio sobre la biblioteca de muestra")
    parser.add_argument("salida")
    parser.add_argument("--esquema", help="archivo .colors de KDE (relanza con XDG_CONFIG_HOME temporal)")
    parser.add_argument("--area", default="catalogo", help="inicio · catalogo · lectura · fichas · metodo · coherencia · revision · bandejas")
    parser.add_argument("--vista", default="", help="la etapa: adquirir · entrada · catalogar · fichas · manifiestos · sincronizar · puerta · tareas")
    parser.add_argument("--libro", default="", help="el libro de la ficha editorial (su número de Calibre)")
    parser.add_argument("--buscar", default="", help="la búsqueda del catálogo (autor:… año:…)")
    parser.add_argument("--lista", action="store_true", help="el catálogo en lista compacta (no en cuadrícula)")
    parser.add_argument("--agrupar", default="", help="el catálogo agrupado: coleccion · autor · tipo · decada (pasa a la lista)")
    parser.add_argument("--orden", default="", help="el orden del catálogo: titulo · autor · año · añadido · serie")
    parser.add_argument("--orden-colecciones", default="", help="el orden de las colecciones del filtro: n · nombre · reciente")
    parser.add_argument("--bandeja", default="", help="clasificar · fichas · sin_clave · sin_zotero · sin_portada")
    parser.add_argument("--operacion", default="", help="la operación elegida (id del catálogo)")
    parser.add_argument("--fila", type=int, default=0, help="en una etapa, la fila seleccionada de la tabla (−1 ninguna)")
    parser.add_argument("--pestana", type=int, default=-1, help="en una etapa, el lado: 0 Elemento · 1 Operación · 2 Plan · 3 Registro · 4 Salida")
    parser.add_argument("--dialogo", action="store_true", help="abre el diálogo de Aplicar de la operación (solo lo muestra: no aplica)")
    parser.add_argument("--sin-correr", action="store_true", help="no corre la operación de muestra antes de capturar")
    parser.add_argument("--paleta", default=None, help="abre la paleta de órdenes con este texto")
    parser.add_argument("--ficha", action="store_true", help="con --libro: abre «Nueva ficha» con una textual de muestra ya revisada (§9.4)")
    parser.add_argument("--ficha-obra", action="store_true", help="con --libro: abre «Nueva ficha» de obra rellena con la de Yachay de la muestra, revisada (§9.13)")
    parser.add_argument("--estudio", action="store_true", help="con --libro: abre «Estudiar con la IA» con una respuesta de muestra leída (§9.5)")
    parser.add_argument("--repaso", action="store_true", help="con --area fichas: el «Repaso para estudiantes» (§9.9)")
    parser.add_argument("--mostrar", action="store_true", help="con --repaso: la tarjeta con su cita a la vista")
    parser.add_argument("--filtro", default="", help="con --area fichas: todas · textual · parafrasis · obra · revisar · ia")
    parser.add_argument("--flujo", action="store_true", help="siembra en la muestra una revisión con su PRISMA y una ficha de la IA (§9.10)")
    parser.add_argument("--catalogar-ia", action="store_true", help="con --area metodo y --vista entrada o catalogar: «Catalogar con un chat» con una respuesta de muestra revisada (§9.15)")
    parser.add_argument("--filtro-columna", default="", help="en una etapa, un filtro por columna: «<número de columna>=<valor>»")
    parser.add_argument("--sin-panel", action="store_true", help="en una etapa, la tabla ampliada (sin el panel de la derecha)")
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
        if args.flujo:
            sembrar_flujo(carpeta / "muestra" / "escritura" / "reports" / "2026-11-17-informe-de-muestra")
        (carpeta / "muestra" / "core").symlink_to(REPO.parent / "core")      # DOCS_ROOT = la muestra: las rutas se ven relativas a ella
        env.update(m.entorno)
        env.update({"HOME": str(hogar), "XDG_CACHE_HOME": str(hogar / ".cache"), "XDG_DATA_HOME": str(Path.home() / ".local" / "share"),
                    "DOCS_ROOT": str(carpeta / "muestra"), "WRITING_DIR": str(carpeta / "muestra" / "escritura"), "BIBLIOTECA_STUDIO_CAPTURA": str(carpeta), "QT_QPA_PLATFORM": "offscreen"})
        # los prompts del ecosistema y el catálogo de miradas de Yachay (código público, solo se leen): la muestra cambia DOCS_ROOT
        env.update({"PROMPTS_DIR": str(REPO.parent / "prompts"), "YACHAY_CODIGO": str(REPO.parent / "yachay")})
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
        if args.orden:
            libros.fijarOrden(args.orden)
        if args.agrupar:
            libros.fijarAgrupar(args.agrupar)
        if args.orden_colecciones:
            libros.fijarOrdenFaceta("coleccion", args.orden_colecciones)
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
        if args.filtro:
            piezas["fichas"].fijarFiltro(args.filtro)
        if args.repaso:
            piezas["fichas"].fijarModo("repaso")
            if args.mostrar:
                QTimer.singleShot(1200, piezas["fichas"].mostrar)
        if args.area in ("metodo", "coherencia") and args.fila >= 0:
            QTimer.singleShot(300, lambda: interfaz.pedir.emit("seleccionar_fila", {"fila": args.fila}))
        if args.pestana >= 0:
            QTimer.singleShot(600, lambda: interfaz.pedir.emit("pestana", {"indice": args.pestana}))
        if args.filtro_columna:
            columna, _, valor = args.filtro_columna.partition("=")
            piezas["etapas"].filtrarColumna(args.vista, int(columna), valor)
        if args.sin_panel:
            from gui_comun.qt import QObject as _Q
            QTimer.singleShot(700, lambda: raiz.findChild(_Q, "metodo" if args.area == "metodo" else "coherencia").setProperty("conPanel", False))
        if args.catalogar_ia:
            QTimer.singleShot(1200, lambda: interfaz.pedir.emit("catalogar_ia", {"texto": CATALOGACION_DE_MUESTRA}))
        if args.paleta is not None:
            QTimer.singleShot(900, lambda: interfaz.pedir.emit("paleta", {"texto": args.paleta}))
        if args.dialogo:
            QTimer.singleShot(900, lambda: interfaz.pedir.emit("aplicar", {}))
        if args.ficha or args.ficha_obra or args.estudio:
            from gui_comun.qt import QMetaObject, QObject
            try:
                from PySide6.QtCore import Q_ARG
            except ImportError:
                from PyQt6.QtCore import Q_ARG

            def llamar(nombre, valor):
                QMetaObject.invokeMethod(raiz.findChild(QObject, nombre), "abrir", Q_ARG("QVariant", valor))

            def abrir():
                if args.ficha_obra:
                    llamar("dialogoFicha", {"tipo": "obra", "revisar": True})
                elif args.ficha:
                    llamar("dialogoFicha", {"tipo": "textual", "pagina": "12", "hoja": 2, "categoria": "Idea principal", "tema": "escala urbana",
                             "uso": "marco", "revisar": True,
                             "textos": {"Cita exacta": "Las ciudades pequeñas crecen cuando se integran a su región.",
                                        "Análisis": "La tesis del capítulo: la escala importa menos que la integración regional."}})
                else:
                    llamar("dialogoEstudio", ESTUDIO_DE_MUESTRA)
            QTimer.singleShot(1500, abrir)
        app.capturar(args.salida, espera_ms=6000 if args.ficha or args.ficha_obra or args.estudio or args.catalogar_ia else 2600)

    QTimer.singleShot(400, correr_siguiente)
    codigo = app.app.exec()
    app.cerrar()
    print("CAPTURA", args.salida)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
