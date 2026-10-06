---
tipo: decision
titulo: "Decisiones de scripts-biblioteca: autoridad de los datos, escritura segura, organización y Método Documental"
genero: explicacion
estado: activo
---
# Decisiones de `scripts-biblioteca`

Registro acumulativo, por tema y con la fecha de cada decisión. **Los números son identificadores
permanentes**: una entrada no se renumera ni se borra; si deja de regir, lleva *Superada por §X*.
Lo pendiente vive en [`../estado.md`](../estado.md) §Por hacer (desde la ola 2a, K9). La crónica de
las campañas hasta 2026-10-01, en `historial/campanas-sobre-la-biblioteca.md`; la de las
posteriores, en su commit.


**Fusión (ola 2, fase E, 2026-10-05).** `scripts_for_calibre` y `scripts_for_fuentes` son un solo repo. Las
secciones §1–§4 son las de Calibre; las del Método Documental (antes `scripts_for_fuentes/docs/decisiones.md`)
son ahora §5–§8 con el mismo segundo número: su §1.x es §5.x, §2.x es §6.x, §3.x es §7.x y §4.x es §8.x.

## 1. Autoridad de los datos

### §1.1 Calibre manda en los metadatos bibliográficos (2026-07-28)

En conflicto gana Calibre y se propaga a Zotero; Zotero solo rellena vacíos en Calibre y puebla las
columnas espejo `#zotero_*`. Vacío en el origen nunca borra en el destino. Política campo a campo:
`../sincronizar-zotero/README.md`; autoridad por dato en el workspace:
`meta/docs/historial/MODELO_METADATOS.md`.

### §1.2 Título y autor no se escriben en Calibre por sincronización ni verificación (2026-07-28)

Zotero enlaza los adjuntos por la ruta `Autor/Título (id)`. Desde 2026-09-30 se admite una
excepción: una campaña aprobada que reescriba en la misma operación las rutas y los datos de Zotero
(hoy con `lib/adjuntos_zotero.py`, §2.9).

### §1.3 Los relojes de lectura no se copian entre sí (2026-08-09)

`#ko_tiempo` es de KOReader, `#zot_tiempo` de Zotero (Ethereal Style) y `#tiempo_estudio` los suma:
ningún segundo entra dos veces al mismo contador, así que no hay deduplicación que implementar.
Diseño: `historial/diseno-ecosistema-lectura-2026-08.md` §3.

### §1.4 Estado de lectura y estado de estudio son columnas distintas (2026-08-09)

`#estado_estudio` lo calculan las suites; `#estudio` es manual y ningún script lo toca.

### §1.5 El título se compara exacto entre Calibre y Zotero (2026-10-01)

Los demás campos siguen comparándose normalizados. Con `norm()` una corrección de tildes o
mayúsculas en Calibre nunca llegaba a Zotero.

## 2. Escritura segura

### §2.1 Un solo escritor de `metadata.db` a la vez (auditoría C5, 2026-08-09)

Un candado `flock` compartido; los timers lo pasan al hijo por descriptor
(`ECOSISTEMA_LOCK_HELD=1`). *Precisión (2026-10-05, ola 2, C1):* el candado ya no es
`.lock_calibre_write` de la raíz del repo sino `LOCK_CALIBRE` de `core/env.sh` (estado de usuario), y
ocupado sale 75; lo toman todos los escritores por la puerta (§2.5).

### §2.2 Simulación por defecto y `--aplicar` explícito (2026-07-28)

Con respaldo verificado antes de escribir y `PRAGMA integrity_check` después. Desde la ola 2a no
quedan excepciones: `metadatos_calibre` también simula por defecto (K5) y `--apuntes` de
`koreader_estudio` es una orden explícita que escribe por la puerta.

### §2.3 Tras escribir por SQLite, `calibredb backup_metadata --all` (2026-07-28)

*Superada por §2.7:* Calibre ya no se escribe por SQLite.

