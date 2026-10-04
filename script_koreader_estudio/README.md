---
tipo: readme
estado: activo
---
# script_koreader_estudio/ — KOReader → Calibre: progreso, tiempo, estado y apuntes de cada libro

<!-- suite:inicio -->
**Suite `koreader_estudio`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Convierte Calibre en tablero de estudio: progreso, tiempo y anotaciones de KOReader hacia las columnas del libro.

- Escribe en: calibre · simula por defecto: sí
- Entrada: statistics.sqlite3 de KOReader
- Depende de: calibredb, koreader, core/shell-lib
- Timer: `koreader-calibre-sync.timer`

Comandos:

```bash
main.sh                      # simula
main.sh --aplicar
main.sh --desde-timer
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-20); no se edita a mano.</sub>
<!-- suite:fin -->

Convierte Calibre en un **tablero de seguimiento de estudio**: KOReader (en este mismo Linux) es el
lector; este script vuelca automáticamente su progreso, estado y estadísticas en columnas de
Calibre, y añade un enlace clicable a los apuntes `.md` de cada libro.

> **Sin duplicar nada:** KOReader abre los mismos archivos de la biblioteca
> Calibre (`BIBLIOTECA_DIR`); el script reutiliza las columnas que ya
> creó el plugin *KOReader Sync* (que en escritorio no puede sincronizar, al no
> haber "dispositivo") y respeta su convención de escalas.

## Cómo funciona

KOReader ya escribe dos fuentes de datos; el script solo las une con Calibre:

```
Sidecars <libro>.sdr/metadata.<ext>.lua     statistics.sqlite3 (plugin Estadísticas)
  · percent_finished (fracción 0–1)           · tiempo total de lectura
  · summary.status (reading/complete/…)       · primera/última sesión (page_stat_data)
            │                                           │  emparejado por MD5 parcial
            └────────────────┬──────────────────────────┘  (algoritmo de KOReader,
                             ▼                              verificado contra esta BD)
                   lib/sync_koreader.py  (calibre-debug, escritura en lote)
                             ▼
                     Columnas de Calibre
```

## Columnas

| Columna | Tipo | Contenido | Origen |
|---|---|---|---|
| `#ko_progfloat` | float | fracción leída 0–1 (convención del plugin) | sidecar |
| `#ko_progint` | int | porcentaje 0–100 | sidecar |
| `#ko_status` | text | `reading` / `complete` / `abandoned` | sidecar (o `#leído` manual) |
| `#ko_tiempo` | int | minutos totales de lectura | statistics.sqlite3 |
| `#ko_start` / `#ko_finish` | fecha | primera lectura / fecha de término | statistics / sidecar |
| `#ko_lastmod` | fecha | última actividad de lectura | statistics / sidecar |
| `#ko_lastsync` | fecha | última pasada de este script | script |
| `#ko_md5` | text | MD5 parcial (caché del emparejamiento) | script |
| `#estado_estudio` | composite | ⬜ Pendiente · 📖 En proceso · ✅ Finalizado · ⏸ Abandonado | calculada |
| `#barra` | composite | `▰▰▰▰▰▰▰▱▱▱ 70%` | calculada |
| `#apuntes` | comments | enlace clicable `file://` al `.md` de apuntes | `--apuntes` |
| `#leído` / `#read_date` | bool/fecha | ya existían; se marcan al llegar a `complete` | integración |

Las composite se calculan solas: no hay información duplicada almacenada.

## Uso

```bash
./main.sh                  # SIMULACIÓN: muestra qué haría (no escribe)
./main.sh --aplicar        # columnas faltantes + backup metadata.db + sync real
./main.sh --migrar-sdr     # simula la migración de .sdr → hash central
./main.sh --migrar-sdr --aplicar   # migra de verdad (KOReader cerrado)

./main.sh --apuntes ID "/ruta/apuntes.md" "Clase 01"   # escribe YA, sin --aplicar

./main.sh --instalar-timer         # systemd de usuario, cada 30 min (../docs/operacion.md §1.1)
./main.sh --desinstalar-timer
```

Además existe la columna manual **`#estudio`** («Estudio (manual)»: ⬜/📖/🔁/✅) para el *estado de
estudio*, separado del estado de *lectura* automático (`#estado_estudio`): un libro puede estar
100 % leído y aún «📖 En proceso» de estudio. El sync jamás toca `#estudio`.

Requisitos: Calibre (`calibredb`, `calibre-debug`), `sqlite3`, `python3`, KOReader con el plugin de
**Estadísticas de lectura** activo.

**Marca el final en KOReader**: menú ⌄ → estado del libro → *Terminado* (`complete`). Eso pone ✅
Finalizado, marca `#leído` y fija `#read_date` y `#ko_finish`. Antes de aplicar, `--aplicar` respalda
`metadata.db` en `backups/` (rotado) y toma el candado `.lock_calibre_write`: nunca corren dos
escritores a la vez. Lo que hay que saber de Calibre abierto, del volcado al cerrar el libro y de
`#leído` manual está en «Límite honesto».

