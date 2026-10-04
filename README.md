---
tipo: readme
estado: activo
---
# scripts_for_calibre/ — las herramientas que mantienen coherentes Calibre, KOReader y Zotero

<!-- suites:inicio -->
Suites de esta carpeta (7); índice global en `meta/INDICE_SCRIPTS.md`. Patrón: M main · C config · L lib.

| Suite | Carpeta | Objetivo | Escribe en | Simula | Timer | Estado | Patrón |
|---|---|---|---|---|---|---|---|
| `catalogacion_biblioteca` | [scripts_for_calibre/script_catalogacion_biblioteca](script_catalogacion_biblioteca/) | fuentes | calibre, archivos | sí |  | activo | `MCL` |
| `ecosistema_lectura` | [scripts_for_calibre/script_ecosistema_lectura](script_ecosistema_lectura/) | biblioteca | calibre | sí | ecosistema-lectura.timer · ecosistema-metadatos.timer | activo | `MCL` |
| `koreader_estudio` | [scripts_for_calibre/script_koreader_estudio](script_koreader_estudio/) | biblioteca | calibre | sí | koreader-calibre-sync.timer | activo | `MCL` |
| `metadatos_calibre` | [scripts_for_calibre/script_metadatos_calibre](script_metadatos_calibre/) | biblioteca | calibre, archivos | no |  | activo | `MCL` |
| `normalizacion_metadatos` | [scripts_for_calibre/script_normalizacion_metadatos](script_normalizacion_metadatos/) | biblioteca | calibre, zotero, archivos | no |  | archivado | `···` |
| `sincronizar_zotero` | [scripts_for_calibre/script_sincronizar_zotero](script_sincronizar_zotero/) | biblioteca | calibre, zotero | sí |  | activo | `MCL` |
| `verificar_metadatos` | [scripts_for_calibre/script_verificar_metadatos](script_verificar_metadatos/) | biblioteca | ninguno | sí |  | activo | `MCL` |

<sub>Bloque generado desde los `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suites:fin -->

Herramientas de línea de comandos (Bash y Python) alrededor de la biblioteca Calibre (`biblioteca/`,
la autoridad bibliográfica del workspace): catalogación desde fichas, verificación de metadatos,
incrustación en los PDF, las campañas de normalización y la plomería que une Calibre con KOReader
(lectura) y con Zotero (referencias). Tres timers systemd de usuario la mueven solos: KOReader →
Calibre y Zotero → Calibre cada 30 minutos, y la sincronización bidireccional de metadatos a diario
a las 04:30. La regla de todo el repo: **Calibre manda** en los metadatos bibliográficos, Zotero
solo rellena vacíos, y los relojes de lectura de KOReader y de Zotero **nunca se copian entre sí**:
Calibre los suma en `#tiempo_estudio`.

**No es** la biblioteca (esa es `biblioteca/`, con su `metadata.db`), ni el lugar donde nacen las
fichas de catalogación (las escribe `scripts_for_fuentes/ingesta` en
`script_catalogacion_biblioteca/fichas/`, que es el registro de esa suite), ni una biblioteca de
código: `lib_comun/` son envoltorios de `core/shell-lib` y `core/py-common`. Depende de `core/`
(raíz, logger, candado, respaldo, resolutor de la biblioteca), de `biblioteca/`, de
`~/Zotero/zotero.sqlite` y del repo de datos `~/.local/share/koreader-respaldo/`. La autoridad de
cada dato y la dirección de cada sincronización están en `meta/MODELO_METADATOS.md` y
`meta/SINCRONIZACION.md`.

## Uso

```bash
script_koreader_estudio/main.sh                          # simula KOReader → Calibre
script_koreader_estudio/main.sh --aplicar                # escribe (Calibre cerrado)
script_ecosistema_lectura/main.sh --aplicar              # Zotero → Calibre (Calibre cerrado)
script_ecosistema_lectura/main.sh --metadatos            # orquesta sincronizar_zotero (simula)
script_ecosistema_lectura/main.sh --enlazar --ris        # libros sin #zotero_key y .ris para Zotero
script_sincronizar_zotero/main.sh --limite 20 --aplicar  # canario de la sync; ambas apps cerradas
script_verificar_metadatos/main.sh --limite 5            # solo lectura: discrepancias en reportes/
script_catalogacion_biblioteca/main.sh --ids 10265,10266 # simula esas filas; --aplicar escribe
script_metadatos_calibre/main.sh embed --root "$BIBLIOTECA_DIR" --dry-run   # sin --dry-run, ESCRIBE
script_koreader_estudio/main.sh --instalar-timer         # timers (y script_ecosistema_lectura)
systemctl --user list-timers | grep -E "koreader|ecosistema"   # ¿cuándo corren?
```

Las suites simulan por defecto y escriben con `--aplicar`, salvo tres casos:
`script_metadatos_calibre` (`embed` y `register` escriben salvo `--dry-run`), `--apuntes` de
`script_koreader_estudio` (escribe al invocarse) y las campañas de `script_normalizacion_metadatos`
(cada `main.sh` dice su uso en la cabecera). Requisitos: Calibre con `calibredb` y `calibre-debug`
en el `PATH`, `python3` (biblioteca estándar), `sqlite3`, y `exiftool` para
`script_metadatos_calibre`; nada pide `sudo`. Qué es automático, qué es manual y cómo saber si
funciona: `docs/operacion.md`.

## Estructura

