"""biblioteca_app/controladores/lectura.py — el área «Lectura» (decisiones §9.6): lo que dice la base de lectura, en solo
lectura (`lectura_base/lib/consulta.py`, `mode=ro`).

A la izquierda, los libros con lectura (tiempo, progreso o subrayados), los más recientes primero, y arriba el resumen
de toda la base (horas, este mes, racha, sesiones, de dónde vienen los subrayados) con las horas de las últimas doce
semanas. A la derecha, el libro elegido: su tiempo y su progreso en cada herramienta, sus sesiones y sus subrayados, que
se filtran por origen (KOReader, Zotero, Okular, Yachay) y se copian como cita. El libro elegido sigue al del catálogo.
La ventana no escribe la base: lo hace la operación «Base de lectura» (la CLI `lectura_base/main.py sincronizar`).
"""

from __future__ import annotations

import sys
from pathlib import Path

from gui_comun.qt import QFileSystemWatcher, QGuiApplication, QObject, QTimer, Property, Signal, Slot

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lectura_base.lib import base as lb  # noqa: E402
from lectura_base.lib import consulta  # noqa: E402

NOMBRES = {"koreader": "KOReader", "zotero": "Zotero", "okular": "Okular", "yachay": "Yachay"}
ESTADOS = {"reading": "leyendo", "complete": "terminado", "abandoned": "abandonado"}


def _cita(a: dict) -> str:
    """«“texto” (p. 73)»: lo que copia el botón de un subrayado."""
    texto = (a.get("texto") or "").strip()
    lugar = a.get("lugar") or ""
    if not texto:
        return a.get("nota") or ""
    return f"“{texto}”" + (f" ({lugar})" if lugar else "")


