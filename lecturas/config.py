# config.py — suite `lecturas`: extrae pasajes con número de página de ítems de la biblioteca (paso 07).
#
# Generaliza el `06_lecturas_biblioteca.py` del proyecto delegación de facultades (datafw, 2026-08): la lista curada
# (calibre_id, conceptos, patrones) deja de vivir dentro de un script y pasa a un `lecturas.yml` del proyecto;
# el texto lo da el resolutor core/py-common/biblioteca.py (caché compartida). Creada en FD2 (2026-09-07).

from pathlib import Path
import importlib.util

# core/env.py da la raíz y las carpetas por nombre (normativa 5.1-5.2): se sube hasta hallarlo.
_d = Path(__file__).resolve()
while _d != _d.parent and not (_d / "core" / "env.py").is_file():
    _d = _d.parent
_s = importlib.util.spec_from_file_location("core_env", _d / "core" / "env.py")
env = importlib.util.module_from_spec(_s)
_s.loader.exec_module(env)

RAIZ = Path(__file__).resolve().parent
DOCS = env.DOCS_ROOT
PY_COMMON = env.PY_COMMON                                       # resolutor core/py-common/biblioteca.py
SUITE_FICHAS = RAIZ.parent / "fichas"                           # frontmatter único (lib/ficha.py)

CONTEXTO_ANTES = 350          # caracteres antes de la coincidencia
CONTEXTO_DESPUES = 450        # caracteres después
MAX_POR_PATRON = 6            # pasajes por patrón si el spec no dice otra cosa
SUFIJO_ARCHIVO = "-lectura-extraida.md"   # fichas_formato_y_voz.md §2: <clave_bibtex>-lectura-extraida.md
DESTINO_DEFECTO = "fuentes/fichas"        # relativo al proyecto (escritura/docs/estructura-de-proyecto.md §3.5), si el spec no declara `destino`

# El bloque generado se delimita con marcas: al reejecutar se sustituye solo eso y se conserva lo redactado.
MARCA_INICIO = "<!-- lecturas: pasajes generados por scripts_for_fuentes/lecturas; no editar entre las marcas -->"
MARCA_FIN = "<!-- lecturas: fin de los pasajes generados -->"

# Secciones del cuerpo que la ficha `lectura` debe tener (fichas_formato_y_voz.md §2); se crean vacías.
SECCIONES = ["Propósito", "Estructura", "Ideas principales", "Datos", "Preguntas", "Vocabulario", "Uso previsto"]
