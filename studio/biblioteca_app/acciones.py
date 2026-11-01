"""Las acciones de Biblioteca Studio (sin Qt, se prueba solo): cada una es una orden de una suite de este repo.

La ventana no escribe nada por su cuenta: corre la misma CLI que se usa en la terminal, primero «Simular» (como la
suite por omisión) y después «Aplicar» (con su bandera). Así la puerta de escritura sigue siendo una sola
(`lib/escribir*`). Una acción que escribe en Calibre o en Zotero no se aplica con la aplicación abierta.
"""
from __future__ import annotations

import fcntl
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Accion:
    id: str
    titulo: str
    descripcion: str
    orden: tuple[str, ...]                 # programa relativo al repo y sus argumentos fijos
    aplicar: tuple[str, ...] | None = ("--aplicar",)   # lo que se añade para aplicar; None: una sola orden
    simular: tuple[str, ...] = ()          # lo que se añade para simular (si la suite no simula sola)
    bases: tuple[str, ...] = ()            # «calibre», «zotero»: aplicar exige la aplicación cerrada
    entrada: str = ""                      # «texto», «carpeta» o «archivo»: lo que pide antes de la orden
    etiqueta: str = ""                     # qué se escribe en esa entrada
    defecto: str = ""                      # valor inicial de la entrada (relativo al repo si es una ruta)

    def argv(self, aplicar: bool, valor: str = "") -> list[str]:
        programa, *fijos = self.orden
        ruta = REPO / programa
        base = ["bash", str(ruta)] if programa.endswith(".sh") else [sys.executable, str(ruta)]
        extra = []
        if self.entrada == "texto":
            extra = shlex.split(valor)
        elif self.entrada and valor:
            extra = [valor]
        cola = list(self.aplicar or ()) if aplicar else list(self.simular)
        return base + fijos + extra + cola


@dataclass(frozen=True)
class Pagina:
    id: str
    nombre: str
    icono: str
    para_que: str
    acciones: tuple[Accion, ...] = field(default_factory=tuple)


