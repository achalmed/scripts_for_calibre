---
tipo: readme
estado: activo
---
# scripts-biblioteca/ — la biblioteca del ecosistema: adquirir, ingerir, catalogar y fichar fuentes, y mantener coherentes Calibre, KOReader y Zotero

<!-- suite:inicio -->
<!-- suite:fin -->

<!-- suites:inicio -->
<!-- suites:fin -->

Las herramientas de línea de comandos (Bash y Python) alrededor de la biblioteca Calibre (`biblioteca/`, la
autoridad bibliográfica del workspace). Nació en la ola 2 del programa de reingeniería (2026-10-05) de la fusión de
`scripts_for_calibre` y `scripts_for_fuentes`, que compartían la biblioteca, el ledger de catalogación, el candado y
la escritura en `metadata.db` sin compartir código. Hace dos cosas:

- **El Método Documental ejecutable** (`prompts/00 metodo/METODO_DOCUMENTAL.md`): cada paso que toca archivos tiene
  aquí su comando. Descarga documentos (normas, informes, libros, artículos, tesis) con procedencia, los ingiere y
  cataloga en Calibre, los prepara para Zotero, coteja las fichas contra el libro, extrae pasajes con página y
  mantiene el `fuentes.yml` con el que cada proyecto declara qué obras usa. Es el único lugar del ecosistema donde
  se descarga un documento.
- **La coherencia de la biblioteca**: tres timers systemd de usuario la mueven solos (KOReader → Calibre y Zotero →
  Calibre cada 30 minutos; la sincronización bidireccional de metadatos a diario a las 04:30). **Calibre manda** en
  los metadatos bibliográficos, Zotero solo rellena vacíos, y los relojes de lectura de KOReader y de Zotero nunca
  se copian entre sí: Calibre los suma en `#tiempo_estudio`.

Y una sola **puerta de escritura** (`lib/escribir.*`): nada escribe en `metadata.db` ni en `zotero.sqlite` sin la
app cerrada, el candado (`LOCK_CALIBRE`, `LOCK_ZOTERO` de `core/env`) y un respaldo verificado. **No es** la
biblioteca (`biblioteca/`), ni el gestor de citas (Zotero), ni adquiere datos (eso es `02 analysis/connectors`).
Dónde está el repo hoy: [`estado.md`](estado.md).

## Uso

Todo simula por defecto; `--aplicar` escribe. Lo que escribe en Calibre exige Calibre cerrado (y Zotero cerrado lo
que escribe en Zotero).

```bash
cd ~/Documents/scripts-biblioteca
# Método Documental
python3 main.py verificar "Ley N.° 31143"             # paso 00: ¿ya está en la biblioteca?
python3 main.py localizar congreso "Ley N.° 31143"    # paso 01: la URL, sin descargar
python3 main.py descargar congreso --lista normas.txt # a entrada/, con hash y ledger
ingesta/main.sh identificar                           # paso 02: pendientes.tsv + ficha provisional
ingesta/main.sh catalogar --aplicar                   # a Calibre por la puerta
ingesta/main.sh zotero                                # paso 03: .ris para importar en Zotero
ingesta/main.sh cursos --escanear                     # material externo de los cursos, a TSV
P="../03 writing/reports/<slug>/fuentes"
python3 fichas/main.py verificar "$P/fichas"          # paso 05: cotejo contra el libro
python3 lecturas/main.py "$P/lecturas.yml"            # paso 07: pasajes con página
python3 manifiesto/main.py generar "$P" --aplicar     # paso 09: el fuentes.yml del proyecto
# Coherencia de la biblioteca
koreader/main.sh --aplicar                            # KOReader → Calibre
lectura/main.sh --aplicar                             # Zotero → Calibre
lectura/main.sh --metadatos                           # orquesta sincronizar-zotero (simula)
sincronizar-zotero/main.sh --limite 20 --aplicar      # canario de la sync; ambas apps cerradas
verificacion/main.sh --limite 5                       # solo lectura: discrepancias en reportes/
catalogacion/main.sh --ids 10265,10266                # simula esas filas; --aplicar escribe
metadatos-pdf/main.sh embed --root "$BIBLIOTECA_DIR"  # simula; --aplicar modifica los PDF
lib/adjuntos_zotero.py verificar                      # adjuntos de Zotero que no resuelven
systemd/instalar.sh                                   # timers: simula; --aplicar instala; --verificar
```

Pruebas, desde `~/Documents` y sobre copias de las bases (nunca las reales): `python3 -m pytest
scripts-biblioteca/tests/calibre` y `python3 -m pytest scripts-biblioteca/tests/fuentes`. Requisitos: Calibre con
`calibredb` y `calibre-debug` en el `PATH`, el Python de `core` (`CORE_PYTHON`), `ocrmypdf` para el OCR y `exiftool`
para `metadatos-pdf`. Qué es automático y qué es manual: [`docs/operacion.md`](docs/operacion.md).

