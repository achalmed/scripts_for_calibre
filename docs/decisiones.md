---
tipo: decision
titulo: "Decisiones de scripts_for_calibre: autoridad de los datos, escritura segura, campañas y pendientes"
estado: activo
---
# Decisiones de `scripts_for_calibre`

Registro acumulativo, por tema y con la fecha de cada decisión. Los números de sección no se
renumeran: se añaden al final. Lo pendiente va a §Pendientes. La crónica de las campañas hasta
2026-10-01, en `historial/campanas-sobre-la-biblioteca.md`; la de las posteriores, en su carpeta y
en su commit (§4.6).

## 1. Autoridad de los datos

1.1. **Calibre manda en los metadatos bibliográficos** (2026-07-28). En conflicto gana Calibre y se
propaga a Zotero; Zotero solo rellena vacíos en Calibre y puebla las columnas espejo `#zotero_*`.
Vacío en el origen nunca borra en el destino. Política campo a campo:
`../script_sincronizar_zotero/README.md`; autoridad por dato en el workspace:
`meta/MODELO_METADATOS.md`.

1.2. **Título y autor no se escriben en Calibre por sincronización ni verificación** (2026-07-28):
Zotero enlaza los adjuntos por la ruta `Autor/Título (id)`. Desde 2026-09-30 se admite una
excepción: una campaña aprobada que reescriba en la misma operación las rutas y los datos de Zotero
(`historial/campanas-sobre-la-biblioteca.md` §4 y §5).

1.3. **Los relojes de lectura no se copian entre sí** (2026-08-09). `#ko_tiempo` es de KOReader,
`#zot_tiempo` de Zotero (Ethereal Style) y `#tiempo_estudio` los suma: ningún segundo entra dos
veces al mismo contador, así que no hay deduplicación que implementar. Diseño:
`historial/diseno-ecosistema-lectura-2026-08.md` §3.

1.4. **Estado de lectura y estado de estudio son columnas distintas** (2026-08-09):
`#estado_estudio` lo calculan las suites; `#estudio` es manual y ningún script lo toca.

1.5. **El título se compara exacto** entre Calibre y Zotero (2026-10-01); los demás campos siguen
comparándose normalizados. Con `norm()` una corrección de tildes o mayúsculas en Calibre nunca
llegaba a Zotero.

## 2. Escritura segura

2.1. **Un solo escritor de `metadata.db` a la vez**, con el candado `flock` compartido
`.lock_calibre_write` de la raíz (auditoría C5, 2026-08-09). Los timers lo pasan al hijo por
descriptor (`ECOSISTEMA_LOCK_HELD=1`). Qué suites lo toman de verdad: §Pendientes P1.

2.2. **Simulación por defecto y `--aplicar` explícito**, con respaldo rotado antes de escribir y
`PRAGMA integrity_check` después (2026-07-28). Excepciones vigentes: §Pendientes P2 y el patrón de
campaña (§4.2).

2.3. **Tras escribir por SQLite, `calibredb backup_metadata --all`** con Calibre cerrado, para que
los OPF no queden rancios; nunca `embed_metadata`, que modifica el archivo del libro (2026-07-28).

2.4. **Zotero se escribe por SQL directo** solo desde `sincronizar_zotero` y desde las campañas, con
ambas apps cerradas y `synced=0` en cada ítem tocado para que la cuenta lo suba (2026-07-28).

## 3. KOReader

3.1. **Sidecars por hash** (2026-08-09): `document_metadata_folder = "hash"` y los `.sdr` en
`~/.config/koreader/hashdocsettings/`; renombrar en Calibre ya no rompe el emparejamiento, que se
hace por el MD5 parcial de KOReader cacheado en `#ko_md5`.

3.2. **El respaldo de KOReader va a un repo de datos propio** (`KOREADER_RESPALDO_DIR`, FG3,
2026-09-15), no a `~/.dotfiles`, y excluye `settings.reader.lua` porque lleva credenciales `kosync`.

## 4. Organización del repositorio

4.1. **`lib_comun/` son envoltorios de `core/`** (FS2, 2026-09-07) y no se amplían; el código nuevo
carga `core/env.sh` o `core/env.py` directamente.

4.2. **Una campaña sobre la biblioteca es una carpeta en
`script_normalizacion_metadatos/migraciones/<tema>_<fecha>/`** (2026-09-30) con `main.sh`, foto
previa, `propuesta.tsv`, `hechos.tsv` (registro y guarda contra la repetición) y `deshacer.sh`. Su
`main.sh` aplica sobre las bases reales; el ensayo es `--simular <biblioteca> <zotero.sqlite>` sobre
una copia.

4.3. **`script_catalogacion_biblioteca/fichas/` y `resumen_catalogacion.tsv` son el registro de esa
suite** (D12, 2026-09-20): las fichas y las filas nuevas las escriben `scripts_for_fuentes/ingesta`
e `ingesta_cursos`; aquí solo se aplican al catálogo.

4.4. **Un solo incrustador de PDF** (auditoría A7, 2026-08-10): `script_metadatos_calibre embed`,
con InfoDict y XMP Dublin Core; el de `scripts_for_zotero` quedó absorbido.

