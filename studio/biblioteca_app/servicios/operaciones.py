"""biblioteca_app/servicios/operaciones.py — el catálogo de las operaciones de Biblioteca Studio (sin Qt, se prueba solo):
cada una es una orden de una suite de este repo, agrupada por la vista (etapa) en la que se ofrece.

La ventana no escribe nada por su cuenta: corre la misma CLI que se usa en la terminal, primero sin `--aplicar`
(«Simular», F5; la suite simula por omisión) y después con su bandera («Aplicar», Ctrl+Intro, tras confirmar). Así
la puerta de escritura sigue siendo una sola (`lib/escribir*`). Una operación que escribe en Calibre o en Zotero no
se aplica con la aplicación abierta ni con el candado ocupado (`puerta.py`). Las de Bash corren con `bash`; las de
Python, con el intérprete que ya usan las suites y los timers (`CORE_PYTHON` de `core/env`), nunca con el de la ventana.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Operacion:
    id: str
    titulo: str
    descripcion: str
    orden: tuple[str, ...]                 # programa relativo al repo y sus argumentos fijos
    aplicar: tuple[str, ...] | None = ("--aplicar",)   # lo que se añade para aplicar; None: una sola orden (no escribe en bases)
    simular: tuple[str, ...] = ()          # lo que se añade para simular (si la suite no simula sola)
    bases: tuple[str, ...] = ()            # «calibre», «zotero»: aplicar exige la aplicación cerrada y el candado libre
    entrada: str = ""                      # «texto», «carpeta» o «archivo»: lo que pide antes de la orden
    etiqueta: str = ""                     # qué se escribe en esa entrada
    defecto: str = ""                      # valor inicial de la entrada (relativo al repo si es una ruta)

    @property
    def escribe(self) -> bool:
        """¿Tiene un modo «aplicar» distinto de la simulación?"""
        return self.aplicar is not None

    @property
    def verbo(self) -> str:
        """Lo que hace F5: «Simular» si hay un modo aplicar; si no, «Ejecutar»."""
        return "Simular" if self.escribe else "Ejecutar"

    def programa(self) -> Path:
        return REPO / self.orden[0]

    def argv(self, aplicar: bool, valor: str = "", python: str = "python3") -> list[str]:
        """La orden completa: `bash` para los `.sh`, `python` (CORE_PYTHON) para los `.py`; la entrada se parte como en
        la terminal si es texto, o va entera si es una ruta; al final, la cola de simular o de aplicar."""
        programa, *fijos = self.orden
        ruta = REPO / programa
        base = ["bash", str(ruta)] if programa.endswith(".sh") else [python, str(ruta)]
        extra: list[str] = []
        if self.entrada == "texto":
            extra = shlex.split(valor)
        elif self.entrada and valor:
            extra = [valor]
        cola = list(self.aplicar or ()) if aplicar else list(self.simular)
        return base + fijos + extra + cola

    def texto_orden(self, aplicar: bool, valor: str = "", python: str = "python3") -> str:
        """La orden tal como se escribiría en la terminal, relativa al repo (para el diálogo y la pestaña Operación)."""
        partes = self.argv(aplicar, valor, python)
        return shlex.join(p[len(str(REPO)) + 1:] if p.startswith(str(REPO) + "/") else p for p in partes)

    def valor_inicial(self) -> str:
        """Lo que la entrada trae al principio: una ruta relativa al repo (la orden corre con el repo como carpeta actual)."""
        return self.defecto


def relativa_al_repo(ruta: str) -> str:
    """Una ruta dentro del repo, relativa a él (así la orden y la pantalla no llevan la carpeta de la máquina); las demás, igual."""
    ruta = (ruta or "").strip()
    prefijo = str(REPO) + "/"
    return ruta[len(prefijo):] if ruta.startswith(prefijo) else ruta


@dataclass(frozen=True)
class Etapa:
    id: str                                # también el nombre de la vista
    nombre: str
    icono: str
    para_que: str
    operaciones: tuple[Operacion, ...] = field(default_factory=tuple)


O = Operacion
ETAPAS = (
    Etapa("libros", "Libros", "folder-book", "Los libros del índice (lib/indice.py): el índice lo leen también los complementos "
          "de Calibre, KOReader y Zotero", (
        O("indice", "Actualizar el índice", "El índice que leen la ventana y los complementos de Calibre, KOReader y Zotero "
          "(solo lee las bases; escribe el JSON fuera del repo).", ("lib/indice.py",)),
    )),
    Etapa("adquirir", "Adquirir", "download", "¿Ya está en la biblioteca? Y si no, descargarlo de una fuente abierta (suite "
          "fuentes; ledger fuentes_descargadas.tsv)", (
        O("verificar", "¿Ya está en la biblioteca?", "Por título, autor, ISBN, DOI o una referencia completa.",
          ("main.py", "verificar"), aplicar=None, entrada="texto", etiqueta="referencia, DOI o ISBN"),
        O("fuentes", "Fuentes disponibles", "Las fuentes abiertas de las que se puede descargar.", ("main.py", "fuentes"),
          aplicar=None),
        O("localizar", "Localizar en una fuente", "Busca la referencia en una fuente sin descargar.", ("main.py", "localizar"),
          aplicar=None, entrada="texto", etiqueta="fuente y referencia"),
        O("descargar", "Descargar", "Descarga la referencia de la fuente a la zona de entrada (con hash y procedencia).",
          ("main.py", "descargar"), aplicar=None, entrada="texto", etiqueta="fuente y referencia"),
        O("estado_fuentes", "Estado de lo descargado", "El ledger de descargas.", ("main.py", "estado"), aplicar=None),
    )),
    Etapa("entrada", "Entrada", "document-import", "De la zona de entrada a la biblioteca: identificar, catalogar en Calibre y "
          "exportar el RIS para Zotero (suite ingesta)", (
        O("estado", "Estado de la entrada", "Qué hay en la zona de entrada y en qué paso está cada archivo.",
          ("ingesta/main.sh", "estado"), aplicar=None),
        O("recibir", "Recibir", "Toma lo nuevo de la zona de entrada y lo anota en el ledger.", ("ingesta/main.sh", "recibir"),
          aplicar=None),
        O("identificar", "Identificar", "Busca título, autor, ISBN o DOI de cada archivo recibido.",
          ("ingesta/main.sh", "identificar"), aplicar=None),
        O("catalogar", "Catalogar en Calibre", "Añade lo identificado a Calibre, deduplicando por huella y título.",
          ("ingesta/main.sh", "catalogar"), bases=("calibre",)),
        O("zotero", "Exportar a Zotero", "El RIS de lo catalogado para importarlo en Zotero.", ("ingesta/main.sh", "zotero"),
          aplicar=None),
        O("archivar", "Archivar", "Saca de la entrada lo ya catalogado y lo registra en el fuentes.yml del proyecto.",
          ("ingesta/main.sh", "archivar")),
        O("ocr", "OCR de los escaneados", "Reconoce el texto de los PDF que no lo tienen (ocrmypdf).", ("ingesta/main.sh", "ocr")),
        O("todo", "Todo el recorrido", "Recibir → identificar → catalogar → exportar → archivar.", ("ingesta/main.sh", "todo"),
          bases=("calibre",)),
    )),
    Etapa("catalogar", "Catalogar", "view-catalog", "Los metadatos de Calibre: aplicar lo catalogado (resumen_catalogacion.tsv) y "
          "cotejarlos contra bases públicas", (
        O("catalogacion", "Aplicar la catalogación", "Lleva a Calibre lo de resumen_catalogacion.tsv (autor «Nombre, "
          "Apellidos», serie, etiquetas del vocabulario cerrado).", ("catalogacion/main.sh",), bases=("calibre",)),
        O("verificacion", "Verificar contra bases públicas", "Coteja los metadatos de Calibre y deja un informe (solo lee).",
          ("verificacion/main.sh",), aplicar=None),
        O("verificacion_isbn", "Verificar por ISBN", "Lo mismo, solo con los ISBN.", ("verificacion/main.sh", "--modo", "isbn"),
          aplicar=None),
        O("migracion", "Campaña de migración", "Una campaña de metadatos (P1–P9): plan, ensayo sobre una copia y "
          "deshacer probado; aplicar la lleva a la base real por la puerta.", ("migraciones/main.py",), bases=("calibre",),
          entrada="texto", etiqueta="campaña (P1…P9)"),
    )),
    Etapa("fichas", "Fichas", "document-edit-verify", "Las fichas canónicas del Método Documental (catalogacion/fichas/) y los "
          "pasajes con su página", (
        O("fichas_validar", "Validar las fichas", "El formato único de cada ficha.", ("fichas/main.py", "validar"),
          aplicar=None, entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        O("fichas_estado", "Estado de las fichas", "Cuántas hay, verificadas y pendientes.", ("fichas/main.py", "estado"),
          aplicar=None, entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        O("fichas_verificar", "Verificar textuales y paráfrasis", "Coteja cada cita contra el texto del libro.",
          ("fichas/main.py", "verificar"), entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        O("lecturas", "Pasajes por concepto", "Del lecturas.yml de un curso o proyecto: cada concepto con su página.",
          ("lecturas/main.py",), entrada="archivo", etiqueta="lecturas.yml"),
    )),
    Etapa("manifiestos", "Manifiestos", "view-list-text", "El fuentes.yml de cada proyecto en vez de enlaces a la biblioteca", (
        O("manifiesto_todo", "Todos los fuentes.yml", "Genera y verifica el de cada proyecto vigilado.",
          ("manifiesto/main.py", "todo")),
        O("manifiesto_verificar", "Verificar un proyecto", "¿Cada fuente de su fuentes.yml está en la biblioteca?",
          ("manifiesto/main.py", "verificar"), aplicar=None, entrada="carpeta", etiqueta="carpeta del proyecto"),
        O("manifiesto_generar", "Generar el de un proyecto", "Su fuentes.yml desde lo que cita.",
          ("manifiesto/main.py", "generar"), entrada="carpeta", etiqueta="carpeta del proyecto"),
        O("manifiesto_bib", "Bibliografía de un proyecto", "Su references.bib desde Calibre y Zotero.",
          ("manifiesto/main.py", "bib"), entrada="carpeta", etiqueta="carpeta del proyecto"),
    )),
    Etapa("sincronizar", "Sincronizar", "folder-sync", "Calibre ⇄ Zotero ⇄ KOReader: las comprobaciones de coherencia y los "
          "sincronizadores; cada uno simula y reporta, aplicar escribe por la puerta", (
        O("zotero_calibre", "Zotero ⇄ Calibre", "Metadatos en las dos direcciones: Zotero manda en citas y metadatos, "
          "Calibre en los archivos.", ("sincronizar-zotero/main.sh",), bases=("calibre", "zotero")),
        O("koreader", "KOReader → Calibre", "Progreso, tiempo, estado y apuntes de cada libro (también corre cada 30 min).",
          ("koreader/main.sh",), bases=("calibre",)),
        O("lectura", "Tiempo de lectura de Zotero", "El tiempo de lectura y los metadatos de estudio, a sus columnas.",
          ("lectura/main.sh",), bases=("calibre",)),
        O("enlazar_zotero", "Enlazar con Zotero lo que falta", "Simular deja el informe y el .ris de lo que no está en "
          "Zotero; aplicar escribe las claves de los adjuntos.", ("lectura/main.sh", "--enlazar"), simular=("--ris",),
          bases=("calibre",)),
        O("notas", "Enlazar las notas de lectura", "Las notas que creó el complemento de KOReader o Zotero Integration, "
          "en la columna «apuntes» de su libro.", ("lib/enlazar_notas.py",), bases=("calibre",)),
        O("metadatos_pdf", "Metadatos en los PDF", "Incrusta los metadatos de Calibre en cada PDF (XMP).",
          ("metadatos-pdf/main.sh", "embed"), bases=("calibre",)),
    )),
    Etapa("puerta", "Puerta", "object-locked", "Una sola puerta escribe en Calibre y en Zotero: con la aplicación cerrada, "
          "con candado y con respaldo verificado. Aquí, sus respaldos y cómo deshacer"),
    Etapa("tareas", "Tareas automáticas", "chronometer", "Los tres timers de usuario (KOReader → Calibre y Zotero → Calibre "
          "cada 30 min; los metadatos a diario) y sus plantillas de systemd/", (
        O("timers_verificar", "Verificar las tareas automáticas", "¿Lo instalado coincide con las plantillas de systemd/?",
          ("systemd/instalar.sh", "--verificar"), aplicar=None),
        O("timers_instalar", "Instalar las tareas automáticas", "Escribe las tres unidades desde las plantillas y las activa "
          "(simula por omisión).", ("systemd/instalar.sh",)),
    )),
)

NOMBRES_ETAPAS = tuple(e.id for e in ETAPAS)
_POR_ID = {o.id: o for e in ETAPAS for o in e.operaciones}
_ETAPA_DE = {o.id: e.id for e in ETAPAS for o in e.operaciones}


def todas() -> list[Operacion]:
    return [o for e in ETAPAS for o in e.operaciones]


def etapa(nombre: str) -> Etapa:
    return next(e for e in ETAPAS if e.id == nombre)


def operacion(id_: str) -> Operacion | None:
    return _POR_ID.get(id_)


def etapa_de(id_: str) -> str:
    return _ETAPA_DE.get(id_, "")
