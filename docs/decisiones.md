---
tipo: decision
titulo: "Decisiones de scripts_for_calibre: autoridad de los datos, escritura segura, campañas y pendientes"
estado: activo
---
# Decisiones de `scripts_for_calibre`

Registro acumulativo, por tema y con la fecha de cada decisión. Los números de sección no se
renumeran: se añaden al final. Lo pendiente va a §Pendientes. La crónica de cada campaña, en
`historial/campanas-sobre-la-biblioteca.md`.

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

## Pendientes

- **P1. El candado no lo toman todos los escritores.** `script_catalogacion_biblioteca` (con
  `--aplicar`) y `script_metadatos_calibre register` escriben `metadata.db` por `calibredb` sin
  `tomar_lock_calibre`; solo comprueban (la primera) que Calibre esté cerrado. Su `suite.yml` o su
  README decían lo contrario.
- **P2. `script_metadatos_calibre` escribe por defecto.** `embed` y `register` modifican los PDF y
  `metadata.db` salvo que se pase `--dry-run`; `--aplicar` solo lo lee `limpiar-json`. Su
  `suite.yml` declara `simula_por_defecto: true` y anuncia `embed --aplicar` y `register --aplicar`,
  que no cambian nada. Además, sin `--root`, la raíz es el directorio actual.
- **P3. Manifiestos que se quedaron cortos.** El `suite.yml` de `normalizacion_metadatos` dice
  «géneros, tipos de ítem y vocabulario de etiquetas» y «sin main.sh»: no cuenta las campañas de
  autores, títulos y duplicados, que sí tienen `main.sh`. El de `catalogacion_biblioteca` promete
  «serie» (el TSV no tiene esa columna) y «lock» en `--aplicar` (P1). Al corregir un `suite.yml` hay
  que regenerar los bloques con `core/suites.py generar --aplicar`.
- **P4. Respaldos de ruta literal.** `config.sh` de `catalogacion_biblioteca`, `verificar_metadatos`
  y `metadatos_calibre` y las migraciones `01`–`09` caen a `~/Documents/biblioteca` si no reciben
  `BIBLIOTECA_DIR` o `CALIBRE_DB`, en vez de cargar `core/env.sh`.
- **P5. Fase 5 del diseño** (exportar sesiones de KOReader al registro de Ethereal Style): opcional,
  no planificada.
- **P6. `reportes/` no rota sola**: la poda de más de 30 días la hace una fase de higiene.
- **P7. Licencia**: MIT declarada en el remoto público, sin archivo `LICENSE` en el repo.
