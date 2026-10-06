---
tipo: estado
estado: activo
actualizado: 2026-10-05
---
# estado.md — scripts-biblioteca

El estado único del repo (normativa-documental §3.2): lo hecho reciente, lo que está en curso y lo pendiente, con
fecha y dueño. Las decisiones vigentes viven en [docs/decisiones.md](docs/decisiones.md). Nació de la fusión de
`scripts_for_calibre` y `scripts_for_fuentes` en la ola 2 (`meta/programa/06-olas/ola-02-reingenieria.md`, §2–§5).

## Hecho

| fecha | qué | dónde se ve |
|---|---|---|
| 2026-10-05 | Ola 2, fase E: **fusión** de `scripts_for_calibre` y `scripts_for_fuentes` en este repo; suites de Calibre con nombre por función (`catalogacion`, `lectura`, `koreader`, `sincronizar-zotero`, `metadatos-pdf`, `verificacion`); una sola puerta de escritura (`lib/escribir.*`, la de K2 con la interfaz de F2); decisiones de fuentes como §5–§8 | `docs/decisiones.md` (nota de fusión); `README.md` |
| 2026-10-05 | Ola 2a, K9: documentación de la fila 13: `estado.md` normativo; `docs/decisiones.md` en `### §N.M` sin «Pendientes» (los abiertos, aquí abajo); `CLAUDE.md` bajo las 100 líneas (`wc -l CLAUDE.md`) y sin resumir `docs/`; README raíz, de suites y de `docs/` al día con la puerta, `systemd/`, `tests/` y los respaldos fuera del repo; `metadatos_calibre` sin `logger.sh` propio (`lib/sesion.sh` + el de `core`) y con `set -euo pipefail`; `pruebas:` en los `suite.yml` que escriben; bloques regenerados con las funciones de `core/suites.py` solo en este repo | validador: 0 fallos (antes 90) |
| 2026-10-05 | Ola 2a, K8: `script_normalizacion_metadatos` (11 campañas cerradas) sale del árbol al historial de git (se lee en `467c8a7`); los respaldos de dentro del repo (1,0 GB: `normalizacion_metadatos/backups` 820 MB, `ecosistema_lectura/backups`, `koreader_estudio/backups`, `sincronizar_zotero/estado/backups`) se copiaron a `$RESPALDOS_DIR/biblioteca/<suite>/` con `SHA256SUMS` verificado y los originales se movieron a `~/.local/share/residuos-programa/2026-10-05/scripts_for_calibre/` (verificados también); nada se borró. Las primitivas SQL de Zotero pasan a `lib/escribir_zotero.py`: ningún archivo que nombre `metadata.db` lleva SQL que modifique (RQ-PRE-06 parte D = 0 en el repo) | `tests/test_puerta.py` sin exclusiones |
| 2026-10-05 | Ola 2a, K7: el correo del «polite pool» de Crossref sale de `verificacion/config.sh` a la variable `CROSSREF_MAILTO` (P227, P14); las 86 fichas del programa citan `proyecto: meta` (id, normativa 1.10) y la fase en `uso:` (RQ-BIB-04: 86 → 0) | `tests/test_privacidad_k7.py` |
| 2026-10-05 | Ola 2a, K6: los seis `config.sh` cargan `core/env.sh` (sin `$HOME/Documents/biblioteca` de respaldo, P217/P4); los tres timers como plantillas en `systemd/` con `%h`, `SuccessExitStatus=75` y PATH sin anaconda (P221/P8), instaladas por `systemd/instalar.sh` (simula por defecto; `--verificar` compara lo instalado con la plantilla); lecturas de SQLite y Python con `CORE_PYTHON` (`lib/leer.sh`), sin el `sqlite3` de anaconda; el estado de `ecosistema_lectura` y `sincronizar_zotero` fuera del repo; ninguna suite usa ya `lib_comun/` | `tests/test_entorno_k6.py` (`systemd-analyze --user verify`, corridas con el PATH de los timers) |
| 2026-10-05 | Ola 2a, K5: `catalogacion_biblioteca --aplicar` y `metadatos_calibre register` escriben por la puerta (cierra P1: ahora toman el candado y respaldan); `metadatos_calibre` simula por defecto y `--aplicar` escribe (cierra P2); la catalogación usa la detección canónica de Calibre abierto; `test_puerta.py` sin pendientes | `tests/test_escritores_k5.py`, `tests/test_puerta.py` |
| 2026-10-05 | Ola 2a, K4: un solo `lib/adjuntos_zotero.py` (`rutas`, `titulos`, `autores`, `verificar`) en lugar de los diez `aplicar_zotero.py` de las campañas: simula por defecto; con `--aplicar`, Zotero cerrado, `LOCK_ZOTERO` y respaldo verificado por la puerta; tras reescribir, 0 rutas nuevas rotas o sale 1 (hoy, en una copia, 21 adjuntos ya rotos: dato para 2b, RQ-BIB-03) | `tests/test_adjuntos_zotero.py` |
| 2026-10-05 | Ola 2a, K3: `sincronizar_zotero` sin SQL sobre `metadata.db`: columnas por etiqueta, plan de Calibre aplicado por la API (`escribir.py aplicar-plan`), Zotero por las primitivas de la puerta, respaldos verificados de ambas bases por la puerta (fuera el respaldo propio sin verificar, P143); corrige el relleno de `pubdate` (title_sort); OPF solo de los libros cambiados | caracterización idéntica sobre la copia perturbada y la orquestación de las 04:30; `test_sincronizar_zotero_relleno_de_fecha` pasa |
| 2026-10-05 | Ola 2a, K2: una sola puerta de escritura, `lib/escribir.sh` y `lib/escribir.py` (Calibre cerrado, candado `LOCK_CALIBRE`/`LOCK_ZOTERO`, respaldo verificado en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/`, `calibredb` o la API); `ecosistema_lectura` y `koreader_estudio` (sync, `--enlazar`, `--apuntes`, columnas) ya pasan por ella; `verificar_metadatos` lee en solo lectura | `tests/test_puerta.py`, `tests/test_escribir.py`; la caracterización sigue igual |
| 2026-10-05 | Ola 2a, K1: caracterización de los tres sincronizadores vivos (simulación y `--aplicar`) contra copias de `metadata.db` y `zotero.sqlite`, comparada con la referencia `467c8a7`; fija el defecto del relleno de `pubdate` (xfail estricto) | `python3 -m pytest scripts_for_calibre/tests` (< 2 min) |
| 2026-10-05 | Ola 2 (fuentes), F1: caracterización en una caja de arena (copia de `metadata.db` en solo lectura, entorno aislado): `ingesta` (recibir, identificar, catalogar simulado y aplicado en la copia, ocr, paquetes), `ingesta_cursos` (escaneo y simulación), `verificar`, `manifiesto` (carga por ruta, `cargar`, `ruta`, `bib` en seco) y `fichas validar` | `python3 -m pytest -q` (tests/) |
| 2026-10-05 | Ola 2 (fuentes), F2: puerta de escritura `lib/escribir.sh` + `lib/escribir.py` (core/shell-lib o 69; Calibre cerrado y candado o 75; respaldo verificado fuera del repo, `$RESPALDOS_DIR/biblioteca/fuentes/metadata`, o 74); `catalogar`, `ocr`, `paquetes` y `ingesta_cursos --aplicar` pasan por ella; `ingesta` e `ingesta_cursos` sin `lib_comun`; `ingesta/main.sh` con `set -euo pipefail` | `tests/test_puerta.py` |
| 2026-10-05 | Ola 2, C3 (en `core`, commit 12dc8a5): `core/py-common/red.py` (descarga con hash, reintentos, agente de usuario, validación por bytes con `%PDF-`; intermedios TLS por `RED_INTERMEDIOS`); falta documentarlo en `core` (README, consumidores, CHANGELOG): lo hace el director | `core/tests/test_red.py` |
| 2026-10-05 | Ola 2 (fuentes), F4: la red sale de `core/py-common/red.py`; ningún código importa `02 analysis/connectors` (la arista hacia `datafw` desaparece: pedido al director para el manifiesto y la excepción E5); `descargar` comprueba `%PDF-` | `tests/test_red_fuentes.py`; [decisiones §3.4](docs/decisiones.md) |
| 2026-10-05 | Ola 2 (fuentes), F3: `ingesta_cursos` fundida en `ingesta/main.sh cursos` (`--escanear`, `--dry-run`, `--aplicar` por la puerta); fuera `ingesta_cursos/lib/biblioteca.py`; simular ya no deja informes; `ORIGINALES_DIR` en `$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos`; respaldos del repo copiados y verificados a `$RESPALDOS_DIR/biblioteca/fuentes/` y movidos a residuos | `tests/test_ingesta_cursos.py`; [decisiones §2.8](docs/decisiones.md) |
| 2026-10-05 | Ola 2 (fuentes), F5: ledgers con rutas relativas a `DOCS_ROOT` (2 220 celdas: 710 de `ingesta.tsv`, 1 510 de `pendientes.tsv`; solo la forma) y `lib/rutas.py` para leerlas y escribirlas; correo de Unpaywall a `FUENTES_CORREO_CONTACTO` (P248); nada carga `lib_comun` ni la carpeta personal; `fichas grafia`/`migrar` respaldan fuera del repo (P240); `manifiesto todo` en seco idéntico antes y después | `tests/test_privacidad_rutas.py`; [decisiones §3.5](docs/decisiones.md) |
| 2026-10-05 | Ola 2 (fuentes), F6: las 812 fichas provisionales sin rastrear, clasificadas por cabecera y ledger: 0 confirmadas (ninguna corresponde a una obra de `ingesta.tsv` con `calibre_id`), 35 sustituidas y 777 sin obra; copiadas con `SHA256SUMS` verificado a `$RESPALDOS_DIR/biblioteca/fuentes/ingesta-fichas-provisionales/` y movidas a `~/.local/share/residuos-programa/2026-10-05/scripts_for_fuentes/ingesta-fichas-provisionales/`; la carpeta queda temporal en `.gitignore` | `tests/test_arbol.py`; [decisiones §2.9](docs/decisiones.md) |
| 2026-10-05 | Ola 2 (fuentes), F7: `manifiesto/` conserva nombre, interfaz y salida (`manifiesto todo` en seco idéntico; carga por ruta probada); `manifiestos/marco_legal/` declarado dato en `docs/arquitectura.md` §4, regenerable a idéntico; sus dos generadores con `set -euo pipefail` y sin la carpeta personal | `tests/test_marco_legal.py`, `tests/test_verificar_manifiesto_fichas.py` |
| 2026-10-05 | Ola 2 (fuentes), F8: `estado.md` en la forma de la normativa documental 3.2; `docs/decisiones.md` en `### §N.M`, sin «Pendientes» (pasaron aquí) y con `genero:`; `CLAUDE.md` dentro de su máximo (RQ-DOC-05) y sin resumir `docs/`. Validador: de 4 fallos · 10 avisos a 0 fallos · 2 avisos (RQ-IDN-03, nombres de carpeta: fase E) | `core/archivos.py validar scripts_for_fuentes` |

## En curso

scripts-biblioteca · main · ola 2, fase E (la hace el director, en ventana exclusiva con los timers parados) ·
siguiente paso: renombre de la carpeta, reinstalación de los timers y cierre de la 2a.

## Por hacer

- 2026-10-05 · **Reinstalar los tres timers desde `systemd/`** (dueño: el director, fase E de la ola 2): `systemd/instalar.sh --aplicar` y después `systemd/instalar.sh --verificar` = 0; hasta entonces corren las unidades viejas (PATH con anaconda), que siguen funcionando con el código nuevo.
- 2026-10-05 · **Residuos de la ola 2a** (dueño: el director, con la copia 3): `~/.local/share/residuos-programa/2026-10-05/scripts_for_calibre/` guarda los respaldos movidos (con su `*.SHA256SUMS`) y el `.lock_calibre_write` vacío; la copia externa está en `$RESPALDOS_DIR/biblioteca/{normalizacion_metadatos,ecosistema_lectura,koreader_estudio,sincronizar_zotero}/`. Nada se borra antes de la copia 3.
- 2026-10-05 · **Estado viejo dentro del repo** (dueño: el director, después de la orquestación de las 04:30 del 2026-10-06): `lectura/estado/` (la marca, que la orquestación copia sola a `$XDG_STATE_HOME/biblioteca/ecosistema_lectura/`) y `sincronizar-zotero/estado/ultimo_sync.json` quedan sin uso; van a residuos cuando la marca nueva exista.
- 2026-10-05 · **`meta/INDICE_SCRIPTS.md` desfasado** (dueño: el director): `python3 core/suites.py generar --aplicar` (sale `normalizacion_metadatos`, cambian `metadatos_calibre` y los `depende_de`); aquí se regeneraron solo los bloques de este repo.
- 2026-10-05 · **21 adjuntos de Zotero que no resuelven** (dueño: el director y el autor, ola 2b, P9): `lib/adjuntos_zotero.py verificar` los lista sobre una copia; RQ-BIB-03.
- 2026-10-05 · **`reportes/` no rota solo** (dueño: la higiene del programa; antes P6): la poda de más de 30 días la hace una fase de higiene.
- 2026-10-05 · **Rutas de máquina en la sección «Origen» de muchas fichas** (dueño: `scripts_for_fuentes/ingesta`, la herramienta que las escribe; antes P9): son registro y se limpian con esa herramienta, no a mano.
- 2026-10-05 · **Filas sin ficha** (dueño: el autor; antes P10): 10423–10425 están en `resumen_catalogacion.tsv` y no en `fichas/`.
- 2026-10-05 · **Ayuda de CLI fuera de la norma de idioma** (dueño: agente «calibre», ola 2b o la fusión; antes P11): `metadatos-pdf` (en inglés, también `verificacion/lib/db.sh`), `sincronizar-zotero` y `verificacion` (sin tildes).
- 2026-10-05 · **La campaña `zotero_alta_2026-09-30` no se aplicó** (dueño: el autor; antes P12): manda a la papelera de Zotero la segunda importación del RIS de `--enlazar`; vive en la historia (`467c8a7`); si se quiere, se rehace como migración de la ola 2b por `lib/adjuntos_zotero.py` y la puerta.
- 2026-10-05 · **Nombres de carpeta fuera de kebab-case** (dueño: el director, fase E): `script_*` y la raíz (RQ-IDN-03, 7 avisos) cambian con la fusión y la reorganización de `scripts-biblioteca`.
- 2026-10-05 · dueño: autor · Decidir las 1 448 filas de `ingesta/pendientes.tsv` (INEI y ESCALE de
  `02 analysis/data/raw`, identificadas en septiembre y nunca catalogadas): catalogarlas (sus borradores
  están en la copia de F6) o quitarlas (§2.9).
- 2026-10-05 · dueño: director · Regenerar `meta/INDICE_SCRIPTS.md` (`core/suites.py generar --aplicar`): la
  suite `ingesta_cursos` ya no existe (§2.8); y en `meta/workspace.yml`, las evidencias de las aristas de
  este repo y la excepción E5 (ver el informe de la ola 2a).
- 2026-10-05 · dueño: director · Documentar `core/py-common/red.py` en `core` (README, consumidores, CHANGELOG)
  y pasar `datafw` a él en la ola 3 (§3.4).
- 2026-10-05 · dueño: director · Alinear la puerta `lib/escribir.*` con la de `scripts_for_calibre` (K2) en la
  fusión: el mismo candado y la misma sede de respaldos (`$RESPALDOS_DIR/biblioteca/`).
- 2026-10-04 · dueño: autor · `identificar` exige el nivel `peru/` al deducir la institución de una ruta de
  `02 analysis/data/raw`, que lo perdió el 2026-09-25.
- 2026-10-04 · dueño: autor · La serie «Informe <slug> - Fuentes» solo se asigna bajo `01_fuentes/`
  (`ingesta/lib/identificar.py`): un PDF bajo la carpeta canónica `fuentes/` de un informe queda sin serie.
- 2026-10-04 · dueño: autor · `lecturas` toma `proyecto:` como ruta relativa a la raíz: un `lecturas.yml` con el
  id del proyecto no resuelve, y con el spec en `fuentes/` el destino por defecto es fuentes/fuentes/fichas.
- 2026-10-04 · dueño: autor · Configuración muerta del CIL: `INBOX_DIRS` e `INBOX_GLOBS` de `ingesta/config.sh`
  nombran subcarpetas que ya no existen y se siguen recorriendo.
- 2026-10-04 · dueño: autor · Los comandos de `ingesta/suite.yml` no muestran `bib --tags/--proyecto/--archivo`
  ni `archivar --mover`.
- 2026-10-04 · dueño: autor · `logs/` está reservada y nadie escribe en ella (`DIR_LOGS` sin uso; las suites
  bash no fijan `LOG_FILE`).
- 2026-10-04 · dueño: autor · Cabeceras que describen lo que ya no es: «Inteligencia Legislativa» en
  `ingesta/main.sh`, `ingesta/config.sh` y `config.py`; el modo `enlace` de `data/raw`; el
  `localizar_normas.py` de `fuentes/congreso/config.py`; el destino de ejemplo de `lecturas/main.py`.
- 2026-10-04 · dueño: autor · `ingesta/lib/cursos_temario_bib.py` reescribe el `curso.yml` y conserva solo los
  comentarios de sus tres primeras líneas.
- 2026-10-03 · dueño: autor · `ingesta/lib/ris.py` busca `core/py-common` por su ubicación si `PY_COMMON` no
  llega del entorno.

## Futuro

- Fase 5 del diseño del ecosistema de lectura (exportar sesiones de KOReader al registro de Ethereal Style): opcional, no planificada (antes P5).
- Fuentes previstas: repositorios de tesis (ALICIA, RENATI), preprints y catálogos de libros.
- La fusión con `scripts_for_calibre` en `scripts-biblioteca` (ola 2, fase E del director).
