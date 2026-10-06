---
tipo: readme
estado: activo
---
# scripts_for_calibre/ — las herramientas que mantienen coherentes Calibre, KOReader y Zotero

<!-- suites:inicio -->
Suites de esta carpeta (6); índice global en `meta/INDICE_SCRIPTS.md`. Patrón: M main · C config · L lib.

| Suite | Carpeta | Objetivo | Escribe en | Simula | Timer | Estado | Patrón |
|---|---|---|---|---|---|---|---|
| `catalogacion_biblioteca` | [scripts_for_calibre/catalogacion](catalogacion/) | fuentes | calibre, archivos | sí |  | activo | `MCL` |
| `ecosistema_lectura` | [scripts_for_calibre/lectura](lectura/) | biblioteca | calibre | sí | ecosistema-lectura.timer · ecosistema-metadatos.timer | activo | `MCL` |
| `koreader_estudio` | [scripts_for_calibre/koreader](koreader/) | biblioteca | calibre | sí | koreader-calibre-sync.timer | activo | `MCL` |
| `metadatos_calibre` | [scripts_for_calibre/metadatos-pdf](metadatos-pdf/) | biblioteca | calibre, archivos | sí |  | activo | `MCL` |
| `sincronizar_zotero` | [scripts_for_calibre/sincronizar-zotero](sincronizar-zotero/) | biblioteca | calibre, zotero | sí |  | activo | `MCL` |
| `verificar_metadatos` | [scripts_for_calibre/verificacion](verificacion/) | biblioteca | ninguno | sí |  | activo | `MCL` |

<sub>Bloque generado desde los `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suites:fin -->

Herramientas de línea de comandos (Bash y Python) alrededor de la biblioteca Calibre (`biblioteca/`,
la autoridad bibliográfica del workspace): catalogación desde fichas, verificación de metadatos,
incrustación en los PDF y la plomería que une Calibre con KOReader (lectura) y con Zotero
(referencias). Tres timers systemd de usuario la mueven solos: KOReader → Calibre y Zotero → Calibre
cada 30 minutos, y la sincronización bidireccional de metadatos a diario a las 04:30. La regla de
todo el repo: **Calibre manda** en los metadatos bibliográficos, Zotero solo rellena vacíos, y los
relojes de lectura de KOReader y de Zotero **nunca se copian entre sí**: Calibre los suma en
`#tiempo_estudio`. Y una sola **puerta de escritura** (`lib/escribir.*`): nada escribe en
`metadata.db` ni en `zotero.sqlite` sin la app cerrada, el candado y un respaldo verificado.

**No es** la biblioteca (esa es `biblioteca/`, con su `metadata.db`), ni el lugar donde nacen las
fichas de catalogación (las escribe `scripts_for_fuentes/ingesta` en
`catalogacion/fichas/`, que es el registro de esa suite). Depende de `core/` (raíz,
logger, candado, respaldo verificado, resolutor de la biblioteca), de `biblioteca/`, de
`zotero.sqlite` y del repo de datos de KOReader (`KOREADER_RESPALDO_DIR`). La autoridad de cada dato
y la dirección de cada sincronización están en `meta/docs/historial/MODELO_METADATOS.md` y
`meta/docs/historial/SINCRONIZACION.md`. Dónde está el repo hoy: [`estado.md`](estado.md).

## Uso

```bash
koreader/main.sh                          # simula KOReader → Calibre
koreader/main.sh --aplicar                # escribe por la puerta (Calibre cerrado)
lectura/main.sh --aplicar              # Zotero → Calibre (Calibre cerrado)
lectura/main.sh --metadatos            # orquesta sincronizar_zotero (simula)
lectura/main.sh --enlazar --ris        # libros sin #zotero_key y .ris para Zotero
sincronizar-zotero/main.sh --limite 20 --aplicar  # canario de la sync; ambas apps cerradas
verificacion/main.sh --limite 5            # solo lectura: discrepancias en reportes/
catalogacion/main.sh --ids 10265,10266 # simula esas filas; --aplicar escribe
metadatos-pdf/main.sh embed --root "$BIBLIOTECA_DIR"   # simula; --aplicar modifica los PDF
lib/adjuntos_zotero.py verificar                         # adjuntos de Zotero que no resuelven
systemd/instalar.sh                                      # timers: simula; --aplicar instala; --verificar
python3 -m pytest scripts_for_calibre/tests              # desde ~/Documents: pruebas sobre copias
```

