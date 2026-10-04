---
tipo: readme
estado: archivado
---
# script_normalizacion_metadatos/ — las campañas de una sola vez sobre la biblioteca (archivado)

<!-- suite:inicio -->
**Suite `normalizacion_metadatos`** · objetivo *biblioteca* · estado *archivado* · - · interfaz cli

Campañas de una sola vez sobre la biblioteca: las migraciones NN_*.py de etiquetas, géneros y tipos de ítem, y las campañas con carpeta propia (autores, títulos, duplicados) que tocan Calibre y Zotero con respaldo y deshacer.

- Escribe en: calibre, zotero, archivos · simula por defecto: no
- Nota: Sin main.sh de suite: las NN_*.py simulan sin --apply; las campañas con main.sh propio (no todas simulan por defecto: lo dice su cabecera) exigen Calibre y Zotero cerrados, toman el candado, respaldan y dejan hechos.tsv y deshacer.sh; la campaña de un solo script toca solo Zotero, simula sin --aplicar y se deshace con su respaldo.

Comandos:

```bash
python3 migraciones/02_genres.py            # imprime el plan
python3 migraciones/02_genres.py --apply    # escribe
migraciones/<campaña>/main.sh                # su modo, en la cabecera del main.sh
migraciones/<campaña>/deshacer.sh
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suite:fin -->

Las **campañas de una sola vez** sobre la biblioteca: el código que las aplicó, las tablas que dicen
qué cambió y, en las que llevan `deshacer.sh`, cómo deshacerlas. No es una herramienta que se
corra con regularidad: cada campaña se aprueba antes de aplicarse y queda aquí como registro. Qué
hicieron las aplicadas hasta 2026-10-01: `../docs/historial/campanas-sobre-la-biblioteca.md`; las
posteriores, su carpeta y su commit (`../docs/decisiones.md` §4.6); la regla del patrón:
`../docs/decisiones.md` §4.2.

## Uso

```bash
ls migraciones/                                  # NN_*.py (2026-07-28) y <tema>_<fecha>/
head -6 migraciones/<campaña>/main.sh            # su uso exacto, en la cabecera
python3 migraciones/02_genres.py                 # las NN_*.py simulan; --apply escribe
migraciones/<campaña>/deshacer.sh                # revierte una campaña con carpeta propia
```

**Una carpeta de campaña no simula siempre por defecto.** Las de títulos aplican sobre las bases
reales al invocarse y ensayan con `--simular <biblioteca> <zotero.sqlite>` sobre una copia; la de
autores aplica sin más; la de duplicados simula y escribe con `--aplicar`. Todas las que tienen `main.sh` exigen Calibre y
Zotero cerrados, toman el candado `.lock_calibre_write`, respaldan antes y se niegan a repetir si ya
existe su `hechos.tsv`.

**Una campaña de un solo script** (`migraciones/zotero_alta_2026-09-30/papelera_duplicado.py`) solo toca Zotero:
simula por defecto, escribe con `--aplicar` y Zotero cerrado, respalda `zotero.sqlite` en `backups/`
y no lleva `hechos.tsv` ni `deshacer.sh` (se deshace restaurando el respaldo o desde la papelera de
Zotero). No consta aplicada (`../docs/decisiones.md`, Pendientes P12).

Las `NN_*.py` escriben directo en `metadata.db` por SQLite (ruta en `CALIBRE_DB`, con respaldo a
`~/Documents/biblioteca/metadata.db`). Después de cualquiera, con Calibre cerrado:

```bash
calibredb --with-library "$BIBLIOTECA_DIR" backup_metadata --all   # OPF; nunca embed_metadata
sqlite3 "$BIBLIOTECA_DIR/metadata.db" "PRAGMA integrity_check;"
```

## Estructura

| ruta | qué es |
|---|---|
| `migraciones/NN_*.py` | la normalización de etiquetas, géneros y tipos de 2026-07-28, una migración por script en orden |
| `migraciones/<tema>_<fecha>/` | una campaña: `main.sh`, `aplicar*.py`, `hechos.tsv` (lo hecho, que lee el deshacer) y `deshacer.sh`; las de autores y títulos añaden `propuesta.tsv` (lo aprobado), `carpetas.tsv` y `zotero.tsv`, y las de títulos `foto.py` y `foto_antes.tsv` (estado previo); la de duplicados, `auditar.py` y sus tablas de candidatos |
| `migraciones/<tema>_<fecha>/<script>.py` | una campaña de un solo script, con su uso y su deshacer en el docstring |
| `vocabulario_etiquetas.txt` | vocabulario cerrado de etiquetas: ninguna migración inventa una |
| `itemtype_lote_sin_catalogar.tsv` | insumo de la migración 07 |
| `backups/` | respaldos de las bases; fuera de git |
| `suite.yml` | manifiesto (`core/suite.schema.yml`) |

Una campaña nueva copia el patrón de la más reciente parecida, nace de un diagnóstico aprobado en
`meta/diagnosticos/` y se ensaya sobre una copia antes de tocar las bases reales.

## Límite honesto

- **No se re-ejecuta en bloque**: 05, 07, 08 y 09 leían TSV de un scratchpad de sesión que ya no
  existe; solo 01–04 y 06 se pueden volver a correr sobre la base actual.
- **Las `NN_*.py` dejan los OPF rancios** hasta `backup_metadata --all`, y no tienen deshacer más
  allá del respaldo de `metadata.db`.
- **Título y autor solo se tocan en campañas que reescriben Zotero en la misma operación**, porque
  Zotero enlaza los PDF por la ruta `Autor/Título (id)`.
- **El `suite.yml` se quedó corto** («sin main.sh», solo géneros y tipos): `../docs/decisiones.md`,
  Pendientes P3.
