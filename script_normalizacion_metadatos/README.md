# script_normalizacion_metadatos

Migraciones puntuales que normalizaron en bloque los metadatos de la
biblioteca **Calibre** el **2026-07-28**: etiquetas, Géneros, Item type y
Clasificador de los 4 484 libros, derivados **solo de los metadatos ya
existentes** (sin abrir PDFs), respetando la regla de no tocar título ni
autor.

> Estos scripts **ya se aplicaron**. Se conservan aquí como registro
> reproducible y base para trabajo futuro. Todos escriben **directo en
> `metadata.db` vía SQLite** y son **dry-run por defecto** (requieren
> `--apply` para escribir). Ver "Gotcha del OPF" más abajo.

## Orden de ejecución

| # | Script | Qué hace |
| --- | --- | --- |
| 01 | `migraciones/01_merge_tags.py` | Fusiona/renombra etiquetas duplicadas (`mathematics→matematicas`, `ethics/etica`, `economía_*→economia_*`, el typo `ecuacione s_lineales`, etc.). 245 → 222 etiquetas. |
| 02 | `migraciones/02_genres.py` | Deriva el campo **Géneros** por voto de las etiquetas (mapa tag→género, ~15 géneros). Desempate por especificidad (gana el género menos frecuente). 13 etiquetas neutras no votan. |
| 03 | `migraciones/03_itemtype_desde_clasificador.py` | Rellena **Item type** desde el Clasificador con el mapeo dominante de alta confianza (Sesión→Presentation, Libro→Book, …). |
| 04 | `migraciones/04_itemtype_examenes_practicas.py` | Item type del material de examen/práctica/ejercicio → **Manuscript** (docs de aula inéditos), Capítulo/Parte → Book Section, Documento de trabajo/etc. → Report. |
| 05 | `migraciones/05_aplicar_tags_por_titulo.py` | Aplica los TSV `id,tags,genero,clasificador,item_type` producidos al clasificar por título los 739 libros sin etiquetas. Valida cada valor contra el vocabulario/enums **antes** de escribir. |

`vocabulario_etiquetas.txt` es el vocabulario cerrado de etiquetas usado como
lista blanca (ninguna migración inventa etiquetas nuevas).

## Uso (patrón dry-run)

```bash
python3 migraciones/02_genres.py            # SIMULACIÓN: imprime el plan
python3 migraciones/02_genres.py --apply    # escribe en metadata.db
```

Todas siguen la misma convención: sin `--apply` solo reportan; con `--apply`
hacen commit en la base. La ruta de la biblioteca está fijada arriba en cada
script (`DB = ".../biblioteca/metadata.db"`).

## Gotcha del OPF (IMPORTANTE)

Como estas migraciones escriben **directo en SQLite** (evitando `calibredb`
para leer/escribir barato), los `metadata.opf` de cada carpeta —lo que el
plugin **ZMI** lee para exportar a Zotero— quedan **desactualizados**. Tras
aplicar cualquiera de ellas hay que regenerarlos, con **Calibre cerrado**:

```bash
calibredb --with-library /home/achalmaedison/Documents/biblioteca \
          backup_metadata --all
```

`backup_metadata` **solo reescribe los OPF**, no toca los PDFs. **No usar
`embed_metadata`** (ese sí modifica el archivo del ebook).

## Precauciones

- Hacer copia de `metadata.db` antes de un `--apply` masivo.
- Ejecutar con **Calibre cerrado** (si está abierto, su caché en memoria
  puede pisar los cambios).
- Verificar después: `sqlite3 metadata.db "PRAGMA integrity_check;"`.

## Relación con las otras herramientas

- `../script_catalogacion_biblioteca/` — catalogación de libros sin autor
  (fichas duales Zotero+Calibre).
- `../script_verificar_metadatos/` — verifica los metadatos ya existentes
  contra OpenLibrary y reporta discrepancias (solo lectura).
