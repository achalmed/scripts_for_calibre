"""tests/studio/test_studio.py — Biblioteca Studio (QML + Kirigami sobre gui-comun 3.0, VentanaBase) abre su ventana sin
pantalla con el Python del sistema sobre la muestra: la ventana entera (acciones, menús, áreas, búsqueda, resumen, el
enlace de los complementos, los pasos de la puerta, las portadas), cada componente QML con un libro abierto, `--smoke`,
y las reglas de la familia (sin colores propios, sin marca dentro, sin QtWidgets ni
gui_comun.widgets, el Python del sistema en main.py e install.sh)."""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from conftest import PYTHON_SISTEMA, REPO, STUDIO, correr_python, entorno_gui, requiere_sistema

QML = STUDIO / "biblioteca_app" / "qml"

ABRIR = """
import sys, json; sys.path.insert(0, sys.argv[1])
from biblioteca_app import aplicacion
from gui_comun.nucleo import Aplicacion
from gui_comun.qt import QTimer
app = Aplicacion("biblioteca-studio", "Biblioteca Studio", version="prueba", nombre_ajustes="BibliotecaStudio")
piezas = aplicacion.construir(app, vigilar_puerta=False)
errores = []
app.motor.warnings.connect(lambda avisos: errores.extend(a.toString() for a in avisos))
ok = app.cargar(aplicacion.QML_DIR / "Main.qml")
raiz = app.motor.rootObjects()[0] if ok else None
titulo = raiz.property("title") if raiz else ""
a, l, o = piezas["acciones"], piezas["libros"], piezas["operaciones"]
sin_libro = (a.accion("libro.calibre").habilitada, a.accion("archivo.abrir").habilitada)
l.abrirUrl("biblioteca-studio://libro/1")
con_libro = (a.accion("libro.calibre").habilitada, a.accion("libro.zotero").habilitada, a.accion("libro.copiar_clave").habilitada, a.accion("libro.fichas").habilitada, a.accion("archivo.abrir").habilitada, a.accion("libro.dolphin").habilitada)
areas = []
for i in range(4):
    a.accion(["ver.area.catalogo", "ver.area.bandejas", "ver.area.metodo", "ver.area.coherencia"][i]).disparar(); app.app.processEvents(); areas.append(piezas["espacio"].area)
    if i == 1:
        op_bandeja = o.actual                                    # la operación de la bandeja, elegida sola sin salir del área
a.accion("ver.area.catalogo").disparar()
l.buscar("autor:quispe"); app.app.processEvents(); buscado = l.visibles
l.limpiarFiltros()
from gui_comun.qt import QSize
portada = piezas["portadas"].requestImage("1", QSize(), QSize())
o.fijar("catalogar")
aplicar = (a.accion("op.aplicar").visible, a.accion("op.aplicar").habilitada, a.accion("op.simular").textoPlano, [p["clave"] for p in o.pasos])
o.fijar("estado")
ejecutar = (a.accion("op.aplicar").visible, a.accion("op.simular").textoPlano)
QTimer.singleShot(800, app.app.quit); app.app.exec(); app.cerrar()
print(json.dumps({"ok": ok, "titulo": titulo, "errores": errores, "acciones": a.nombres(), "menus": [m["titulo"] for m in a.menus],
                  "sin_libro": sin_libro, "con_libro": con_libro, "aplicar": aplicar, "ejecutar": ejecutar, "areas": areas, "buscado": buscado, "op_bandeja": op_bandeja,
                  "portada": [portada.width(), portada.height()], "conflictos": a.conflictos(),
                  "resumen": piezas["espacio"].resumen, "contexto": piezas["espacio"].contexto, "vista": piezas["espacio"].vista,
                  "area": piezas["espacio"].area}))
"""

