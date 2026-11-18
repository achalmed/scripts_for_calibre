---
tipo: decision
titulo: "Decisiones de biblioteca-studio: autoridad de los datos, escritura segura, organización y Método Documental"
genero: explicacion
estado: activo
---
# Decisiones de `biblioteca-studio`

Registro acumulativo, por tema y con la fecha de cada decisión. **Los números son identificadores
permanentes**: una entrada no se renumera ni se borra; si deja de regir, lleva *Superada por §X*.
Lo pendiente vive en [`../estado.md`](../estado.md) §Por hacer (desde la ola 2a, K9). La crónica de
las campañas hasta 2026-10-01, en `historial/campanas-sobre-la-biblioteca.md`; la de las
posteriores, en su commit.


**Fusión (ola 2, fase E, 2026-10-05).** `biblioteca-studio` y `scripts_for_fuentes` son un solo repo. Las
secciones §1–§4 son las de Calibre; las del Método Documental (antes §5–§8 de este registro)
son ahora §5–§8 con el mismo segundo número: su §1.x es §5.x, §2.x es §6.x, §3.x es §7.x y §4.x es §8.x.

## 1. Autoridad de los datos

### §1.1 Calibre manda en los metadatos bibliográficos (2026-07-28)

*Superada por §1.6 (2026-10-06) en cuanto a la autoridad y por §1.7 (2026-10-08) en el sincronizador.*

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

### §1.6 Zotero manda en citas y metadatos; Calibre, en los archivos (Edison, 2026-10-06)

Zotero es la autoridad de los metadatos, las referencias y las citas en todo el ecosistema
(`escritura`, SGDP, Obsidian, LibreOffice), por sus complementos: la clave de cita es la de Better
BibTeX y la fuente de los `.bib` es su exportación automática (`ZOTERO_BIB` de `core/env.sh`).
Calibre organiza los archivos y da su ubicación por `calibre_id`; el puente es la ruta del adjunto
en Zotero, `<Autor>/<Título> (<calibre_id>)/`. Cómo se cita: [citar.md](citar.md). No se reescribe
de golpe: la política de `sincronizar-zotero` (§1.1), `manifiesto bib` (§8.5) y la regla N 9.6 de
la normativa cambian en su propio ciclo (`../estado.md` §Por hacer; `meta/estado.md`).

### §1.7 El sincronizador solo rellena lo vacío en Zotero (director, 2026-10-08)

Aplica §1.6 en `sincronizar-zotero` sin invertir la política campo a campo: `CONFLICT_POLICY="zotero"`
(`config.sh`). Calibre → Zotero solo escribe donde Zotero está vacío (título, fecha, editorial, ISBN,
serie, páginas, edición, etiquetas, resumen, creadores); un valor que Zotero ya tiene se deja y se
reporta (`reporte (Zotero manda: no se sobrescribe)`), y el tipo de ítem no cambia. Siguen como reglas
duras, por ser del archivo o del formato y no del contenido: el idioma se normaliza a ISO 639-1 y las
rutas de adjunto y la línea de ruta de `Extra` se reparan. Zotero → Calibre no cambia (relleno de
vacíos y columnas espejo; §1.2). Por qué no invertir campo a campo: Zotero → Calibre ya rellena lo
vacío, y sobrescribir Calibre desde Zotero tocaría título y autor (§1.2) o exigiría excepciones que
el relleno de vacíos no necesita; en ambos sistemas vale «vacío en el origen nunca borra». La política
anterior queda disponible (`POLITICA=calibre`) y fijada por la caracterización (`tests/calibre`,
referencia de git); la nueva tiene su prueba propia. El timer `ecosistema-metadatos` se reactiva con
esta política.

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
biblioteca) o con las primitivas `z_*`. `tests/calibre/test_puerta.py` hace fallar a cualquier escritor
fuera de la puerta. Fuente: normativa 9.1 y RQ-PRE-06.

### §2.6 Los respaldos viven fuera del repo (ola 2a, K2 y K8, 2026-10-05)

Los de cada escritura, en `$PUERTA_RESPALDOS/<suite>/{calibre,zotero}/` (5 de
`metadata.db`, 3 de `zotero.sqlite`): sobreviven a la fusión y al renombre del repo y no se mezclan
con el código. Los que vivían dentro del repo se copiaron verificados a
`$RESPALDOS_DIR/biblioteca/<suite>/` y los originales quedaron en los residuos del programa del disco interno hasta el 2026-10-25, cuando fueron a
la papelera tras verificarlos contra el SSD.

**Al SSD externo (2026-10-25, pedido de Edison).** El disco interno tiene unos 15 GB libres y los timers respaldan
`metadata.db` cada media hora (12 MB cada uno): `PUERTA_RESPALDOS` es ahora `$RESPALDOS_DIR/biblioteca/puerta`
cuando el SSD está montado (`mountpoint`). Sin el SSD, la escritura no se detiene: el respaldo cae en
`$XDG_STATE_HOME/biblioteca/respaldos` con un aviso por stderr. Los 392 MB que había en el disco interno se
movieron al SSD, verificados con `sha256sum -c`. Las pruebas fijan `ARCHDISK_DIR` a una carpeta sin montar.

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

### §2.10 Biblioteca Studio y los complementos no abren una segunda puerta (2026-10-31)

El autor aprobó (`meta/programa/08-mantenimiento/biblioteca-studio-2026-10-31.md`) que el repo entre a la familia de
studios sin cambiar de nombre: la aplicación es **Biblioteca Studio** (`studio/`, `gui-comun`, acento sepia) y la
acompañan tres complementos, uno por aplicación: `calibre-plugin/`, `koreader-plugin/` y `zotero-plugin/`. Ninguno
es una puerta nueva:

- **El Studio no escribe por su cuenta**: cada tarjeta corre la CLI de su suite, primero simulando; «Aplicar» pide
  confirmación y se desactiva con la aplicación de la base abierta (el catálogo de operaciones, hoy `studio/biblioteca_app/servicios/operaciones.py`, §2.12).
