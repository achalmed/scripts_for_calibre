"""biblioteca_app/controladores/operaciones.py — la operación actual de cada vista (del catálogo `servicios.operaciones`):
lo que pide (texto, carpeta o archivo; se recuerda por operación en QSettings), Simular (F5: la orden sin `--aplicar`)
y Aplicar (Ctrl+Intro: con `--aplicar`, tras confirmar en QML con la orden exacta, las bases y el estado de la puerta)
por `gui_comun.tareas.proceso` con la salida íntegra en el panel inferior y Esc para cancelar; el plan (la última
simulación) y el registro (la última aplicación) de cada operación, guardados íntegros en la caché del studio (B7).
La ventana no escribe en ninguna base: toda corrida es la CLI de una suite, por la puerta. Reingeniería B9: los seis
pasos de la puerta (`servicios/pasos.py`) se siguen desde fuera —el estado previo de la puerta, la salida de la suite
y, al terminar, la integridad (`lib/escribir.py integridad`, solo lectura) y el candado libre—, sin abrirla."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from gui_comun.qt import QObject, QSettings, QStandardPaths, Property, Signal, Slot

from biblioteca_app.servicios import operaciones as ops
from biblioteca_app.servicios import pasos as pasos_svc


def cache_del_studio() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation) or (Path.home() / ".cache" / "biblioteca-studio"))


class Operaciones(QObject):
    cambiado = Signal()                     # la operación actual, su entrada, su disponibilidad
    listaCambiada = Signal()                # las operaciones de la vista
    corridaCambiada = Signal()              # en curso, plan, registro
    terminada = Signal(str, bool, int)      # id, aplicar, código de salida
    pasosCambiados = Signal()               # los seis pasos de la puerta
    aviso = Signal(str, str)

    def __init__(self, espacio, puerta, consola, tareas, env, cache: Path | None = None, parent=None):
        super().__init__(parent)
        self.espacio, self.puerta, self.consola, self.tareas, self.env = espacio, puerta, consola, tareas, env
        self._s = QSettings()
        self._cache = (cache or cache_del_studio()) / "corridas"
        self._por_vista: dict[str, str] = {}
        for e in ops.ETAPAS:
            guardada = str(self._s.value(f"operacion/{e.id}", "") or "")
            self._por_vista[e.id] = guardada if ops.operacion(guardada) and ops.etapa_de(guardada) == e.id else (e.operaciones[0].id if e.operaciones else "")
        self._worker = None
        self._id_en_curso = ""
        self._aplicando = False
        self._lineas: list[str] = []
        self._inicio = 0.0
        self._argv: list[str] = []
        self._pasos: list[dict] = []
        self._pasos_de = ""                    # la operación de esos pasos
        self._pasos_corrida = False            # ¿son los de una aplicación (no la vista previa)?
        espacio.vistaCambiada.connect(self._vista_cambio)
        puerta.cambiado.connect(self.cambiado)
        puerta.cambiado.connect(self._previa)
        self.cambiado.connect(self._previa)
        tareas.cambiada.connect(self.cambiado)
        tareas.linea.connect(self._linea)

    def _vista_cambio(self) -> None:
        self.listaCambiada.emit()
        self.cambiado.emit()
        self.corridaCambiada.emit()

    # --------------------------------------------------------- la operación actual
    def _op(self) -> ops.Operacion | None:
        return ops.operacion(self._por_vista.get(self.espacio.vista, ""))

    @Property("QVariantList", notify=listaCambiada)
    def lista(self) -> list:
        """Las operaciones de la vista activa (la lista desplegable de la barra)."""
        return [{"id": o.id, "titulo": o.titulo, "descripcion": o.descripcion} for o in ops.etapa(self.espacio.vista).operaciones]

    @Property(int, notify=listaCambiada)
    def indiceActual(self) -> int:
        actual = self._por_vista.get(self.espacio.vista, "")
        return next((i for i, o in enumerate(ops.etapa(self.espacio.vista).operaciones) if o.id == actual), -1)

    @Slot(int)
    def fijarPorIndice(self, i: int) -> None:
        lista = ops.etapa(self.espacio.vista).operaciones
        if 0 <= i < len(lista):
            self.fijar(lista[i].id)

    @Slot(str)
    def fijar(self, id_: str) -> None:
        """Elige la operación (y lleva a su vista)."""
        o = ops.operacion(id_)
        if o is None:
            return
        vista = ops.etapa_de(id_)
        if self._por_vista.get(vista) != id_:
            self._por_vista[vista] = id_
            self._s.setValue(f"operacion/{vista}", id_)
        if self.espacio.vista != vista:
            self.espacio.fijarVista(vista)         # emite listaCambiada y cambiado
        else:
            self.listaCambiada.emit()
            self.cambiado.emit()
            self.corridaCambiada.emit()

    @Property(bool, notify=cambiado)
    def hayOperacion(self) -> bool:
        return self._op() is not None

    @Property(str, notify=cambiado)
    def actual(self) -> str:
        o = self._op()
        return o.id if o else ""

    @Property(str, notify=cambiado)
    def titulo(self) -> str:
        o = self._op()
        return o.titulo if o else ""

    @Property(str, notify=cambiado)
    def descripcion(self) -> str:
        o = self._op()
        return o.descripcion if o else ""

    @Property(str, notify=cambiado)
    def etapaTexto(self) -> str:
        o = self._op()
        return ops.etapa(ops.etapa_de(o.id)).nombre if o else ""

    @Property(str, notify=cambiado)
    def verbo(self) -> str:
        o = self._op()
        return o.verbo if o else "Simular"

    @Property(bool, notify=cambiado)
    def escribe(self) -> bool:
        o = self._op()
        return bool(o and o.escribe)

    @Property(str, notify=cambiado)
    def bases(self) -> str:
        o = self._op()
        return ",".join(o.bases) if o else ""

    @Property(str, notify=cambiado)
    def basesTexto(self) -> str:
        o = self._op()
        if not o or not o.escribe:
            return "no escribe en ninguna base"
        if not o.bases:
            return "escribe archivos del repo o del vault, no en una base"
        return "escribe en " + " y ".join({"calibre": "Calibre", "zotero": "Zotero"}[b] for b in o.bases) + " (por la puerta: app cerrada, candado y respaldo verificado)"

    @Property(str, notify=cambiado)
    def entradaTipo(self) -> str:
        o = self._op()
        return o.entrada if o else ""

    @Property(str, notify=cambiado)
    def entradaEtiqueta(self) -> str:
        o = self._op()
        return o.etiqueta if o else ""

    def _valor_de(self, o: ops.Operacion) -> str:
        return str(self._s.value(f"entrada/{o.id}", o.valor_inicial()) or "")

    @Property(str, notify=cambiado)
    def valor(self) -> str:
        o = self._op()
        return self._valor_de(o) if o and o.entrada else ""

    @Slot(str)
    def fijarValor(self, v: str) -> None:
        o = self._op()
        v = ops.relativa_al_repo(v)
        if o and o.entrada and v != self._valor_de(o):
            self._s.setValue(f"entrada/{o.id}", v)
            self.cambiado.emit()

    def _python(self) -> str:
        return str(getattr(self.env, "CORE_PYTHON", "") or "python3")

    @Property(str, notify=cambiado)
    def ordenSimular(self) -> str:
        o = self._op()
        return o.texto_orden(False, self._valor_de(o), self._python()) if o else ""

    @Property(str, notify=cambiado)
    def ordenAplicar(self) -> str:
        o = self._op()
        return o.texto_orden(True, self._valor_de(o), self._python()) if o and o.escribe else ""

    # ----------------------------------------------------------- disponibilidad
    @Property(bool, notify=cambiado)
    def enCurso(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @Property(str, notify=cambiado)
    def motivoNoSimular(self) -> str:
        o = self._op()
        if o is None:
            return "Esta vista no tiene operaciones."
        if self.tareas.activa:
            return "Hay una operación en curso (Esc la cancela)."
        if o.entrada and not self._valor_de(o).strip():
            return f"Falta {o.etiqueta} (pestaña Operación)."
        return ""

    @Property(bool, notify=cambiado)
    def puedeSimular(self) -> bool:
        return self.motivoNoSimular == ""

    @Property(str, notify=cambiado)
    def motivoNoAplicar(self) -> str:
        o = self._op()
        if o is None or not o.escribe:
            return "Esta operación no tiene modo «aplicar»: con F5 se ejecuta."
        motivo = self.motivoNoSimular
        if motivo:
            return motivo
        return self.puerta.impedimento(",".join(o.bases))

    @Property(bool, notify=cambiado)
    def puedeAplicar(self) -> bool:
        return self.motivoNoAplicar == ""

    @Property(str, notify=cambiado)
    def textoConfirmacion(self) -> str:
        """Lo que el diálogo de Aplicar muestra: la orden exacta, las bases que toca y el estado de la puerta."""
        o = self._op()
        if o is None:
            return ""
        return (f"Orden: {self.ordenAplicar}\n\nEsta operación {self.basesTexto}.\n"
                + (f"Ahora: {self.puerta.estadoDe(','.join(o.bases))}.\n" if o.bases else "")
                + "\nLa puerta vuelve a comprobarlo antes de escribir; el respaldo queda en la carpeta de la puerta (vista Puerta).")

    # ------------------------------------------------------------------ los pasos de la puerta (B9)
    def _previa(self) -> None:
        """Fuera de una aplicación: los pasos de la operación actual como están ahora (app cerrada, candado libre)."""
        if self._aplicando and self.enCurso:
            return
        o = self._op()
        if o is None or not o.escribe or not o.bases:
            nuevo, de = [], ""
        elif self._pasos_corrida and self._pasos_de == o.id:
            return                                   # se conservan los de la última aplicación de esta operación
        else:
            nuevo, de = pasos_svc.previa(pasos_svc.nuevos(o.bases), self.puerta.abiertas, self.puerta.ocupados, o.bases), o.id
        if nuevo != self._pasos or de != self._pasos_de:
            self._pasos, self._pasos_de, self._pasos_corrida = nuevo, de, False
            self.pasosCambiados.emit()

    @Property("QVariantList", notify=pasosCambiados)
    def pasos(self) -> list:
        return [dict(p) for p in self._pasos]

    @Property(bool, notify=pasosCambiados)
    def pasosDeCorrida(self) -> bool:
        return self._pasos_corrida

    @Property(str, notify=pasosCambiados)
    def resumenPasos(self) -> str:
        if not self._pasos:
            return ""
        return pasos_svc.resumen(self._pasos) if self._pasos_corrida else "Así está la puerta ahora; la suite la abre al aplicar"

    def _bases_rutas(self, o) -> list[str]:
        rutas = []
        if "calibre" in o.bases:
            rutas.append(str(getattr(self.env, "CALIBRE_DB", "") or Path(self.env.BIBLIOTECA_DIR) / "metadata.db"))
        if "zotero" in o.bases and getattr(self.env, "ZOTERO_DB", ""):
            rutas.append(str(self.env.ZOTERO_DB))
        return rutas

    def _integridad(self, o) -> bool | None:
        """`lib/escribir.py integridad` (PRAGMA integrity_check en solo lectura) de las bases que toca la operación."""
        rutas = self._bases_rutas(o)
        if not rutas:
            return None
        try:
            r = subprocess.run([self._python(), str(ops.REPO / "lib" / "escribir.py"), "integridad", *rutas],
                               capture_output=True, text=True, timeout=300, cwd=str(ops.REPO))
        except (OSError, subprocess.SubprocessError):
            return None
        return r.returncode == 0

    # ------------------------------------------------------------------ correr
    @Slot(result=bool)
    def simular(self) -> bool:
        """F5: la orden sin `--aplicar` (la suite simula por omisión; las que no escriben, se ejecutan)."""
        return self._lanzar(False)

    @Slot(result=bool)
    def aplicar(self) -> bool:
        """Ctrl+Intro, tras la confirmación en QML: la orden con `--aplicar`, por la puerta."""
        if not self.puedeAplicar:
            self.aviso.emit(self.motivoNoAplicar, "aviso")
            return False
        return self._lanzar(True)

    def _lanzar(self, aplicar: bool) -> bool:
        o = self._op()
        if o is None or not self.puedeSimular:
            self.aviso.emit(self.motivoNoSimular, "aviso")
            return False
        if not o.programa().is_file():
            self.aviso.emit(f"No existe {o.orden[0]} en el repo.", "error")
            return False
        valor = self._valor_de(o).strip()
        argv = o.argv(aplicar, valor, self._python())
        self._argv, self._id_en_curso, self._aplicando, self._lineas, self._inicio = argv, o.id, aplicar, [], time.monotonic()
        nombre = f"{'Aplicando' if aplicar else ('Simulando' if o.escribe else 'Ejecutando')}: {o.titulo}"
        if aplicar and o.bases:
            self._pasos = pasos_svc.empezar(pasos_svc.previa(pasos_svc.nuevos(o.bases), self.puerta.abiertas, self.puerta.ocupados, o.bases))
            self._pasos_de, self._pasos_corrida = o.id, True
            self.pasosCambiados.emit()
        self._worker = self.tareas.proceso(nombre, argv, cwd=str(ops.REPO), al_terminar=lambda codigo, i=o.id, a=aplicar: self._fin(codigo, i, a))
        self.cambiado.emit()
        self.corridaCambiada.emit()
        return True

    def _linea(self, texto: str, nivel: str) -> None:
        if self._worker is not None:
            self._lineas.append(texto)
            if self._aplicando and self._pasos_corrida and pasos_svc.linea(self._pasos, texto):
                self.pasosCambiados.emit()

    def _fin(self, codigo: int, id_: str, aplicar: bool) -> None:
        self._worker = None
        segundos = time.monotonic() - self._inicio
        o = ops.operacion(id_)
        if aplicar and o is not None and o.bases and self._pasos_corrida and self._pasos_de == id_:
            respaldo = next((p["estado"] for p in self._pasos if p["clave"] == "respaldo"), "")
            integridad = self._integridad(o) if respaldo == "hecho" else None
            pasos_svc.terminar(self._pasos, codigo, integridad, self.puerta.candado_libre(o.bases))
            self.pasosCambiados.emit()
            self.consola.registrar("info" if "falló" not in pasos_svc.resumen(self._pasos) else "error", f"Puerta: {pasos_svc.resumen(self._pasos)}")
        cabecera = (f"# {time.strftime('%Y-%m-%d %H:%M:%S')} · {'aplicado' if aplicar else 'simulación'} · {o.titulo if o else id_}\n"
                    f"# {' '.join(self._argv)}\n# código de salida {codigo} · {segundos:.1f} s\n\n")
        self._escribir(id_, aplicar, cabecera + "\n".join(self._lineas[1:] if self._lineas and self._lineas[0].startswith("$ ") else self._lineas) + "\n")
        que = "aplicada" if aplicar else ("simulada" if o and o.escribe else "ejecutada")
        if codigo == 0:
            self.aviso.emit(f"{o.titulo if o else id_} {que} en {segundos:.1f} s" + (": revisa el plan antes de aplicar (Ctrl+Intro)." if not aplicar and o and o.escribe else "."),
                            "positivo" if aplicar else "informacion")
        elif codigo == 75:
            self.aviso.emit(f"{o.titulo if o else id_}: la puerta no se abrió (75): la aplicación está abierta u otra suite tiene el candado.", "aviso")
        else:
            self.aviso.emit(f"{o.titulo if o else id_} terminó con código {codigo} ({segundos:.1f} s): revisa la salida (F4).", "error")
        self.cambiado.emit()
        self.corridaCambiada.emit()
        self.terminada.emit(id_, aplicar, codigo)

    @Slot()
    def cancelar(self) -> None:
        if self.enCurso:
            self.tareas.cancelar()

    # ------------------------------------------------------------- plan y registro
    def _archivo(self, id_: str, aplicar: bool) -> Path:
        return self._cache / f"{id_}.{'registro' if aplicar else 'plan'}.txt"

    def _escribir(self, id_: str, aplicar: bool, texto: str) -> None:
        try:
            self._cache.mkdir(parents=True, exist_ok=True)
            self._archivo(id_, aplicar).write_text(texto, encoding="utf-8")
        except OSError as e:
            self.consola.registrar("warn", f"No se pudo guardar el {'registro' if aplicar else 'plan'}: {e}")

    def _leer(self, aplicar: bool) -> str:
        o = self._op()
        if o is None:
            return ""
        try:
            return self._archivo(o.id, aplicar).read_text(encoding="utf-8")
        except OSError:
            return ""

    @Property(str, notify=corridaCambiada)
    def plan(self) -> str:
        """La salida íntegra de la última simulación (o ejecución) de la operación actual."""
        return self._leer(False)

    @Property(str, notify=corridaCambiada)
    def registro(self) -> str:
        """La salida íntegra de la última aplicación de la operación actual."""
        return self._leer(True)

    # --------------------------------------------------------------------- paleta
    def entradas_paleta(self, _texto: str) -> list[dict]:
        return [{"nombre": f"op.ir.{o.id}", "texto": f"Operación: {o.titulo}", "grupo": ops.etapa(e.id).nombre, "icono": e.icono,
                 "ejecutar": lambda i=o.id: self.fijar(i)} for e in ops.ETAPAS for o in e.operaciones]