### §2.4 Zotero se escribe por SQL directo, con ambas apps cerradas y `synced=0` (2026-07-28)

Para que la cuenta suba cada ítem tocado. *Precisión (ola 2a):* el SQL vive solo en
`lib/escribir_zotero.py`; lo usan `sincronizar_zotero` y `lib/adjuntos_zotero.py`.

### §2.5 Una sola puerta de escritura (ola 2a, K2, 2026-10-05)

`lib/escribir.sh` (Bash) y `lib/escribir.py` / `lib/escribir_zotero.py` (Python) son los únicos que
escriben en `metadata.db` y en `zotero.sqlite`. Abrir la puerta de Calibre es, en este orden y todo o
nada: Calibre cerrado (detección canónica de `core/shell-lib/detectar_apps.sh`), candado
`LOCK_CALIBRE` y respaldo verificado (`backup_metadata_db` de `core`); la de Zotero, igual con
`LOCK_ZOTERO` y un respaldo verificado de `zotero.sqlite`. Después se escribe con
`calibredb_escribe`, con la API de Calibre (`set_campos`, que exige `PUERTA_CALIBRE=abierta` para esa
biblioteca) o con las primitivas `z_*`. `tests/test_puerta.py` hace fallar a cualquier escritor
fuera de la puerta. Fuente: normativa 9.1 y RQ-PRE-06.

### §2.6 Los respaldos viven fuera del repo (ola 2a, K2 y K8, 2026-10-05)

Los de cada escritura, en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/{calibre,zotero}/` (5 de
`metadata.db`, 3 de `zotero.sqlite`): sobreviven a la fusión y al renombre del repo y no se mezclan
con el código. Los que vivían dentro del repo se copiaron verificados a
`$RESPALDOS_DIR/biblioteca/<suite>/` y los originales están en
`~/.local/share/residuos-programa/2026-10-05/scripts_for_calibre/`.

### §2.7 Calibre se escribe por su API o por `calibredb`, nunca por SQL (ola 2a, K3, 2026-10-05)

El SQL directo choca con los disparadores de Calibre (`title_sort`: el relleno de `pubdate` de
`sincronizar_zotero` fallaba después de haber escrito Zotero) y no marca los libros para su OPF.
`sincronizar_zotero` deja su plan en `plan_calibre.json` y lo aplica `escribir.py aplicar-plan`
dentro de `calibre-debug`; las columnas se resuelven por etiqueta. Como la API marca los libros
cambiados, basta `calibredb backup_metadata` sin `--all` (0,6 s en vez de 20 s).

### §2.8 La caracterización precede al cambio (ola 2a, K1, 2026-10-05)

`tests/` corre cada sincronizador vivo sobre copias de las bases (biblioteca espejo de enlaces,
HOME, XDG y candado propios, `unshare -rn` contra el socket de instancia única de Calibre) y compara
reporte y delta de las bases con un commit de referencia (`467c8a7`). Nunca toca las bases reales.
Un defecto hallado se fija primero como `xfail` estricto y su arreglo lo vuelve verde.

### §2.9 Un solo escritor de rutas de adjuntos en Zotero (ola 2a, K4, 2026-10-05)

`lib/adjuntos_zotero.py` (`rutas`, `titulos`, `autores`, `verificar`) sustituye a las diez copias
de `aplicar_zotero.py` de las campañas: simula por defecto y, tras reescribir, exige 0 rutas nuevas
rotas.

## 3. KOReader

### §3.1 Sidecars por hash (2026-08-09)

`document_metadata_folder = "hash"` y los `.sdr` en `~/.config/koreader/hashdocsettings/`; renombrar
en Calibre ya no rompe el emparejamiento, que se hace por el MD5 parcial de KOReader cacheado en
`#ko_md5`.

### §3.2 El respaldo de KOReader va a un repo de datos propio (FG3, 2026-09-15)