- **Los complementos solo leen las bases** (la excepción, las colecciones por series de Zotero, es §2.11). Lo que saben de un libro lo leen de `lib/indice.py`
  (`$XDG_STATE_HOME/biblioteca/indice.json`, generado en `mode=ro`; lo regenera cada 30 min el `ExecStartPost` de
  `koreader-calibre-sync.service`, con un «-» para que su fallo no haga fallar la sincronización): KOReader no abre `metadata.db` ni Zotero la de
  Calibre. Lo único que escriben son archivos de texto fuera de las bases: la nota de lectura (KOReader añade al final
  sus resaltados, nunca reescribe) y la cola `por-verificar.tsv` (Calibre). El enlace de una nota nueva en
  `#apuntes` lo pide KOReader a `koreader/main.sh --apuntes`, y `lib/enlazar_notas.py` enlaza después las que se
  crearon con Calibre abierto; ambos por la puerta.
- **La nota de un libro es una sola**: la de `#apuntes` si la hay; si no, `notas/<clave para citar en minúsculas>.md`,
  la misma ruta que usa Zotero Integration en Obsidian.
- **`biblioteca-studio://libro/<id>`** es el enlace común: lo registra `studio/install.sh` y lo abren los tres
  complementos; con la ventana abierta va a ella.

### §2.11 «Organizar por series» pasa a la extensión de Zotero: excepción declarada a la puerta (2026-10-31)

`zotero-series/series_organizer.js` se pegaba a mano en la consola de Zotero y movía ítems entre colecciones con
Zotero abierto, fuera de la puerta. Lo reemplaza la orden «Organizar por series…» de `zotero-plugin/` (Herramientas y
el menú de la colección): arma el plan, lo muestra y solo escribe si se acepta, una transacción por serie con la API
de Zotero (`Zotero.Collection`, `addItems`, `removeItems`). Escribe colecciones con Zotero abierto, como antes: el
riesgo no cambia, pero ahora tiene vista previa. Es **la única escritura fuera de la puerta**, solo en colecciones
(nunca en campos de ítems ni en adjuntos), y queda declarada aquí; `zotero-series/` pasa a `retirado`.

El resto de la extensión solo lee: la sección del panel del ítem saca el `calibre_id` de la ruta del adjunto (la
misma expresión que `lib/indice.py`) y lo demás del índice (§2.10). El `manifest.json` lleva un `update_url` de un
dominio que no existe (`example.invalid`) porque Zotero lo exige y el repo es público; las versiones nuevas se
instalan a mano desde `zotero-plugin/dist/`.

### §2.12 Biblioteca Studio pasa a QML + Kirigami como espacio de trabajo, y sigue sin ser una puerta (fase 5, 2026-11-02)

La ventana de 1.x (`gui-comun` 1.1, Widgets: ocho páginas de tarjetas con Simular y Aplicar) se reescribe sobre
`gui-comun` 2.x (QML + Qt Quick + Kirigami, el diseño aprobado para toda la familia: `docs/rediseno.md`). Lo que
cambia para la puerta: nada. La ventana sigue sin escribir en `metadata.db` ni en `zotero.sqlite`: cada operación es
la CLI de su suite, elegida en la lista de la barra o en el menú Método; **F5 la corre sin `--aplicar`** (la suite
simula por omisión; las que solo leen se ejecutan) y **Ctrl+Intro la corre con `--aplicar`** tras un diálogo que muestra
la orden exacta, las bases que toca y el estado de la puerta, y que no se ofrece con la aplicación abierta o el candado
ocupado (la puerta lo volvería a comprobar y saldría 75). Lo que gana: la tabla de lo que cada etapa maneja (la zona de
entrada cruzada con los ledgers, las filas de catalogación, las fichas con su verificación, los manifiestos, las
comprobaciones de coherencia calculadas del índice sin correr nada, los respaldos, los timers), el plan y el registro
de cada operación conservados en la caché del studio, y el libro de los complementos como fila de la vista Libros.
Las suites de Python se invocan con `CORE_PYTHON` (el mismo intérprete de los timers), nunca con el de la ventana
(`/usr/bin/python3`, el único cuyo Qt trae Kirigami). Las pruebas y las capturas corren sobre una biblioteca de
muestra con libros ficticios (`studio/muestra.py`; `calibredb` en un temporal), nunca sobre la real; ninguna prueba
aplica una suite que escriba en una base. `studio/tests` pasa a `tests/run.sh` (`tests/studio/`). Los complementos
«Ecosistema» no cambian.

### §2.13 Biblioteca Studio es un gestor bibliográfico, lee lo editorial por `lib/` y muestra los seis pasos de la puerta sin darlos (reingeniería, 2026-11-02)

La reingeniería de los diez studios (`docs/reingenieria.md`, decisiones B1–B12) cambia la ventana de nueve tablas al
mismo nivel por un gestor bibliográfico sobre la biblioteca de Calibre: **Catálogo** con portadas (o lista compacta),
búsqueda por campo y filtros por colección, autor, año y tipo, con la **ficha editorial** del libro a la derecha;
**Bandejas** de trabajo; y las etapas del **Método Documental** y de la **Coherencia**, donde las tablas de los ledgers
siguen. Tres reglas nuevas, ninguna sobre la puerta:

- **Lo editorial se lee por `lib/`, nunca desde la ventana**: `editorial(db)` de `lib/indice.py` lee `metadata.db` en solo
  lectura (año, serie, etiquetas, editorial, idiomas, identificadores, descripción, tipo, páginas, lectura de KOReader;
  columnas por etiqueta) y la ventana lo une al índice. Es aditiva: el JSON del índice y `lib/indice.py --aplicar` no
  cambian (los complementos no la necesitan y KOReader leería un índice mayor). `test_la_ventana_no_escribe_en_las_bases`
  sigue prohibiendo `sqlite3.connect` en `studio/biblioteca_app`.
- **Las portadas son miniaturas de caché**: `cover.jpg` se lee en solo lectura, se escala al leerlo y la miniatura va a
  `$XDG_CACHE_HOME/biblioteca-studio/portadas/` con un tope (200 MB); nada se escribe en la carpeta de la biblioteca.
