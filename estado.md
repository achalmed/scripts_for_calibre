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
| 2026-10-05 | Ola 2a, K6: los seis `config.sh` cargan `core/env.sh` (sin `$HOME/Documents/biblioteca` de respaldo, P217/P4); los tres timers como plantillas en `systemd/` con `%h`, `SuccessExitStatus=75` y PATH sin anaconda (P221/P8), instaladas por `systemd/instalar.sh` (simula por defecto; `--verificar` compara lo instalado con la plantilla); lecturas de SQLite y Python con `CORE_PYTHON` (`lib/leer.sh`), sin el `sqlite3` de anaconda; el estado de `ecosistema_lectura` y `sincronizar_zotero` fuera del repo; ninguna suite usa ya `lib_comun/` | `tests/test_entorno_k6.py` (`systemd-analyze --user verify`, corridas con el PATH de los timers) |
| 2026-10-05 | Ola 2a, K5: `catalogacion_biblioteca --aplicar` y `metadatos_calibre register` escriben por la puerta (cierra P1: ahora toman el candado y respaldan); `metadatos_calibre` simula por defecto y `--aplicar` escribe (cierra P2); la catalogación usa la detección canónica de Calibre abierto; `test_puerta.py` sin pendientes | `tests/test_escritores_k5.py`, `tests/test_puerta.py` |
| 2026-10-05 | Ola 2a, K4: un solo `lib/adjuntos_zotero.py` (`rutas`, `titulos`, `autores`, `verificar`) en lugar de los diez `aplicar_zotero.py` de las campañas: simula por defecto; con `--aplicar`, Zotero cerrado, `LOCK_ZOTERO` y respaldo verificado por la puerta; tras reescribir, 0 rutas nuevas rotas o sale 1 (hoy, en una copia, 21 adjuntos ya rotos: dato para 2b, RQ-BIB-03) | `tests/test_adjuntos_zotero.py` |
| 2026-10-05 | Ola 2a, K3: `sincronizar_zotero` sin SQL sobre `metadata.db`: columnas por etiqueta, plan de Calibre aplicado por la API (`escribir.py aplicar-plan`), Zotero por las primitivas de la puerta, respaldos verificados de ambas bases por la puerta (fuera el respaldo propio sin verificar, P143); corrige el relleno de `pubdate` (title_sort); OPF solo de los libros cambiados | caracterización idéntica sobre la copia perturbada y la orquestación de las 04:30; `test_sincronizar_zotero_relleno_de_fecha` pasa |
| 2026-10-05 | Ola 2a, K2: una sola puerta de escritura, `lib/escribir.sh` y `lib/escribir.py` (Calibre cerrado, candado `LOCK_CALIBRE`/`LOCK_ZOTERO`, respaldo verificado en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/`, `calibredb` o la API); `ecosistema_lectura` y `koreader_estudio` (sync, `--enlazar`, `--apuntes`, columnas) ya pasan por ella; `verificar_metadatos` lee en solo lectura | `tests/test_puerta.py`, `tests/test_escribir.py`; la caracterización sigue igual |
| 2026-10-05 | Ola 2a, K1: caracterización de los tres sincronizadores vivos (simulación y `--aplicar`) contra copias de `metadata.db` y `zotero.sqlite`, comparada con la referencia `467c8a7`; fija el defecto del relleno de `pubdate` (xfail estricto) | `python3 -m pytest scripts_for_calibre/tests` (< 2 min) |

## En curso

- 2026-10-05 · ola 2a, K7: privacidad (correo a variable; fichas con `proyecto:` por id) (dueño: agente «calibre»)

## Por hacer

- 2026-10-05 · K7–K9 de la ola 2a (dueño: agente «calibre»): ver el encargo.

- 2026-10-05 · **Reinstalar los tres timers desde `systemd/`** (dueño: el director, fase E de la ola 2): `systemd/instalar.sh --aplicar` y después `systemd/instalar.sh --verificar` = 0; hasta entonces corren las unidades viejas (PATH con anaconda), que siguen funcionando con el código nuevo.

## Futuro

- Fusión con `scripts_for_fuentes` y renombre a `scripts-biblioteca` (fase E de la ola 2, la hace el director).
