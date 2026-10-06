---
tipo: readme
estado: activo
---
# script_metadatos_calibre/ — incrusta en los PDF los metadatos de Calibre y registra PDF sueltos

<!-- suite:inicio -->
**Suite `metadatos_calibre`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Incrusta los metadatos OPF de Calibre en los PDF (XMP con exiftool) y registra PDF sueltos como libros.

- Escribe en: calibre, archivos · simula por defecto: sí
- Depende de: calibredb, exiftool, core/shell-lib, lib/escribir.sh (la puerta)
- Nota: todo simula por defecto (ola 2a, K5); con --aplicar, embed modifica los PDF, register escribe metadata.db por la puerta y limpiar-json borra los huérfanos.

Comandos:

```bash
main.sh                      # menú interactivo (simula)
main.sh embed
main.sh embed --aplicar
main.sh register
main.sh register --aplicar   # por la puerta: Calibre cerrado, candado y respaldo
main.sh limpiar-json --aplicar
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
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
main.sh embed --root "$BIBLIOTECA_DIR"                    # simula; --aplicar escribe en los PDF
main.sh register --root "$BIBLIOTECA_DIR" --library "$BIBLIOTECA_DIR"             # simula
main.sh register --root "$BIBLIOTECA_DIR" --library "$BIBLIOTECA_DIR" --aplicar   # por la puerta
main.sh all --root "$BIBLIOTECA_DIR" --library "$BIBLIOTECA_DIR"
main.sh limpiar-json                       # solo lista; --aplicar borra
main.sh --help                             # todas las opciones
main.sh                                    # menú interactivo
```

**Todo simula por defecto** (ola 2a, K5): `embed` modifica los PDF, `register` escribe
`metadata.db` y `limpiar-json` borra solo con `--aplicar`; `--dry-run` (`-n`) se admite por
compatibilidad y choca con `--aplicar`. `register --aplicar` entra por la puerta
(`../lib/escribir.sh`): Calibre cerrado, candado y respaldo verificado antes del primer
`add_format`. Sin `--root`, la raíz es el directorio actual; sin `--library`,
`register` toma el directorio padre. `--force` sobrescribe un PDF ya registrado; `--verbose` muestra
los mensajes de depuración. El log de cada sesión va a `/tmp/calibre-metadata-manager_<fecha>.log`.

Requisitos: Bash ≥ 4, `exiftool`, `calibredb`, GNU `find`, `grep` y `sed`. Pruebas de `register`
(simula, aplica por la puerta, no escribe con Calibre abierto): `../tests/test_escritores_k5.py`.

## Estructura

`main.sh` (carga los módulos y despacha la operación) · `config.sh` (códigos de salida, valores por
defecto y los mapas de campos de `exiftool`) · `lib/`: `cli.sh` (opciones, ayuda y menú),
`validator.sh` (dependencias, rutas y biblioteca), `sesion.sh` (cabecera de sesión y secciones; el
logger es el de `core/shell-lib`), `embed_metadata.sh`, `register_formats.sh`, `limpiar_json_huerfanos.sh`.

Para añadir una operación: un módulo en `lib/` con una función pública `run_<operación>()` y guarda
de doble carga, su `source` en `main.sh`, su rama en el `case` de `main()` y su entrada en
`show_help()` y `show_interactive_menu()` de `lib/cli.sh`. Los defectos que corrigió la
refactorización modular están en `../docs/historial/refactorizacion-modular.md`.

## Límite honesto

- **No hay deshacer de `embed`** más allá de la simulación previa y del log en `/tmp` (los PDF no se
  respaldan); `register` sí deja el respaldo verificado de la puerta.
- **`embed` no actualiza Calibre**: cambia el PDF, no la base; para lo inverso está «Actualizar
  metadatos desde libro» en Calibre. Es redundante para los PDF que Calibre ya incrustó al enviarlos
  a un dispositivo.
- **El OPF se lee con `grep` y `sed`**, sin `xmllint`: vale para el OPF estándar de Calibre;
  elementos multilínea o espacios de nombres propios pueden leerse mal.
- **`register` decide por heurística** si la raíz es una carpeta de autor (hijos que terminan en
  `(id)`) o la biblioteca entera.