- **Los seis pasos de la puerta se ven, no se dan**: la ventana no abre ni cierra la puerta (eso sigue en
  `lib/escribir.*` dentro de cada suite). Muestra el estado previo de los dos primeros (aplicación cerrada, candado
  libre), lee en la salida de la suite la línea «── Backup:» del respaldo verificado y los «✗» de la puerta, y al
  terminar comprueba en solo lectura la integridad (`lib/escribir.py integridad`, la misma función de la puerta) y que
  el candado quedó libre.

La muestra de las pruebas (`studio/muestra.py`) gana metadatos editoriales, lectura de KOReader y portadas que genera el
propio Calibre (`calibre-debug`, `create_cover`), sobre su biblioteca temporal; se guarda como plantilla en la caché.
`tests/calibre/test_puerta.py` la exime (como a `tests/`): escribe solo en esa biblioteca temporal de muestra.

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

Datos y documentos se adquieren por separado: los datos, `datafw/connectors` hacia
`datafw/data/raw/`; los documentos, este repo hacia Calibre y Zotero. Confundirlos fue el error que
originó el sistema: un artículo y una serie no se guardan ni se citan igual. Comparten la
maquinaria de red y hash (§7.1) y el modelo de procedencia, no el destino.

### §5.2 El único lugar de fuentes del ecosistema (2026-09-06; M10 D6, 2026-09-15)

Aquí se descarga, se identifica y se cataloga; un proyecto (informe, curso, post) solo conserva su
`fuentes.yml`. La ingesta del CIL del despacho (`CIL/00_ingesta`), el manifiesto del marco legal y
`script_ingesta_recursos` de `biblioteca-studio` se mudaron aquí; cuando el CIL se disolvió
(M10 D6), `entrada/` pasó a ser la zona de aterrizaje. Nada del despacho queda en el repo: el
marco legal es dato público, no del cliente. La procedencia de cada carpeta:
[historial/procedencia-de-las-carpetas.md](historial/procedencia-de-las-carpetas.md).

### §5.3 Ningún proyecto escribe su propio descargador (2026-09-06)

Si un documento hace falta y su fuente no existe, se añade aquí como `fuentes/<nombre>/` (dos
archivos), no como un script en el proyecto. Lo recoge `meta/docs/historial/ARQUITECTURA.md` §2 (la fila de
este repo) y `prompts/skills/fuentes-documentales/references/paso-01-localizar-descargar.md`.

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

### §6.6 La ficha de catalogación canónica vive en `biblioteca-studio` (D12, 2026-09-20)

`ingesta/fichas/<sha8>_<slug>.md` es un borrador; `catalogar --aplicar` escribe la ficha con id en
`biblioteca-studio/catalogacion/fichas/` y su fila en
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
lo mismo que antes (`tests/fuentes/test_ingesta_cursos.py`) pero ya no deja informes; `ORIGINALES_DIR` deja la carpeta
retirada de `meta/reparaciones/` y va a `$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos`.

### §6.9 Las fichas provisionales no se versionan (ola 2, F6, 2026-10-05)

`ingesta/fichas/` acumulaba 812 borradores sin rastrear. Se clasificaron por su cabecera (la primera línea y el
frontmatter, sin leer el cuerpo) y por su fila en `ingesta.tsv`: ninguno correspondía a una obra con
`calibre_id` (la ficha de lo catalogado ya está, con su id, en `biblioteca-studio`); 35 llevaban la marca
«sustituida» y 777 eran borradores sin obra (773 de filas de `pendientes.tsv` aún sin catalogar, de
`datafw/data/raw`, y 4 sin fila). Los 812 se copiaron con `SHA256SUMS` verificado a
`$RESPALDOS_DIR/biblioteca/fuentes/ingesta-fichas-provisionales/` (con `clasificacion.tsv`) y se movieron a los
residuos del programa; `.gitignore` declara la carpeta temporal. Si una de esas filas se cataloga, su borrador
se recupera de la copia o se regenera con `identificar` tras quitar la fila de `pendientes.tsv`.

### §6.10 Los expedientes presupuestales del Congreso: una carpeta por libro (2026-11-16)

Los 18 expedientes del ciclo presupuestal 2022-2027 (378 archivos del portal de proyectos de ley) no se catalogan
uno por archivo: `identificar` les ponía títulos como «61710 AU2909», autor desconocido o el MEF en un reporte de
la DIDP. Se reordenan en `datafw/data/raw/congreso/presupuesto/<año>-<PL>-<etapa>/` con `doc_<id>.pdf` (proyecto,
dictamen, texto sustitutorio aprobado, autógrafa) y `adj_<id>_<nombre>.pdf` (oficios, votación, Junta de
Portavoces, adhesiones, anexos), y `PAQUETES_JSON` los trata como paquete; los metadatos salen del índice del
portal (número, etapa, fecha y descripción), no del nombre del archivo. Serie `datafw congreso - Presupuesto <año>`,
autor del dictamen `Congreso de la República. Comisión de Presupuesto y Cuenta General de la República` (desde 2027,
la Comisión Bicameral), como el 10841. Por decisión de Edison entran solo los anexos sin otra copia; los que repiten
los del MEF van a la papelera. Los escaneados se pasan por `ocrmypdf -l spa --skip-text` antes de catalogar.
Una trampa: en las leyes 2022 y 2023 (10263, 10264), el «PDF de 7 KB» del libro era su **anexo 1** puesto como
formato provisional por `sin_principal`; al entrar el texto de la ley por `add_format` se devolvió a `data/` y se
corrigió su entrada en el manifiesto. Antes de reemplazar el formato de un libro `sin_principal`, mirar qué es.

## 7. Maquinaria y dependencias

### §7.1 Se importa la maquinaria de `datafw`, no se reimplementa (2026-09-06)

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
vuelve a pedir. `tests/fuentes/test_red_fuentes.py` corre sin `datafw` en la caja de arena.

### §7.5 Rutas relativas a la raíz y nada personal en el repo (ola 2, F5, 2026-10-05)