| carpeta | qué es | dueño / generador |
|---|---|---|
| `script_koreader_estudio/` | KOReader → Calibre: columnas `#ko_*`, `#barra`, `#estado_estudio`, `#apuntes`; sidecars por hash; respaldo continuo al repo de datos | a mano; timer `koreader-calibre-sync` |
| `script_ecosistema_lectura/` | Zotero (Ethereal Style) → Calibre: `#zot_*`, `#tiempo_estudio`; orquesta `sincronizar_zotero`; enlaza libros con Zotero | a mano; timers `ecosistema-lectura`, `ecosistema-metadatos` |
| `script_sincronizar_zotero/` | metadatos y etiquetas Calibre ⇄ Zotero para los libros con `#zotero_key`; política «Calibre manda» | a mano |
| `script_verificar_metadatos/` | coteja Calibre con OpenLibrary y Crossref; solo lectura | a mano |
| `script_metadatos_calibre/` | incrustador OPF → PDF (InfoDict y XMP-dc), registro de PDF sueltos, limpieza de `zotero_metadata.json` huérfanos | a mano |
| `script_catalogacion_biblioteca/` | aplica `resumen_catalogacion.tsv` a Calibre; `fichas/` y el TSV son su registro | a mano; el registro lo escriben `scripts_for_fuentes/ingesta` e `ingesta_cursos` |
| `script_normalizacion_metadatos/` | las campañas de una sola vez sobre la biblioteca, con su registro y su deshacer; archivado | una carpeta por campaña |
| `lib_comun/` | envoltorios de 2–4 líneas hacia `core/shell-lib/` y `core/py-common/`; los usa `scripts_for_fuentes` (`docs/consumidores.md`) | derivado de `core/`; el código nuevo carga `core/` directamente |
| `docs/` | operación, decisiones e historial | a mano; índice por `core/docs.py indice` |
| `suite.yml` (uno por suite) | manifiesto de cada herramienta (`core/suite.schema.yml`) | a mano; los bloques de README los genera `core/suites.py generar --aplicar` |
| `.lock_calibre_write` | candado `flock` de los escritores de `metadata.db` (`LOCK_CALIBRE` en `core/env.sh`) | runtime, ignorado |
| `*/reportes/`, `*/backups/`, `*/estado/` | informes de cada pasada, respaldos rotados, marcas de la última pasada | runtime, ignorados |

## Documentación

| documento | para qué leerlo |
|---|---|
| [`docs/operacion.md`](docs/operacion.md) | lo automático (timers), lo manual, chuleta de comandos, verificación y qué no tocar |
| [`docs/consumidores.md`](docs/consumidores.md) | lo que otros repos usan de aquí (`lib_comun/`, fichas y TSV, candado) y lo que no se cambia sin avisarles |
| [`docs/decisiones.md`](docs/decisiones.md) | por qué es así (autoridad, escritura segura, campañas) y qué está pendiente |
| [`docs/README.md`](docs/README.md) | el mapa por lector y el índice de `docs/`, con el historial |
| [`script_koreader_estudio/README.md`](script_koreader_estudio/README.md) | columnas `#ko_*`, sidecars por hash, respaldo continuo, restaurar en otra máquina |
| [`script_ecosistema_lectura/README.md`](script_ecosistema_lectura/README.md) | Read Time de Zotero, columnas `#zot_*`, orquestación y enlazado con Zotero |
| [`script_sincronizar_zotero/README.md`](script_sincronizar_zotero/README.md) | política de sincronización campo a campo y escritura segura |
| [`script_verificar_metadatos/README.md`](script_verificar_metadatos/README.md) | alcance y criterios de comparación |
| [`script_metadatos_calibre/README.md`](script_metadatos_calibre/README.md) | operaciones `embed`, `register`, `all`, `limpiar-json` |
| [`script_catalogacion_biblioteca/README.md`](script_catalogacion_biblioteca/README.md) | el registro de fichas y el circuito ficha → TSV → Calibre |
| [`script_normalizacion_metadatos/README.md`](script_normalizacion_metadatos/README.md) | el patrón de una campaña y cómo se deshace |
| [`CLAUDE.md`](CLAUDE.md) | reglas para el asistente: autoridad de campo, candado, timers, qué no se toca |
| `meta/MODELO_METADATOS.md`, `meta/SINCRONIZACION.md` | autoridad por dato y arquitectura de sincronización (frontera con `meta`) |
| `meta/INDICE_SCRIPTS.md` | estas suites entre las del workspace (generado) |

## Límite honesto

- **No hay pruebas automáticas**: la comprobación es la simulación de cada `main.sh`, `bash -n`,
  `py_compile`, el informe de `reportes/` y mirar Calibre.
- **Escribir exige Calibre cerrado** (y Zotero cerrado para `sincronizar_zotero` y las campañas);
  los timers no fallan por eso, reintentan en la siguiente pasada.
- **No todos los escritores toman el candado**: `script_catalogacion_biblioteca` y
  `script_metadatos_calibre register` no lo hacen (`docs/decisiones.md`, Pendientes).
- **Zotero se escribe por SQL directo** (como hace el plugin ZMI): método no soportado por Zotero;
  cada ítem tocado queda `synced=0` para que la cuenta lo suba. Sin respaldo previo no se aplica.
- **Título y autor no se escriben en Calibre** por sincronización ni verificación: Zotero enlaza los
  adjuntos por la ruta `Autor/Título (id)`. Los escriben la catalogación, antes de que el libro
  tenga ítem en Zotero, y las campañas que reescriben Zotero en la misma operación.
- **`verificar_metadatos` solo cubre lo que tiene identificador**: el material de aula no existe en
  ninguna base.
- **Los `reportes/` no rotan solos**: la poda (30 días) la aplica una fase de higiene, no las
  suites.
- **Sin `LICENSE`**: el repo es público y la licencia está pendiente del autor
  (`docs/decisiones.md`, Pendientes P7).