`KOREADER_RESPALDO_DIR`, no `~/.dotfiles`, y excluye `settings.reader.lua` porque lleva credenciales
`kosync`. *Precisión (ola 2a, K6):* el volcado de `statistics.sqlite3` se hace con `CORE_PYTHON`
(`iterdump`), porque los timers ya no llevan el `sqlite3` de anaconda.

## 4. Organización del repositorio

### §4.1 `lib_comun/` son envoltorios de `core/` (FS2, 2026-09-07)

No se amplían; el código nuevo carga `core/env.sh` o `core/env.py` directamente. Desde la ola 2a
ninguna suite de este repo los usa; quedan para `scripts_for_fuentes` hasta C4.

### §4.2 Una campaña es una carpeta con su registro y su deshacer (2026-09-30)

*Superada por §4.8.*

### §4.3 `catalogacion/fichas/` y `resumen_catalogacion.tsv` son el registro de esa suite (D12, 2026-09-20)

Las fichas y las filas nuevas las escribe `scripts_for_fuentes/ingesta`; aquí solo se aplican al
catálogo. Una ficha cita su proyecto por id (`proyecto: meta`), no por ruta (normativa 1.10, K7).

### §4.4 Un solo incrustador de PDF (auditoría A7, 2026-08-10)

`metadatos-pdf embed`, con InfoDict y XMP Dublin Core; el de `scripts_for_zotero` quedó
absorbido.

### §4.5 Los timers se instalan con la herramienta (2026-09-20)

*Superada por §4.9.*

### §4.6 La crónica de una campaña nueva va a su carpeta y al commit (2026-10-04)

La bitácora `historial/campanas-sobre-la-biblioteca.md` cubre hasta 2026-10-01, está cerrada y no
se reabre.

### §4.7 La interfaz que usan otros repos vive en `consumidores.md` (2026-10-04)

`lib_comun/`, el registro de catalogación, la puerta y el candado. `lib_comun/` se conserva
mientras tenga consumidores.

### §4.8 Las campañas cerradas salen al historial de git (ola 2a, K8, 2026-10-05)

`script_normalizacion_metadatos` (11 campañas aplicadas) salió del árbol con `git rm`; se lee en
`467c8a7`. Las campañas de la ola 2b usarán la plantilla común de `migraciones/` (simular,
respaldar, aplicar, reescribir `attachments:`, verificar, deshacer) por la puerta.

### §4.9 Los timers son plantillas en `systemd/` (ola 2a, K6, 2026-10-05)

Con `@RAIZ@` → `%h/<ruta bajo el HOME>`, `SuccessExitStatus=75` y un PATH sin anaconda (P221).
`systemd/instalar.sh` simula por defecto, instala con `--aplicar` y compara lo instalado con la
plantilla con `--verificar`; `--instalar-timer` de las suites lo delega. `~/.dotfiles` no las
gestiona; si el repo cambia de carpeta, se reinstalan con la herramienta.

### §4.10 Las rutas salen de `core/env.sh` (ola 2a, K6, 2026-10-05)

Los `config.sh` cargan `core/env.sh`: ni `$HOME/Documents` ni `~/Zotero` de respaldo. El estado de
las suites (marca de la orquestación, último sync, plan de Calibre) vive en
`$XDG_STATE_HOME/biblioteca/<suite>/`.

## 5. Qué es este repo

### §5.1 Dos adquisiciones, dos sistemas (2026-09-06)

Datos y documentos se adquieren por separado: los datos, `02 analysis/connectors` hacia
`02 analysis/data/raw/`; los documentos, este repo hacia Calibre y Zotero. Confundirlos fue el error que
originó el sistema: un artículo y una serie no se guardan ni se citan igual. Comparten la
maquinaria de red y hash (§7.1) y el modelo de procedencia, no el destino.

### §5.2 El único lugar de fuentes del ecosistema (2026-09-06; M10 D6, 2026-09-15)

