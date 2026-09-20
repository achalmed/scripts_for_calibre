---
tipo: readme
estado: activo
---
# scripts_for_calibre/ — las herramientas que mantienen coherentes Calibre, KOReader y Zotero (7 suites, 3 timers)

<!-- suites:inicio -->
Suites de esta carpeta (7); índice global en `meta/INDICE_SCRIPTS.md`. Patrón: M main · C config · L lib.

| Suite | Carpeta | Objetivo | Escribe en | Simula | Timer | Estado | Patrón |
|---|---|---|---|---|---|---|---|
| `catalogacion_biblioteca` | [scripts_for_calibre/script_catalogacion_biblioteca](script_catalogacion_biblioteca/) | fuentes | calibre, archivos | sí |  | activo | `MCL` |
| `ecosistema_lectura` | [scripts_for_calibre/script_ecosistema_lectura](script_ecosistema_lectura/) | biblioteca | calibre | sí | ecosistema-lectura.timer · ecosistema-metadatos.timer | activo | `MCL` |
| `koreader_estudio` | [scripts_for_calibre/script_koreader_estudio](script_koreader_estudio/) | biblioteca | calibre | sí | koreader-calibre-sync.timer | activo | `MCL` |
| `metadatos_calibre` | [scripts_for_calibre/script_metadatos_calibre](script_metadatos_calibre/) | biblioteca | calibre, archivos | sí |  | activo | `MCL` |
| `normalizacion_metadatos` | [scripts_for_calibre/script_normalizacion_metadatos](script_normalizacion_metadatos/) | biblioteca | calibre | sí |  | archivado | `···` |
| `sincronizar_zotero` | [scripts_for_calibre/script_sincronizar_zotero](script_sincronizar_zotero/) | biblioteca | calibre, zotero | sí |  | activo | `MCL` |
| `verificar_metadatos` | [scripts_for_calibre/script_verificar_metadatos](script_verificar_metadatos/) | biblioteca | ninguno | sí |  | activo | `MCL` |

<sub>Bloque generado desde los `suite.yml` por `core/suites.py generar` (2026-09-20); no se edita a mano.</sub>
<!-- suites:fin -->

## Qué es

Siete herramientas de línea de comandos (Bash + Python) alrededor de la biblioteca Calibre
(`biblioteca/`, la autoridad bibliográfica del workspace): catalogación desde fichas, normalización
y verificación de metadatos, incrustación en los PDF, y la plomería que une Calibre con KOReader
(lectura) y con Zotero (referencias y citas). Tres de ellas corren solas con timers systemd de
usuario: KOReader → Calibre y Zotero → Calibre cada 30 minutos, y la sincronización bidireccional de
metadatos a diario a las 04:30. La regla de oro de todo el repo: **Calibre manda** en los metadatos
bibliográficos, Zotero solo rellena vacíos, y los relojes de lectura de KOReader y de Zotero **nunca se
copian entre sí**: Calibre los agrega en `#tiempo_estudio`.

**No es** la biblioteca (esa es `biblioteca/`, con su `metadata.db`), ni el sitio donde nacen las
fichas de catalogación nuevas (`scripts_for_fuentes/ingesta` las escribe aquí, en
`script_catalogacion_biblioteca/fichas/`, que es el registro de esa suite), ni una biblioteca de código:
`lib_comun/` son envoltorios de compatibilidad de `core/shell-lib` y `core/py-common`, no módulos
propios. Depende de `core/` (raíz, logger, lock, resolutor de la biblioteca), de `biblioteca/`, de
`~/Zotero/zotero.sqlite` y del repo de datos `~/.local/share/koreader-respaldo/` (`meta/workspace.yml`).
La autoridad de cada dato y la dirección de cada sincronización están en `meta/MODELO_METADATOS.md`
§2 y §4 y en `meta/SINCRONIZACION.md`.

## Uso

```bash
script_koreader_estudio/main.sh                          # simula KOReader → Calibre (progreso, tiempo, estado)
script_koreader_estudio/main.sh --aplicar                # escribe: Calibre cerrado; toma el lock y respalda metadata.db
script_ecosistema_lectura/main.sh --aplicar              # Zotero (readingTime) → Calibre; Zotero puede estar abierto
script_ecosistema_lectura/main.sh --metadatos            # orquesta sincronizar_zotero (simula; --aplicar con ambas cerradas)
script_ecosistema_lectura/main.sh --enlazar              # informe de libros sin #zotero_key (nunca escribe)
script_sincronizar_zotero/main.sh --limite 20 --aplicar  # canario de la sync bidireccional; ambas apps cerradas
script_verificar_metadatos/main.sh --limite 5            # solo lectura: discrepancias contra OpenLibrary/Crossref en reportes/
script_metadatos_calibre/main.sh embed --dry-run         # OPF → PDF con exiftool; register --aplicar registra PDF sueltos
script_catalogacion_biblioteca/main.sh --ids 10265,10266 # aplica filas de resumen_catalogacion.tsv (simula; --aplicar escribe)
script_koreader_estudio/main.sh --instalar-timer         # timers systemd de usuario (también script_ecosistema_lectura)
systemctl --user list-timers | grep -E "koreader|ecosistema"   # ¿cuándo corren?
```

Simulación por defecto en las siete; se escribe solo con `--aplicar` (`--apply` en las migraciones
archivadas). Requisitos: Calibre con `calibredb` y `calibre-debug` en el PATH, `python3` (biblioteca
estándar), `sqlite3`, y `exiftool` solo para `script_metadatos_calibre`; todo corre sin sudo. Qué es
automático, qué es manual y cómo saber si funciona: `docs/operacion.md`.