A = Accion
PAGINAS = (
    Pagina("entrada", "Entrada", "bandeja", "De la zona de entrada a la biblioteca: identificar, catalogar en Calibre y "
           "exportar el RIS para Zotero (suite ingesta)", (
        A("estado", "Estado de la entrada", "Qué hay en la zona de entrada y en qué paso está cada archivo.",
          ("ingesta/main.sh", "estado"), aplicar=None),
        A("recibir", "Recibir", "Toma lo nuevo de la zona de entrada y lo anota en el ledger.", ("ingesta/main.sh", "recibir"),
          aplicar=None),
        A("identificar", "Identificar", "Busca título, autor, ISBN o DOI de cada archivo recibido.",
          ("ingesta/main.sh", "identificar"), aplicar=None),
        A("catalogar", "Catalogar en Calibre", "Añade lo identificado a Calibre, deduplicando por huella y título.",
          ("ingesta/main.sh", "catalogar"), bases=("calibre",)),
        A("zotero", "Exportar a Zotero", "El RIS de lo catalogado para importarlo en Zotero.", ("ingesta/main.sh", "zotero"),
          aplicar=None),
        A("archivar", "Archivar", "Saca de la entrada lo ya catalogado.", ("ingesta/main.sh", "archivar")),
        A("ocr", "OCR de los escaneados", "Reconoce el texto de los PDF que no lo tienen (ocrmypdf).", ("ingesta/main.sh", "ocr")),
        A("todo", "Todo el recorrido", "Recibir → identificar → catalogar → exportar → archivar.", ("ingesta/main.sh", "todo"),
          bases=("calibre",)),
    )),
    Pagina("adquirir", "Adquirir", "descarga", "¿Ya está en la biblioteca? Y si no, descargarlo de una fuente abierta "
           "(suite fuentes)", (
        A("verificar", "¿Ya está en la biblioteca?", "Por título, autor, ISBN, DOI o una referencia completa.",
          ("main.py", "verificar"), aplicar=None, entrada="texto", etiqueta="referencia, DOI o ISBN"),
        A("fuentes", "Fuentes disponibles", "Las fuentes abiertas de las que se puede descargar.", ("main.py", "fuentes"),
          aplicar=None),
        A("localizar", "Localizar en una fuente", "Busca la referencia en una fuente sin descargar.", ("main.py", "localizar"),
          aplicar=None, entrada="texto", etiqueta="fuente y referencia"),
        A("descargar", "Descargar", "Descarga la referencia de la fuente a la zona de entrada.", ("main.py", "descargar"),
          aplicar=None, entrada="texto", etiqueta="fuente y referencia"),
        A("estado_fuentes", "Estado de lo descargado", "El ledger de descargas.", ("main.py", "estado"), aplicar=None),
    )),
    Pagina("catalogar", "Catalogar y verificar", "verificar", "Los metadatos de Calibre contra bases públicas y la "
           "aplicación de lo catalogado", (
        A("catalogacion", "Aplicar la catalogación", "Lleva a Calibre lo de resumen_catalogacion.tsv (autor «Nombre, "
          "Apellidos», serie, etiquetas del vocabulario cerrado).", ("catalogacion/main.sh",), bases=("calibre",)),
        A("verificacion", "Verificar contra bases públicas", "Coteja los metadatos de Calibre y deja un informe.",
          ("verificacion/main.sh",), aplicar=None),
        A("verificacion_isbn", "Verificar por ISBN", "Lo mismo, solo con los ISBN.", ("verificacion/main.sh", "--modo", "isbn"),
          aplicar=None),
        A("migracion", "Campaña de migración", "Una campaña de metadatos (P1–P9): plan, ensayo sobre una copia y "
          "deshacer probado; aplicar la lleva a la base real por la puerta.", ("migraciones/main.py",), bases=("calibre",),
          entrada="texto", etiqueta="campaña (P1…P9)"),
    )),
    Pagina("sincronizar", "Sincronizar", "sincronizar", "Calibre ⇄ Zotero ⇄ KOReader: cada sincronizador simula y "
           "reporta; aplicar escribe por la puerta", (
        A("zotero_calibre", "Zotero ⇄ Calibre", "Metadatos en las dos direcciones: Zotero manda en citas y metadatos, "
          "Calibre en los archivos.", ("sincronizar-zotero/main.sh",), bases=("calibre", "zotero")),
        A("koreader", "KOReader → Calibre", "Progreso, tiempo, estado y apuntes de cada libro (también corre cada 30 min).",
          ("koreader/main.sh",), bases=("calibre",)),
        A("lectura", "Tiempo de lectura de Zotero", "El tiempo de lectura y los metadatos de estudio, a sus columnas.",
          ("lectura/main.sh",), bases=("calibre",)),
        A("enlazar_zotero", "Enlazar con Zotero lo que falta", "Simular deja el informe y el .ris de lo que no está en "
          "Zotero; aplicar escribe las claves de los adjuntos.", ("lectura/main.sh", "--enlazar"), simular=("--ris",),
          bases=("calibre",)),
        A("notas", "Enlazar las notas de lectura", "Las notas que creó el complemento de KOReader o Zotero Integration, "
          "en la columna «apuntes» de su libro.", ("lib/enlazar_notas.py",), bases=("calibre",)),
        A("metadatos_pdf", "Metadatos en los PDF", "Incrusta los metadatos de Calibre en cada PDF (XMP).",
          ("metadatos-pdf/main.sh", "embed"), bases=("calibre",)),
        A("indice", "Actualizar el índice", "El índice que leen los complementos de Calibre, KOReader y Zotero (solo "
          "lee las bases).", ("lib/indice.py",)),
    )),
    Pagina("fichas", "Fichas y lecturas", "documento", "Las fichas del Método Documental y los pasajes con su página", (
        A("fichas_validar", "Validar las fichas", "El formato único de cada ficha.", ("fichas/main.py", "validar"),
          aplicar=None, entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        A("fichas_estado", "Estado de las fichas", "Cuántas hay, verificadas y pendientes.", ("fichas/main.py", "estado"),
          aplicar=None, entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        A("fichas_verificar", "Verificar textuales y paráfrasis", "Coteja cada cita contra el texto del libro.",
          ("fichas/main.py", "verificar"), entrada="carpeta", etiqueta="carpeta de fichas", defecto="catalogacion/fichas"),
        A("lecturas", "Pasajes por concepto", "Del lecturas.yml de un curso o proyecto: cada concepto con su página.",
          ("lecturas/main.py",), entrada="archivo", etiqueta="lecturas.yml"),
    )),
    Pagina("manifiestos", "Manifiestos", "receta", "El fuentes.yml de cada proyecto en vez de enlaces a la biblioteca", (
        A("manifiesto_todo", "Todos los fuentes.yml", "Genera y verifica el de cada proyecto vigilado.",
          ("manifiesto/main.py", "todo")),
        A("manifiesto_verificar", "Verificar un proyecto", "¿Cada fuente de su fuentes.yml está en la biblioteca?",
          ("manifiesto/main.py", "verificar"), aplicar=None, entrada="carpeta", etiqueta="carpeta del proyecto"),
        A("manifiesto_generar", "Generar el de un proyecto", "Su fuentes.yml desde lo que cita.",
          ("manifiesto/main.py", "generar"), entrada="carpeta", etiqueta="carpeta del proyecto"),
        A("manifiesto_bib", "Bibliografía de un proyecto", "Su references.bib desde Calibre y Zotero.",
          ("manifiesto/main.py", "bib"), entrada="carpeta", etiqueta="carpeta del proyecto"),
    )),
)


def todas() -> list[Accion]:
    return [a for p in PAGINAS for a in p.acciones]


# --- el estado de las aplicaciones y de la puerta ---------------------------------------------------------------

def abiertas() -> set[str]:
    """«calibre» y «zotero» si su proceso corre (el mismo criterio que core/shell-lib/detectar_apps.sh)."""
    vistas = set()
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            nombre = comm.read_text().strip().lower()
        except OSError:
            continue
        for app in ("calibre", "zotero"):
            if nombre.startswith(app):
                vistas.add(app)
    return vistas


def candado_ocupado(ruta: str | os.PathLike) -> bool:
    """¿Alguna suite tiene el candado? Se prueba sin quedárselo (flock compartido, sin esperar)."""
    p = Path(ruta)
    if not p.exists():
        return False
    try:
        with open(p) as f:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        return False
    except OSError:
        return True