COMPONENTE = """
import sys, json, os; sys.path.insert(0, sys.argv[1])
from biblioteca_app import aplicacion
from gui_comun.nucleo import Aplicacion
from gui_comun.qt import QTimer
app = Aplicacion("biblioteca-studio", "Biblioteca Studio", version="prueba", nombre_ajustes="BibliotecaStudio")
aplicacion.construir(app, vigilar_puerta=False)
app.motor.addImportPath(str(aplicacion.QML_DIR))
errores = []
app.motor.warnings.connect(lambda avisos: errores.extend(a.toString() for a in avisos))
nombre, carpeta = sys.argv[2], sys.argv[3]
ruta = os.path.join(os.environ["XDG_CACHE_HOME"], "Prueba_" + nombre + ".qml")
os.makedirs(os.path.dirname(ruta), exist_ok=True)
extra = "" if nombre.startswith("Dialogo") else "; anchors.fill: parent" + ("; filas: studio.etapas.filasMetodo" if nombre == "EspacioEtapas" else "")
if nombre in ("TarjetaLibro", "FilaLibro"):                 # los delegados: una fila del modelo, como la daría la vista
    extra = ('; width: 200; height: 360; index: 0; model: ({id: "1", titulo: "Un título", autores: "Autora", "año": "2021", serie: "S [1]", tipo: "book", '
             'portada: true, fuente: "image://portadas/1", zotero: true, clave: "clave2021", koProgreso: 0.4, koEstado: "reading", fichas: 1, '
             'etiquetas: "", seccion: "", otro: false, detalle: "", nivel: ""})')
open(ruta, "w").write('import QtQuick\\nimport GuiComun\\nimport "file://%s/%s"\\nVentanaBase { id: ventana; acciones: studio.acciones; visible: false; %s { id: objeto%s } }\\n' % (str(aplicacion.QML_DIR), carpeta, nombre, extra))
ok = app.cargar(ruta)
app.app.processEvents()
app._piezas["libros"].abrirUrl("biblioteca-studio://libro/1")      # las ligaduras con un libro abierto y la operación que escribe
app._piezas["operaciones"].fijar("catalogar")
app._piezas["libros"].fijarBandeja("clasificar")
app.app.processEvents()
QTimer.singleShot(400, app.app.quit); app.app.exec(); app.cerrar()
print(json.dumps({"ok": ok, "errores": errores}))
"""


def _graves(errores):
    return [e for e in errores if "TypeError" in e or "ReferenceError" in e or "is not a type" in e or "Cannot assign" in e or "No se puede asignar" in e]


@requiere_sistema
def test_abre_y_cierra_su_ventana(tmp_path, muestra):
    r = correr_python(ABRIR, entorno_gui(tmp_path, muestra))
    assert r.returncode == 0, f"código {r.returncode}\n{r.stderr[-3000:]}"
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["ok"], r.stderr[-3000:]
    assert datos["titulo"].endswith(" — Biblioteca Studio")
    assert not _graves(datos["errores"]), "\n".join(_graves(datos["errores"]))
    for n in ("archivo.abrir", "archivo.carpeta", "archivo.copiar", "archivo.entrada", "archivo.terminal", "editar.filtrar", "editar.todo",
              "ver.area.catalogo", "ver.area.bandejas", "ver.area.metodo", "ver.area.coherencia", "ver.forma", "ver.filtros",
              "ver.vista.entrada", "ver.vista.tareas", "ver.releer", "ver.indice",
              "op.simular", "op.aplicar", "op.cancelar", "op.indice", "op.catalogar", "op.zotero_calibre", "op.timers_instalar",
              "libro.calibre", "libro.zotero", "libro.archivo", "libro.dolphin", "libro.nota", "libro.copiar_clave", "libro.fichas",
              "herr.lanzador", "ayuda.manual", "ayuda.metodo", "ayuda.operacion", "ventana.paleta", "app.ajustes", "app.acerca", "app.salir"):
        assert n in datos["acciones"], n
    assert not any(n in datos["acciones"] for n in ("ventana.navegacion", "ventana.detalles", "ventana.inferior"))   # VentanaBase
    assert not datos["conflictos"], datos["conflictos"]
    assert datos["menus"] == ["&Archivo", "&Editar", "&Ver", "&Método", "&Libro", "&Herramientas", "A&justes", "Ay&uda"]
    assert datos["sin_libro"] == [False, False]
    assert datos["con_libro"] == [True, True, True, True, True, True]
    assert datos["areas"] == ["catalogo", "bandejas", "metodo", "coherencia"] and datos["buscado"] == 1
    assert datos["op_bandeja"] == "catalogar"                                     # «Pendientes de clasificar» → Catalogar en Calibre
    assert datos["aplicar"][0] is True and datos["aplicar"][2] == "Simular"      # catalogar escribe en Calibre
    assert datos["aplicar"][3] == ["cerrada", "candado", "respaldo", "aplicar", "integridad", "liberar"]
    assert datos["ejecutar"] == [False, "Ejecutar"]                               # estado solo lee
    assert datos["resumen"].startswith("8 libros · 3 sin Zotero")
    assert datos["contexto"].startswith("Calibre") and datos["contexto"].endswith("Estado de la entrada")
    assert datos["vista"] == "entrada"
    if muestra.con_calibre:
        assert datos["portada"][0] == 220 and datos["portada"][1] > 220          # la miniatura de cover.jpg