Los ledgers `ingesta/ingesta.tsv` y `ingesta/pendientes.tsv` guardaban 2 220 rutas absolutas de la máquina
(`origen` y `ruta_calibre`). Se reescribieron solo en su forma (se quitó el prefijo de la raíz; las que
apuntan a archivos que ya no existen quedan como texto) y el código escribe y lee por `lib/rutas.py`: lo
relativo que empieza por una carpeta de la raíz es relativo a `DOCS_ROOT`; lo demás, a la zona de entrada,
como siempre. El correo de Unpaywall sale del entorno (`FUENTES_CORREO_CONTACTO`, P248); ninguna
configuración carga ya `biblioteca-studio/lib_comun` ni la carpeta personal; `fichas grafia` y `migrar`
respaldan en `$RESPALDOS_DIR/biblioteca/fuentes/fichas/` (P240). `manifiesto todo` en seco da la misma
salida antes y después. `tests/fuentes/test_privacidad_rutas.py` lo vigila.

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

### §8.4 El manifiesto de un proyecto de `escritura` vive en `fuentes/` (P5, 2026-09-08)

Cuando la raíz que dicta `REGLAS_RAIZ` tiene una carpeta `fuentes/`, el `fuentes.yml` va ahí, para
que un documento archivado desde `referencias/` no deje el manifiesto suelto en la raíz. Las reglas
se prueban primero contra la ruta tal como se dio y después contra la resuelta, porque
`datafw/data` es un enlace simbólico a un disco externo (2026-09-29).

### §8.5 `references.bib` se genera desde Calibre (2026-09-16)

*Superada por §1.6 (2026-10-06) para los documentos nuevos: citan desde la exportación de Better
BibTeX; los existentes conservan su `references.bib` generado hasta migrarlos.*

`manifiesto/main.py bib` escribe el bloque generado de `references.bib` (APA 7 vía biblatex) y la
`clave_bibtex` de cada entrada; un error se corrige en Calibre y se regenera. Informes y libros se
fechan por año; la fecha completa, solo en normas.

### §8.6 `traer`: los pasos 00 a 03 de una norma, para Inteligencia Legislativa (2026-11-15)

Edison pidió subir normas desde Qillqa sin un módulo nuevo. `main.py traer` no escribe por su cuenta: orquesta lo que
ya existe y pasa por la puerta (`lib/traer.py`): verificar con el resolutor; la ficha en gob.pe (sumilla, fecha,
emisor; fuente nueva `fuentes/gobpe`, que el Congreso no tiene decretos supremos) y el PDF del Congreso para las leyes;
`ingesta bib` con un `.bib` que arma en la caché (campos propios `emisor` y `date`, y `--indice` para el siguiente lugar
de la serie) y `catalogar --aplicar --solo <el archivo>`; el RIS de ese libro (`RIS_IDS`). Simula por omisión; con
Calibre abierto o el candado ocupado sale 75 antes de descargar. Propone la serie y las etiquetas de la norma que la
nueva modifica o reglamenta (por su número o por su nombre en la sumilla). Qillqa (Yachay) solo corre esta orden con
`--json`. Importar el RIS en Zotero sigue a mano (Zotero abierto) y `lectura --enlazar` cierra el puente.

### §8.7 La campaña NORMAS y el RIS de las normas (2026-11-15)

44 normas de «Marco legal» (las tandas del 2026-11-03) entraron como `Document`/«Documento oficial»: su RIS sale `GEN`.
`migraciones/main.py NORMAS` las deja `Statute`/«Normativa» y cambia `documento_oficial` por `norma` y `legislacion`,
sin tocar título, autor, fecha ni serie; se aplica solo con el «sí» de Edison. El RIS de una norma (`core`,
`biblioteca.ris`) lleva ahora su número, fecha completa, título corto y URL, y ya no la serie en `T2`/`M1`, que en
`statute` son el código y el número: unas 300 normas de Zotero quedaron así y piden una campaña propia de Zotero.

## 9. La familia de los studios y Yachay trabajan juntos

Pedido del autor el 2026-11-17: que Biblioteca Studio, LaTeX Studio, Datafw Studio y Yachay (Qillqa) trabajen
sincronizados y se complementen, con lo que Yachay ya hace (el fichado textual, los prompts del ecosistema) también en
los studios, y que un cambio en uno se vea en los demás. Decisiones del autor (preguntadas ese día): **el canal con
Yachay es su API con un token personal** (no la base directa ni copias en archivos); **una sola base de lectura**, de
Biblioteca Studio, donde se juntan los subrayados, notas y resaltados de KOReader, Zotero, Okular y el lector de Yachay,
y también las horas y estadísticas de lectura, para que todas las herramientas lean y escriban ahí; y **primero los
studios**, luego el fichado y los prompts en ellos, y al final la sincronía con Yachay.

Lo que ya estaba sincronizado sin hacer nada: el texto de un escrito y sus fichas viven en `escritura/` (Yachay no
guarda copia en su base): una coma en Yachay es la misma coma en LaTeX Studio, que vigila el archivo y lo recarga; y
al revés, Yachay protege lo suyo con la huella del archivo (409 si cambió).

### §9.1 La biblioteca en LaTeX Studio, y los escritos en Biblioteca Studio (2026-11-17)

`lib/consulta.py` sirve la biblioteca a los otros programas, en JSON: `buscar` (el índice compartido, más el año de
`metadata.db` en solo lectura), `fichas <proyecto>` (las de la carpeta fuentes/fichas del escrito, con el lector único de
`fichas/lib/ficha.py`, y lo que se inserta: la textual como «“cita” \parencite[p.~N]{clave}»), `citar <proyecto>
<calibre_id>` (la única que escribe, y solo en el proyecto: añade el libro a su `fuentes.yml` con la clave de Better
BibTeX y regenera su `references.bib` con el manifiesto, que conserva toda clave existente; simula sin `--aplicar`) y
`usos <calibre_id>` (los escritos que lo declaran o tienen fichas de él). Escritura lo declara en la sección
`biblioteca:` de su `escritura/core/config/latex-studio.yml` (contrato §9 de LaTeX Studio): la pestaña «Citas» busca en toda la
biblioteca con portada y cita (si el libro aún no es fuente, lo añade tras confirmar), muestra las fichas del proyecto
y abre el libro aquí (`biblioteca-studio://libro/<id>`). La ficha editorial suma «Usado en»: los escritos que usan el
libro, y un clic los abre en LaTeX Studio. Las capturas apuntan `WRITING_DIR` a la muestra: ningún escrito real en una
imagen.

