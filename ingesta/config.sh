#!/usr/bin/env bash
# config.sh — ingesta documental de Inteligencia Legislativa. Todo lo editable vive aquí.
# Zona de ENTRADA: scripts_for_fuentes/entrada/ (aterrizaje; nunca almacén permanente). El CIL del despacho
# (01_inteligencia_legislativa) fue la zona de entrada hasta su disolución en M10 D6 (2026-09-15).
# Almacén PERMANENTE: ~/Documents/biblioteca (Calibre, autoridad bibliográfica) + Zotero (citas).

# --- Rutas -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_core_d="$SCRIPT_DIR"; while [ "$_core_d" != / ] && [ ! -f "$_core_d/core/env.sh" ]; do _core_d="$(dirname "$_core_d")"; done
[ -f "$_core_d/core/env.sh" ] && source "$_core_d/core/env.sh"; unset _core_d   # rutas del workspace (FS2)
[ -n "${DOCS_ROOT:-}" ] || { echo "[ERROR] ingesta: no encuentro core/env.sh (DOCS_ROOT); sin él no hay rutas (salida 69)" >&2; exit 69; }
DOCS="$DOCS_ROOT"
REPO_FUENTES="$(cd "$SCRIPT_DIR/.." && pwd)"                                   # este repo, por su ubicación
# CIL_DIR: raíz histórica de la zona de entrada (los módulos la tratan como raíz opcional: origen relativo, INBOX_DIRS).
# Desde M10 D8 apunta a entrada/, la zona de aterrizaje real; INBOX_DIRS (subcarpetas del antiguo CIL) ya no existen.
CIL_DIR="${INGESTA_ENTRADA:-$REPO_FUENTES/entrada}"
MANIFIESTO_MARCO_LEGAL="$SCRIPT_DIR/../manifiestos/marco_legal/manifiesto.tsv"   # dato del marco legal (carpeta, archivo, URL, fuente, nota)
BIBLIOTECA="${BIBLIOTECA_DIR:-$DOCS/biblioteca}"                               # biblioteca Calibre (metadata.db)
CATALOGACION_DIR="$REPO_FUENTES/catalogacion"                                   # hogar canónico de fichas + TSV
: "${DATAFW_DIR:?core/env.sh define DATAFW_DIR}"            # OCR (pipeline/documentos) si el PDF no tiene texto
PROMPTS_DIR="${PROMPTS_DIR:-$DOCS/prompts}"                  # prompt de catalogación (ficha dual)

# Carpetas de entrada que se rastrean (relativas a CIL_DIR). Se excluyen 00_ingesta y enlaces simbólicos.
# Raíces de entrada FUERA del CIL. Un documento de consulta puede nacer en otro
# sistema (datafw descarga informes del INEI, BCRP, MEF… a data/raw/) y debe
# catalogarse con este mismo flujo, sin copiarlo a una zona de paso: se cataloga
# donde está y `archivar` lo sustituye ahí mismo por el enlace a Calibre.
# Regla de datafw 0b / DECISIONES §1.14.
#
# Dos raíces, dos modos de archivar (ver `archivar` y `ARCHIVAR_MODO`):
#   datafw/data/raw              → ENLACE: un script necesita esa ruta para leer.
#   scripts_for_fuentes/entrada  → MOVER:  es zona de aterrizaje, nadie la necesita
#                                  después; Calibre queda como único almacén.
INBOX_RAICES=("$DATAFW_DIR/data/raw"
              "$CIL_DIR"
              "$WRITING_DIR")                        # ver INBOX_RAICES_SOLO