Todas las suites simulan por defecto y escriben con `--aplicar`; `--apuntes` de
`koreader` es una orden explícita que escribe por la puerta. Requisitos: Calibre con
`calibredb` y `calibre-debug` en el `PATH`, el Python de `core` (`CORE_PYTHON`, biblioteca estándar)
y `exiftool` para `metadatos-pdf`; ni `sqlite3` ni `sudo`. Qué es automático, qué es
manual y cómo saber si funciona: `docs/operacion.md`.

## Estructura

| carpeta | qué es | dueño / generador |
|---|---|---|
| `koreader/` | KOReader → Calibre: columnas `#ko_*`, `#barra`, `#estado_estudio`, `#apuntes`; sidecars por hash; respaldo continuo al repo de datos | a mano; timer `koreader-calibre-sync` |
| `lectura/` | Zotero (Ethereal Style) → Calibre: `#zot_*`, `#tiempo_estudio`; orquesta `sincronizar_zotero`; enlaza libros con Zotero | a mano; timers `ecosistema-lectura`, `ecosistema-metadatos` |
| `sincronizar-zotero/` | metadatos y etiquetas Calibre ⇄ Zotero para los libros con `#zotero_key`; política «Calibre manda» | a mano |
| `verificacion/` | coteja Calibre con OpenLibrary y Crossref; solo lectura | a mano |
| `metadatos-pdf/` | incrustador OPF → PDF (InfoDict y XMP-dc), registro de PDF sueltos, limpieza de `zotero_metadata.json` huérfanos | a mano |
| `catalogacion/` | aplica `resumen_catalogacion.tsv` a Calibre; `fichas/` y el TSV son su registro | a mano; el registro lo escribe `scripts_for_fuentes/ingesta` |
| `lib/` | la puerta de escritura (`escribir.sh`, `escribir.py`, `escribir_zotero.py`), las lecturas sin `sqlite3` (`leer.sh`) y el escritor de rutas de adjuntos de Zotero (`adjuntos_zotero.py`) | a mano |
| `systemd/` | las plantillas de los tres timers y su instalador (`instalar.sh`) | a mano; las unidades instaladas son su render |
| `tests/` | caracterización de los sincronizadores contra la referencia de git, la puerta y el entorno, sobre copias | a mano |
| `lib_comun/` | envoltorios hacia `core/shell-lib/` y `core/py-common/`; solo para `scripts_for_fuentes` (`docs/consumidores.md`) | derivado de `core/`; se retira con C4 |
| `docs/` | operación, consumidores, decisiones e historial | a mano; índice por `core/docs.py indice` |
| `suite.yml` (uno por suite) | manifiesto de cada herramienta (`core/suite.schema.yml`) | a mano; los bloques de README los genera `core/suites.py generar --aplicar` |
| `*/reportes/` | informes de cada pasada | runtime, ignorados |

Los respaldos y el estado de las suites viven fuera del repo, en `$XDG_STATE_HOME/biblioteca/`
(`docs/decisiones.md` §2.6 y §4.10). Las campañas de normalización de 2026-09 y 2026-10 están en la
historia de git (`docs/decisiones.md` §4.8).

## Documentación

El mapa por lector y el índice de `docs/` están en [`docs/README.md`](docs/README.md); cada suite
documenta su uso en su `README.md`; las reglas para el asistente, en [`CLAUDE.md`](CLAUDE.md).

## Límite honesto

- **Escribir exige Calibre cerrado** (y Zotero cerrado para `sincronizar_zotero` y
  `lib/adjuntos_zotero.py`); los timers no fallan por eso, reintentan en la siguiente pasada.
- **Zotero se escribe por SQL directo** (como hace el plugin ZMI): método no soportado por Zotero;
  cada ítem tocado queda `synced=0` para que la cuenta lo suba. Sin respaldo verificado no se aplica.
- **Título y autor no se escriben en Calibre** por sincronización ni verificación: Zotero enlaza los
  adjuntos por la ruta `Autor/Título (id)`. Los escriben la catalogación, antes de que el libro
  tenga ítem en Zotero, y las campañas que reescriben Zotero en la misma operación.
- **Las pruebas comparan con una referencia de git** sobre una foto del día: un camino que la foto
  no ejercita lo cubren las copias perturbadas, no todos los casos posibles.
- **`verificar_metadatos` solo cubre lo que tiene identificador**: el material de aula no existe en
  ninguna base.
- **Los `reportes/` no rotan solos**: la poda (30 días) la aplica una fase de higiene.
- **Licencia MIT** (`LICENSE`), como el resto del código del ecosistema.