@requiere_sistema
def test_main_smoke(tmp_path, muestra):
    r = subprocess.run([PYTHON_SISTEMA, str(STUDIO / "main.py"), "--smoke"], env=entorno_gui(tmp_path, muestra), capture_output=True, text=True,
                       timeout=150, cwd=tmp_path)
    assert r.returncode == 0, f"código {r.returncode}\n{r.stderr[-3000:]}"
    ruido = [l for l in r.stderr.splitlines() if "TypeError" in l or "ReferenceError" in l or "polish() loop" in l]
    assert not ruido, "\n".join(ruido)


COMPONENTES = sorted((p.parent.name, p.stem) for p in QML.glob("*/*.qml"))


@requiere_sistema
@pytest.mark.parametrize("carpeta,nombre", COMPONENTES, ids=[f"{c}/{n}" for c, n in COMPONENTES])
def test_cada_componente_qml(carpeta, nombre, tmp_path, muestra):
    r = correr_python(COMPONENTE, entorno_gui(tmp_path, muestra), nombre, carpeta)
    assert r.returncode == 0, r.stderr[-3000:]
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert datos["ok"], r.stderr[-3000:]
    assert not _graves(datos["errores"]), "\n".join(_graves(datos["errores"]))


def test_sin_colores_propios_en_qml():
    malos = []
    for qml in QML.rglob("*.qml"):
        for n, linea in enumerate(qml.read_text(encoding="utf-8").splitlines(), 1):
            sin_comentario = linea.split("//")[0]
            if re.search(r'"#[0-9a-fA-F]{3,8}"', sin_comentario) or re.search(r'\bfont\.(pointSize|pixelSize|family)\s*:\s*["\d]', sin_comentario):
                malos.append(f"{qml.relative_to(STUDIO)}:{n}: {linea.strip()}")
    assert not malos, "\n".join(malos)


def test_sin_marca_dentro_de_la_ventana():
    """Ningún nombre ni logotipo del studio dentro de la ventana (rediseno.md): el título lo pone KWin."""
    codigo = "\n".join(l.split("//")[0] for l in (QML / "Main.qml").read_text(encoding="utf-8").splitlines())
    assert "logotipo" not in codigo.lower() and "logo_svg" not in codigo and "marca.svg" not in codigo
    assert 'text: "Biblioteca Studio"' not in codigo and '"Biblioteca Studio"' not in codigo.replace('" — Biblioteca Studio"', "")


def test_sin_qtwidgets_y_con_el_python_del_sistema():
    """El studio no importa QtWidgets ni gui_comun.widgets (corre con el Qt del sistema, en QML); main.py e install.sh usan /usr/bin/python3."""
    for py in (STUDIO / "biblioteca_app").rglob("*.py"):
        texto = py.read_text(encoding="utf-8")
        assert "QtWidgets" not in texto and "gui_comun.widgets" not in texto and "gui_comun.diseno" not in texto, py
    assert (STUDIO / "main.py").read_text(encoding="utf-8").startswith("#!/usr/bin/python3")
    assert "/usr/bin/python3" in (STUDIO / "install.sh").read_text(encoding="utf-8")
    assert "/usr/bin/python3" in (STUDIO / "suite.yml").read_text(encoding="utf-8")


def test_la_ventana_no_escribe_en_las_bases():
    """Ningún archivo del studio nombra SQL que modifique ni abre metadata.db o zotero.sqlite para escribir (la puerta es una)."""
    for py in (STUDIO / "biblioteca_app").rglob("*.py"):
        texto = py.read_text(encoding="utf-8").lower()
        assert not re.search(r"\b(insert into|update \w+ set|delete from)\b", texto), py
        assert "mode=rw" not in texto and "sqlite3.connect" not in texto, py


