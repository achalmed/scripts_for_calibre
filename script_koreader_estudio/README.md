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
- Depende de: calibredb, koreader, core/shell-lib, lib/escribir.sh (la puerta)
- Timer: `koreader-calibre-sync.timer`

Comandos:

```bash
main.sh                      # simula
main.sh --aplicar
main.sh --desde-timer
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suite:fin -->

Convierte Calibre en un **tablero de seguimiento de estudio**: KOReader (en este mismo Linux) lee
los mismos archivos de la biblioteca (`BIBLIOTECA_DIR`); este script vuelca su progreso, estado y
estadísticas en columnas de Calibre (reutiliza las del plugin *KOReader Sync* y su convención de
escalas) y añade un enlace clicable a los apuntes `.md` de cada libro.

## Cómo funciona

KOReader ya escribe dos fuentes: los sidecars `metadata.<ext>.lua` (`percent_finished` en fracción
0–1, `summary.status`) y `statistics.sqlite3` (tiempo total, primera y última sesión). El núcleo
`lib/sync_koreader.py` (vía `calibre-debug`) las empareja con cada libro por el MD5 parcial de
KOReader (su algoritmo, verificado contra esta base) y escribe en lote, por la puerta, solo los
valores que cambiaron.

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

## Uso

```bash
./main.sh                  # SIMULACIÓN: muestra qué haría (no escribe)
./main.sh --aplicar        # por la puerta: respaldo verificado, columnas faltantes y sync real
./main.sh --migrar-sdr [--aplicar]   # .sdr → hash central (de una vez; KOReader cerrado)
./main.sh --apuntes ID "/ruta/apuntes.md" "Clase 01"   # orden explícita: escribe YA, por la puerta
./main.sh --instalar-timer | --desinstalar-timer       # desde ../systemd/ (../docs/operacion.md §1.1)
```

La columna manual **`#estudio`** (⬜/📖/🔁/✅, estado de *estudio*) es distinta del estado de
*lectura* automático (`#estado_estudio`); el sync jamás la toca. **Marca el final en KOReader**
(estado del libro → *Terminado*): pone ✅ Finalizado, `#leído`, `#read_date` y `#ko_finish`.
`--aplicar` escribe por la puerta (`../lib/escribir.sh`): Calibre cerrado, candado `LOCK_CALIBRE` y
respaldo verificado en `$XDG_STATE_HOME/biblioteca/respaldos/koreader_estudio/`. Requisitos:
Calibre (`calibredb`, `calibre-debug`), `CORE_PYTHON` y el plugin de **Estadísticas de lectura**.

## Sidecars centralizados por hash

Los `.sdr` viven en `~/.config/koreader/hashdocsettings/<md5[0:2]>/<md5>.sdr/` (se migraron con
`--migrar-sdr`; `document_metadata_folder = "hash"`): el sidecar se encuentra por el hash del
contenido, así que renombrar en Calibre no rompe nada y todo lo valioso queda en un solo árbol. Los
`.sdr` huérfanos de renombrados antiguos se dejaron en su sitio; KOReader los lee como respaldo.

## Respaldo continuo (no volver a perder lecturas)

Cada pasada espeja **en texto** las estadísticas (volcado SQL hecho con `CORE_PYTHON`), los sidecars
`hashdocsettings/` y `history.lua` al repo git de datos `KOREADER_RESPALDO_DIR` (`core/env.sh`), con
commit local (publicar = `git push` desde ese repo, remoto privado). Los datos vivos siguen en
`~/.config/koreader/`. **`settings.reader.lua` se excluye a propósito** (bloque `kosync` con
credenciales). Restaurar en otra máquina: `sqlite3 ~/.config/koreader/settings/statistics.sqlite3 <
statistics.sql` y copiar `hashdocsettings/` e `history.lua`; el emparejamiento por hash funciona
aunque la biblioteca cambie de ruta.

## Trampas conocidas

- `calibredb set_custom` (no `set_custom_column`) escribe columnas en Calibre 9.
- En plantillas composite: `field()` devuelve el valor **formateado** (`'4.35%'`) — usa
  `raw_field()` para aritmética; `substr(s, 0, 0)` devuelve la cadena **entera**, no vacía (por eso
  la barra trata n=0 y n=10 aparte).
- `#ko_progfloat` guarda **fracción 0–1** (no 0–100): es la convención que dejó el plugin KOReader
  Sync y se respeta por compatibilidad.

## Estructura

`main.sh` (orquestación y CLI) · `config.sh` (rutas de `core/env.sh` y columnas) · `lib/`: `checks.sh`
(entorno, KOReader cerrado), `setup_columnas.sh` (columnas y plantillas, idempotente),
`sync_koreader.py` (núcleo), `migrar_sdr.py` (de una vez), `respaldo_koreader.sh` (espejo en texto) ·
`reportes/` es runtime ignorado. El timer está en `../systemd/`; las pruebas, en `../tests/`.

## Límite honesto

- **Calibre cerrado para escribir**: el timer que lo encuentra abierto se salta la pasada y reintenta.
- **No es instantáneo**: KOReader vuelca sidecar y estadísticas al cerrar el libro (y en pausas); el
  progreso de la sesión en curso aparece en la pasada siguiente.
- **Solo escribe valores que cambiaron** y jamás toca `#estudio`, etiquetas ni series; `#leído`
  marcado a mano promueve a Finalizado, nunca degrada.
- **Restaurar en otra máquina exige reconfigurar la cuenta `kosync`** (su archivo no se respalda).
- **`--migrar-sdr` fue una migración de una vez**; vuelve a tener sentido solo si
  aparecen `.sdr` nuevos junto a los libros.
- **Mover el repo de carpeta rompe el timer**: la unidad instalada lleva la ruta de `main.sh` bajo
  `%h`; se reinstala con `../systemd/instalar.sh --aplicar`.
