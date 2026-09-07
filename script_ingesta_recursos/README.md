# script_ingesta_recursos — material externo de los cursos → Calibre (F5.4)

Lleva a la biblioteca Calibre los PDF **externos** (de otros autores) que viven en `06_RECURSOS/` y
`08_INVESTIGACION/` de los cursos de `10 Class/areas/`, y deja en el `temario.yml` del curso la referencia
`bibliografia: [{calibre_id, titulo, autor, origen}]`. El curso cita la biblioteca; no guarda copias.

> **Regla de oro (aprendida el 2026-09-06):** subir no es catalogar. La biblioteca ya tenía el curso completo
> de Hinojosa y 43 de los 60 PDF «nuevos» eran copias. Por eso esta suite ahora **deduplica antes de añadir**,
> **no inventa grafías de autor ni etiquetas**, y deja cada libro nuevo listo para la ficha de
> `../script_catalogacion_biblioteca/` (el hogar canónico de la catalogación).

## Uso

```bash
./main.sh --escanear            # reportes/candidatos_<fecha>.tsv con una decisión por PDF
./main.sh                       # simula la aplicación del último TSV
./main.sh --aplicar [--tsv X]   # Calibre cerrado; toma el lock; backup rotado de metadata.db
```

Decisiones del TSV (edítalo antes de aplicar):

| decision | Qué hace `--aplicar` |
|---|---|
| `ingestar` | `calibredb add` con título en frase y autor canónico (o `Unknown`), **sin etiquetas**; id en el temario; original retirado a `ORIGINALES_DIR`; fila prellenada en `reportes/catalogar_<fecha>.tsv` |
| `duplicado` | no añade nada: enlaza el temario al `duplicado_id` que ya existe y retira la copia del curso |
| `omitir` | material propio, de estudiantes, plantillas, administrativo, compilados (`deck_*`, `build/`), cursos en `CURSOS_EXCLUIDOS` |
| `revisar` | ambiguo (pocas páginas en carpeta genérica): decide a mano |

## Cómo decide

- **Duplicado** (`lib/biblioteca.py duplicado`): mismo título normalizado por tokens y mismas páginas
  (`#pages`, tolerancia `DEDUPE_TOLERANCIA_PAGINAS`) que un libro ya catalogado. Varios candidatos → aviso, no se toca.
- **Autor** (`lib/biblioteca.py autor`): el `Author` del PDF se compara **por tokens** con los autores existentes;
  si está contenido en exactamente uno (`TONY HINOJOSA` ⊂ `Tony, Hinojosa Vivanco`) se usa esa grafía. Si es
  genérico (`AUTORES_GENERICOS`), ambiguo (`hinojosa` → Tony o Sergio) o desconocido → `Unknown`, la convención
  de la biblioteca. **Nunca se crea una grafía nueva desde el PDF.**
- **Título** (`lib/biblioteca.py titulo`): `Title` del PDF si es real; si no, nombre de archivo sin numeración
  (`2 4 costo de capital ii` → `Costo de capital ii`), en frase como el resto de la biblioteca.

## Después de aplicar (obligatorio para los `ingestar`)

Los libros nuevos entran sin serie, etiquetas, tipo ni clasificador. Complétalos con el patrón de la biblioteca:
autores `Nombre, Apellidos`; etiquetas solo del vocabulario cerrado
(`../script_normalizacion_metadatos/vocabulario_etiquetas.txt`); serie `<Autor> - <Curso>` con `series_index`
= unidad.sesión (y `#numerodeserie`); `#clasificador`, `#item_type`, `#genres`, `#pages`, idioma, editorial, fecha.
Escribe la ficha en `../script_catalogacion_biblioteca/fichas/<id>_<slug>.md`, añade la fila a su
`resumen_catalogacion.tsv` y aplica con esa suite.

## Archivos

| Ruta | Función |
|---|---|
| `main.sh` | orquestación (modos, dependencias, lock, backup) |
| `config.sh` | rutas, carpetas escaneadas, cursos excluidos, autores genéricos, tolerancia |
| `lib/clasificar.sh` | `escanear`: clase, decisión, autor canónico, título, duplicado |
| `lib/biblioteca.py` | consultas de solo lectura a `metadata.db` (duplicado, autor, título) |
| `lib/ingestar.sh` | aplica el TSV (add / enlazar duplicado / retirar original / fila para catalogar) |
| `lib/temario_bib.py` | escribe `bibliografia:` en el `temario.yml` del curso |
| `reportes/` | `candidatos_*`, `ingesta_*` (ids añadidos: los lee el `UNDO.sh` de la reparación), `catalogar_*`, `duplicados_*`, `historial/` |

Reversión: `meta/reparaciones/F5.4_biblioteca_2026-09-06/UNDO.sh --aplicar`.