4.5. **Los timers se instalan con la herramienta** (`--instalar-timer`) desde las plantillas
versionadas en `../script_koreader_estudio/lib/systemd/` y
`../script_ecosistema_lectura/lib/systemd/`; `~/.dotfiles` no los gestiona (2026-09-20).

4.6. **La crónica de una campaña nueva va a su carpeta y al commit** (2026-10-04): la cabecera de
su `main.sh`, sus tablas (`propuesta.tsv`, `hechos.tsv`) y el mensaje de commit. La bitácora
`historial/campanas-sobre-la-biblioteca.md` cubre hasta 2026-10-01, está cerrada y no se reabre.

4.7. **La interfaz que usan otros repos vive en `consumidores.md`** (2026-10-04): `lib_comun/`, el
registro de catalogación y el candado. `lib_comun/` se conserva mientras tenga consumidores.

## Pendientes

- **P1. El candado no lo toman todos los escritores.** `script_catalogacion_biblioteca` (con
  `--aplicar`) y `script_metadatos_calibre register` escriben `metadata.db` por `calibredb` sin
  `tomar_lock_calibre`; solo comprueban (la primera) que Calibre esté cerrado. Su `suite.yml` o su
  README decían lo contrario.
- **P2. `script_metadatos_calibre` escribe por defecto.** `embed` y `register` modifican los PDF y
  `metadata.db` salvo que se pase `--dry-run`; `--aplicar` solo lo lee `limpiar-json`. Además, sin
  `--root`, la raíz es el directorio actual, y `register` no comprueba que Calibre esté cerrado
  (lo exige `calibredb`). Desde 2026-10-04 su `suite.yml` lo declara así; lo pendiente es el código.
- ~~**P3. Manifiestos que se quedaron cortos.**~~ *Cerrado el 2026-10-04:* los `suite.yml` de
  `normalizacion_metadatos`, `catalogacion_biblioteca` y `metadatos_calibre` dicen lo que hace el
  código y los bloques se regeneraron con `core/suites.py generar --aplicar`.
- **P4. Respaldos de ruta literal.** Los `config.sh` de las seis suites con `main.sh` y las
  migraciones `01`–`09` caen a `~/Documents/biblioteca` (y las dos que leen Zotero, a `~/Zotero`)
  si no reciben la ruta por variable (`BIBLIOTECA_DIR`, `CALIBRE_DB`, `ZOTERO_DIR` o la propia de
  la suite), en vez de cargar `core/env.sh`.
- **P5. Fase 5 del diseño** (exportar sesiones de KOReader al registro de Ethereal Style): opcional,
  no planificada.
- **P6. `reportes/` no rota sola**: la poda de más de 30 días la hace una fase de higiene.
- ~~**P7. Licencia**~~ *Cerrado el 2026-10-04 por decisión del autor:* MIT (`LICENSE`), la del resto
  del código del ecosistema y la que anunciaba el primer README.
- **P8. Plantillas systemd con ruta de máquina** (2026-10-04, autor): los tres `.service` de
  `script_koreader_estudio/lib/systemd/` y `script_ecosistema_lectura/lib/systemd/` fijan un `PATH` con el directorio personal; solo `@MAIN@` se renderiza al instalar.
- **P9. Rutas de máquina en las fichas** (2026-10-04, autor): la sección «Origen» de muchas fichas de
  catalogación lleva la ruta absoluta del archivo de entrada, y el repo es público. Son registro:
  se limpian con la herramienta que las escribe (`scripts_for_fuentes/ingesta`), no a mano.
- **P10. Filas sin ficha** (2026-10-04, autor): 10423–10425 están en `resumen_catalogacion.tsv` y no
  en `fichas/`.
- **P11. Ayuda de CLI fuera de la norma de idioma** (2026-10-04, autor): `script_metadatos_calibre`
  (en inglés, también `script_verificar_metadatos/lib/db.sh`), `script_sincronizar_zotero` y
  `script_verificar_metadatos` (sin tildes).
- **P12. `script_normalizacion_metadatos/migraciones/zotero_alta_2026-09-30/` sin aplicar** (2026-10-04, autor): un solo script que
  manda a la papelera de Zotero la segunda importación del RIS de `--enlazar`; no sigue el patrón de
  §4.2 (sin `hechos.tsv` ni `deshacer.sh`) y no hay respaldo que pruebe que se aplicó.
- **P13. El `suite.yml` de `verificar_metadatos` declara `curl`** (2026-10-04, autor): el código hace
  las peticiones con `urllib` y `script_verificar_metadatos/lib/cli.sh` no comprueba `curl`; el
  bloque generado del README lo repite. Al corregirlo, `core/suites.py generar --aplicar`.
- **P14. Un correo personal en `script_verificar_metadatos/config.sh`** (2026-10-04, autor): el
  contacto del «polite pool» de Crossref está escrito como valor por defecto en un repo público;
  cabe moverlo a `core/env.sh` o exigir la variable de entorno.