# En las raíces externas solo entran rutas que cumplen este regex.
#  · `fuentes/` sustituye a `01_fuentes/` desde P5 (2026-09-08); se conservan las
#    dos porque un proyecto migrado y otro sin migrar conviven.
#  · `referencias/` son los PDF de consulta que las TESIS guardaban junto al
#    documento. La regla 0b —los documentos viven en Calibre— dejó de aplicarse
#    solo a `datafw` en P7: también alcanza a `escritura`.
INBOX_RAICES_SOLO=".*/(data/raw|entrada|01_fuentes|fuentes|referencias)/.*"
INBOX_GLOBS=("02_investigacion/20[0-9][0-9]-*/fuentes")      # carpetas de fuentes de cada investigación fechada (glob relativo al CIL)
# Rutas excluidas dentro de esas raíces (regex de `find -regex`).
#  · data/raw/biblioteca/ = paquetes que pipeline/replicacion movió DESDE Calibre.
INBOX_RAICES_EXCLUIR=".*/(data/raw/biblioteca/.*|.*\.ocr\.pdf)$"   # los .ocr.pdf son FORMATO de un libro ya catalogado: los trata 'ocr'
# Extensiones en las raíces externas: SOLO documentos de consulta. En datafw un
# .xlsx es dato de procesamiento (notas tributarias de SUNAT, anexos tabulares
# que parsea un script), no un documento que se lea: no se cataloga.
INBOX_RAICES_EXTENSIONES="pdf"

# PAQUETES: carpetas cuyos documentos son UNA entrada de Calibre con adjuntos, y
# no una entrada por archivo. Caso real: los anexos del presupuesto del MEF, entre
# 13 y 24 por Ley o Proyecto — catalogarlos sueltos daría ~192 entradas para ~10
# documentos (decisión de Edison, 2026-09-06). El documento PRINCIPAL se cataloga
# normalmente; los demás archivos de esa carpeta son adjuntos: van a la carpeta
# `data/` de su entrada (la misma que usa datafw/pipeline/replicacion y que Calibre
# no registra en metadata.db) y se sustituyen por un enlace, como todo lo demás.
#   raiz          carpeta madre; cada subcarpeta directa es un paquete
#   principal     PREFIJOS del nombre, en orden de preferencia. Se exige PREFIJO y
#                 no subcadena: «Anexo_1_LeyPpto2024.PDF» contiene «leyppto» y
#                 «EM_PL_Presupuesto_SP_2027.pdf» contiene «pl_presupuesto».
PAQUETES_JSON='[
  {"raiz": "'"$DATAFW_DIR"'/data/raw/mef/presupuesto/aprobado",
   "familias": [{"principal": "^ley.*(ppto|presupuesto)", "adjuntos": "^anexo",
                 "sin_principal": {"titulo": "Ley N.° {ley}. Presupuesto del sector público para el año fiscal {anio} (anexos; texto de la ley pendiente)",
                                   "leyes": {"2022": "31365", "2023": "31638"}, "autor": "Ministerio de Economía y Finanzas", "serie": "datafw mef - Presupuesto aprobado",
                                   "tags": "presupuesto_publico, politica_fiscal, legislacion", "clasificador": "Normativa", "item_type": "Statute"}}]},
  {"raiz": "'"$DATAFW_DIR"'/data/raw/mef/presupuesto/proyecto",
   "familias": [{"principal": "^pl_presupuesto", "adjuntos": "^anexo"}]}
]'

INBOX_DIRS=("02_investigacion/marco_legal" "02_investigacion/informes" "02_investigacion/articulos" "02_investigacion/bibliografia" "02_investigacion/notas_tecnicas" "02_investigacion/policy_briefs" "01_estadistica/01_bases_datos" "03_observatorio")
EXTENSIONES="pdf|docx|epub|xlsx"

# --- Salidas de la suite -----------------------------------------------------
LEDGER="$SCRIPT_DIR/ingesta.tsv"              # fuente de verdad: qué entró, sha256, calibre_id, zotero_key, destino
PENDIENTES="$SCRIPT_DIR/pendientes.tsv"       # candidatos identificados (misma columnas que resumen_catalogacion.tsv, sin id)
FICHAS_DIR="$SCRIPT_DIR/fichas"               # ficha dual por documento (formato prompt_para_zotero_1_catalogacion)
RIS_DIR="$SCRIPT_DIR/salida_ris"              # .ris por lote para importar en Zotero (mapeo ZMI)
# Respaldo de metadata.db antes de escribir: lo hace la puerta ../lib/escribir.sh fuera del repo
# (PUERTA_RESPALDOS, por defecto $RESPALDOS_DIR/biblioteca/fuentes/metadata; ola 2, F2).
REPORTES_DIR="$SCRIPT_DIR/reportes"

