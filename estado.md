---
tipo: estado
estado: activo
actualizado: 2026-10-05
---
# estado.md — scripts_for_calibre

El estado único del repo (normativa-documental §3.2): lo hecho reciente, lo que está en curso y lo
pendiente, con fecha y dueño. Las decisiones vigentes viven en [docs/decisiones.md](docs/decisiones.md).
El encargo de la ola 2a es `meta/programa/06-olas/ola-02-reingenieria.md` §2 (K1–K9).

## Hecho

| fecha | qué | dónde se ve |
|---|---|---|
| 2026-10-05 | Ola 2a, K3: `sincronizar_zotero` sin SQL sobre `metadata.db`: columnas por etiqueta, plan de Calibre aplicado por la API (`escribir.py aplicar-plan`), Zotero por las primitivas de la puerta, respaldos verificados de ambas bases por la puerta (fuera el respaldo propio sin verificar, P143); corrige el relleno de `pubdate` (title_sort); OPF solo de los libros cambiados | caracterización idéntica sobre la copia perturbada y la orquestación de las 04:30; `test_sincronizar_zotero_relleno_de_fecha` pasa |
| 2026-10-05 | Ola 2a, K2: una sola puerta de escritura, `lib/escribir.sh` y `lib/escribir.py` (Calibre cerrado, candado `LOCK_CALIBRE`/`LOCK_ZOTERO`, respaldo verificado en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/`, `calibredb` o la API); `ecosistema_lectura` y `koreader_estudio` (sync, `--enlazar`, `--apuntes`, columnas) ya pasan por ella; `verificar_metadatos` lee en solo lectura | `tests/test_puerta.py`, `tests/test_escribir.py`; la caracterización sigue igual |
| 2026-10-05 | Ola 2a, K1: caracterización de los tres sincronizadores vivos (simulación y `--aplicar`) contra copias de `metadata.db` y `zotero.sqlite`, comparada con la referencia `467c8a7`; fija el defecto del relleno de `pubdate` (xfail estricto) | `python3 -m pytest scripts_for_calibre/tests` (< 2 min) |

## En curso

- 2026-10-05 · ola 2a, K4: un solo `adjuntos_zotero.py` (dueño: agente «calibre»)

## Por hacer

- 2026-10-05 · K4–K9 de la ola 2a (dueño: agente «calibre»): ver el encargo; lo que aún no pasa por la puerta está en `PENDIENTES` de `tests/test_puerta.py`.

## Futuro

- Fusión con `scripts_for_fuentes` y renombre a `scripts-biblioteca` (fase E de la ola 2, la hace el director).
