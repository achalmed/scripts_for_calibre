---
tipo: readme
estado: activo
---
# lectura/ — Zotero (Read Time) → Calibre y orquestación del sync de metadatos

<!-- suite:inicio -->
**Suite `ecosistema_lectura`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Lleva el tiempo de lectura de Zotero (readingTime) y los metadatos de estudio a las columnas de Calibre.

- Escribe en: calibre · simula por defecto: sí
- Depende de: calibredb, zotero.sqlite, core/shell-lib, lib/escribir.sh (la puerta)
- Timer: `ecosistema-lectura.timer · ecosistema-metadatos.timer`

Comandos:

```bash
main.sh                      # simula
main.sh --aplicar
main.sh --metadatos --desde-timer
main.sh --enlazar --ris          # informe y .ris de lo que falta en Zotero
main.sh --enlazar --aplicar      # escribe las claves «adjunto»
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suite:fin -->

**Zotero → Calibre** (diseño de 2026-08: `../docs/historial/diseno-ecosistema-lectura-2026-08.md`;
operación: `../docs/operacion.md`): lleva a Calibre el tiempo de lectura que registra **Ethereal
Style** en Zotero, y lo agrega al de KOReader sin posibilidad de doble conteo.

```
Zotero (zotero.sqlite, solo lectura)          KOReader (koreader)
  notas readingTime del "Addon Item"                    │
            │  ITEMKEY == #zotero_key                   │
            ▼                                           ▼
      #zot_tiempo · #zot_ultima              #ko_tiempo · #barra · #estado…
            └────────────────┬──────────────────────────┘
                             ▼
              #tiempo_estudio (composite: suma)
```

## Columnas

| Columna | Tipo | Contenido |
|---|---|---|
| `#zot_tiempo` | int | minutos leídos según Zotero (Σ segundos por página, techo al minuto) |
| `#zot_ultima` | fecha | última modificación del registro de lectura en Zotero |
| `#zot_progreso` | float 0–1 | `(lastPageIndex+1) / páginas` del lector de Zotero; solo cuando ambos datos existen — no se inventa |
| `#tiempo_estudio` | composite | `#ko_tiempo + #zot_tiempo` — **cada app es dueña de su reloj; Calibre solo agrega**, por eso nunca hay doble conteo |

Además, `#barra` y `#estado_estudio` (de `koreader`) muestran **max(progreso
KOReader, progreso Zotero)** y consideran el tiempo Zotero para el estado — regla de conflicto del
diseño (`../docs/historial/diseno-ecosistema-lectura-2026-08.md` §5).

## Uso

```bash
./main.sh                # SIMULACIÓN (no escribe)
./main.sh --aplicar      # por la puerta: respaldo verificado, columnas y escritura real
./main.sh --metadatos            # metadatos: orquesta sincronizar_zotero (simulación)
./main.sh --metadatos --aplicar  #   …con escritura (Calibre Y Zotero cerrados)
./main.sh --enlazar              # enlazador: reporte de libros sin #zotero_key y de claves anómalas
./main.sh --enlazar --ris        #   …y el .ris de los que no tienen ítem en Zotero
./main.sh --enlazar --aplicar    #   …y escribe #zotero_key de los «adjunto» (Calibre cerrado)
./main.sh --instalar-timer       # timers: lectura 30 min + metadatos 04:30 (../systemd/instalar.sh)
./main.sh --desinstalar-timer
```

**Metadatos y etiquetas (`--metadatos`):** corre `sincronizar-zotero` solo si Calibre y Zotero están
cerrados **y** alguna base cambió desde la última pasada aplicada (marca en
`$XDG_STATE_HOME/biblioteca/ecosistema_lectura/`). El timer diario de las 04:30 la ejecuta con
`--aplicar`; la herramienta orquestada abre su propia puerta (respaldos de ambas bases) y deja sus
reportes.

**Enlazador (`--enlazar`):** genera `reportes/enlazar_*.tsv` con el candidato Zotero de cada libro sin
`#zotero_key`, del más firme al más débil:

