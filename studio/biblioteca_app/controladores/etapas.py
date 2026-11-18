"""biblioteca_app/controladores/etapas.py — las tablas de las vistas de etapa (Adquirir, Entrada, Catalogar, Fichas,
Manifiestos, Sincronizar, Puerta, Tareas automáticas), leídas tal cual de los ledgers, las fichas, los manifiestos, los
respaldos y systemd (`servicios.datos`, `servicios.puerta`); el elemento seleccionado con sus campos y, si es un `.md`
o un `.yml`, su texto (pestaña Elemento); y lo que se hace con él: abrir, abrir su carpeta, copiar la ruta. Solo lee."""

from __future__ import annotations

from pathlib import Path

from gui_comun.modelos import ModeloFiltrado, ModeloTabla
from gui_comun.qt import QObject, Property, Signal, Slot

from biblioteca_app import modelos as mod
from biblioteca_app.servicios import datos, operaciones as ops, puerta as svc_puerta

VISTAS_DATOS = ("adquirir", "entrada", "catalogar", "fichas", "manifiestos", "sincronizar", "puerta", "tareas")
MAX_TEXTO = 200_000
_PEREZOSAS = ("manifiestos",)          # recorren carpetas grandes: se leen la primera vez que se muestran


class Etapas(QObject):
    cambiado = Signal()                 # las tablas y sus contadores
    elementoCambiado = Signal()
    aviso = Signal(str, str)

    def __init__(self, espacio, libros, env, consola, repo: Path = datos.REPO, parent=None):
        super().__init__(parent)
        self.espacio, self.libros, self.env, self.consola, self.repo = espacio, libros, env, consola, repo
        self._tablas = {v: ModeloTabla(mod.COLUMNAS[v], parent=self) for v in VISTAS_DATOS}
        self._modelos = {v: ModeloFiltrado(self._tablas[v], parent=self) for v in VISTAS_DATOS}
        self._leidas: set[str] = set()
        self._fichas: list[dict] = []
        self._catalogacion: list[dict] = []
        self._elemento: dict = {}
        self._vista_elemento = ""
        self._texto = ""
        libros.cambiado.connect(lambda: self.recargar("sincronizar"))
        espacio.vistaCambiada.connect(self._al_cambiar_vista)
        self.recargarTodo()

    # --------------------------------------------------------------- tablas
    @Slot(str, result=QObject)
    def modeloDe(self, vista: str):
        return self._modelos.get(vista)

    @Slot(str, result=QObject)
    def tablaDe(self, vista: str):
        return self._tablas.get(vista)

    def _al_cambiar_vista(self) -> None:
        v = self.espacio.vista
        if v in _PEREZOSAS and v not in self._leidas:
            self.recargar(v)

    @Slot()
    def recargarTodo(self) -> None:
        for v in VISTAS_DATOS:
            if v not in _PEREZOSAS or v == self.espacio.vista or v in self._leidas:
                self.recargar(v)

    @Slot(str)
    def recargar(self, vista: str) -> None:
        """Relee de donde vive lo que esa vista lista (F6, o al terminar una operación)."""
        if vista not in VISTAS_DATOS:
            return
        if vista == "adquirir":
            filas = [mod.fila_descarga(f) for f in datos.descargas(self.repo)]
        elif vista == "entrada":
            filas = [mod.fila_entrada(f) for f in datos.entrada(self.repo, Path(self.env.DOCS_ROOT))]
        elif vista == "catalogar":
            self._catalogacion = datos.catalogacion(self.repo)
            filas = [mod.fila_catalogacion(f) for f in self._catalogacion]
        elif vista == "fichas":
            self._fichas = datos.fichas(self.repo)
            filas = [mod.fila_ficha(f) for f in self._fichas]
        elif vista == "manifiestos":
            filas = [mod.fila_manifiesto(f) for f in datos.manifiestos(self.env, self.repo)]
        elif vista == "sincronizar":
            if "fichas" not in self._leidas:
                self._fichas = datos.fichas(self.repo)
            if "catalogar" not in self._leidas:
                self._catalogacion = datos.catalogacion(self.repo)
            filas = [mod.fila_coherencia(c, (ops.operacion(c["operacion"]) or ops.operacion("indice")).titulo)
                     for c in datos.coherencia(self.libros.indice, self._fichas, self._catalogacion)]
        elif vista == "puerta":
            filas = [mod.fila_respaldo(r) for r in svc_puerta.respaldos()]
        else:
            filas = [mod.fila_tarea(t) for t in svc_puerta.timers()]
        self._tablas[vista].poner(filas)
        self._leidas.add(vista)
        self.cambiado.emit()
        if self._vista_elemento == vista:
            self._fijar_elemento(vista, -1)

    @Property("QVariantMap", notify=cambiado)
    def contadores(self) -> dict:
        """Lo que la navegación muestra junto a cada vista: filas (en Sincronizar, comprobaciones con algo que atender)."""
        c = {v: (self._tablas[v].filas if v in self._leidas else "") for v in VISTAS_DATOS}
        c["sincronizar"] = sum(1 for f in self._tablas["sincronizar"].todas() if f.get("nivel") == "negativo") or ""
        c["entrada"] = sum(1 for f in self._tablas["entrada"].todas() if f.get("paso") != "catalogado")
        return c

    @Property("QVariantList", notify=cambiado)
    def filasMetodo(self) -> list:
        c = self.contadores
        return [{"nombre": e.id, "texto": e.nombre, "icono": e.icono, "contador": c.get(e.id, "")}
                for e in ops.ETAPAS if e.id in ("adquirir", "entrada", "catalogar", "fichas", "manifiestos")]

    @Property("QVariantList", notify=cambiado)
    def filasCoherencia(self) -> list:
        c = self.contadores
        return [{"nombre": e.id, "texto": e.nombre, "icono": e.icono, "contador": c.get(e.id, "") or ""}
                for e in ops.ETAPAS if e.id in ("sincronizar", "puerta", "tareas")]

    @Property("QVariantList", notify=cambiado)
    def tarjetasCoherencia(self) -> list:
        """Las tres tarjetas de arriba de Coherencia (decisiones §9.9): Calibre ⇄ Zotero, Calibre ⇄ KOReader y las tareas
        automáticas, cada una con su estado (positivo · neutro · negativo), una línea y la operación o la vista que la atiende."""
        comp = {f.get("comprobacion"): f for f in self._tablas["sincronizar"].todas()}

        def cuantos(nombre: str) -> int:
            try:
                return int((comp.get(nombre) or {}).get("cuantos") or 0)
            except (TypeError, ValueError):
                return 0
        sin_zotero, sin_clave = cuantos("Libros sin clave de Zotero"), cuantos("Libros sin clave para citar")
        if not comp:
            zotero = {"estado": "neutro", "linea": "Sin comprobar: hace falta el índice (Ctrl+R)"}
        elif sin_zotero or sin_clave:
            zotero = {"estado": "negativo", "linea": " · ".join(x for x in (f"{sin_zotero} sin Zotero" if sin_zotero else "",
                                                                             f"{sin_clave} sin clave para citar" if sin_clave else "") if x)}
        else:
            zotero = {"estado": "positivo", "linea": "Todo enlazado y con clave para citar"}
        zotero.update(titulo="Calibre ⇄ Zotero", boton="Preparar", operacion="enlazar_zotero" if sin_zotero else "zotero_calibre",
                      vista="sincronizar", icono="zotero")

        timers = {f.get("unidad", ""): f for f in self._tablas["tareas"].todas()}
        ko = timers.get("koreader-calibre-sync.timer", {})
        leyendo = int(self.libros.contadores.get("leyendo", 0) or 0)
        lineas = [f"{leyendo} leyéndose" if leyendo else ""]
        if ko.get("activo") == "instalado":
            lineas.append(f"cada 30 min, última {ko.get('ultima', '—')}")
            estado_ko = {"positivo": "positivo", "negativo": "negativo"}.get(ko.get("nivel", ""), "neutro")
        else:
            lineas.append("sin la tarea de cada 30 min")
            estado_ko = "neutro"
        koreader = {"titulo": "Calibre ⇄ KOReader", "estado": estado_ko, "linea": " · ".join(x for x in lineas if x),
                    "boton": "Preparar", "operacion": "koreader", "vista": "sincronizar", "icono": "view-readermode"}

        instaladas = [f for f in timers.values() if f.get("activo") == "instalado"]
        fallidas = [f for f in timers.values() if f.get("nivel") == "negativo"]
        if not timers:
            linea, estado = "systemd no responde", "neutro"
        elif fallidas:
            linea, estado = f"{len(fallidas)} con fallos de {len(timers)}", "negativo"
        elif len(instaladas) < len(timers):
            linea, estado = f"{len(instaladas)} de {len(timers)} instaladas", "neutro"
        else:
            linea, estado = f"Las {len(timers)} en marcha y bien", "positivo"
        tareas = {"titulo": "Tareas automáticas", "estado": estado, "linea": linea, "boton": "Ver", "operacion": "",
                  "vista": "tareas", "icono": "chronometer"}
        return [zotero, koreader, tareas]

    # ------------------------------------------------------------ elemento
    @Slot(str, int)
    def fijarFila(self, vista: str, fila: int) -> None:
        self._fijar_elemento(vista, fila)

    def _fijar_elemento(self, vista: str, fila: int) -> None:
        self._vista_elemento = vista
        modelo = self._modelos.get(vista)
        if modelo is None or fila < 0 or fila >= modelo.rowCount():
            self._elemento, self._texto = {}, ""
        else:
            self._elemento = dict(self._tablas[vista].fila(modelo.filaOrigen(fila)))
            self._texto = self._leer_texto(self._elemento.get("ruta", ""))
        self.elementoCambiado.emit()

    def _leer_texto(self, ruta: str) -> str:
        p = Path(ruta) if ruta else None
        if not p or not p.is_file() or p.suffix.lower() not in (".md", ".yml", ".yaml", ".txt", ".tsv", ".ris"):
            return ""
        try:
            if p.stat().st_size > MAX_TEXTO:
                return f"(archivo de {p.stat().st_size // 1024} KB: ábrelo con Intro)"
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    @Property(bool, notify=elementoCambiado)
    def hayElemento(self) -> bool:
        return bool(self._elemento)

    @Property(str, notify=elementoCambiado)
    def vistaElemento(self) -> str:
        return self._vista_elemento

    @Property(str, notify=elementoCambiado)
    def elementoTitulo(self) -> str:
        e = self._elemento
        if not e:
            return ""
        for clave in ("archivo", "ficha", "proyecto", "comprobacion", "suite", "unidad", "titulo", "referencia"):
            if e.get(clave):
                return str(e[clave])
        return "elemento"

    @Property(str, notify=elementoCambiado)
    def elementoSubtitulo(self) -> str:
        """La ruta del elemento, relativa a la raíz del espacio de trabajo cuando cae dentro."""
        e = self._elemento
        if not e:
            return ""
        texto = str(e.get("ruta") or e.get("carpeta") or e.get("origen") or "")
        docs = str(self.env.DOCS_ROOT).rstrip("/") + "/"
        return texto[len(docs):] if texto.startswith(docs) else texto

    @Property(str, notify=elementoCambiado)
    def elementoRuta(self) -> str:
        e = self._elemento
        return str(e.get("ruta") or e.get("carpeta") or "") if e else ""

    @Property("QVariantList", notify=elementoCambiado)
    def elementoCampos(self) -> list:
        if not self._elemento:
            return []
        campos = mod.campos_elemento(self._elemento, mod.COLUMNAS.get(self._vista_elemento, []))
        if self._elemento.get("afectados"):
            campos.append({"etiqueta": "Afectados", "valor": "\n".join(self._elemento["afectados"])})
        return campos

    @Property(str, notify=elementoCambiado)
    def elementoTexto(self) -> str:
        return self._texto

    @Property(bool, notify=elementoCambiado)
    def elementoEsMarkdown(self) -> bool:
        return self._elemento.get("ruta", "").lower().endswith(".md") if self._elemento else False

    @Property(str, notify=elementoCambiado)
    def elementoOperacion(self) -> str:
        """La operación que resuelve una comprobación de coherencia (vacío en las demás vistas)."""
        return str(self._elemento.get("operacion", "")) if self._elemento else ""

    @Slot()
    def abrirElemento(self) -> None:
        ruta = self.elementoRuta
        if ruta:
            self.espacio.abrir(ruta)
        elif self._elemento:
            self.aviso.emit("Este elemento no es un archivo.", "informacion")

    @Slot()
    def abrirCarpetaElemento(self) -> None:
        if self.elementoRuta:
            self.espacio.abrirDolphin(self.elementoRuta)

    @Slot()
    def copiarRutaElemento(self) -> None:
        self.espacio.copiar(self.elementoRuta or self.elementoTitulo)