CORREGIR = """
import sys, json, os, time; sys.path.insert(0, sys.argv[1])
from pathlib import Path
from biblioteca_app import aplicacion
from gui_comun.nucleo import Aplicacion
from gui_comun.qt import QMetaObject, QObject
try:
    from PySide6.QtCore import Q_ARG
except ImportError:
    from PyQt6.QtCore import Q_ARG
app = Aplicacion("biblioteca-studio", "Biblioteca Studio", version="prueba", nombre_ajustes="BibliotecaStudio")
piezas = aplicacion.construir(app, vigilar_puerta=False)
errores = []
app.motor.warnings.connect(lambda avisos: errores.extend(a.toString() for a in avisos))

class Falso:                                   # el Yachay de las pruebas: la primera vez, un 409; sobre la versión que dio, acepta
    def __init__(self):
        self.llamadas = []
    def ficha_a_yachay(self, calibre_id, respuestas, aplicar, sobre=None):
        self.llamadas.append([calibre_id, dict(respuestas), aplicar, sobre])
        plan = {"calibre_id": calibre_id, "ficha": {"limites": respuestas.get("Límites", "")}, "version_base": sobre if sobre is not None else 3,
                "cambian": ["Límites"], "nueva": False, "leida": False, "faltan": [], "escrita": False}
        if not aplicar:
            return plan
        if sobre is None:
            return {**plan, "codigo": "lectura_modificada", "version": 4, "actual": {"ficha": {"limites": "Otra cosa"}, "version": 4}}
        return {**plan, "escrita": True, "version": sobre + 1, "aviso": ""}
    def sincronizar_yachay(self):
        return {"ok": True, "error": ""}

fichado = piezas["fichado"]
fichado.canal = canal = Falso()
def esperar(cond, segundos=60):
    t0 = time.monotonic()
    while time.monotonic() - t0 < segundos:
        app.app.processEvents()
        if cond():
            return True
        time.sleep(0.03)
    return False
def leer(obj, nombre):
    v = obj.property(nombre)
    return v.toVariant() if hasattr(v, "toVariant") else v
def llamar(obj, fn, *args):
    QMetaObject.invokeMethod(obj, fn, *[Q_ARG("QVariant", a) for a in args])
    app.app.processEvents()

ruta = os.path.join(os.environ["XDG_CACHE_HOME"], "Prueba_corregir.qml")
os.makedirs(os.path.dirname(ruta), exist_ok=True)
qml = str(aplicacion.QML_DIR / "componentes")
open(ruta, "w").write('import QtQuick\\nimport GuiComun\\nimport "file://%s"\\nVentanaBase { id: ventana; acciones: studio.acciones; visible: false\\n'
                      '  DialogoFicha { objectName: "pruebaFicha" }\\n  DialogoObraYachay { objectName: "pruebaObra" } }\\n' % qml)
ok = app.cargar(ruta)
raiz = app.motor.rootObjects()[0]
piezas["libros"].abrirUrl("biblioteca-studio://libro/1")
fichado.preparar(1); esperar(lambda: not fichado.ocupado)
carpeta = fichado.escritos[0]["carpeta"]; escrito = fichado.escritos[0]["titulo"]
seis = {"Pregunta": "Si las ciudades chicas ganan algo al unirse a su región.", "Método": "Compara series de varias décadas.",
        "Datos": "Censos nacionales.", "Hallazgo": "Las que se unen a su región ganan más.",
        "Límites": "No separa el efecto de la carretera.", "Uso que le daré": "El marco del capítulo dos."}
hecho = []
fichado.revisada.connect(lambda r: hecho.append(dict(r)))
fichado.revisar(carpeta, {"tipo": "obra", "secciones": seis}, True); esperar(lambda: bool(hecho))
archivo = Path(carpeta) / "fuentes" / "fichas" / hecho[-1]["archivo"]

d = raiz.findChild(QObject, "pruebaFicha")
llamar(d, "corregir", {"tipo": "obra", "carpeta": carpeta, "archivo": str(archivo), "calibreId": "1", "escrito": escrito})
esperar(lambda: bool((leer(d, "corrigiendo") or {}).get("huella")))
r = {"titulo": leer(d, "title"), "leidos": leer(d, "textos"), "corrigiendo": leer(d, "corrigiendo")}
llamar(d, "poner", {"tipo": "obra", "archivo": archivo.name, "huella": r["corrigiendo"]["huella"], "pagina": "", "uso": "", "categoria": "",
                    "secciones": [{"titulo": k, "texto": v} for k, v in {**seis, "Límites": "No separa la carretera de otras obras del mismo año."}.items()]})
vuelta = d.findChild(QObject, "vueltaYachay")
llamar(d, "revisar", False)
esperar(lambda: leer(d, "revision") is not None and leer(vuelta, "plan") is not None and not fichado.ocupado)
r["revision"] = {k: (leer(d, "revision") or {}).get(k) for k in ("archivo", "error", "correccion", "escrito", "aplicar")}
r["llevable"], r["resumen"] = leer(d, "llevable"), leer(vuelta, "resumen")
confirmar, conflicto = vuelta.findChild(QObject, "confirmarYachay"), vuelta.findChild(QObject, "conflictoYachay")
llamar(d, "revisar", True)
esperar(lambda: bool(leer(confirmar, "opened")))
r["confirmar"] = {"abierto": leer(confirmar, "opened"), "titulo": leer(confirmar, "title"), "texto": leer(confirmar, "subtitle")}
r["en_disco"] = "otras obras del mismo año" in archivo.read_text(encoding="utf-8")
llamar(vuelta, "llevar", -1)
esperar(lambda: bool(leer(conflicto, "opened")))
r["conflicto"] = {"abierto": leer(conflicto, "opened"), "texto": leer(conflicto, "subtitle")}
llamar(vuelta, "llevar", 4)
esperar(lambda: not leer(d, "visible"))
r["cerrado"], r["llamadas"] = not leer(d, "visible"), canal.llamadas[:]

antes = archivo.stat().st_mtime_ns
o = raiz.findChild(QObject, "pruebaObra")
canal.llamadas.clear()
llamar(o, "abrir", {"calibreId": 1, "detalle": "versión 3", "preguntas": [{"titulo": k, "texto": v} for k, v in seis.items()]}, "Economía de ciudades")
o.setProperty("textos", {**seis, "Hallazgo": "Ganan más las que se unen a su región."})
vo = o.findChild(QObject, "vueltaYachay")
llamar(o, "revisar")
esperar(lambda: leer(vo, "plan") is not None and not fichado.ocupado)
r["obra"] = {"titulo": leer(o, "title"), "llevable": leer(vo, "llevable"), "simulo": canal.llamadas[-1][:1] + canal.llamadas[-1][2:]}
llamar(vo, "llevar", 4)
esperar(lambda: not leer(o, "visible"))
r["obra"].update(cerrado=not leer(o, "visible"), llevo=canal.llamadas[-1][:1] + canal.llamadas[-1][2:],
                 hallazgo=canal.llamadas[-1][1]["Hallazgo"], escrito_intacto=archivo.stat().st_mtime_ns == antes)
app.cerrar()
print(json.dumps({"ok": ok, "errores": errores, **r}, ensure_ascii=False, default=str))
"""


