# config.py — suite `fichas`: validar, verificar contra el PDF e indexar las fichas del Método Documental.
#
# Normativo: ~/Documents/prompts/00 metodo/fichas_formato_y_voz.md (frontmatter único, nombres y secciones
# por tipo, once categorías, estados de verificación). Esta suite no inventa nada: aplica ese documento.
# Creada en FD2 (2026-09-07). Todo valor editable vive aquí; lib/ no fija rutas.

from pathlib import Path
import importlib.util

# core/env.py da la raíz y las carpetas por nombre (normativa 5.1-5.2; ola 0): se sube hasta hallarlo.
_d = Path(__file__).resolve()
while _d != _d.parent and not (_d / "core" / "env.py").is_file():
    _d = _d.parent
_s = importlib.util.spec_from_file_location("core_env", _d / "core" / "env.py")
env = importlib.util.module_from_spec(_s)
_s.loader.exec_module(env)

RAIZ = Path(__file__).resolve().parent
DOCS = env.DOCS_ROOT                                              # ~/Documents
PY_COMMON = env.PY_COMMON                                          # resolutor core/py-common/biblioteca.py
RESPALDOS = env.RESPALDOS_DIR / "biblioteca" / "fuentes" / "fichas"   # respaldo y UNDO de grafia y migrar (P240; antes una carpeta retirada de meta)
NORMA = env.PROMPTS_DIR / "00 metodo" / "fichas_formato_y_voz.md"   # «00 metodo» es carpeta de prompts, no del vault

# Claves del frontmatter, en este orden (fichas_formato_y_voz.md §1; snake_case desde meta/NORMATIVA_ARCHIVOS.md §1,
# 2026-09-13; `main.py grafia <carpeta> --aplicar` migra las fichas anteriores). Los valores vacíos se escriben vacíos.
CLAVES = ["tipo", "calibre_id", "zotero_key", "clave_bibtex", "proyecto", "pagina", "categoria", "uso", "verificacion"]
CLAVES_VERIFICACION = ["estado", "metodo", "fecha"]

# Qué claves omite cada tipo (§1: catalogación omite pagina/categoria/uso; síntesis, fuente y lectura omiten pagina).
OMITE = {
    "ficha_catalogacion": {"pagina", "categoria", "uso"},
    "ficha_fuente": {"pagina", "categoria"},
    "ficha_textual": set(),
    "ficha_parafrasis": set(),
    "ficha_sintesis": {"pagina"},
    "lectura": {"pagina", "categoria"},
    "apunte": {"pagina", "categoria"},
}
TIPOS = list(OMITE)
ESTADOS = ["pendiente", "verificada_script", "verificada_autor", "observada"]
CATEGORIAS = ["Concepto/definición", "Teoría o enfoque", "Idea principal", "Idea secundaria", "Cita clave", "Dato/estadística",
              "Argumento", "Contraargumento/limitación", "Hallazgo", "Vacío", "Conclusión"]

# Nombre de archivo por tipo (§2). `<clave>` = clave_bibtex tal como está en el .bib (Better BibTeX admite mayúsculas y
# guion bajo: `contraloriaPanama2005`, `dl1186_2015`); NNN = página impresa con tres dígitos, o sN-M-… (sección, artículo; tantos niveles como la obra numere, p. ej. s3-4-7-1-1).
CLAVE = r"[A-Za-z0-9_.:]+"
PATRON_NOMBRE = {
    "ficha_catalogacion": r"^\d+_[a-z0-9-]+\.md$",
    "ficha_fuente": rf"^{CLAVE}-fuente\.md$",
    "ficha_textual": rf"^{CLAVE}-(p\d{{3,}}|s\d+(-\d+)*[a-z]?)-textual-[a-z0-9-]+\.md$",
    "ficha_parafrasis": rf"^{CLAVE}-(p\d{{3,}}|s\d+(-\d+)*[a-z]?)-parafrasis-[a-z0-9-]+\.md$",
    "ficha_sintesis": r"^sintesis-[a-z0-9-]+\.md$",
    "lectura": rf"^{CLAVE}-lectura(-extraida)?\.md$",
    "apunte": r".*\.md$",
}

# Secciones del cuerpo por tipo (§2), en orden. Se avisa si falta alguna; no se rechaza la ficha.
SECCIONES = {
    "ficha_catalogacion": ["Origen", "Zotero", "Calibre", "Notas"],
    "ficha_fuente": ["Datos de verificación de existencia", "Resumen", "Fichas derivadas", "Apunte de estudio", "Observaciones", "Nuevas fuentes detectadas"],
    "ficha_textual": ["Cita exacta", "Localización para el cotejo", "Análisis", "Encadenamiento", "Observaciones"],
    "ficha_parafrasis": ["Paráfrasis", "Origen literal", "Control de fidelidad", "Encadenamiento"],
    "ficha_sintesis": ["Fichas de entrada", "Coincidencias y divergencias", "Párrafo de síntesis", "Control de fidelidad", "Encadenamiento"],
    "lectura": ["Propósito", "Estructura", "Ideas principales", "Datos", "Preguntas", "Vocabulario", "Uso previsto"],
    "apunte": [],
}

# Sección de la que se toma la cadena literal a cotejar contra el PDF.
SECCION_LITERAL = {"ficha_textual": "Cita exacta", "ficha_parafrasis": "Origen literal"}

# Cotejo: página declarada = impresa; el PDF puede ir desfasado. Se prueba la declarada (+ desfase), luego ± TOLERANCIA,
# luego todo el documento (eso último nunca da «verificada»: da «observada» con la página real).
TOLERANCIA_PAGINAS = 2
DESFASE_DEFECTO = 0
METODO_SCRIPT = "pdftotext + búsqueda exacta"
MARCAS_ELIPSIS = ["[. . .]", "(. . .)", ". . .", "[...]", "(...)", "...", "…"]
MIN_FRAGMENTO = 12          # caracteres mínimos de cada fragmento entre elipsis para que el cotejo tenga sentido

INDICE_NOMBRE = "00-indice_fichas.md"
