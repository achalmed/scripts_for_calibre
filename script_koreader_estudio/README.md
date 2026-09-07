# script_koreader_estudio — KOReader → Calibre como gestor de estudio

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

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-07); no se edita a mano.</sub>
<!-- suite:fin -->

#readme

Convierte Calibre en un **tablero de seguimiento de estudio**: KOReader (en este
mismo Linux) es el lector; este script vuelca automáticamente su progreso,
estado y estadísticas en columnas de Calibre, y añade un enlace clicable a los
apuntes `.md` de cada libro.

> **Sin duplicar nada:** KOReader abre los mismos archivos de la biblioteca
> Calibre (`~/Documents/biblioteca`); el script reutiliza las columnas que ya
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

# Enlazar apuntes de un libro (clic en Detalles del libro → panel derecho):
./main.sh --apuntes 3694 "/ruta/a/clase 01 introduccion conceptos basicos.md" "Clase 01"

# Automatización (systemd de usuario, cada 30 min):
./main.sh --instalar-timer
./main.sh --desinstalar-timer
```

Además existe la columna manual **`#estudio`** («Estudio (manual)»: ⬜/📖/🔁/✅)
para el *estado de estudio*, separado del estado de *lectura* automático
(`#estado_estudio`): un libro puede estar 100 % leído y aún «📖 En proceso» de
estudio. El sync jamás toca `#estudio`.

Requisitos: Calibre (`calibredb`, `calibre-debug`), `sqlite3`, `python3`, KOReader
con el plugin de **Estadísticas de lectura** activo.

## Reglas de operación (importantes)

- **Calibre debe estar cerrado** para escribir (la base se bloquea). El timer
  lo detecta y simplemente reintenta a los 30 min; una ejecución manual avisa.
- **KOReader vuelca sidecar y estadísticas al cerrar el libro** (y en pausas):
  el progreso de la sesión en curso aparece en la siguiente pasada.
- **Marca el final en KOReader**: menú ⌄ → estado del libro → *Terminado*
  (`complete`). Eso pone ✅ Finalizado, marca `#leído` y fija `#read_date` y
  `#ko_finish`. Un `#leído` marcado a mano (sin KOReader) también cuenta como
  Finalizado en la siguiente sincronización.
- Solo se escriben valores **que cambiaron** (idempotente); siempre hay backup
  rotado de `metadata.db` en `backups/` antes de aplicar.
- Lock `flock`: nunca corren dos sincronizaciones a la vez.

## Sidecars centralizados por hash (migrado el 2026-08-09)

Los `.sdr` ya **no** viven junto a los libros: se migraron con `--migrar-sdr` a
`~/.config/koreader/hashdocsettings/<md5[0:2]>/<md5>.sdr/` (layout de
`docsettings.lua` de KOReader) y KOReader quedó configurado con
`document_metadata_folder = "hash"`. Ventajas:

- **Renombrar/editar metadatos en Calibre ya no rompe nada**: el sidecar se
  encuentra por hash del contenido, no por ruta (KOReader incluso omite la
  relocalización de sidecars en modo hash — `docsettings.lua:443`).
- **Todo lo valioso queda en un solo árbol** (`~/.config/koreader/`), fácil de
  respaldar y de llevar a otra laptop.
- Los `.sdr` huérfanos de renombrados antiguos (7) se dejaron en su sitio y se
  listan al migrar; KOReader sigue leyendo sidecars legacy como fallback.

## Respaldo continuo (no volver a perder lecturas)

Cada sincronización (y el timer cada 30 min) espeja **en texto** las
estadísticas (dump SQL), los sidecars hash y el historial al repo de dotfiles,
con commit local automático (publicar = `dotfiles sync-push`):

```
~/.dotfiles/koreader-data/         ← versionado en git (dotfiles)
├── statistics.sql     (dump SQL de statistics.sqlite3, restaurable)
├── hashdocsettings/   (todos los sidecars .lua de texto)
└── history.lua
```

Los datos **vivos** siguen en `~/.config/koreader/` (principio de mínima
captura de los dotfiles); esto es un respaldo versionado, no la copia de
trabajo. **`settings.reader.lua` se EXCLUYE a propósito**: contiene el bloque
`kosync` con credenciales y el escáner de sensibles de los dotfiles lo vetaría.

**Restaurar en una laptop nueva:** instalar KOReader y reconstruir desde el
repo — `sqlite3 ~/.config/koreader/settings/statistics.sqlite3 < statistics.sql`
y copiar `hashdocsettings/` + `history.lua` a `~/.config/koreader/`. Las
estadísticas y sidecars emparejan por hash del contenido, así que funcionan
aunque la biblioteca cambie de ruta.

## Trampas conocidas (documentadas con sangre)

- `calibredb set_custom` (no `set_custom_column`) escribe columnas en Calibre 9.
- En plantillas composite: `field()` devuelve el valor **formateado**
  (`'4.35%'`) — usa `raw_field()` para aritmética; `substr(s, 0, 0)` devuelve la
  cadena **entera**, no vacía (por eso la barra trata n=0 y n=10 aparte).
- `#ko_progfloat` guarda **fracción 0–1** (no 0–100): es la convención que dejó
  el plugin KOReader Sync y se respeta por compatibilidad.

## Estructura

```
script_koreader_estudio/
├── main.sh              # orquestación y CLI (sin lógica)
├── config.sh            # rutas y nombres de columnas (todo lo editable)
├── lib/
│   ├── checks.sh        # validación de entorno / Calibre y KOReader cerrados
│   ├── setup_columnas.sh# creación idempotente de columnas y plantillas
│   ├── sync_koreader.py # núcleo (calibre-debug): sidecars + stats → columnas
│   ├── migrar_sdr.py    # migración .sdr → hashdocsettings (una vez)
│   ├── respaldo_koreader.sh # espejo continuo (texto) a ~/.dotfiles/koreader-data
│   └── systemd/         # unidades service + timer (usuario)
├── reportes/            # TSV de cada pasada
└── backups/             # metadata.db rotados (5) + tars pre-migración
```
