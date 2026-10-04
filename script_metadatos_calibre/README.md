---
tipo: readme
estado: activo
---
# script_metadatos_calibre/ — incrusta en los PDF los metadatos de Calibre y registra PDF sueltos

<!-- suite:inicio -->
**Suite `metadatos_calibre`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Incrusta los metadatos OPF de Calibre en los PDF (XMP con exiftool) y registra PDF sueltos como libros.

- Escribe en: calibre, archivos · simula por defecto: no
- Depende de: calibredb, exiftool, core/shell-lib
- Nota: embed y register escriben salvo --dry-run; --aplicar solo lo lee limpiar-json, que sin él lista los huérfanos y no borra.

Comandos:

```bash
main.sh                      # menú interactivo
main.sh embed --dry-run
main.sh embed
main.sh register --dry-run
main.sh limpiar-json --aplicar
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suite:fin -->

Lleva a los PDF de la biblioteca los metadatos que Calibre guarda en cada `metadata.opf` y registra
como formato los PDF que están en la carpeta de un libro pero no en `metadata.db`. Es el único
incrustador de PDF del workspace: el de `scripts_for_zotero` quedó absorbido aquí.

| operación | qué hace |
|---|---|
| `embed` | lee el `metadata.opf` de cada carpeta de libro y escribe en sus PDF el InfoDict y el XMP Dublin Core (`XMP-dc:*`) con `exiftool`; los campos salen de `EXIFTOOL_TAG_MAP` y `EXIFTOOL_XMP_TAG_MAP` de `config.sh` |
| `register` | añade con `calibredb add_format` los PDF presentes en las carpetas de libro que Calibre no tenía registrados |
| `all` | `embed` y después `register` |
| `limpiar-json` | lista los `zotero_metadata.json` huérfanos que sembró el incrustador retirado; con `--aplicar`, los borra |

## Uso

```bash
# BIBLIOTECA_DIR la resuelve core/env.sh (core/env.sh --print)
main.sh embed --root "$BIBLIOTECA_DIR" --dry-run          # simula; sin --dry-run ESCRIBE en los PDF
main.sh register --root "$BIBLIOTECA_DIR" --library "$BIBLIOTECA_DIR" --dry-run
main.sh all --root "$BIBLIOTECA_DIR" --library "$BIBLIOTECA_DIR" --dry-run
main.sh limpiar-json                       # solo lista; --aplicar borra
main.sh --help                             # todas las opciones
main.sh                                    # menú interactivo
```

**`embed` y `register` escriben por defecto**: la simulación es `--dry-run` (`-n`), y `--aplicar`
solo lo lee `limpiar-json`. Sin `--root`, la raíz es el directorio actual; sin `--library`,
`register` toma el directorio padre. `--force` sobrescribe un PDF ya registrado; `--verbose` muestra
los mensajes de depuración. El log de cada sesión va a `/tmp/calibre-metadata-manager_<fecha>.log`.

Requisitos: Bash ≥ 4, `exiftool`, `calibredb`, GNU `find`, `grep` y `sed`.

## Estructura

`main.sh` (carga los módulos y despacha la operación) · `config.sh` (códigos de salida, valores por
defecto y los mapas de campos de `exiftool`) · `lib/`: `cli.sh` (opciones, ayuda y menú),
`validator.sh` (dependencias, rutas y biblioteca), `logger.sh` (envoltorio del de `core/shell-lib`
con la cabecera de sesión), `embed_metadata.sh`, `register_formats.sh`, `limpiar_json_huerfanos.sh`.

Para añadir una operación: un módulo en `lib/` con una función pública `run_<operación>()` y guarda
de doble carga, su `source` en `main.sh`, su rama en el `case` de `main()` y su entrada en
`show_help()` y `show_interactive_menu()` de `lib/cli.sh`. Los defectos que corrigió la
refactorización modular están en `../docs/historial/refactorizacion-modular.md`.

## Límite honesto

- **Escribe sin pedirlo**: `embed` modifica los PDF y `register` la base salvo con `--dry-run`, y no
  toma el candado `.lock_calibre_write` (`../docs/decisiones.md`, Pendientes P1 y P2).
- **No hay deshacer de `embed`** más allá del `--dry-run` previo y del log en `/tmp`.
- **`embed` no actualiza Calibre**: cambia el PDF, no la base; para lo inverso está «Actualizar
  metadatos desde libro» en Calibre. Es redundante para los PDF que Calibre ya incrustó al enviarlos
  a un dispositivo.
- **El OPF se lee con `grep` y `sed`**, sin `xmllint`: vale para el OPF estándar de Calibre;
  elementos multilínea o espacios de nombres propios pueden leerse mal.
- **`register` necesita Calibre cerrado pero no lo comprueba** (lo exige `calibredb`), y decide por
  heurística si la raíz es una carpeta de autor (hijos que terminan en `(id)`) o la biblioteca
  entera.
