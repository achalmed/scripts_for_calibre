---
tipo: doc
titulo: "Consumidores de scripts_for_calibre: lo que otros repos usan de aquí y lo que no se cambia sin avisarles"
estado: activo
---
# Consumidores de `scripts_for_calibre`

Referencia de la frontera (NORMATIVA §15.6): qué ofrece este repo a otros, quién lo usa y qué no se
puede renombrar, mover ni cambiar de forma sin actualizar al consumidor en el mismo ciclo. El
contrato vive aquí; cada consumidor lleva un puntero a esta página.

## Lo que ofrece y quién lo usa

| interfaz | qué es | consumidor | dónde lo usa | no se cambia sin avisar |
|---|---|---|---|---|
| `lib_comun/` (`LIB_COMUN` en `core/env.sh` y `core/env.py`) | envoltorios de compatibilidad: `biblioteca.py` (el resolutor de `core/py-common/biblioteca.py`), `logger.sh`, `lock.sh`, `detectar_apps.sh`, `backup_rotado.sh` (los de `core/shell-lib/`) | `scripts_for_fuentes` | `scripts_for_fuentes/ingesta/main.sh`, `scripts_for_fuentes/ingesta/lib/catalogar.py` y `desde_bib.py`, `scripts_for_fuentes/ingesta_cursos/main.sh` y `scripts_for_fuentes/ingesta_cursos/lib/biblioteca.py`, y los `config.py` de la raíz de `scripts_for_fuentes` y de sus `fichas/`, `manifiesto/` y `lecturas/` | la carpeta y los cinco nombres de archivo. La API es la de `core/` (`existe`, `ruta`, `datos`, `texto`…): su contrato está en `core/docs/consumidores.md` |
| `CATALOGACION_DIR` = `script_catalogacion_biblioteca/` | el registro de catalogación: `fichas/<calibre_id>_<slug>.md` y `resumen_catalogacion.tsv` | `scripts_for_fuentes` | `scripts_for_fuentes/ingesta/lib/catalogar.py` escribe la ficha con su `calibre_id` y añade filas al TSV; `scripts_for_fuentes/ingesta_cursos/lib/ingestar.sh` prepara filas con las mismas columnas y pide copiarlas aquí | la ruta, el patrón de nombre de la ficha, su frontmatter `tipo: ficha_catalogacion` con `calibre_id`, y las columnas del TSV en este orden: `id · autores · titulo · tipo_zotero · clasificador · editorial · fecha · identificador · idioma · tags · confianza · nota`. El TSV solo crece por el final |
| `.lock_calibre_write` (`LOCK_CALIBRE`) | candado `flock` de todo escritor de `metadata.db` | `scripts_for_fuentes` (`ingesta`, `ingesta_cursos`), `meta/doctor` | las dos suites lo toman antes de escribir en Calibre; el doctor avisa de un candado viejo sin escritor vivo (`meta/doctor/lib/chequeos.sh`) | la ruta del candado y que los escritores de este repo se lancen como `…/scripts_for_calibre/…/main.sh` (el doctor los busca con `pgrep -f "scripts_for_calibre.*main.sh"`) |
| `SCRIPTS_CALIBRE` | la raíz de este repo, resuelta por `core/env.sh` y `core/env.py` | todos los anteriores | — | el nombre de la carpeta |
| `KOREADER_RESPALDO_DIR` | el repo de datos de lectura que escribe `script_koreader_estudio/lib/respaldo_koreader.sh` en cada pasada | `koreader-respaldo` | dump de `statistics.sqlite3`, sidecars `hashdocsettings/` e `history.lua`, con commit local | el formato en texto y la exclusión de `settings.reader.lua` (credenciales) |
| `suite.yml` de cada suite | manifiesto según `core/suite.schema.yml` | `core/suites.py`, `meta/INDICE_SCRIPTS.md` | los bloques `suite:`/`suites:` de los README y el índice global | las claves del esquema |

Una interfaz que deja de tener consumidores se retira con una entrada en
[decisiones.md](decisiones.md); mientras tenga uno, `lib_comun/` se conserva aunque no se amplíe.

## Lo que este repo consume

- La biblioteca Calibre (`BIBLIOTECA_DIR`, `CALIBRE_DB`): `core/docs/biblioteca.md`.
- Zotero (`ZOTERO_DB`): solo `script_sincronizar_zotero` y las campañas lo escriben (`decisiones.md` §2.4).
- `core/` (raíz, logger, candado, respaldo, resolutor): `core/docs/consumidores.md`.
- La autoridad por dato y la dirección de cada sincronización: `meta/MODELO_METADATOS.md` y
  `meta/SINCRONIZACION.md`.