Aquí se descarga, se identifica y se cataloga; un proyecto (informe, curso, post) solo conserva su
`fuentes.yml`. La ingesta del CIL del despacho (`CIL/00_ingesta`), el manifiesto del marco legal y
`script_ingesta_recursos` de `scripts_for_calibre` se mudaron aquí; cuando el CIL se disolvió
(M10 D6), `entrada/` pasó a ser la zona de aterrizaje. Nada del despacho queda en el repo: el
marco legal es dato público, no del cliente. La procedencia de cada carpeta:
[historial/procedencia-de-las-carpetas.md](historial/procedencia-de-las-carpetas.md).

### §5.3 Ningún proyecto escribe su propio descargador (2026-09-06)

Si un documento hace falta y su fuente no existe, se añade aquí como `fuentes/<nombre>/` (dos
archivos), no como un script en el proyecto. Lo recoge `meta/docs/historial/ARQUITECTURA.md` §2 (la fila de
este repo) y `prompts/01 fuentes/prompt_01_localizar_descargar.md`.

### §5.4 El marco legal: el dato se queda, el código se fue (2026-09-06; M10 D6, 2026-09-15; DOC10, 2026-10-04)

El marco legal se descargó el 2026-07-31 en el CIL del despacho con dos scripts propios (una descarga
y un localizador de normas); lo que no se pudo bajar, recortar ni leer quedó anotado en el registro
que hoy es `registro/marco-legal-pendientes.md`. El 2026-09-06 el código se retiró: localizar una norma
por su número pasó a `fuentes/congreso/` y la descarga a la maquinaria compartida (§7.1). Cuando el CIL
se disolvió (M10 D6), los PDF quedaron en Calibre (serie «Marco legal NN - …») y en
`manifiestos/marco_legal/` se quedó solo el dato: el manifiesto que `ingesta` lee para los metadatos
de las normas y los dos scripts que lo arman, que desde entonces exigen `MARCO_LEGAL`. Esa carpeta
llevaba un README `archivado` con esta bitácora; como la carpeta sigue viva, su README volvió a ser
una puerta `activa` (§15.2 no prevé un README archivado para una carpeta en uso) y la bitácora vive
aquí y en `git log -- manifiestos/marco_legal/README.md`.

## 6. Ingesta y catalogación

### §6.1 Subir no es catalogar (2026-09-06)

Una ingesta de material de cursos encontró que la mayor parte de los PDF «nuevos» ya estaban en
la biblioteca. Desde entonces `ingesta` e `ingesta_cursos` (hoy `ingesta cursos`, §6.8) deduplican por huella y por título
normalizado más páginas antes de `calibredb add`, no inventan grafías de autor (por tokens contra
los autores existentes, o `Unknown`) ni etiquetas fuera del vocabulario cerrado.

### §6.2 Cómo queda un documento en Calibre (2026-09-06)

Serie = la carpeta de origen; en documentos oficiales el autor es la institución y nunca el
`Author` del PDF; títulos de norma con su número; etiquetas solo del vocabulario cerrado. Todo en
**una** llamada `set_metadata` por libro: eran siete y costaban unos cuarenta minutos por cada
doscientos documentos. La tabla completa: `ingesta/README.md`.

### §6.3 Paquetes: un libro por ley, no uno por anexo (2026-09-06)

Los anexos del presupuesto del MEF (decenas por ley) catalogados sueltos habrían dado cientos de
entradas para una decena de documentos. El principal es el libro; los anexos van a la carpeta
`data/` de su entrada en Calibre (`PAQUETES_JSON`). Los principales se reconocen por **prefijo**,
no por subcadena, porque un anexo puede llevar el nombre de la ley.

### §6.4 Las variantes OCR son formatos, no libros (2026-09-06)

`X.ocr.pdf`, `X_ocr_buscable.pdf` y `X_texto.pdf` pasan a ser el formato con texto del libro de
`X.pdf` (`ingesta/main.sh ocr`). Los PDF oficiales del Congreso tienen la capa de texto corrupta
(hallazgo del 2026-07-31, `fuentes/congreso/README.md`): todo documento del Congreso pasa por
`ocrmypdf -l spa`.