## Estructura

| carpeta | qué es | dueño / generador |
|---|---|---|
| `script_koreader_estudio/` | KOReader → Calibre: columnas `#ko_*`, `#barra`, `#estado_estudio`, `#apuntes`; sidecars por hash; respaldo continuo al repo de datos | a mano; timer `koreader-calibre-sync` |
| `script_ecosistema_lectura/` | Zotero (Ethereal Style) → Calibre: `#zot_*`, `#tiempo_estudio`; orquesta `sincronizar_zotero`; informe de enlaces | a mano; timers `ecosistema-lectura`, `ecosistema-metadatos` |
| `script_sincronizar_zotero/` | metadatos y etiquetas Calibre ⇄ Zotero para los libros con `#zotero_key`; política «Calibre manda» | a mano |
| `script_verificar_metadatos/` | coteja Calibre contra OpenLibrary y Crossref; solo lectura | a mano |
| `script_metadatos_calibre/` | incrustador canónico OPF → PDF (InfoDict + XMP-dc), registro de PDF, limpieza de `zotero_metadata.json` huérfanos | a mano |
| `script_catalogacion_biblioteca/` | aplica `resumen_catalogacion.tsv` a Calibre; `fichas/` y el TSV son su registro (los escriben `scripts_for_fuentes/ingesta` e `ingesta_cursos`) | a mano; registro versionado |
| `script_normalizacion_metadatos/` | migraciones de una sola vez (2026-07-28) que normalizaron etiquetas, géneros y tipos; archivado | bitácora, no se ejecuta en bloque |
| `lib_comun/` | envoltorios de 2–4 líneas hacia `core/shell-lib/` y `core/py-common/` (FS2) para quien todavía hace `source ../lib_comun/x.sh` | derivado de `core/`; el código nuevo carga `core/` directamente |
| `docs/` | operación (timers, rutina manual, verificación) e historial (diseño de 2026-08) | a mano; índice por `core/docs.py indice` |
| `suite.yml` (uno por suite) | manifiesto de cada herramienta (`core/suite.schema.yml`) | a mano; los bloques de README los genera `core/suites.py generar --aplicar` |
| `.lock_calibre_write` | candado `flock` que comparten todos los escritores de `metadata.db` (`LOCK_CALIBRE` en `core/env.sh`) | runtime, ignorado |
| `*/reportes/`, `*/backups/`, `*/estado/` | informes de cada pasada, `metadata.db` rotados, marcas de la última pasada | runtime, ignorados (`.gitignore` por clase) |

## Documentación

| documento | para qué leerlo |
|---|---|
| `CLAUDE.md` | reglas para el asistente: autoridad de campo, lock, timers, qué no se toca |
| `docs/operacion.md` | lo automático (timers), lo manual, chuleta de comandos, verificación y problemas |
| `docs/historial/diseno-ecosistema-lectura-2026-08.md` | por qué el ecosistema es así (hallazgos de inspección, opción elegida, fases cumplidas) |
| `script_koreader_estudio/README.md` | columnas, sidecars por hash, respaldo continuo, trampas de Calibre |
| `script_ecosistema_lectura/README.md` | fuente de datos de Zotero, columnas `#zot_*`, orquestación |
| `script_sincronizar_zotero/README.md` | política de sincronización campo a campo y reglas duras |
| `script_verificar_metadatos/README.md` | alcance realista y criterios de comparación |
| `script_metadatos_calibre/README.md` | operaciones `embed`, `register`, `limpiar-json` |
| `script_catalogacion_biblioteca/README.md` | flujo prompt → ficha → TSV → Calibre y el registro de fichas |
| `script_normalizacion_metadatos/README.md` | bitácora de las migraciones de 2026-07-28 y el gotcha del OPF |
| `meta/MODELO_METADATOS.md`, `meta/SINCRONIZACION.md` | autoridad por dato y arquitectura de sincronización (frontera con `meta`) |
| `meta/INDICE_SCRIPTS.md` | las 7 suites entre las del workspace (generado) |

## Límite honesto

- **No hay pruebas automáticas**: la comprobación es la simulación de cada `main.sh`, `bash -n`,
  `py_compile`, el informe de `reportes/` y mirar Calibre.
- **Escribir exige Calibre cerrado** (y Zotero cerrado para `sincronizar_zotero`); los timers no fallan
  por eso, reintentan en la siguiente pasada.
- **Zotero se escribe por SQL directo** (como hace el plugin ZMI): método no soportado por Zotero; cada
  ítem tocado queda `synced=0` para que la cuenta lo suba. Sin backup previo no se aplica.
- **Título y autor jamás se escriben en Calibre**: Zotero enlaza los adjuntos por la ruta
  `Autor/Título (id)`; cambiarlos rompería el vínculo. Solo van Calibre → Zotero.
- **El progreso de lectura tiene una sola fuente por reloj**: KOReader y Zotero no se deduplican porque
  ningún segundo entra dos veces al mismo contador; la fase 5 del diseño (exportar sesiones de KOReader
  a Ethereal Style) no está hecha ni planificada.
- **`verificar_metadatos` solo cubre lo verificable** (unos 220 libros con identificador); los ~4 300
  documentos de aula no existen en ninguna base.
- **`normalizacion_metadatos` no se re-ejecuta en bloque**: cuatro de sus nueve migraciones leían un
  scratchpad extinto; se conservan como historia.
- **Los `reportes/` no rotan solos**: la poda (30 días) la aplica una fase de higiene, no las suites.
- Licencia MIT declarada en el remoto público; no hay archivo `LICENSE` en el repo.