# --- Política ----------------------------------------------------------------
APPLY_CHANGES=false          # simulación por defecto; --aplicar escribe (calibredb add, ledger, enlaces)
# FD4 (2026-09-07): «manifiesto» = el original se borra y queda registrado en el fuentes.yml de su proyecto
# (scripts_for_fuentes/manifiesto); nadie necesita ya la ruta: la da el resolutor. «enlace» y «mover» se conservan
# por compatibilidad. Regla 1 del Método Documental: ningún proyecto guarda copias ni enlaces simbólicos a PDF.
ARCHIVAR_MODO="manifiesto"
MANIFIESTO_DIR="$REPO_FUENTES/manifiesto"   # suite del fuentes.yml (raíz de cada manifiesto: config.REGLAS_RAIZ)
# Serie de Calibre = carpeta de origen (pedido 2026-09-06): «Marco legal NN - Nombre», «CIL fecha - Tema», «Informe slug - Fuentes»
SERIE_MARCO_LEGAL_PREFIJO="Marco legal"
SERIE_CIL_PREFIJO="CIL"
SERIE_INFORME_PREFIJO="Informe"
AUTOR_DESCONOCIDO="Unknown"          # convención de la biblioteca (catalogacion eliminó «Desconocido»)
# Institución por defecto según la carpeta del marco legal (el Author del PDF nunca se usa en documentos oficiales)
INSTITUCION_POR_CARPETA_JSON='{"01_normativa_fundamental":"Congreso de la República","02_leyes_organicas":"Congreso de la República","03_congreso":"Congreso de la República","04_administracion_publica":"Presidencia del Consejo de Ministros","05_contrataciones":"Organismo Especializado para las Contrataciones Públicas Eficientes","06_presupuesto":"Ministerio de Economía y Finanzas","07_economia":"Ministerio de Economía y Finanzas","08_planeamiento":"Centro Nacional de Planeamiento Estratégico","09_inversion_publica":"Ministerio de Economía y Finanzas","10_control":"Contraloría General de la República","11_seguridad":"Congreso de la República","12_educacion":"Ministerio de Educación","13_salud":"Ministerio de Salud","14_trabajo":"Ministerio de Trabajo y Promoción del Empleo","15_ambiente":"Ministerio del Ambiente","16_derechos_humanos":"Organización de las Naciones Unidas","17_jurisprudencia":"Tribunal Constitucional","18_manuales":"Presidencia del Consejo de Ministros","19_informes_permanentes":"","20_desarrollo_productivo":"Congreso de la República","21_vivienda_urbanismo":"Ministerio de Vivienda, Construcción y Saneamiento"}'
# Sigla inicial del nombre de archivo → institución autora
SIGLAS_JSON='{"inei":"Instituto Nacional de Estadística e Informática","bcrp":"Banco Central de Reserva del Perú","mef":"Ministerio de Economía y Finanzas","servir":"Autoridad Nacional del Servicio Civil","contraloria":"Contraloría General de la República","defensoria":"Defensoría del Pueblo","ceplan":"Centro Nacional de Planeamiento Estratégico","inpe":"Instituto Nacional Penitenciario","sunat":"Superintendencia Nacional de Aduanas y de Administración Tributaria","produce":"Ministerio de la Producción","congreso":"Congreso de la República","pcm":"Presidencia del Consejo de Ministros","tc":"Tribunal Constitucional","oit":"Organización Internacional del Trabajo","onu":"Organización de las Naciones Unidas","pidcp":"Organización de las Naciones Unidas","pidesc":"Organización de las Naciones Unidas","cadh":"Organización de los Estados Americanos","oea":"Organización de los Estados Americanos","minedu":"Ministerio de Educación","ilo":"Organización Internacional del Trabajo","oms_unicef":"Organización Mundial de la Salud","world_bank":"Banco Mundial","cepal":"CEPAL","iadb":"Banco Interamericano de Desarrollo","unesco":"UNESCO","minsa":"Ministerio de Salud","minem":"Ministerio de Energía y Minas","mtpe":"Ministerio de Trabajo y Promoción del Empleo","minam":"Ministerio del Ambiente","mvcs":"Ministerio de Vivienda, Construcción y Saneamiento","jne":"Jurado Nacional de Elecciones","osce":"Organismo Supervisor de las Contrataciones del Estado","oece":"Organismo Especializado para las Contrataciones Públicas Eficientes","indecopi":"Instituto Nacional de Defensa de la Competencia y de la Protección de la Propiedad Intelectual","sunafil":"Superintendencia Nacional de Fiscalización Laboral","fmv":"Fondo MiVivienda","mclcp":"Mesa de Concertación para la Lucha contra la Pobreza","escale":"Ministerio de Educación","enla":"Ministerio de Educación","endes":"Instituto Nacional de Estadística e Informática","per":"Gobierno Regional de Ayacucho","gore":"Gobierno Regional de Ayacucho","cvr":"Comisión de la Verdad y Reconciliación","directiva":"Congreso de la República","pta":"Congreso de la República","reglamento":"Congreso de la República","acuerdo":"Congreso de la República","manual":"Congreso de la República","constitucion":"Congreso de la República","codigo":"Congreso de la República","tuo":"Congreso de la República","convenio":"Organización Internacional del Trabajo","pacto":"Organización de las Naciones Unidas","convencion":"Organización de los Estados Americanos","sentencia":"Tribunal Constitucional","exp":"Tribunal Constitucional","stc":"Tribunal Constitucional"}'       # enlace = sustituir el original por symlink a la copia de Calibre | mover = borrar original
IDIOMA_DEFECTO="es"
CLASIFICADOR_DEFECTO="Informe"       # enum #clasificador de Calibre (se valida contra la BD)
ITEM_TYPE_DEFECTO="report"           # #item_type (Zotero): statute | report | document | book | journalArticle
CONFIANZA_MINIMA_AUTO="media"        # alta|media|baja: por debajo, no se cataloga sin revisión humana de la ficha
TAGS_POR_CARPETA_JSON='{"11_seguridad":"seguridad_ciudadana, legislacion","14_trabajo":"economia_laboral, legislacion","07_economia":"politica_economica, legislacion","15_ambiente":"economia_ambiental, legislacion","04_administracion_publica":"gestion_publica, legislacion","09_inversion_publica":"inversion_publica, legislacion","06_presupuesto":"politica_fiscal, legislacion","20_desarrollo_productivo":"desarrollo_productivo, legislacion","21_vivienda_urbanismo":"vivienda, urbanismo, legislacion","01_normativa_fundamental":"derecho, legislacion","19_informes_permanentes":"informe_tecnico","informes":"informe_tecnico","2026-09-02-delegacion-facultades-2026":"informe_tecnico, delegacion_facultades_2026"}'
ZOTERO_CONNECTOR="http://localhost:23119"    # si Zotero está abierto, alta directa best-effort (además del RIS)