### §9.2 La piel de la familia (2026-11-17)

La barra de arriba deja las pestañas y el óvalo de la puerta: las cuatro áreas son chips (la elegida, rellena), la
puerta es un punto con una línea, y lo demás sigue en ⋮ y Ctrl+K, como en Datafw Studio y LaTeX Studio (el mismo
`Chip`). La tarjeta del libro elegido lleva un anillo del color de acento en vez de pintarse entera, y los botones de la
ficha son chips. Sin colores propios, como siempre.

### §9.3 Lo que sigue del programa (en orden)

1. **El fichado y los prompts de Yachay en los studios**: crear y editar fichas textuales desde el PDF (Biblioteca
   Studio y LaTeX Studio) con la norma de fichas y su verificación contra el PDF; los prompts de `prompts/` (los de las
   partes de un escrito y el estudio de obra) para copiar con su traductor y pegar de vuelta, como en Yachay.
2. **La base de lectura** (una sola, de Biblioteca Studio): subrayados, notas y resaltados con su origen (KOReader,
   Zotero, Okular, Yachay) y las sesiones y estadísticas de lectura, con adaptadores de ida y vuelta; lo que se escribe
   en Calibre o Zotero pasa por la puerta (aplicación cerrada, candado, respaldo).
3. **Yachay por su API con token**: un token personal emitido desde Qillqa y una ruta de cambios (las fichas de los
   estudios, los resaltados del lector, el progreso) que los studios consultan y a la que escriben con la huella; toca
   Qillqa en producción, y su reinicio lo corre el autor.

### §9.4 Fichar desde los studios, como en Yachay (2026-11-17)

El punto 1 de §9.3, la mitad de las fichas. `lib/fichar.py` crea y corrige las fichas de un escrito (textual, paráfrasis,
síntesis y fuente) en su carpeta de fichas (fuentes/fichas del escrito) con el lector y escritor único (`fichas/lib/ficha.py`: el frontmatter en su
orden, las secciones de cada tipo, los once rótulos) y la forma de Yachay (`fuentes_escritura.py` de los estudios de Yachay): el
nombre `<clave>-pNNN-<tipo>-<tema>.md` (o `sNN` si la obra no pagina), el literal entre comillas tipográficas, la
localización, «Proviene de» la ficha de fuente, que lista la nueva entre sus derivadas (y nace si falta), y la firma
«Ficha hecha en Biblioteca Studio el <fecha>» en «Observaciones». Corregir exige la **huella sha256 del archivo entero**
con que se abrió: si en disco es otra (Yachay, LaTeX Studio o una mano la cambiaron), no se pisa y se responde
`{"codigo": "ficha_cambiada", "actual": …}`, lo que Yachay responde con 409; una página o un tipo nuevos cambian el
nombre y los enlaces de las otras fichas se corrigen. Cada guardado se **coteja contra el PDF** con el verificador de la
suite (`fichas/lib/verificar.py`): una textual o paráfrasis nueva, o con otro literal, sale `verificada_script` u
`observada` con su detalle; lo que verificó el autor no baja si el literal no cambió.

`lib/consulta.py` lo sirve con `formulario` (los tipos, sus secciones editables y los rótulos: las ventanas pintan el
formulario sin saber de la norma), `ficha`, `nueva_ficha` y `guardar_ficha` (simulan; escriben con `--aplicar`, solo en
la carpeta de fichas y, si el libro aún no es fuente del escrito, en su `fuentes.yml` y su `references.bib` por `citar`) y
`escritos` (todos los de escritura, para elegir el destino). En **Biblioteca Studio**, la ficha editorial suma «Nueva
ficha»: el PDF del libro a la izquierda (el visor de gui-comun) y a la derecha el escrito (primero los que ya usan el
libro), el tipo, la página impresa (con la hoja del PDF al lado), la categoría y las secciones; «Revisar» muestra el
nombre, el cotejo y lo que la norma objeta, y «Guardar la ficha» escribe lo revisado (`studio/biblioteca_app/controladores/fichado.py`,
`studio/biblioteca_app/qml/componentes/DialogoFicha.qml`). En **LaTeX Studio**, la pestaña Citas › Fichas (su decisión §1.19, por las
órdenes que escritura declara en su `latex-studio.yml`). Ninguna de las dos toca Calibre ni Zotero: no son puertas.

Trampa: `fichas/lib/verificar.py` hace `from lib import ficha`, y en Biblioteca Studio `lib` es el paquete de este repo (un
paquete regular le gana a la carpeta sin `__init__` de la suite): `fichar._verificador()` lo carga por su ruta bajo un
`lib` propio y devuelve el de antes (`tests/fuentes/test_fichar_y_ayuda.py` lo vigila).

### §9.5 Los prompts del ecosistema en los studios (2026-11-17)

La otra mitad del punto 1 de §9.3. `lib/ayuda_ia.py` copia el prompt y lee lo pegado, **sin llamar a ningún modelo**: el
autor lo lleva a su chat y trae la respuesta. Qué prompt sirve a cada parte de un escrito lo dice el cuadro de Yachay
(`prompts_por_parte.py` de sus estudios) y cuáles son las veinticinco miradas del estudio de una obra, su catálogo
(`catalogo.py`): los dos son puros y se **cargan por su ruta** (`YACHAY_CODIGO`, por omisión `~/Documents/yachay`), como el
traductor `prompts/scripts/para_ia_externa.py`, para que el cuadro viva una sola vez; sin Yachay, el prompt general de
redacción y ninguna mirada. No se importa el paquete de Yachay (arrastra Tiqsi y su base): el canal con Yachay es su API
(§9.3, punto 3).

