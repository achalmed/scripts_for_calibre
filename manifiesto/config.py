# config.py — suite `manifiesto`: el `fuentes.yml` de cada proyecto sustituye a los enlaces simbólicos (FD4, 2026-09-07).
#
# Regla 1 del Método Documental: todo documento vive en Calibre; un proyecto dice QUÉ usa (calibre_id, zotero_key,
# clave_bibtex) y no DÓNDE está. Cuando una herramienta necesita la ruta física la pide al resolutor
# (core/py-common/biblioteca.py) a partir del manifiesto. Todo valor editable vive aquí.

import re
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
DOCS = env.DOCS_ROOT
PY_COMMON = env.PY_COMMON                      # resolutor core/py-common/biblioteca.py
BIBLIOTECA = env.BIBLIOTECA_DIR
REPO = RAIZ.parent                             # scripts-biblioteca (este repo, por su ubicación)
CIL_DIR = REPO / "entrada"   # raíz histórica de entrada (el CIL del despacho, disuelto en M10 D6); hoy la zona de aterrizaje
LEDGER_INGESTA = REPO / "ingesta" / "ingesta.tsv"   # origen (relativo al CIL o absoluto) → calibre_id, sha256

NOMBRE = "fuentes.yml"

# Qué carpeta lleva el manifiesto de un archivo dado: la primera regla cuyo grupo 1 coincide con el inicio de la ruta
# absoluta. Si ninguna coincide, el manifiesto va en la carpeta del archivo.
_W, _A = re.escape(env.WRITING_DIR.name), re.escape(env.DATAFW_DIR.name)   # carpetas de WRITING_DIR y DATAFW_DIR
REGLAS_RAIZ = [re.compile(p) for p in (
    rf"^(.*/{_W}/reports/[^/]+/fuentes)/",          # canónico desde P5
    rf"^(.*/{_W}/reports/[^/]+/01_fuentes)/",       # informes sin migrar
    rf"^(.*/{_A}/data/raw)/",
    rf"^(.*/{_W}/(?:monographs|essays|theses|articles)/[^/]+)/",
)]

# Raíces que el doctor y `todo` recorren buscando manifiestos y enlaces simbólicos hacia la biblioteca.
RAICES_VIGILADAS = [CIL_DIR, env.DATAFW_DIR / "data" / "raw",
                    env.WRITING_DIR]   # WRITING_DIR incluye reports/ (FR1)

# Orden de las claves de cada entrada del manifiesto.
CLAVES_ENTRADA = ["origen", "calibre_id", "zotero_key", "clave_bibtex", "titulo", "autores", "serie", "anexo", "sha256", "uso", "nota"]
# Claves que el usuario edita a mano y que `generar` conserva entre regeneraciones.
CLAVES_MANUALES = ["clave_bibtex", "uso", "nota"]

# Siglas de los autores corporativos (shortauthor de APA 7, normas_apa7.md §7 y §14): la primera cita lleva el
# nombre completo y la sigla; las siguientes, la sigla. Solo las que el ecosistema usa; una institución sin sigla
# se cita entera, que es lo que APA manda cuando la sigla no es conocida. (`bib`, 2026-09-16)
SIGLAS = {
    "INEI": "Instituto Nacional de Estadística e Informática",
    "BCRP": "Banco Central de Reserva del Perú",
    "MEF": "Ministerio de Economía y Finanzas",
    "MINEDU": "Ministerio de Educación",
    "MINSA": "Ministerio de Salud",
    "MINEM": "Ministerio de Energía y Minas",
    "MTPE": "Ministerio de Trabajo y Promoción del Empleo",
    "MINAM": "Ministerio del Ambiente",
    "MVCS": "Ministerio de Vivienda, Construcción y Saneamiento",
    "MIDAGRI": "Ministerio de Desarrollo Agrario y Riego",
    "MINJUSDH": "Ministerio de Justicia y Derechos Humanos",
    "PRODUCE": "Ministerio de la Producción",
    "PCM": "Presidencia del Consejo de Ministros",
    "SERVIR": "Autoridad Nacional del Servicio Civil",
    "CGR": "Contraloría General de la República",
    "CEPLAN": "Centro Nacional de Planeamiento Estratégico",
    "INPE": "Instituto Nacional Penitenciario",
    "SUNAT": "Superintendencia Nacional de Aduanas y de Administración Tributaria",
    "SBS": "Superintendencia de Banca, Seguros y AFP",
    "SUNAFIL": "Superintendencia Nacional de Fiscalización Laboral",
    "INDECOPI": "Instituto Nacional de Defensa de la Competencia y de la Protección de la Propiedad Intelectual",
    "OSCE": "Organismo Supervisor de las Contrataciones del Estado",
    "TC": "Tribunal Constitucional",
    "CVR": "Comisión de la Verdad y Reconciliación",
    "MCLCP": "Mesa de Concertación para la Lucha contra la Pobreza",
    "GORE Ayacucho": "Gobierno Regional de Ayacucho",
    "UMC": "Oficina de Medición de la Calidad de los Aprendizajes",
    "OIT": "Organización Internacional del Trabajo",
    "ONU": "Organización de las Naciones Unidas",
    "OEA": "Organización de los Estados Americanos",
    "RAE": "Real Academia Española",
    "OMS": "Organización Mundial de la Salud",
    "BID": "Banco Interamericano de Desarrollo",
    "CAF": "Banco de Desarrollo de América Latina",
    "CEPAL": "Comisión Económica para América Latina y el Caribe",
    "IEP": "Instituto de Estudios Peruanos",
    "FMV": "Fondo MiVivienda",
    "MOVADEF": "Movimiento por Amnistía y Derechos Fundamentales",
}
