---
tipo: readme
estado: activo
---
# script_catalogacion_biblioteca/ — el registro de fichas de catalogación y su aplicación a Calibre

<!-- suite:inicio -->
**Suite `catalogacion_biblioteca`** · objetivo *fuentes* · estado *activo* · bash · interfaz cli

Aplica a Calibre los metadatos catalogados en resumen_catalogacion.tsv (autor «Nombre, Apellidos», vocabulario cerrado, serie, identificadores); registro canónico de lo catalogado.

- Escribe en: calibre, archivos · simula por defecto: sí
- Entrada: resumen_catalogacion.tsv (lo alimentan ingesta e ingesta_cursos)
- Depende de: calibredb, core/shell-lib
- Método Documental: paso 02
- Nota: fichas/ y resumen_catalogacion.tsv son el registro de esta suite (D12): las fichas nuevas y sus filas las escriben scripts_for_fuentes/ingesta e ingesta_cursos con su calibre_id; aquí se aplican a Calibre

Comandos:

```bash
main.sh                      # simula sobre resumen_catalogacion.tsv
main.sh --aplicar            # escribe (Calibre cerrado, lock)
main.sh --aplicar --ids 10265,10266
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-20); no se edita a mano.</sub>
<!-- suite:fin -->

Dos cosas en una carpeta: el **registro de catalogación** de la biblioteca —una ficha por libro en
`fichas/<calibre_id>_<slug>.md` y una fila por libro en `resumen_catalogacion.tsv`— y la herramienta
`main.sh`, que aplica las filas del TSV a Calibre con `calibredb set_metadata`. El formato de la
ficha lo define `prompts/01 fuentes/prompt_02_catalogar.md`, con el frontmatter de `prompts/00
metodo/fichas_formato_y_voz.md`; las fichas y filas nuevas las escriben
`scripts_for_fuentes/ingesta` (`scripts_for_fuentes/ingesta/lib/catalogar.py`) e `ingesta_cursos`
(D12). Mapa del ecosistema de aprendizaje: `prompts/docs/dominios/aprendizaje.md`.

## Uso

```bash
main.sh                             # simula todas las filas del TSV
main.sh --ids 10265,10266           # simula solo esas filas (las altas recientes)
main.sh --aplicar --ids 10265,10266 # escribe; Calibre cerrado
main.sh --aplicar --solo-alta       # solo las filas de confianza alta
main.sh --help                      # opciones; --verbose da trazas por fila
```

El circuito de un libro nuevo, ya importado en Calibre con su `id`: catalogarlo con el prompt
leyendo la portada o la página legal → ficha en `fichas/` y fila en el TSV (lo hace `ingesta`) →
simular con `--ids` → aplicar con Calibre cerrado → la parte Zotero de la ficha, a mano o con ZMI →
opcionalmente, `../script_metadatos_calibre/` para incrustar en el PDF.

Las columnas del TSV son `id · autores · titulo · tipo_zotero · clasificador · editorial · fecha ·
identificador · idioma · tags · confianza · nota`. Un campo vacío no se envía, así que nunca borra
lo que Calibre ya tenía; los campos ricos (`#edition`, `#pages`, `#genres`, `#sub_tipo`) no pasan
por aquí. Cuántas fichas y filas hay: `ls fichas | wc -l` y `wc -l < resumen_catalogacion.tsv`
(cuenta también la cabecera).

## Estructura

| ruta | qué es | dueño |
|---|---|---|
| `fichas/` | registro: una ficha por libro | la escriben `scripts_for_fuentes/ingesta` e `ingesta_cursos` |
| `resumen_catalogacion.tsv` | registro y entrada de `main.sh`: una fila por libro | ídem; se corrige aquí cuando una ficha cambia |
| `main.sh` · `config.sh` | orquestación; ruta de la biblioteca, TSV y enum de respaldo | a mano |
| `lib/cli.sh` · `lib/validator.sh` | opciones (`--aplicar` y `--dry-run` son incompatibles: salida 2); dependencias, TSV y Calibre cerrado | a mano |
| `lib/clasificador.sh` · `lib/metadata.sh` | enum `#clasificador` leído en vivo, tildes y validación; fila → `calibredb set_metadata` | a mano |

Para añadir una opción: el valor por defecto en `config.sh`, la bandera en `lib/cli.sh`, la lógica
en un módulo de `lib/` cargado desde `main.sh`, y `bash -n` sobre cada archivo tocado. La campaña de
los libros sin autor que dio origen a la suite y los defectos que corrigió su refactorización están
en `../docs/historial/`.

## Límite honesto

- **El TSV manda, no la ficha**: corregir una ficha sin reflejarlo en `resumen_catalogacion.tsv` no
  cambia nada en Calibre.
- **Escribe autor y título**, y Calibre renombra la carpeta del libro: si el libro ya tiene ítem en
  Zotero, el enlace del adjunto se rompe. Se aplica antes de llevar el libro a Zotero.
- **No toma el candado `.lock_calibre_write`**: solo comprueba que Calibre esté cerrado
  (`../docs/decisiones.md`, Pendientes P1).
- **El enum `Clasificador` de Calibre y la lista del prompt no coinciden** (tildes, valores que
  faltan): lo que el enum rechaza se omite y se reporta, no se inventa.
- **No genera fichas ni filas**: aquí solo se aplican y se conserva el registro.
- **Sin pruebas automáticas**: la comprobación es `bash -n`, `--help` y la simulación.