- **Una parte de un escrito** (`prompt_parte`, `pegar_parte`; LaTeX Studio, Ctrl+Alt+I): el prompt de su `\componente`,
  traducido, con su sección «4 Entrada» rellena (el escrito, el texto de la parte sin comentarios, las fichas que la
  respaldan por su `uso`, las claves de su bibliografía) y el formato de vuelta de Yachay (un bloque ```latex). Lo pegado
  se comprueba como en `ayuda_componente.verificar`: sin `\componente`, `\section` ni preámbulo, solo claves de su
  bibliografía, las llaves cerradas, las marcas de trabajo (`[H]`, `[VERIFICAR: …]`) quitadas o vueltas `[dato pendiente:
  …]`; vuelve el tramo de antes y el de después, y la ventana lo pone en el editor si el autor acepta (se guarda con Ctrl+S).
- **Un estudio de obra** (`miradas`, `prompt_obra`, `pegar_obra`; Biblioteca Studio, «Estudiar con la IA»): el prompt de
  la mirada (`prompts/14 estudio`) con el paquete del tramo: la obra y sus hojas del PDF como unidades «[uN] hoja N» (Yachay
  usa las de su acervo). Lo pegado es el bloque `tipo: estudio-de-obra` del contrato de Qillqa (`estudio-de-obra.yml`): sus
  fichas propuestas se cotejan en su hoja (o se dice en cuál están) y cada una se lleva a un escrito con «Nueva ficha» ya
  rellena, que se revisa antes de guardar. Las afirmaciones y lo demás del estudio no se guardan aquí: viven en Yachay.

Las pruebas: `tests/fuentes/test_fichar_y_ayuda.py` (un escrito en un temporal, el texto del PDF simulado) y
`tests/studio/test_fichado.py` (el controlador sobre la muestra, que trae un informe en escritura y un libro con texto).

### §9.6 Una sola base de lectura, de Biblioteca Studio (2026-11-17)

Pedido del autor: «yo puedo usar KOReader, otra vez Zotero, otra vez Okular o desde mi Yachay: todas esas notas,
subrayados y resaltados deben sincronizar en una misma base de datos, en Biblioteca Studio, incluso sus horas de lectura y
sus estadísticas». La suite `lectura_base/` la construye:

- **Dónde**: `$XDG_DATA_HOME/biblioteca/lectura.sqlite` (`LECTURA_DB`). Son datos del usuario (lo subrayado solo en Yachay
  no está en otra parte), así que no van a la caché ni al estado, y nunca a una base de Calibre o de Zotero ni a un repo.
  `lectura_base/lib/base.py` es su único escritor y se niega a abrir `CALIBRE_DB`, `ZOTERO_DB` o algo dentro de la
  biblioteca o de la carpeta de Zotero; `tests/calibre/test_puerta.py` la declara «base propia» (`PROPIAS`): las reglas
  de la puerta valen para Calibre y Zotero, no para ella. Antes de escribir, el respaldo verificado de la puerta
  (`escribir.respaldar`) en `<respaldos de la puerta>/lectura/`.
- **El modelo**: una anotación por pasaje (libro por `calibre_id` y MD5 parcial de KOReader, hoja del PDF, página o
  capítulo, texto, rectángulos como fracciones de la hoja con el origen arriba, igual que Yachay, color, tipo,
  intención, nota, fechas, huella) y sus **presencias** (en qué herramienta vive y con qué identificador). Un mismo
  subrayado en KOReader y en Zotero es una anotación con dos presencias, no dos anotaciones. Aparte, las sesiones (solo
  KOReader guarda la hora de cada página) y el progreso por libro y por origen. Los relojes no se copian (como
  `#ko_tiempo` y `#zot_tiempo`): cada origen guarda su tiempo y las estadísticas los suman.
- **Sin duplicados**: un registro nuevo se une a la anotación de otro origen que sea el mismo pasaje (la misma huella:
  libro, hoja y comienzo del texto normalizado; o el texto casi igual en la misma hoja o la vecina; o los rectángulos
  solapados, que es como se reconoce lo de Okular, que no guarda texto). Dos subrayados iguales de una misma herramienta
  siguen siendo dos. Lo que la base escribe en una herramienta queda como presencia y vuelve como la misma anotación.
- **Conciliar, no copiar**: un cambio en un origen llega a la base si es más nuevo; lo que un origen leyó entero y ya no
  trae queda «ausente» allí, y la anotación ausente en todos, «borrada» en la base. Borrar en una herramienta no borra
  en las demás.
- **La cola de cambios**: cada alta, cambio o baja la apuntan disparadores de SQLite en `cambios`; un consumidor lee
  desde su cursor (`main.py cambios --consumidor X`). Es el canal de los studios y del adaptador de Yachay.
- **Leer es seguro**: KOReader por sus `metadata.*.lua` y `statistics.sqlite3` (`mode=ro`); Zotero de una copia de
  `zotero.sqlite` (API de respaldo de SQLite; con Zotero abierto, una copia del archivo); Okular por su docdata (el
  texto se recorta del PDF con `pdftotext`, porque Okular no lo guarda); Calibre en `mode=ro` (títulos, archivos,
  `#ko_md5`); Yachay solo por su API con token (§9.3.3), con el cliente que trae la fase 3b.
- **En la ventana**: el área **Lectura** (Ctrl+5): el resumen de la base (horas, este mes, racha, sesiones, de dónde vienen
  los subrayados), las horas de las últimas doce semanas, los libros con lectura y, del libro elegido (sigue al del
  catálogo), su progreso y tiempo en cada herramienta, sus subrayados filtrados por origen con los chips (cada uno se
  copia como cita) y sus sesiones. Solo lee; la base la escriben las operaciones «Base de lectura» y «Subrayados de la
  base → Zotero» de Coherencia › Sincronizar.

La primera simulación sobre los datos reales (2026-11-17, sin escribir): 61 resaltados de KOReader en 19 libros, 65
anotaciones de Zotero, 128 sesiones de KOReader, ningún pasaje en común entre ellos y nada en el docdata de Okular.
KOReader escribe `nan` en algunos sidecars (`percent_finished`); el lector Lua de la base lo entiende y reescribe los 287
sidecars reales idénticos byte a byte (probado en memoria).

### §9.7 La vuelta: qué se escribe en cada herramienta (2026-11-17)

La sincronía de ida y vuelta lleva a cada herramienta lo que la base tiene y ella no (`main.py exportar <destino>`;
simula siempre). Qué destino se escribe es decisión del autor, y por ahora:

- **Zotero, sí, por la puerta**: Zotero cerrado, `LOCK_ZOTERO`, respaldo verificado, la primitiva nueva
  `z_anadir_anotacion` de `lib/escribir_zotero.py` (un ítem «annotation» y su fila de `itemAnnotations` en el adjunto PDF del
  libro, sin sincronizar para que la cuenta lo suba) e `integrity_check` al final. Con Zotero abierto no se escribe.
- **KOReader y Okular, sí** (el autor, 2026-11-17: «También KOReader y Okular»): `exportar.ESCRIBE` los incluye.
  KOReader, en el `metadata.pdf.lua` de cada PDF que ya abrió (no crea sidecars); Okular, en el docdata del PDF (lo crea
  si falta), **nunca en el PDF**, que cambiaría su MD5 de KOReader. Los dos solo con la aplicación cerrada (al cerrar un
  libro reescriben su archivo con lo que tienen en memoria y borrarían lo escrito), con respaldo verificado en
  `<respaldos de la puerta>/lectura/<herramienta>/`, escritura atómica y relectura antes de reemplazar. El `.lua` sale
  con el formato de KOReader (idéntico byte a byte en los 287 sidecars reales) y la entrada con la misma forma que los
  resaltados que hace KOReader en un PDF; lo escrito en Okular lleva `uniqueName` = `okular-<uid de la base>` y vuelve
  como la misma anotación aunque su texto no se pueda recortar del PDF (un escaneo, una franja fina).
- **Las hojas giradas no se exportan** (a ninguna herramienta): en una hoja con `rot` 90 o 270 cada una mide sus
  rectángulos a su modo y el subrayado caería en otro lugar; tampoco los rectángulos fuera de la hoja. Se quedan en la
  base, con su aviso. Ensayo sobre copias de los datos reales (2026-11-17): 9 subrayados de Zotero a KOReader, 115 a
  Okular, 8 retenidos por hoja girada (un solo libro escaneado de lado); la segunda pasada, 0 cambios.
- **Yachay, por su API** (habilitado el 2026-11-17, con el cliente de la fase 3b ya fusionado y el token del autor en
  el llavero): `exportar yachay --aplicar` escribe con `POST /lector/{id}/resaltados`, con el `uid` de la base como
  `origen_id` para que Yachay no duplique. Admite el subrayado sin rectángulos (solo el texto). Las hojas giradas
  también se quedan en la base: el lector de Yachay mide sobre el mismo PDF. Ensayo: 115 a Yachay, 8 retenidos.
- **Cada hora** (el autor lo aprobó el 2026-11-17): `systemd/lectura-base.timer` corre `main.py ciclo`, la ida y la
  vuelta. Primero simula y escribe solo si hay algo, así una hora sin cambios no deja respaldos. Una herramienta
  abierta, Yachay sin token o un ciclo aún corriendo (candado `ciclo.lock` junto a la base) salen 75, «reintentar
  luego». El Python del sistema no trae `keyring`: el token se lee con `secret-tool` (`libsecret-tools`), que
  encuentra el mismo secreto (atributos `service=qillqa`, `username=studios`).


### §9.8 Sincronizar desde la ventana (2026-11-17)

- **Botón y timer, en el mismo lugar.** El área Lectura abre con la tarjeta «Sincronización». «Sincronizar ahora» corre
  una vuelta, `main.py ciclo --json`, la misma del timer, en un hilo. Al terminar dice qué trajo, qué llevó y qué quedó
  para la próxima vuelta. El interruptor «Cada hora» enciende o apaga `lectura-base.timer`, y lo instala con
  `systemd/instalar.sh` si falta. Apagado, la base se sincroniza solo con el botón: es el ajuste manual de lo automático.
- **La próxima vuelta se calcula.** Con `OnUnitActiveSec=1h`, systemd da la próxima solo en tiempo monótono. La ventana
  la cuenta desde la última vuelta, del timer o a mano (`ExecMainStartTimestamp` del servicio), más una hora.
- **Las llamadas al sistema van por `Sincronia`**, que las pruebas reemplazan por una falsa: ninguna prueba toca el timer
  real ni corre una vuelta sobre los datos reales.

### §9.9 El rediseño de la ventana y el repaso de las fichas (2026-11-18)

Pedido del autor: rehacer Biblioteca Studio según una maqueta que aprobó, más interactiva, intuitiva y fácil de usar, sin
perder nada de lo que hace, y sumar un repaso de las fichas para estudiantes.

- **La cabecera**: seis áreas como chips, en este orden y con Ctrl+1 a Ctrl+6: **Inicio · Catálogo · Lectura · Fichas ·
  Método · Coherencia**; después, la búsqueda y el punto de la puerta. **Bandejas** deja de ser chip pero no desaparece:
  Ctrl+7, el menú Ver, la paleta (Ctrl+K) y, desde Inicio, la cifra «Pendientes» y cada fila de «Siguiente paso» que la
  nombra (`SIN_CHIP` en `studio/biblioteca_app/controladores/espacio.py`). La ventana abre en Inicio. La maqueta ponía el nombre del studio antes
  de los chips; no se puso, porque la familia no lleva nombre ni logotipo dentro de la ventana (gui-comun, y
  `tests/studio/test_studio.py` lo vigila): el título lo pone KWin. Si el autor lo quiere, se decide para toda la familia.
- **Inicio** (`studio/biblioteca_app/controladores/inicio.py` y su `Inicio.qml`): «Esto es lo de hoy» con el estado breve de la sincronización;
  cuatro cifras (leído esta semana, subrayados nuevos de los últimos siete días, fichas por revisar y pendientes de las
  bandejas), «Seguir leyendo» (hasta tres libros en curso con su portada y la barra del color de la herramienta donde se
  leyeron por última vez) y «Siguiente paso» (hasta cuatro filas: fichar los subrayados que ninguna ficha de su libro
  contiene, con el primero ya puesto en «Nueva ficha»; el repaso del día; el escrito cuyo `fuentes.yml` cambió en la
  semana, «Abrir en LaTeX Studio»; las bandejas con algo). Lo que no tiene datos no se muestra: sin base de lectura no
  hay horas ni «Seguir leyendo».
- **Catálogo**: la fila de los filtros puestos (y la búsqueda), que se quitan de un toque; la barra de lectura bajo cada
  portada, del color de KOReader; y la ficha del libro reordenada: portada, título, autor y año, clave en monoespaciada,
  dos cifras (Leído y Subrayados, de la base de lectura), «Abrir» (la acción rellena), «Nueva ficha», «Estudiar con la IA»
  y «Citar en LaTeX» (copia `\parencite{clave}`), «Usado en», y lo de antes debajo.
- **Lectura**: cuatro cifras arriba (subrayados, horas en doce semanas, libros con lectura, racha), el mapa de calor de
  horas por día (7 × 12, más oscuro con más horas: `dias` de `lectura_base/lib/consulta.py`) y una raya a la izquierda de cada
  subrayado con el color de la herramienta donde nació. **Los colores de las herramientas son de la maqueta y viven en
  Python** (`COLORES` en `studio/biblioteca_app/controladores/lectura.py`: KOReader `#378ADD`, Zotero `#D85A30`, Okular `#1D9E75`, Yachay `#7F77DD`):
  el QML no lleva colores propios. Las consultas nuevas (`dias`, `nuevas`, `en_curso`, `subrayados`) solo leen.
- **Fichas** (`studio/biblioteca_app/controladores/fichas.py` y su `Fichas.qml`): las de todos los escritos (`lib/consulta.py` `escritos` y
  `fichas`, que ahora da también el tema y la paráfrasis) y las canónicas, con los filtros en lista (Todas, Textuales,
  Paráfrasis, Por revisar, con su cuenta); cada ficha con su cita en letra de lectura y, tenue, la obra, la página, el
  tipo, si está cotejada con el PDF y el escrito, con «Abrir en LaTeX Studio» (LaTeX Studio no recibe una inserción
  desde fuera: lo más cercano es abrir el escrito) y «Copiar la cita» (lo que se insertaría). «Ver en Yachay» no se puso:
  Yachay no tiene una dirección por ficha de escrito. «Nueva ficha» y «Estudiar con la IA» son los diálogos de §9.4 y
  §9.5, sobre el libro de la ficha elegida.
- **Método y Coherencia** (`EspacioEtapas.qml`): el Método es un recorrido de pasos numerados con su contador, la elegida
  resaltada; debajo, la descripción de la etapa, «Simular (F5)» y «Aplicar (Ctrl+Intro)» con la línea tenue «respaldo
  verificado · se puede deshacer» cuando la operación escribe en una base (en la pestaña Operación ya no se repiten). La
  Coherencia suma arriba tres tarjetas (Calibre ⇄ Zotero, Calibre ⇄ KOReader y Tareas automáticas: un punto de estado,
  una línea tenue y el botón que elige su operación o su etapa; `etapas.tarjetasCoherencia`). La tabla, el elemento, el
  plan, el registro y la salida siguen igual.
- **Piezas comunes**: `Tarjeta` (la de Lectura, ahora un componente: el fondo de la vista, una línea fina y esquinas
  suaves), `Cifra` y `BarraLectura`.

**El repaso para estudiantes** (`lib/repaso.py`). Se apoya en dos resultados: la **práctica de recuperación**, recordar
fija más que releer (Roediger y Karpicke, 2006), y el **repaso espaciado**, repasos separados retienen más que los
seguidos (Cepeda et al., 2006). Por eso la tarjeta muestra primero la pregunta (la categoría o el tema de la ficha y su
obra) y solo con «Mostrar la ficha» la cita, y por eso cada ficha vuelve cada vez más tarde: el **sistema Leitner de
cinco cajas**. Una ficha nueva entra en la caja 1; «La sabía» la sube una caja (hasta la 5) y «Repasar luego» la vuelve
a la 1. La caja 1 vuelve cada día, la 2 cada 2, la 3 cada 4, la 4 cada 8 y la 5 cada 16. Toca hoy lo vencido y lo nunca
repasado, primero la caja más baja. Entran las textuales, las paráfrasis y las síntesis con texto.

- **Su base**: `$XDG_DATA_HOME/biblioteca/repaso.sqlite` (`REPASO_DB`), junto a la base de lectura y por la misma razón:
  es del usuario. No es Calibre ni Zotero, así que no pasa por la puerta; `lib/repaso.py` es su único escritor, su
  conexión de escritura pasa por la guarda de rutas de la base de lectura (`comprobar_ruta`), y `tests/calibre/test_puerta.py`
  la declara base propia. Antes de la primera escritura de cada día deja un respaldo verificado (`escribir.respaldar`)
  en `<respaldos de la puerta>/repaso/`: uno por día y no uno por tarjeta, para no llenar el disco con copias. Una ficha
  se nombra por su clave (`<familia>/<escrito>/<nombre>`), no por su ruta.
- **Simular**: `python3 lib/repaso.py responder <clave> --sabia` dice lo que haría; con `--aplicar` lo escribe. La
  ventana escribe al pulsar, que es la decisión de quien estudia.
- **Las pruebas**: `tests/studio/test_repaso.py` (las cajas, subir, bajar, qué toca hoy, la simulación, el respaldo del
  día, la guarda), `tests/studio/test_inicio.py` (Inicio y Fichas sobre la muestra, que trae dos fichas en su informe y
  una tarjeta ya repasada) y `tests/lectura_base/test_consulta.py` (las consultas nuevas). Las capturas, con
  `studio/capturar.py --area inicio|fichas|…` (y `--repaso --mostrar`), sobre la muestra.

Referencias: Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T. y Rohrer, D. (2006). Distributed practice in verbal recall
tasks: A review and quantitative synthesis. *Psychological Bulletin, 132*(3), 354–380. Roediger, H. L. y Karpicke, J. D.
(2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science, 17*(3), 249–255.
Las dos aún no están en la biblioteca (pendiente en `estado.md`).