## Sidecars centralizados por hash

Los `.sdr` ya **no** viven junto a los libros: se migraron con `--migrar-sdr` a
`~/.config/koreader/hashdocsettings/<md5[0:2]>/<md5>.sdr/` (layout de `docsettings.lua` de KOReader)
y KOReader quedó configurado con `document_metadata_folder = "hash"`. Ventajas:

- **Renombrar/editar metadatos en Calibre ya no rompe nada**: el sidecar se encuentra por hash del
  contenido, no por ruta (KOReader incluso omite la relocalización de sidecars en modo hash —
  `docsettings.lua:443`).
- **Todo lo valioso queda en un solo árbol** (`~/.config/koreader/`), fácil de respaldar y de llevar
  a otra laptop.
- Los `.sdr` huérfanos de renombrados antiguos se dejaron en su sitio y se listan al migrar;
  KOReader sigue leyendo sidecars legacy como fallback.

## Respaldo continuo (no volver a perder lecturas)

Cada sincronización (y el timer cada 30 min) espeja **en texto** las estadísticas (dump SQL), los
sidecars hash y el historial a un repo git propio de datos de lectura (`KOREADER_RESPALDO_DIR` en
`core/env.sh`), con commit local automático (publicar = `git push` desde ese repo, remoto privado):

```
~/.local/share/koreader-respaldo/  ← repo git propio (datos, no configuración)
├── statistics.sql     (dump SQL de statistics.sqlite3, restaurable)
├── hashdocsettings/   (todos los sidecars .lua de texto)
└── history.lua
```

Los datos **vivos** siguen en `~/.config/koreader/`; esto es un respaldo versionado, no la copia de
trabajo. **`settings.reader.lua` se EXCLUYE a propósito**: contiene el bloque `kosync` con
credenciales.

**Restaurar en una laptop nueva:** instalar KOReader y reconstruir desde el repo — `sqlite3
~/.config/koreader/settings/statistics.sqlite3 < statistics.sql` y copiar `hashdocsettings/` +
`history.lua` a `~/.config/koreader/`. Las estadísticas y sidecars emparejan por hash del contenido,
así que funcionan aunque la biblioteca cambie de ruta.

## Trampas conocidas

- `calibredb set_custom` (no `set_custom_column`) escribe columnas en Calibre 9.
- En plantillas composite: `field()` devuelve el valor **formateado** (`'4.35%'`) — usa
  `raw_field()` para aritmética; `substr(s, 0, 0)` devuelve la cadena **entera**, no vacía (por eso
  la barra trata n=0 y n=10 aparte).
- `#ko_progfloat` guarda **fracción 0–1** (no 0–100): es la convención que dejó el plugin KOReader
  Sync y se respeta por compatibilidad.

## Estructura

| ruta | qué es | dueño |
|---|---|---|
| `main.sh` | orquestación y CLI, sin lógica | a mano |
| `config.sh` | rutas y nombres de columnas: todo lo editable | a mano |
| `lib/checks.sh` · `lib/setup_columnas.sh` | entorno y apps cerradas; columnas y plantillas, idempotente | a mano |
| `lib/sync_koreader.py` | núcleo (vía `calibre-debug`): sidecars y estadísticas → columnas | a mano |
| `lib/migrar_sdr.py` | migración de `.sdr` a `hashdocsettings`, de una vez | a mano |
| `lib/respaldo_koreader.sh` | espejo continuo en texto al repo `KOREADER_RESPALDO_DIR` | a mano |
| `lib/systemd/` | plantillas del `.service` y el `.timer` de usuario | a mano; las instala `--instalar-timer` |
| `reportes/` · `backups/` | TSV de cada pasada; `metadata.db` rotados y tars previos a la migración | runtime, ignorado |

## Límite honesto

- **Calibre cerrado para escribir**: el timer que lo encuentra abierto se salta la pasada y
  reintenta a los 30 minutos; solo una ejecución manual avisa.
- **No es instantáneo**: KOReader vuelca sidecar y estadísticas al cerrar el libro (y en pausas); el
  progreso de la sesión en curso aparece en la pasada siguiente.
- **Solo escribe valores que cambiaron** y jamás toca `#estudio`, etiquetas ni series; `#leído`
  marcado a mano promueve a Finalizado, nunca degrada.
- **El respaldo excluye `settings.reader.lua` a propósito** (credenciales `kosync`): restaurar en
  otra máquina exige reconfigurar la cuenta.
- **`--migrar-sdr` fue una migración de una vez**; vuelve a tener sentido solo si
  aparecen `.sdr` nuevos junto a los libros.
- **Mover la suite de carpeta rompe el timer**: la unidad instalada lleva la ruta absoluta de
  `main.sh`; se reinstala con `--instalar-timer`.
