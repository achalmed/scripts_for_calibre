# config.py — sistema central de adquisición de FUENTES DOCUMENTALES.
#
# La distinción que da sentido a este sistema (directiva de Edison, 2026-09-06):
#
#   DATOS       series, microdatos, APIs, geometrías   → los conectores de datafw (02 analysis)
#               destino: data/raw/ + catalogo.sqlite     (los procesa pipeline/)
#   DOCUMENTOS  normas, informes, libros, artículos,   → ESTE SISTEMA
#               tesis, publicaciones                     destino: Calibre + Zotero
#
# Son dos cosas distintas y se separan a propósito: un artículo científico y una
# serie del BCRP no se adquieren igual, no se guardan igual y no se citan igual.
# Pero están RELACIONADOS: comparten la maquinaria de red y de hash, comparten el
# modelo de procedencia (URL · fecha · SHA-256) y un mismo informe cita ambos.
#
# Relación con los otros dos sistemas centrales:
#   este sistema  →  descarga y localiza
#   Calibre       →  almacena y cataloga   (scripts-biblioteca + ingesta/ de este sistema)
#   Zotero        →  referencia y cita      (sincronizar-zotero, .ris)

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
DOCS = env.DOCS_ROOT                                 # ~/Documents
# Maquinaria de red compartida: `core/py-common/red.py` (stdlib puro; ola 2, C3 y F4). Red con reintentos,
# SHA-256 durante la descarga y validación por bytes mágicos no se reimplementan aquí. Antes se importaba la de
# datafw y había un ciclo entre los dos sistemas de adquisición (RQ-MAN-04); datafw pasa a core en la ola 3.
PY_COMMON = env.PY_COMMON

BIBLIOTECA = env.BIBLIOTECA_DIR                      # Calibre: el almacén
LEDGER_INGESTA = RAIZ / "ingesta" / "ingesta.tsv"    # sha256 → calibre_id de todo lo catalogado por ingesta/
ENTRADA = RAIZ / "entrada"                           # zona de aterrizaje
LEDGER = RAIZ / "fuentes_descargadas.tsv"            # procedencia de lo adquirido
DIR_LOGS = RAIZ / "logs"
DIR_FUENTES = RAIZ / "fuentes"                       # una carpeta por tipo de fuente

# La zona de aterrizaje está declarada como raíz de entrada de ingesta/,
# que cataloga en Calibre y luego ARCHIVA EN MODO «mover»: el archivo desaparece
# de aquí y Calibre queda como único almacén. (En datafw/data/raw se archiva en
# modo «enlace» porque allí un script necesita la ruta; aquí no la necesita nadie.)
ARCHIVAR_MODO = "mover"

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 30
PAUSA = 0.8
LIMITE_MB = 80