@requiere_sistema
def test_corregir_una_ficha_de_obra_y_la_de_yachay_en_la_ventana(tmp_path, muestra):
    """La ventana (§9.13, nota del 2026-11-19): «Corregir…» abre la ficha de obra que ya existe con su huella, «Revisar»
    simula la corrección y la vuelta, «Guardar la corrección» la escribe y ofrece «¿Llevarla también a Yachay?»; un 409
    abre «Tu ficha de obra cambió en Yachay» y «Llevar la mía sobre la versión N» la envía. «Corregir…» de la de Yachay lleva
    las seis sin tocar ningún escrito. Todo con un Yachay falso."""
    r = correr_python(CORREGIR, entorno_gui(tmp_path, muestra))
    assert r.returncode == 0, r.stderr[-3000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["ok"] and not _graves(d["errores"]), "\n".join(_graves(d["errores"]))
    assert d["titulo"].startswith("Corregir la ficha de «") and d["leidos"]["Límites"] == "No separa el efecto de la carretera."
    assert d["revision"]["correccion"] and not d["revision"]["error"] and not d["revision"]["escrito"]
    assert d["llevable"] and d["resumen"].startswith("En Yachay: tu ficha de obra va en la versión 3; cambiarían Límites")
    assert d["confirmar"]["abierto"] and d["confirmar"]["titulo"] == "¿Llevarla también a Yachay?" and d["en_disco"]
    assert d["conflicto"]["abierto"] and "Va en la versión 4" in d["conflicto"]["texto"]
    assert d["cerrado"] and [l[2:] for l in d["llamadas"]] == [[False, None], [True, None], [True, 4]]
    o = d["obra"]
    assert o["titulo"] == "Corregir tu ficha de obra de «Economía de ciudades»" and o["llevable"] and o["simulo"] == [1, False, None]
    assert o["cerrado"] and o["llevo"] == [1, True, 4] and o["hallazgo"].startswith("Ganan más") and o["escrito_intacto"]