- **`adjunto`**: el ítem que enlaza un archivo de la carpeta «… (id)/» del libro. Es determinista y
  es el único que `--aplicar` escribe (por la puerta: candado, respaldo y `calibredb set_custom`). Si una
  importación se repitió, cuenta el ítem de la colección viva y no el que solo está en una colección
  mandada a la papelera.
- **ISBN exacto** o **título único**: se confirman a mano, pegando la clave en la columna ZKey.
- **`ya_de_otro_libro`**: el único candidato enlaza el archivo de otro libro (otra edición o un
  duplicado de Calibre), así que este libro necesita su propio ítem.

También reporta las claves que no existen en Zotero y las que no coinciden con el ítem que enlaza el
PDF. Con `--ris` escribe `reportes/enlazar_*.ris` con los libros sin ítem propio, construido desde
Calibre tal como está hoy (`core/py-common/biblioteca.py: ris()`, autores ya en «Apellidos,
Nombre»).

El ciclo para llevar a Zotero lo que falta:

1. `--enlazar --ris`.
2. En Zotero: Archivo → Importar → el `.ris` → «Enlazar a los archivos en su ubicación original».
3. `--enlazar --aplicar`: el puente se cierra por el adjunto, sin adivinar.
4. `--metadatos --aplicar`: completa los campos («Calibre manda»).

- **Calibre cerrado** para escribir; **Zotero puede estar abierto** (su base solo se lee en modo
  ro).
- Candado **compartido** con `koreader` (`LOCK_CALIBRE` de `core/env.sh`): las dos
  herramientas nunca escriben a la vez.
- Simulación por defecto, respaldos verificados y rotados (5) en
  `$XDG_STATE_HOME/biblioteca/respaldos/ecosistema_lectura/`, reporte TSV por pasada.

## Fuente de datos (verificada por inspección; releer el diseño en ../docs/historial/)

Nota hija del ítem "Addon Item" en `~/Zotero/zotero.sqlite` → `itemNotes`:

```html
<div class="zotero-note znv1">ITEMKEY
{"readingTime":{"page":N,"data":{"<página>":segundos}}}</div>
```

`ITEMKEY` == `#zotero_key` de Calibre (puente ya mantenido por `sincronizar-zotero`). Si hay
más de una nota por ítem, gana la de `dateModified` más reciente.

## Estructura

`main.sh` (orquestación y CLI; escribe por `../lib/escribir.sh`) · `config.sh` (rutas de
`core/env.sh`, columnas) · `lib/`: `checks.sh` (entorno), `setup_columnas.sh` (columnas y plantillas,
idempotente), `sync_zotero_lectura.py` (núcleo: zotero.sqlite en solo lectura → columnas por la API,
vía calibre-debug), `orquestar_metadatos.sh` (`--metadatos`), `enlazar_reporte.py` (`--enlazar`) ·
las plantillas de las dos unidades están en `../systemd/` · `reportes/` es runtime ignorado.

## Límite honesto

- **No exporta sesiones de KOReader al registro de Ethereal Style**: es opcional y de riesgo, y no
  está planificado (`../estado.md` §Futuro).
- **`#zot_progreso` solo se calcula cuando existen la página del lector y el total de páginas**; los
  localizadores no numéricos (EPUB) se omiten: no se inventa el dato.
- **Zotero solo se lee**, nunca se escribe desde aquí; escribir en `zotero.sqlite` es de
  `../sincronizar-zotero/`, y solo con ambas apps cerradas.
- **`--metadatos` corre solo si alguna base cambió** desde la última pasada aplicada (marca en el
  estado de usuario); `--enlazar` sin `--aplicar` no escribe; con `--aplicar` escribe solo los enlaces
  «adjunto», y los de ISBN o título se pegan a mano en la columna ZKey.
- **Calibre cerrado para escribir**; el timer que se salta reintenta a los 30 minutos y no avisa a
  nadie: la verificación es `journalctl --user -u ecosistema-lectura`.
