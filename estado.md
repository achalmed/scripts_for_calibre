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
| 2026-10-05 | Ola 2a, K9: documentación de la fila 13: `estado.md` normativo; `docs/decisiones.md` en `### §N.M` sin «Pendientes» (los abiertos, aquí abajo); `CLAUDE.md` bajo las 100 líneas (`wc -l CLAUDE.md`) y sin resumir `docs/`; README raíz, de suites y de `docs/` al día con la puerta, `systemd/`, `tests/` y los respaldos fuera del repo; `metadatos_calibre` sin `logger.sh` propio (`lib/sesion.sh` + el de `core`) y con `set -euo pipefail`; `pruebas:` en los `suite.yml` que escriben; bloques regenerados con las funciones de `core/suites.py` solo en este repo | validador: 0 fallos (antes 90) |
| 2026-10-05 | Ola 2a, K8: `script_normalizacion_metadatos` (11 campañas cerradas) sale del árbol al historial de git (se lee en `467c8a7`); los respaldos de dentro del repo (1,0 GB: `normalizacion_metadatos/backups` 820 MB, `ecosistema_lectura/backups`, `koreader_estudio/backups`, `sincronizar_zotero/estado/backups`) se copiaron a `$RESPALDOS_DIR/biblioteca/<suite>/` con `SHA256SUMS` verificado y los originales se movieron a `~/.local/share/residuos-programa/2026-10-05/scripts_for_calibre/` (verificados también); nada se borró. Las primitivas SQL de Zotero pasan a `lib/escribir_zotero.py`: ningún archivo que nombre `metadata.db` lleva SQL que modifique (RQ-PRE-06 parte D = 0 en el repo) | `tests/test_puerta.py` sin exclusiones |
| 2026-10-05 | Ola 2a, K7: el correo del «polite pool» de Crossref sale de `script_verificar_metadatos/config.sh` a la variable `CROSSREF_MAILTO` (P227, P14); las 86 fichas del programa citan `proyecto: meta` (id, normativa 1.10) y la fase en `uso:` (RQ-BIB-04: 86 → 0) | `tests/test_privacidad_k7.py` |
| 2026-10-05 | Ola 2a, K6: los seis `config.sh` cargan `core/env.sh` (sin `$HOME/Documents/biblioteca` de respaldo, P217/P4); los tres timers como plantillas en `systemd/` con `%h`, `SuccessExitStatus=75` y PATH sin anaconda (P221/P8), instaladas por `systemd/instalar.sh` (simula por defecto; `--verificar` compara lo instalado con la plantilla); lecturas de SQLite y Python con `CORE_PYTHON` (`lib/leer.sh`), sin el `sqlite3` de anaconda; el estado de `ecosistema_lectura` y `sincronizar_zotero` fuera del repo; ninguna suite usa ya `lib_comun/` | `tests/test_entorno_k6.py` (`systemd-analyze --user verify`, corridas con el PATH de los timers) |
| 2026-10-05 | Ola 2a, K5: `catalogacion_biblioteca --aplicar` y `metadatos_calibre register` escriben por la puerta (cierra P1: ahora toman el candado y respaldan); `metadatos_calibre` simula por defecto y `--aplicar` escribe (cierra P2); la catalogación usa la detección canónica de Calibre abierto; `test_puerta.py` sin pendientes | `tests/test_escritores_k5.py`, `tests/test_puerta.py` |
| 2026-10-05 | Ola 2a, K4: un solo `lib/adjuntos_zotero.py` (`rutas`, `titulos`, `autores`, `verificar`) en lugar de los diez `aplicar_zotero.py` de las campañas: simula por defecto; con `--aplicar`, Zotero cerrado, `LOCK_ZOTERO` y respaldo verificado por la puerta; tras reescribir, 0 rutas nuevas rotas o sale 1 (hoy, en una copia, 21 adjuntos ya rotos: dato para 2b, RQ-BIB-03) | `tests/test_adjuntos_zotero.py` |
| 2026-10-05 | Ola 2a, K3: `sincronizar_zotero` sin SQL sobre `metadata.db`: columnas por etiqueta, plan de Calibre aplicado por la API (`escribir.py aplicar-plan`), Zotero por las primitivas de la puerta, respaldos verificados de ambas bases por la puerta (fuera el respaldo propio sin verificar, P143); corrige el relleno de `pubdate` (title_sort); OPF solo de los libros cambiados | caracterización idéntica sobre la copia perturbada y la orquestación de las 04:30; `test_sincronizar_zotero_relleno_de_fecha` pasa |
| 2026-10-05 | Ola 2a, K2: una sola puerta de escritura, `lib/escribir.sh` y `lib/escribir.py` (Calibre cerrado, candado `LOCK_CALIBRE`/`LOCK_ZOTERO`, respaldo verificado en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/`, `calibredb` o la API); `ecosistema_lectura` y `koreader_estudio` (sync, `--enlazar`, `--apuntes`, columnas) ya pasan por ella; `verificar_metadatos` lee en solo lectura | `tests/test_puerta.py`, `tests/test_escribir.py`; la caracterización sigue igual |
| 2026-10-05 | Ola 2a, K1: caracterización de los tres sincronizadores vivos (simulación y `--aplicar`) contra copias de `metadata.db` y `zotero.sqlite`, comparada con la referencia `467c8a7`; fija el defecto del relleno de `pubdate` (xfail estricto) | `python3 -m pytest scripts_for_calibre/tests` (< 2 min) |

## En curso

nada en curso

## Por hacer

- 2026-10-05 · **Reinstalar los tres timers desde `systemd/`** (dueño: el director, fase E de la ola 2): `systemd/instalar.sh --aplicar` y después `systemd/instalar.sh --verificar` = 0; hasta entonces corren las unidades viejas (PATH con anaconda), que siguen funcionando con el código nuevo.
- 2026-10-05 · **Residuos de la ola 2a** (dueño: el director, con la copia 3): `~/.local/share/residuos-programa/2026-10-05/scripts_for_calibre/` guarda los respaldos movidos (con su `*.SHA256SUMS`) y el `.lock_calibre_write` vacío; la copia externa está en `$RESPALDOS_DIR/biblioteca/{normalizacion_metadatos,ecosistema_lectura,koreader_estudio,sincronizar_zotero}/`. Nada se borra antes de la copia 3.
- 2026-10-05 · **Estado viejo dentro del repo** (dueño: el director, después de la orquestación de las 04:30 del 2026-10-06): `script_ecosistema_lectura/estado/` (la marca, que la orquestación copia sola a `$XDG_STATE_HOME/biblioteca/ecosistema_lectura/`) y `script_sincronizar_zotero/estado/ultimo_sync.json` quedan sin uso; van a residuos cuando la marca nueva exista.
- 2026-10-05 · **`meta/INDICE_SCRIPTS.md` desfasado** (dueño: el director): `python3 core/suites.py generar --aplicar` (sale `normalizacion_metadatos`, cambian `metadatos_calibre` y los `depende_de`); aquí se regeneraron solo los bloques de este repo.
- 2026-10-05 · **21 adjuntos de Zotero que no resuelven** (dueño: el director y el autor, ola 2b, P9): `lib/adjuntos_zotero.py verificar` los lista sobre una copia; RQ-BIB-03.
- 2026-10-05 · **`reportes/` no rota solo** (dueño: la higiene del programa; antes P6): la poda de más de 30 días la hace una fase de higiene.
- 2026-10-05 · **Rutas de máquina en la sección «Origen» de muchas fichas** (dueño: `scripts_for_fuentes/ingesta`, la herramienta que las escribe; antes P9): son registro y se limpian con esa herramienta, no a mano.
- 2026-10-05 · **Filas sin ficha** (dueño: el autor; antes P10): 10423–10425 están en `resumen_catalogacion.tsv` y no en `fichas/`.
- 2026-10-05 · **Ayuda de CLI fuera de la norma de idioma** (dueño: agente «calibre», ola 2b o la fusión; antes P11): `script_metadatos_calibre` (en inglés, también `script_verificar_metadatos/lib/db.sh`), `script_sincronizar_zotero` y `script_verificar_metadatos` (sin tildes).
- 2026-10-05 · **La campaña `zotero_alta_2026-09-30` no se aplicó** (dueño: el autor; antes P12): manda a la papelera de Zotero la segunda importación del RIS de `--enlazar`; vive en la historia (`467c8a7`); si se quiere, se rehace como migración de la ola 2b por `lib/adjuntos_zotero.py` y la puerta.
- 2026-10-05 · **Nombres de carpeta fuera de kebab-case** (dueño: el director, fase E): `script_*` y la raíz (RQ-IDN-03, 7 avisos) cambian con la fusión y la reorganización de `scripts-biblioteca`.

## Futuro

- Fase 5 del diseño del ecosistema de lectura (exportar sesiones de KOReader al registro de Ethereal Style): opcional, no planificada (antes P5).
- Fusión con `scripts_for_fuentes` y renombre a `scripts-biblioteca` (fase E de la ola 2, la hace el director).