## Estructura

| carpeta | qué es | dueño / generador |
|---|---|---|
| `main.py`, `config.py`, `fuentes/` | suite `fuentes`: `verificar` (paso 00), `localizar` y `descargar` (paso 01), un conector por fuente de documentos; ledger `fuentes_descargadas.tsv` | a mano |
| `entrada/` | zona de aterrizaje de lo descargado, fuera de git | runtime |
| `ingesta/` | de la entrada a Calibre y Zotero: identificar, catalogar, RIS, archivar, OCR, paquetes, cursos; ledger `ingesta.tsv` | a mano |
| `catalogacion/` | aplica `resumen_catalogacion.tsv` a Calibre; `fichas/` y el TSV son el registro canónico (los escribe `ingesta catalogar`) | a mano |
| `fichas/`, `lecturas/`, `manifiesto/` | pasos 05, 07 y 09 sobre las fichas de un proyecto; `manifiesto/` es contrato con `02 analysis` y `03 writing` y no cambia de nombre | a mano |
| `koreader/`, `lectura/`, `sincronizar-zotero/` | la coherencia Calibre ⇄ KOReader ⇄ Zotero; los tres timers | a mano; timers `koreader-calibre-sync`, `ecosistema-lectura`, `ecosistema-metadatos` |
| `verificacion/`, `metadatos-pdf/` | cotejo con OpenLibrary y Crossref (solo lectura); incrustador OPF → PDF | a mano |
| `manifiestos/marco_legal/`, `registro/` | el dato del marco legal y la memoria documental que no es de ninguna herramienta | a mano |
| `lib/` | la puerta de escritura (`escribir.sh`, `escribir.py`, `escribir_zotero.py`), lecturas sin `sqlite3` (`leer.sh`), el escritor de rutas de adjuntos de Zotero (`adjuntos_zotero.py`) y lo común de las suites de fuentes (`comun.py`, `rutas.py`) | a mano |
| `systemd/` | las plantillas de los tres timers y su instalador | a mano; las unidades instaladas son su render |
| `tests/calibre/`, `tests/fuentes/` | caracterización de los sincronizadores contra la referencia de git, la puerta, el entorno y la caja de arena de ingesta, sobre copias | a mano |
| `docs/` | operación, arquitectura, ampliar, consumidores, decisiones e historial | a mano; índice por `core/docs.py indice` |
| `suite.yml` (raíz y uno por suite) | manifiesto de cada suite (`core/suite.schema.yml`) | a mano; los bloques de README los genera `core/suites.py generar --aplicar` |
| `logs/`, `*/reportes/` | registros e informes de cada pasada | runtime, ignorados |

Los respaldos de la puerta y el estado de las suites viven fuera del repo, en `$XDG_STATE_HOME/biblioteca/`
(`docs/decisiones.md` §2.6 y §4.10). Las campañas de normalización de 2026-09 y 2026-10 están en la historia de git
(§4.8); la de `scripts_for_fuentes` antes de la fusión, en su bundle de `$RESPALDOS_DIR/git-bundles/ola-02/`.

## Documentación

El mapa por lector y el índice de `docs/` están en [`docs/README.md`](docs/README.md); cada suite documenta su uso en
su `README.md`; las reglas para el asistente, en [`CLAUDE.md`](CLAUDE.md). Lo que otros repos usan de aquí y no
cambia sin aviso: [`docs/consumidores.md`](docs/consumidores.md) y [`docs/arquitectura.md`](docs/arquitectura.md) §6.

## Límite honesto

- **Escribir exige las apps cerradas**: los timers no fallan por eso (salida 75, «reintentar luego»), reintentan en
  la siguiente pasada.
- **Subir no es catalogar**: `ingesta` deduplica por huella y por título antes de añadir, no inventa grafías de
  autor ni etiquetas, y deja la ficha final a `catalogacion`.
- **Zotero se escribe por SQL directo** (como el plugin ZMI): método no soportado por Zotero; cada ítem tocado queda
  `synced=0` para que la cuenta lo suba. Sin respaldo verificado no se aplica.
- **Título y autor no se escriben en Calibre** por sincronización ni verificación: Zotero enlaza los adjuntos por la
  ruta `Autor/Título (id)`.
- **Los PDF oficiales del Congreso tienen la capa de texto corrupta**: se pasan por `ocrmypdf -l spa`.
- **Solo acceso abierto**: ninguna fuente usa credenciales ni proxies; los portales con WAF (BCRP, SBS) devuelven
  HTML en vez del PDF y se detecta por bytes mágicos.
- **Las pruebas comparan con una referencia de git** sobre una foto del día: un camino que la foto no ejercita lo
  cubren las copias perturbadas, no todos los casos posibles.
- **Los `reportes/` no rotan solos**: la poda la aplica una fase de higiene.
- **Licencia MIT** (`LICENSE`).