### §6.5 Primero el manifiesto, después el borrado (2026-09-11)

Dos PDF de una tesis se borraron sin quedar registrados porque `archivar` borraba antes de
escribir el manifiesto. El orden se invirtió: si registrar falla, el original sigue en su sitio.

### §6.6 La ficha de catalogación canónica vive en `scripts_for_calibre` (D12, 2026-09-20)

`ingesta/fichas/<sha8>_<slug>.md` es un borrador; `catalogar --aplicar` escribe la ficha con id en
`scripts_for_calibre/catalogacion/fichas/` y su fila en
`resumen_catalogacion.tsv`. Las fichas existentes no se mudan. El doctor avisa si
`ingesta/fichas/` conserva borradores.

### §6.7 El `.ris` sale de Calibre, no del ledger (2026-09-30)

Los `.ris` que `zotero` generaba desde las columnas del ledger nunca llegaron a importarse y no
servían: enlazaban rutas que Calibre ya había movido y escribían `AU` en el orden que Zotero lee
al revés. Desde entonces cada entrada sale de Calibre tal como está (`biblioteca.ris` del
resolutor). Los antiguos se retiraron, fuera de git, a `ingesta/salida_ris/obsoletos_2026-09-30/`
con su explicación.

### §6.8 `ingesta_cursos` se funde en `ingesta cursos` (ola 2, F3, 2026-10-05)

Las dos suites compartían ledger, catalogación y, desde F2, la puerta de escritura; la de cursos llevaba su
propia configuración, su respaldo dentro del repo y un envoltorio propio del resolutor. Pasa a
ser el comando `ingesta/main.sh cursos` con sus módulos `ingesta/lib/cursos_*`, sus valores en
`ingesta/config.sh` §Cursos y el resolutor de `core/py-common` llamado directamente. La simulación anuncia
lo mismo que antes (`tests/test_ingesta_cursos.py`) pero ya no deja informes; `ORIGINALES_DIR` deja la carpeta
retirada de `meta/reparaciones/` y va a `$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos`.

### §6.9 Las fichas provisionales no se versionan (ola 2, F6, 2026-10-05)

`ingesta/fichas/` acumulaba 812 borradores sin rastrear. Se clasificaron por su cabecera (la primera línea y el
frontmatter, sin leer el cuerpo) y por su fila en `ingesta.tsv`: ninguno correspondía a una obra con
`calibre_id` (la ficha de lo catalogado ya está, con su id, en `scripts_for_calibre`); 35 llevaban la marca
«sustituida» y 777 eran borradores sin obra (773 de filas de `pendientes.tsv` aún sin catalogar, de
`02 analysis/data/raw`, y 4 sin fila). Los 812 se copiaron con `SHA256SUMS` verificado a
`$RESPALDOS_DIR/biblioteca/fuentes/ingesta-fichas-provisionales/` (con `clasificacion.tsv`) y se movieron a los
residuos del programa; `.gitignore` declara la carpeta temporal. Si una de esas filas se cataloga, su borrador
se recupera de la copia o se regenera con `identificar` tras quitar la fila de `pendientes.tsv`.

## 7. Maquinaria y dependencias

### §7.1 Se importa la maquinaria de `02 analysis`, no se reimplementa (2026-09-06)

Superada por §7.4 (2026-10-05).

### §7.2 Solo acceso abierto (FD5, 2026-09-07)

La fuente `articulo` busca un PDF libre por DOI o URL: Unpaywall, después Crossref, después la
etiqueta `citation_pdf_url` de la página. Sin credenciales ni proxies: lo que está tras un muro de
pago no se descarga.

### §7.3 Zotero se alimenta por RIS (2026-09-06)

`zotero` deja un `.ris` que se importa a mano; el alta por el conector local de Zotero es un
intento sin garantía. Ninguna suite toca `zotero.sqlite` ni `metadata.db`.

