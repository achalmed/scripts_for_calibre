# script_normalizacion_metadatos

<!-- suite:inicio -->
**Suite `normalizacion_metadatos`** · objetivo *biblioteca* · estado *archivado* · - · interfaz cli

Migraciones puntuales (2026) que normalizaron en bloque géneros, tipos de ítem y vocabulario de etiquetas de la biblioteca.

- Escribe en: calibre · simula por defecto: sí
- Nota: sin main.sh: son scripts de una sola vez; se conservan como historia de la biblioteca

Comandos:

```bash
python3 migraciones/02_genres.py            # imprime el plan
python3 migraciones/02_genres.py --apply    # escribe
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-15); no se edita a mano.</sub>
<!-- suite:fin -->

Migraciones puntuales que normalizaron en bloque los metadatos de la
biblioteca **Calibre** el **2026-07-28**: etiquetas, Géneros, Item type y
Clasificador de los 4 484 libros, derivados **solo de los metadatos ya
existentes** (sin abrir PDFs), respetando la regla de no tocar título ni
autor.

> Estos scripts **ya se aplicaron** (campaña terminada el 2026-07-28). Se
> conservan como **registro histórico**, no como pipeline re-ejecutable en
> bloque. Todos escriben **directo en `metadata.db` vía SQLite** y son
> **dry-run por defecto** (requieren `--apply` para escribir). Ver
> "Reproducibilidad" y "Gotcha del OPF" más abajo.

## Orden de ejecución

| # | Script | Qué hace |
| --- | --- | --- |
| 01 | `migraciones/01_merge_tags.py` | Fusiona/renombra etiquetas duplicadas (`mathematics→matematicas`, `ethics/etica`, `economía_*→economia_*`, el typo `ecuacione s_lineales`, etc.). 245 → 222 etiquetas. |
| 02 | `migraciones/02_genres.py` | Deriva el campo **Géneros** por voto de las etiquetas (mapa tag→género, ~15 géneros). Desempate por especificidad (gana el género menos frecuente). 13 etiquetas neutras no votan. |
| 03 | `migraciones/03_itemtype_desde_clasificador.py` | Rellena **Item type** desde el Clasificador con el mapeo dominante de alta confianza (Sesión→Presentation, Libro→Book, …). |
| 04 | `migraciones/04_itemtype_examenes_practicas.py` | Item type del material de examen/práctica/ejercicio → **Manuscript** (docs de aula inéditos), Capítulo/Parte → Book Section, Documento de trabajo/etc. → Report. |
| 05 | `migraciones/05_aplicar_tags_por_titulo.py` | Aplica los TSV `id,tags,genero,clasificador,item_type` producidos al clasificar por título los 739 libros sin etiquetas. Valida cada valor contra el vocabulario/enums **antes** de escribir. |
| 06 | `migraciones/06_itemtype_por_serie_isbn.py` | Completa **Item type** por señal fuerte determinista: misma **serie** que hermanos ya catalogados → tipo dominante; sin serie pero con **ISBN** → Book. Dry-run (imprime plan). Cubrió 201 libros. |
| 07 | `migraciones/07_itemtype_por_prompt_subagentes.py` | Valida y aplica los TSV `id,item_type` que produjeron 6 subagentes al clasificar los 950 libros restantes **leyendo los criterios del prompt de catalogación** (líneas 84-848). Rechaza cualquier tipo fuera del enum antes de escribir. Con `--apply`. Dejó el Item type al 100%. |
| 08 | `migraciones/08_refinar_itype_openlibrary_crossref.py` | Pasada de **refinamiento**: los libros inciertos (Manuscript/Journal Article sin serie ni editorial) se verifican en OpenLibrary y Crossref (difuso 0.92). Solo lectura; escribe una propuesta TSV. Halla libros publicados mal marcados como Manuscript. |
| 09 | `migraciones/09_aplicar_refino_itype.py` | Valida y aplica la propuesta del 08: reclasifica el Item type y, de regalo, rellena editorial/ISBN hallados donde estaban vacíos (aditivo). Con `--apply`. Refinó 48 libros (+34 editoriales, +30 ISBN). |

`vocabulario_etiquetas.txt` es el vocabulario cerrado de etiquetas usado como
lista blanca (ninguna migración inventa etiquetas nuevas).

## Reproducibilidad (honesta)

Hay que distinguir dos grupos:

- **Re-ejecutables** (01, 02, 03, 04, 06): derivan sus decisiones **solo de
  `metadata.db`** (etiquetas, Clasificador, serie, ISBN ya presentes). Se
  pueden volver a correr tal cual sobre la base actual — son idempotentes en
  la práctica (re-aplicar no cambia lo ya normalizado).

- **NO re-ejecutables — registro histórico** (05, 07, 08, 09): leen/escriben
  archivos `res_*.tsv` / `refinar_prop.tsv` desde un **scratchpad de sesión ya
  extinto** (`/tmp/claude-1000/.../07e95f6c-.../scratchpad`, hardcodeado en
  cada uno). Esos TSV eran salidas efímeras de subagentes/consultas de una
  corrida concreta; **ya no existen**. Correr estos scripts hoy no hace nada
  útil (no encuentran sus insumos). Se conservan para **documentar qué lógica
  de validación** se aplicó (rechazo contra enum/vocabulario antes de escribir)
  y con qué criterios se reclasificó, no para re-ejecutar.

Para una nueva normalización en bloque tras una importación grande: partir de
01–04/06 (que sí leen la base) y regenerar los insumos de clasificación por
título/tipo con las herramientas actuales, no reutilizar los `/tmp` muertos.

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
