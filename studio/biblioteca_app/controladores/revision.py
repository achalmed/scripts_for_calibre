"""biblioteca_app/controladores/revision.py — el área «Revisión» (Ctrl+7; FLUJO_DE_CONOCIMIENTO C2.1, C2.2 y C2.3, decisiones
§9.10): la revisión de literatura de un escrito, con su tipo, su bitácora de búsqueda, el cribado en dos fases y el diagrama
PRISMA 2020.

Objetivo: que quien revisa la literatura deje escrito cómo halló cada obra y por qué la descartó, sin salir de la ventana, y
  que el diagrama salga solo de eso.
Método: todo pasa por `lib/revision.py` y `lib/prisma.py` (cargados por su ruta): `ver` lo que se pinta; cada acción
  (declarar el tipo, añadir una búsqueda, importar o añadir registros, cribar) se simula: cambia una copia en memoria, que
  la ventana pinta, y suma un cambio sin aplicar con su diferencia; «Aplicar» escribe `fuentes/revision.yml` del escrito
  con la huella con que se leyó (si otro la cambió, se dice y se relee) y «Descartar» olvida la copia (normativa 5.10, como
  la CLI, que simula por omisión). El diagrama se compila en un hilo, con los cambios ya aplicados, y su vista previa (un
  PNG) va a la caché.
Límite: no es una puerta: nunca toca Calibre ni Zotero, solo `fuentes/revision.yml` y `fuentes/prisma.*` del escrito.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
import threading
from pathlib import Path

from gui_comun.qt import QGuiApplication, QObject, QSettings, Property, Signal, Slot

from biblioteca_app.servicios import datos


def _lib(nombre: str):
    clave = f"biblioteca_{nombre}"
    if clave in sys.modules:
        return sys.modules[clave]
    spec = importlib.util.spec_from_file_location(clave, datos.REPO / "lib" / f"{nombre}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[clave] = m
    spec.loader.exec_module(m)
    return m


class Revision(QObject):
    cambiado = Signal()
    aviso = Signal(str, str)
    _hecho = Signal(str, "QVariant")

    def __init__(self, fichas, consola, parent=None, en_hilo: bool = True):
        super().__init__(parent)
        self.fichas, self.consola = fichas, consola
        self._en_hilo = en_hilo
        self._s = QSettings()
        self._escrito = str(self._s.value("revision/escrito", "") or "")
        self._ver: dict = {}
        self._fase = "fase1"
        self._ocupado = False
        self._vista = ""
        self._trabajo: dict | None = None      # la revisión simulada, aún sin escribir
        self._base: str | None = None          # la huella del archivo cuando se empezó a simular
        self._cambios: list[str] = []          # qué se simuló, en orden
        self._diff = ""
        self._hecho.connect(self._poner)
        if fichas is not None:
            fichas.cambiado.connect(self._escritos_listos)
        self.releer()

    # ------------------------------------------------------------------ leer
    def _escritos_listos(self) -> None:
        if not self._escrito and self.escritos:
            self.elegir(self.escritos[0]["carpeta"])
        else:
            self.cambiado.emit()

    @Property("QVariantList", notify=cambiado)
    def escritos(self) -> list:
        return list(self.fichas.escritos()) if self.fichas is not None else []

    @Property(str, notify=cambiado)
    def escrito(self) -> str:
        return self._escrito

    @Property(str, notify=cambiado)
    def tituloEscrito(self) -> str:
        e = next((x for x in self.escritos if x["carpeta"] == self._escrito), None)
        return e["titulo"] if e else (Path(self._escrito).name if self._escrito else "")

    @Slot(str)
    def elegir(self, carpeta: str) -> None:
        if self._cambios and (carpeta or "") != self._escrito:
            self.aviso.emit(f"Aplica o descarta los {len(self._cambios)} cambios de «{self.tituloEscrito}» antes de cambiar de escrito.", "aviso")
            self.cambiado.emit()
            return
        self._escrito = carpeta or ""
        self._s.setValue("revision/escrito", self._escrito)
        self._vista = ""
        self.releer()

    @Slot()
    def releer(self) -> None:
        if not self._escrito or not Path(self._escrito).is_dir():
            self._ver = {}
            self.cambiado.emit()
            return
        try:
            self._ver = _lib("revision").ver(Path(self._escrito), self._trabajo)
        except (ValueError, OSError) as e:
            self._ver = {"error": str(e)}
        self._previa()
        self.cambiado.emit()

    def _previa(self) -> None:
        pdf = (self._ver.get("prisma") or {}).get("pdf") if self._ver else ""
        self._vista = _lib("prisma").vista_previa(Path(self._escrito)) if pdf else ""

    @Property("QVariantMap", notify=cambiado)
    def datos(self) -> dict:
        return self._ver

    @Property(bool, notify=cambiado)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(str, notify=cambiado)
    def vistaPrevia(self) -> str:
        return self._vista

    @Property("QVariantList", constant=True)
    def tipos(self) -> list:
        return [{"clave": k, **v} for k, v in _lib("revision").TIPOS.items()]

    @Property("QVariantList", constant=True)
    def clases(self) -> list:
        return [{"clave": k, "texto": v} for k, v in _lib("revision").CLASES.items()]

    # ------------------------------------------------------------------ los registros por fase
    FASES = (("fase1", "Por título y resumen"), ("fase2", "Texto completo"), ("incluidos", "Incluidos"),
             ("excluidos", "Excluidos"), ("duplicados", "Duplicados"))

    def _de_fase(self, x: dict, fase: str) -> bool:
        if fase == "duplicados":
            return bool(x.get("duplicado_de"))
        if x.get("duplicado_de"):
            return False
        if fase == "fase1":
            return not x.get("fase1")
        if fase == "fase2":
            return x.get("fase1") == "incluido" and not x.get("fase2") and x.get("recuperado") is not False
        if fase == "incluidos":
            return x.get("fase2") == "incluido"
        return x.get("fase1") == "excluido" or x.get("fase2") == "excluido" or x.get("recuperado") is False

    @Property("QVariantList", notify=cambiado)
    def fases(self) -> list:
        regs = ((self._ver.get("revision") or {}).get("registros") or []) if self._ver else []
        return [{"clave": k, "texto": t, "n": sum(1 for x in regs if self._de_fase(x, k))} for k, t in self.FASES]

    @Property(str, notify=cambiado)
    def fase(self) -> str:
        return self._fase

    @Slot(str)
    def fijarFase(self, fase: str) -> None:
        if fase in dict(self.FASES) and fase != self._fase:
            self._fase = fase
            self.cambiado.emit()

    @Property("QVariantList", notify=cambiado)
    def registros(self) -> list:
        r = (self._ver.get("revision") or {}) if self._ver else {}
        bases = {b["id"]: b["base"] for b in r.get("busquedas") or []}
        salida = []
        for x in r.get("registros") or []:
            if self._de_fase(x, self._fase):
                estado = ("copia de " + x["duplicado_de"]) if x.get("duplicado_de") else (
                    f"excluido por texto completo: {x.get('motivo2')}" if x.get("fase2") == "excluido" else
                    "texto no conseguido" if x.get("recuperado") is False else
                    ("excluido por título y resumen" + (f": {x['motivo1']}" if x.get("motivo1") else "")) if x.get("fase1") == "excluido" else "")
                detalle = " · ".join(v for v in (x.get("autores", "")[:80], x.get("anio", ""), x.get("doi", ""), bases.get(x["busqueda"], ""), estado) if v)
                salida.append({**x, "detalle": detalle, "recuperadoTexto": "sí" if x.get("recuperado") is True else ""})
        return salida

    # ------------------------------------------------------------------ simular y aplicar
    @Property(int, notify=cambiado)
    def pendientes(self) -> int:
        """Los cambios simulados que aún no están en `fuentes/revision.yml`."""
        return len(self._cambios)

    @Property(str, notify=cambiado)
    def resumenPendientes(self) -> str:
        """«3 cambios sin aplicar: tipo, búsqueda, cribado» (lo que escribiría «Aplicar»)."""
        n = len(self._cambios)
        if not n:
            return ""
        vistos = list(dict.fromkeys(self._cambios))
        return f"{n} cambio" + ("s" if n != 1 else "") + " sin aplicar: " + ", ".join(vistos)

    @Property(str, notify=cambiado)
    def diferencia(self) -> str:
        """La diferencia unificada entre el archivo y la revisión simulada."""
        return self._diff

    def _olvidar(self) -> None:
        self._trabajo, self._base, self._cambios, self._diff = None, None, [], ""

    def _cambiar(self, que: str, fn) -> dict | None:
        """Simula: aplica `fn(r) -> (r, extra)` sobre la copia en memoria (o sobre lo leído, con su huella) y calcula la
        diferencia sin escribir; avisa si otro cambió la bitácora desde que se leyó."""
        m = _lib("revision")
        try:
            if self._trabajo is None:
                r, self._base = m.leer(Path(self._escrito))
            else:
                r = copy.deepcopy(self._trabajo)
            r, extra = fn(r)
            sim = m.escribir(Path(self._escrito), r, self._base, aplicar=False)
        except m.Cambiada as e:
            self.aviso.emit(str(e), "aviso")
            self._olvidar()
            self.releer()
            return None
        except (ValueError, LookupError, OSError) as e:
            self.aviso.emit(str(e), "error")
            return None
        self._trabajo = r
        self._cambios.append(que)
        self._diff = sim["diff"]
        self.consola.registrar("info", f"Revisión ({que}), simulado: {Path(self._escrito).name}/fuentes/revision.yml sin escribir")
        self.releer()
        return extra or {}

    @Slot()
    def aplicar(self) -> None:
        """Escribe la revisión simulada con la huella con que se leyó; si otro la cambió, no pisa: avisa y descarta."""
        if self._trabajo is None:
            return
        m = _lib("revision")
        n = len(self._cambios)
        try:
            m.escribir(Path(self._escrito), self._trabajo, self._base, aplicar=True)
        except m.Cambiada as e:
            self.consola.registrar("warn", "Revisión: no se aplicó; la diferencia descartada era:\n" + self._diff)
            self.aviso.emit(f"{e} Los {n} cambios sin aplicar se descartaron (su diferencia quedó en la consola).", "aviso")
            self._olvidar()
            self.releer()
            return
        except OSError as e:
            self.aviso.emit(str(e), "error")
            return
        self.consola.registrar("ok", f"Revisión: {n} cambios en {Path(self._escrito).name}/fuentes/revision.yml")
        self._olvidar()
        self.aviso.emit(f"Revisión aplicada: {n} cambio" + ("s" if n != 1 else "") + " en fuentes/revision.yml.", "positivo")
        self.releer()

    @Slot()
    def descartar(self) -> None:
        """Olvida la revisión simulada y vuelve a lo que dice el archivo."""
        if self._cambios:
            self.consola.registrar("info", f"Revisión: {len(self._cambios)} cambios descartados sin escribir")
        self._olvidar()
        self.releer()

    @Slot(str, str, str, str)
    def declarar(self, tipo: str, pregunta: str, inclusion: str, exclusion: str) -> None:
        m = _lib("revision")
        lineas = lambda t: [l.strip(" -•\t") for l in (t or "").splitlines() if l.strip(" -•\t")]
        if self._cambiar("tipo", lambda r: (m.declarar(r, tipo, pregunta, lineas(inclusion), lineas(exclusion)), {})) is not None:
            self.aviso.emit(f"Revisión declarada: {m.TIPOS[tipo]['nombre'].lower()} (sin aplicar todavía).", "positivo")

    @Slot("QVariantMap")
    def anadirBusqueda(self, b: dict) -> None:
        m = _lib("revision")
        b = dict(b)
        e = self._cambiar("búsqueda", lambda r: m.buscar(r, str(b.get("base") or ""), str(b.get("cadena") or ""), b.get("resultados"),
                                                        str(b.get("filtros") or ""), str(b.get("fecha") or "") or None,
                                                        str(b.get("clase") or "base"), str(b.get("nota") or "")))
        if e is not None:
            self.aviso.emit(f"Búsqueda {e.get('id', '')} en la bitácora (sin aplicar todavía).", "positivo")

    @Slot(str, str)
    def importar(self, busqueda: str, archivo: str) -> None:
        m = _lib("revision")
        ruta = Path(archivo.removeprefix("file://"))
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            self.aviso.emit(f"No se pudo leer {ruta.name}: {e}", "error")
            return
        e = self._cambiar("importar", lambda r: m.importar(r, busqueda, texto))
        if e is not None:
            self.aviso.emit(f"{e['importados']} registros importados; {e['duplicados']} duplicados (sin aplicar todavía).", "positivo")

    @Slot(str, "QVariantMap")
    def anadirRegistro(self, busqueda: str, x: dict) -> None:
        m = _lib("revision")
        x = dict(x)
        self._cambiar("registro", lambda r: m.registro(r, busqueda, str(x.get("titulo") or ""), str(x.get("autores") or ""),
                                                       str(x.get("anio") or ""), str(x.get("doi") or "")))

    @Slot(str, int, str, str)
    def cribar(self, rid: str, fase: int, decision: str, motivo: str) -> None:
        m = _lib("revision")
        self._cambiar("cribado", lambda r: m.cribar(r, rid, fase, decision, motivo))

    @Slot()
    def generarPrisma(self) -> None:
        """Compila el diagrama con LuaLaTeX en un hilo y escribe `fuentes/prisma.tex` y `.pdf` del escrito (sale del
        archivo: con cambios sin aplicar, pide aplicarlos antes)."""
        if self._cambios:
            self.aviso.emit("Aplica primero los cambios de la revisión: el diagrama sale de fuentes/revision.yml.", "aviso")
            return
        escrito = Path(self._escrito)
        self._ocupado = True
        self.cambiado.emit()

        def trabajo():
            try:
                r = _lib("prisma").generar(escrito, aplicar=True)
            except (ValueError, OSError) as e:
                r = {"error": str(e)}
            self._hecho.emit("prisma", r)
        if self._en_hilo:
            threading.Thread(target=trabajo, name="prisma", daemon=True).start()
        else:
            trabajo()

    def _poner(self, que: str, r) -> None:
        self._ocupado = False
        if r.get("error"):
            self.aviso.emit(r["error"], "error")
        else:
            self.consola.registrar("ok", f"Diagrama PRISMA: {r['pdf']}")
            self.aviso.emit("Diagrama PRISMA listo: fuentes/prisma.pdf" + ("" if r.get("cuadra") else " (no cuadra con la bitácora: revísela)"),
                            "positivo" if r.get("cuadra") else "aviso")
        self.releer()

    @Slot(str)
    def copiar(self, texto: str) -> None:
        if texto:
            QGuiApplication.clipboard().setText(texto)
            self.aviso.emit("Copiado.", "positivo")
