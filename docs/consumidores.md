---
tipo: doc
titulo: "Consumidores de scripts_for_calibre: lo que otros repos usan de aquí y lo que no se cambia sin avisarles"
genero: referencia
estado: activo
---
# Consumidores de `scripts_for_calibre`

Referencia de la frontera (NORMATIVA §15.6): qué ofrece este repo a otros, quién lo usa y qué no se
puede renombrar, mover ni cambiar de forma sin actualizar al consumidor en el mismo ciclo. El
contrato vive aquí; cada consumidor lleva un puntero a esta página.

## Lo que ofrece y quién lo usa

| interfaz | qué es | consumidor | dónde lo usa | no se cambia sin avisar |
|---|---|---|---|---|
| ~~`lib_comun/`~~ (retirado en la fusión de la ola 2, C4; estaba en `LIB_COMUN` de `core/env`) | envoltorios de compatibilidad: `biblioteca.py` (el resolutor de `core/py-common/biblioteca.py`), `logger.sh`, `lock.sh`, `detectar_apps.sh`, `backup_rotado.sh` (los de `core/shell-lib/`) | ninguno en código desde la ola 2a (`git -C scripts_for_fuentes grep lib_comun` solo halla sus pruebas); ninguna suite de este repo lo carga | — | la carpeta y los cinco nombres de archivo hasta que `core` retire `LIB_COMUN` (C4 de la ola 2). La API es la de `core/`: `core/docs/consumidores.md` |
| `catalogacion/` (`CATALOGACION_DIR` en `scripts_for_fuentes/ingesta/config.sh`) | el registro de catalogación: `fichas/<calibre_id>_<slug>.md` y `resumen_catalogacion.tsv` | `scripts_for_fuentes` | `scripts_for_fuentes/ingesta/lib/catalogar.py` escribe la ficha con su `calibre_id` y añade filas al TSV; `scripts_for_fuentes/ingesta/lib/cursos_ingestar.sh` prepara filas con las mismas columnas y pide copiarlas aquí | la ruta, el patrón de nombre de la ficha, su frontmatter `tipo: ficha_catalogacion` con `calibre_id` y `proyecto:` como id (normativa 1.10), y las columnas del TSV en este orden: `id · autores · titulo · tipo_zotero · clasificador · editorial · fecha · identificador · idioma · tags · confianza · nota`. El TSV solo crece por el final |
| la puerta de escritura (`lib/escribir.sh`, `lib/escribir.py`, `lib/escribir_zotero.py`) | Calibre cerrado, candado y respaldo verificado antes de escribir; `calibredb_escribe`, `set_campos`, primitivas `z_*` | este repo; `scripts_for_fuentes` tiene la suya (`scripts_for_fuentes/lib/escribir.sh`) hasta la fusión de la fase E | — | las funciones públicas (`puerta_calibre_abrir`, `puerta_zotero_abrir`, `calibredb_escribe`, `puerta_integridad`, `escribir.puerta`, `set_campos`) y que exijan la app cerrada, el candado y el respaldo |
| `LOCK_CALIBRE` y `LOCK_ZOTERO` (`core/env.sh`) | los candados `flock` de todo escritor de `metadata.db` y de `zotero.sqlite`, en `$XDG_STATE_HOME/biblioteca/` | `scripts_for_fuentes` (`ingesta`) y este repo | se toman antes de escribir; ocupado sale 75 | la ruta la fija `core`; el `.lock_calibre_write` de la raíz de este repo quedó sin uso desde la ola 2 (C1) |
| campo `series` de Zotero (y `publicationTitle` en artículos) | lo que escribe `sincronizar-zotero` desde la serie de Calibre (`sincronizar-zotero/README.md`) | `scripts_for_zotero` (`series_organizer`) | agrupa en colecciones por el campo `series`, después del sync; los artículos, cuya serie va a `publicationTitle`, quedan sin agrupar | el nombre del campo y que el sync corra antes |
| `SCRIPTS_CALIBRE` | la raíz de este repo, resuelta por `core/env.sh` y `core/env.py` | todos los anteriores | — | el nombre de la carpeta |
| `KOREADER_RESPALDO_DIR` | el repo de datos de lectura que escribe `koreader/lib/respaldo_koreader.sh` en cada pasada | `koreader-respaldo` | dump de `statistics.sqlite3`, sidecars `hashdocsettings/` e `history.lua`, con commit local | el formato en texto y la exclusión de `settings.reader.lua` (credenciales) |
| `suite.yml` de cada suite | manifiesto según `core/suite.schema.yml` | `core/suites.py`, `meta/INDICE_SCRIPTS.md` | los bloques `suite:`/`suites:` de los README y el índice global | las claves del esquema |

Una interfaz que deja de tener consumidores se retira con una entrada en
[decisiones.md](decisiones.md); mientras tenga uno, `lib_comun/` se conserva aunque no se amplíe.

## Lo que este repo consume

- La biblioteca Calibre (`BIBLIOTECA_DIR`, `CALIBRE_DB`): `core/docs/biblioteca.md`.
- Zotero (`ZOTERO_DB`): solo `sincronizar-zotero` y `lib/adjuntos_zotero.py` lo escriben, por la puerta (`decisiones.md` §2.4 y §2.5).
- `core/` (raíz, logger, candado, respaldo verificado, detección de apps): `core/docs/consumidores.md`.
- La autoridad por dato y la dirección de cada sincronización: `meta/docs/historial/MODELO_METADATOS.md` y
  `meta/docs/historial/SINCRONIZACION.md`.