class Lectura(QObject):
    cambiado = Signal()
    libroCambiado = Signal()
    aviso = Signal(str, str)

    def __init__(self, libros=None, ruta: Path | None = None, vigilar: bool = True, parent=None):
        super().__init__(parent)
        self._libros = libros
        self._ruta = Path(ruta) if ruta else None
        self._resumen: dict = {}
        self._semanas: list = []
        self._lista: list = []
        self._libro: dict = {}
        self._id = -1
        self._origen = ""
        self._vigia = None
        self._espera = QTimer(self)
        self._espera.setSingleShot(True)
        self._espera.setInterval(1200)
        self._espera.timeout.connect(self.recargar)
        if vigilar:
            self._vigia = QFileSystemWatcher(self)
            self._vigia.fileChanged.connect(lambda *_: self._espera.start())
            self._vigia.directoryChanged.connect(lambda *_: self._espera.start())
        if libros is not None:
            libros.actualCambiado.connect(self._seguir_catalogo)
        self.recargar()

    # ------------------------------------------------------------------------------------------------ leer la base
    def ruta(self) -> Path:
        return self._ruta or lb.ruta_base()

    def _vigilar(self) -> None:
        if self._vigia is None:
            return
        r = self.ruta()
        for p in (str(r), str(r.parent)):
            if Path(p).exists() and p not in self._vigia.files() + self._vigia.directories():
                self._vigia.addPath(p)

    @Slot()
    def recargar(self) -> None:
        try:
            self._resumen = consulta.resumen(self.ruta())
            self._semanas = consulta.semanas(12, self.ruta())
            self._lista = consulta.libros(300, self.ruta())
        except Exception as e:  # noqa: BLE001 — una base a medio escribir: se reintenta en la próxima señal
            self.aviso.emit(f"No se pudo leer la base de lectura: {e}", "aviso")
            return
        for f in self._lista:
            f["detalle"] = " · ".join(x for x in (f["tiempo"] if f["segundos"] else "", f"{f['porcentaje']} %" if f["fraccion"] else "",
                                                  f"{f['anotaciones']} subrayados" if f["anotaciones"] else "",
                                                  ESTADOS.get(f["estado"], "")) if x)
            f["origenesTexto"] = ", ".join(NOMBRES.get(o, o) for o in f["origenes"])
        self._vigilar()
        self.cambiado.emit()
        if self._id < 0 and self._lista and self._lista[0]["calibre_id"] is not None:
            self.elegir(int(self._lista[0]["calibre_id"]))
        else:
            self._leer_libro()

    def _leer_libro(self) -> None:
        self._libro = consulta.libro(self._id, self.ruta()) if self._id >= 0 else {}
        if self._libro and not self._libro.get("titulo") and self._libros is not None and str(self._libros.id) == str(self._id):
            self._libro["titulo"] = self._libros.titulo
        self.libroCambiado.emit()

    def _seguir_catalogo(self) -> None:
        try:
            i = int(self._libros.id) if self._libros is not None and self._libros.hayActual else -1
        except (TypeError, ValueError):
            i = -1
        if i >= 0 and i != self._id:
            self.elegir(i)

    # -------------------------------------------------------------------------------------------- toda la base
    @Property(bool, notify=cambiado)
    def hayBase(self) -> bool:
        return bool(self._resumen.get("existe"))

    @Property(str, notify=cambiado)
    def rutaBase(self) -> str:
        return str(self.ruta())

    @Property("QVariantMap", notify=cambiado)
    def resumen(self) -> dict:
        r = self._resumen
        if not r.get("existe"):
            return {"existe": False}
        return {"existe": True, "tiempo": r["tiempo"], "mes": r["mes"]["tiempo"], "diasMes": r["mes"]["dias"], "racha": r["racha"],
                "sesiones": r["sesiones"], "libros": r["libros"], "anotaciones": r["anotaciones"], "compartidas": r["compartidas"],
                "origenes": " · ".join(f"{NOMBRES.get(o, o)} {n}" for o, n in sorted(r["por_origen"].items())) or "sin subrayados",
                "ultima": consulta.utc_a_local(r["ultima_sincronia"]) or "nunca"}

    @Property("QVariantList", notify=cambiado)
    def semanas(self) -> list:
        return [{"etiqueta": s["etiqueta"], "horas": s["horas"], "proporcion": s["proporcion"], "sesiones": s["sesiones"]}
                for s in self._semanas]

    @Property("QVariantList", notify=cambiado)
    def libros(self) -> list:
        return [{"id": -1 if f["calibre_id"] is None else int(f["calibre_id"]), "titulo": f["titulo"], "autores": f["autores"],
                 "detalle": f["detalle"], "origenes": f["origenesTexto"]} for f in self._lista]

    # ------------------------------------------------------------------------------------------ el libro elegido
    @Slot(int)
    def elegir(self, calibre_id: int) -> None:
        self._id = int(calibre_id)
        self._origen = ""
        self._leer_libro()

    @Property(int, notify=libroCambiado)
    def actualId(self) -> int:
        return self._id

    @Property("QVariantMap", notify=libroCambiado)
    def libro(self) -> dict:
        l = self._libro
        if not l:
            return {"hay": False}
        progreso = [{"origen": NOMBRES.get(g["origen"], g["origen"]),
                     "texto": " · ".join(x for x in (f"{g['porcentaje']} %" if g["porcentaje"] is not None else "",
                                                     f"hoja {g['hoja']}" + (f" de {g['hojas']}" if g["hojas"] else "") if g["hoja"] else "",
                                                     g["tiempo"] if g["segundos"] else "", ESTADOS.get(g["estado"], g["estado"])) if x) or "abierto",
                     "fraccion": g["fraccion"] if g["fraccion"] is not None else -1}
                    for g in l["progreso"]]
        datos = [x for x in (f"{l['n_sesiones']} sesiones" if l["n_sesiones"] else "", f"{l['dias']} días" if l["dias"] else "",
                             f"{l['paginas_hora']} páginas por hora" if l["paginas_hora"] else "",
                             f"de {l['primera']} a {l['ultima']}" if l["primera"] else "") if x]
        return {"hay": True, "titulo": l["titulo"] or f"Libro {l['calibre_id']}", "autores": l["autores"], "tiempo": l["tiempo"],
                "datos": " · ".join(datos), "progreso": progreso, "total": len(l["anotaciones"]),
                "sesiones": [{"fecha": s["fecha"], "tiempo": s["tiempo"], "paginas": s["paginas"],
                              "texto": f"{s['fecha']} · {s['tiempo']} · {s['paginas']} páginas"} for s in l["sesiones"][:12]]}

    @Property("QVariantList", notify=libroCambiado)
    def origenes(self) -> list:
        """Los filtros por origen del libro elegido: Todos y cada herramienta con subrayados aquí."""
        por = (self._libro or {}).get("por_origen") or {}
        total = len((self._libro or {}).get("anotaciones") or [])
        salida = [{"nombre": "", "texto": f"Todos  {total}"}] if total else []
        return salida + [{"nombre": o, "texto": f"{NOMBRES[o]}  {n}"} for o, n in por.items() if n]

    @Property(str, notify=libroCambiado)
    def origen(self) -> str:
        return self._origen

    @Slot(str)
    def fijarOrigen(self, origen: str) -> None:
        self._origen = origen or ""
        self.libroCambiado.emit()

    @Property("QVariantList", notify=libroCambiado)
    def anotaciones(self) -> list:
        salida = []
        for a in (self._libro or {}).get("anotaciones") or []:
            if self._origen and self._origen not in a["vive_en"]:
                continue
            fecha = (a.get("modificada") or a.get("creada") or "")[:10]
            salida.append({"uid": a["uid"], "texto": a["texto"], "nota": a["nota"], "color": a["color"] or "",
                           "lugar": a["lugar"], "intencion": a["intencion"], "tipo": a["tipo"],
                           "detalle": " · ".join(x for x in (a["lugar"], ", ".join(NOMBRES.get(o, o) for o in a["vive_en"]), fecha,
                                                             a["intencion"]) if x),
                           "cita": _cita(a)})
        return salida

    @Slot(str)
    def copiar(self, texto: str) -> None:
        QGuiApplication.clipboard().setText(texto or "")
        self.aviso.emit("Copiado.", "positivo")

    @Slot()
    def verEnCatalogo(self) -> None:
        if self._libros is not None and self._id >= 0:
            self._libros.abrirUrl(f"biblioteca-studio://libro/{self._id}")