# --- Cursos (`main.sh cursos`; antes la sub-suite ingesta_cursos, fundida en la ola 2, F3) -----------
# Material EXTERNO de los cursos (05-recursos de docencia/contenido/cursos/<slug>/) → Calibre, deduplicado contra la
# biblioteca, con el calibre_id anotado en `bibliografia:` del curso.yml (contrato con docencia).
CURSOS="$CLASS_DIR/contenido/cursos"   # M6 (2026-09-15): los cursos viven en docencia/cursos/<slug>/
CURSOS_REPORTES_DIR="$SCRIPT_DIR/reportes/cursos"      # candidatos_*, ingesta_* y catalogar_*, fuera de git
# A dónde se retira el original del curso tras catalogarlo: fuera del repo y del vault, con los respaldos
# (antes una carpeta retirada de meta). Reversible: el original está ahí, intacto.
ORIGINALES_DIR="${QIR_ORIGINALES:-$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos}"
CARPETAS_ESCANEO=("05-recursos")             # 08_INVESTIGACION pasó a 05-recursos/investigacion (M3)
CURSOS_EXCLUIDOS=()                          # cursos que NO se escanean (material de estudiante o administrativo; D2)
MIN_PAGINAS_LIBRO=100                        # un PDF de menos páginas en carpetas ambiguas se manda a revisar
# Autor del PDF que no significa nada (cuentas de Windows, iniciales de digitadores…)
AUTORES_GENERICOS='^(lenovo|usuario|user|dncpr01|mtizon|luis|carolina|balabarca|hp|admin|windows|acer|toshiba|personal autorizado|win98|andres|jorge)$'
AUTOR_PROPIO='achalma'                       # Author del PDF que identifica material propio (no va a Calibre)
DEDUPE_TOLERANCIA_PAGINAS=0                  # duplicado = mismo título normalizado y páginas iguales (±tolerancia)