### §7.4 La red sale de `core/py-common/red.py` (ola 2, F4 y C3, 2026-10-05)

La dependencia de §7.1 hacía un ciclo `datafw ↔ scripts_for_fuentes` (RQ-MAN-04; excepción E5 con plazo
«ola 2»). La red con reintentos, el hash durante la descarga y la validación por bytes mágicos pasan a
`core/py-common/red.py` (stdlib puro); `lib/comun.py` lo carga por `PY_COMMON` y `datafw` se pasa a él en
la ola 3. Dos cambios de comportamiento, a propósito: `descargar` ahora comprueba `%PDF-` en los PDF (el
original no comprobaba nada para esa extensión: una página de WAF servida como PDF entraba en `entrada/`),
y los intermedios TLS que `_lib` traía en `intermedios/` se indican con `RED_INTERMEDIOS` si un portal los
vuelve a pedir. `tests/test_red_fuentes.py` corre sin `02 analysis` en la caja de arena.

### §7.5 Rutas relativas a la raíz y nada personal en el repo (ola 2, F5, 2026-10-05)

Los ledgers `ingesta/ingesta.tsv` y `ingesta/pendientes.tsv` guardaban 2 220 rutas absolutas de la máquina
(`origen` y `ruta_calibre`). Se reescribieron solo en su forma (se quitó el prefijo de la raíz; las que
apuntan a archivos que ya no existen quedan como texto) y el código escribe y lee por `lib/rutas.py`: lo
relativo que empieza por una carpeta de la raíz es relativo a `DOCS_ROOT`; lo demás, a la zona de entrada,
como siempre. El correo de Unpaywall sale del entorno (`FUENTES_CORREO_CONTACTO`, P248); ninguna
configuración carga ya `scripts_for_calibre/lib_comun` ni la carpeta personal; `fichas grafia` y `migrar`
respaldan en `$RESPALDOS_DIR/biblioteca/fuentes/fichas/` (P240). `manifiesto todo` en seco da la misma
salida antes y después. `tests/test_privacidad_rutas.py` lo vigila.

## 8. El proyecto declara qué usa, no dónde está

### §8.1 Paso 00 ejecutable (FD2, 2026-09-07)

`main.py verificar` responde existe, otra edición o no existe, con las búsquedas hechas, por el
resolutor de la biblioteca y, con `--archivo`, también por los dos ledgers. Con él nacieron las
suites `fichas` y `lecturas`.

### §8.2 `fuentes.yml` en vez de enlaces simbólicos (FD4, 2026-09-07)

Un proyecto referencia cada obra por `calibre_id`, `zotero_key` y `clave_bibtex`; la ruta física la
da el resolutor. `archivar` registra en el manifiesto en vez de dejar un enlace; el modo `enlace`
queda solo por compatibilidad.

### §8.3 Formato único de ficha (FD3, 2026-09-07)

`fichas/config.py` transcribe `prompts/00 metodo/fichas_formato_y_voz.md`; `migrar` llevó las
fichas anteriores a ese formato y es de un solo uso.

### §8.4 El manifiesto de un proyecto de `03 writing` vive en `fuentes/` (P5, 2026-09-08)

Cuando la raíz que dicta `REGLAS_RAIZ` tiene una carpeta `fuentes/`, el `fuentes.yml` va ahí, para
que un documento archivado desde `referencias/` no deje el manifiesto suelto en la raíz. Las reglas
se prueban primero contra la ruta tal como se dio y después contra la resuelta, porque
`02 analysis/data` es un enlace simbólico a un disco externo (2026-09-29).

### §8.5 `references.bib` se genera desde Calibre (2026-09-16)

`manifiesto/main.py bib` escribe el bloque generado de `references.bib` (APA 7 vía biblatex) y la
`clave_bibtex` de cada entrada; un error se corrige en Calibre y se regenera. Informes y libros se
fechan por año; la fecha completa, solo en normas.
