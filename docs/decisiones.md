---
tipo: decision
titulo: "Decisiones de scripts_for_calibre: autoridad de los datos, escritura segura y organización"
genero: explicacion
estado: activo
---
# Decisiones de `scripts_for_calibre`

Registro acumulativo, por tema y con la fecha de cada decisión. **Los números son identificadores
permanentes**: una entrada no se renumera ni se borra; si deja de regir, lleva *Superada por §X*.
Lo pendiente vive en [`../estado.md`](../estado.md) §Por hacer (desde la ola 2a, K9). La crónica de
las campañas hasta 2026-10-01, en `historial/campanas-sobre-la-biblioteca.md`; la de las
posteriores, en su commit.

## 1. Autoridad de los datos

### §1.1 Calibre manda en los metadatos bibliográficos (2026-07-28)

En conflicto gana Calibre y se propaga a Zotero; Zotero solo rellena vacíos en Calibre y puebla las
columnas espejo `#zotero_*`. Vacío en el origen nunca borra en el destino. Política campo a campo:
`../script_sincronizar_zotero/README.md`; autoridad por dato en el workspace:
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

### §4.3 `script_catalogacion_biblioteca/fichas/` y `resumen_catalogacion.tsv` son el registro de esa suite (D12, 2026-09-20)

Las fichas y las filas nuevas las escribe `scripts_for_fuentes/ingesta`; aquí solo se aplican al
catálogo. Una ficha cita su proyecto por id (`proyecto: meta`), no por ruta (normativa 1.10, K7).

### §4.4 Un solo incrustador de PDF (auditoría A7, 2026-08-10)

`script_metadatos_calibre embed`, con InfoDict y XMP Dublin Core; el de `scripts_for_zotero` quedó
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
