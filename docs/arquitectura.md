---
tipo: doc
titulo: "Arquitectura: dos adquisiciones, el recorrido de un documento y las piezas que lo mueven"
genero: explicacion
estado: activo
---
# Arquitectura

Cómo está hecho `scripts_for_fuentes`: qué adquiere y qué no, por dónde pasa un documento desde
que se pide hasta que un proyecto lo cita, qué escribe cada suite y de qué depende. Los pasos del
método y el juicio que exige cada uno no están aquí: son de
`prompts/00 metodo/METODO_DOCUMENTAL.md` y de los prompts de `prompts/01 fuentes/`. Este repo es
solo la parte ejecutable de esos pasos.

## 1. Dos adquisiciones, dos sistemas

| | adquiere | destino | sistema |
|---|---|---|---|
| **datos** | series, microdatos, API, geometrías | `02 analysis/data/raw/` y su catálogo | `02 analysis/connectors` |
| **documentos** | normas, informes, libros, artículos, tesis | Calibre (almacén) y Zotero (cita) | **este repo** |

Un artículo y una serie del BCRP no se adquieren, guardan ni citan igual; sí comparten la red con
reintentos, el hash y el modelo de procedencia (URL · fecha · SHA-256), y un mismo informe cita
ambos. Por eso la maquinaria se comparte (§5) y los destinos no. La frontera la fija el dueño de
la capa de datos: `02 analysis/docs/integracion-ecosistema.md` §2 y
`02 analysis/docs/documentos-de-consulta.md`.

Este repo **no** cataloga (la ficha canónica de cada libro la mantiene
`scripts-biblioteca/catalogacion/`), **no** gestiona citas (Zotero) y **no**
guarda copias: la biblioteca es Calibre.

## 2. El recorrido de un documento

```
  referencia («Ley N.° 31143», un DOI, un ISBN…)
        │  main.py verificar (paso 00) · localizar · descargar (paso 01)
        ▼
  entrada/   zona de aterrizaje; su procedencia, en fuentes_descargadas.tsv
        │  ingesta/main.sh recibir → identificar → catalogar → zotero → archivar (pasos 02–03)
        │                  (ocr · paquetes · bib, según el caso)
        ▼
  Calibre (almacén)  +  .ris para Zotero (referencia)
        │  fichas/ (pasos 05 y 09) · lecturas/ (paso 07) · manifiesto/ (paso 09)
        ▼
  el proyecto: fuentes.yml + fuentes/fichas/ + references.bib
```

`ingesta` no solo lee `entrada/`: también barre como raíces de entrada `02 analysis/data/raw` y
`03 writing` (`INBOX_RAICES` de `ingesta/config.sh`), restringidas a PDF bajo carpetas de fuentes
(`INBOX_RAICES_SOLO`). Así un documento que nació en otro sistema se cataloga donde está, sin
copiarlo a una zona de paso.

### Archivar: qué queda en el origen

`archivar` borra el original solo después de comprobar, byte a byte, que la copia de Calibre es
idéntica, y lo hace en uno de tres modos (`ARCHIVAR_MODO` de `ingesta/config.sh`):

| modo | qué queda en el origen | cuándo |
|---|---|---|
| `manifiesto` | nada; una entrada en el `fuentes.yml` de su proyecto | el modo por defecto, en toda raíz externa |
| `mover` | nada, y sin manifiesto | `entrada/`: nadie necesita la ruta después |
| `enlace` | un enlace simbólico a la copia de Calibre | solo por compatibilidad con proyectos anteriores |

Un archivo de `entrada/` se borra sin manifiesto aunque el modo sea `manifiesto` (lo detecta
`ingesta/lib/archivar.py` por la ruta): el proyecto que lo usa hace el suyo con
`manifiesto/main.py generar --bib`. Quien necesite la ruta física la pide al resolutor
(`manifiesto/main.py ruta`), nunca la escribe.

## 3. Qué escribe cada suite

| suite | paso del método | escribe | contrato |
|---|---|---|---|
| `fuentes` (raíz) | 00, 01 | `entrada/<archivo>` y `fuentes_descargadas.tsv`; nada más | `suite.yml` |
| `ingesta` | 02, 03 | Calibre por `calibredb`; `ingesta/ingesta.tsv`, `pendientes.tsv`, fichas provisionales en `ingesta/fichas/`, RIS en `ingesta/salida_ris/`; la ficha con id y la fila de `resumen_catalogacion.tsv` en `scripts-biblioteca/catalogacion/`; el `fuentes.yml` del proyecto al archivar | `ingesta/README.md` |
| `ingesta cursos` (fundida en `ingesta`, ola 2 F3) | 02 (cursos) | Calibre por la puerta; `bibliografia:` del `curso.yml` del curso; `ingesta/reportes/cursos/`; retira el original del curso a `ORIGINALES_DIR` (`$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos`) | `ingesta/README.md` §Cursos |
| `fichas` | 05, 09 | el frontmatter de las fichas del proyecto (`verificacion.*`, `calibre_id`, `zotero_key`) y `00-indice_fichas.md` | `fichas/README.md` |
| `lecturas` | 07 | `<clave>-lectura-extraida.md` en la carpeta de destino; al reejecutar regenera solo lo que está entre sus marcas | `lecturas/README.md` |
| `manifiesto` | 09 | el `fuentes.yml` del proyecto (conserva `clave_bibtex`, `uso` y `nota`), el bloque generado de `references.bib`; con `quitar-enlaces`, borra los enlaces simbólicos hacia la biblioteca que el manifiesto ya cubre | `manifiesto/README.md` |

Todas simulan sin `--aplicar`. Ninguna edita `metadata.db` ni `zotero.sqlite`: Calibre se escribe
solo por `calibredb` a través de la puerta `lib/escribir.sh`/`lib/escribir.py` (Calibre cerrado, candado,
respaldo verificado fuera del repo; ola 2, F2); Zotero se alimenta por RIS. Las suites que
leen un libro (`fichas`, `lecturas`, `manifiesto`, `verificar`) lo hacen por el resolutor y no
escriben en Calibre.

## 4. Las verdades propias: dos ledgers

Lo único que este repo sabe y nadie más guarda son dos registros tabulares:

- `fuentes_descargadas.tsv`: qué se descargó, de qué fuente y URL, con qué hash y con qué nombre
  quedó en `entrada/`.
- `ingesta/ingesta.tsv`: de cada documento ingerido, su SHA-256, su origen, el `calibre_id`, la
  ruta en Calibre, la `zotero_key` y el estado (`catalogado`, `archivado`).

`main.py verificar --archivo` los consulta además de Calibre: responde si un archivo ya se
descargó o se catalogó aunque el título no coincida. Calibre renombra la carpeta de un libro
cuando cambian su título o su autor; por eso `archivar` refresca las rutas del ledger por id antes
de tocar nada, y el `.ris` de `zotero` se construye desde Calibre tal como está, no desde las
columnas del ledger.

Las rutas de `ingesta.tsv` son relativas a la raíz del workspace (o a la zona de entrada) desde la ola 2
(F5; `lib/rutas.py`).

Un tercer registro es **dato, no suite**: `manifiestos/marco_legal/` guarda el manifiesto del marco legal
(`manifiesto.tsv`, `no_localizados.tsv`, `fallidos.tsv` y los `parciales/` de los que se rearma) que
`ingesta` lee para titular y seriar las normas. No tiene `suite.yml` ni se ejecuta en el recorrido; sus dos
generadores solo lo rearman sobre una carpeta local (`MARCO_LEGAL`) y `tests/fuentes/test_marco_legal.py` comprueba
que regenerarlo da los mismos archivos. Es del marco legal, no del despacho (§1.4 de las decisiones), y
`manifiesto/` (la suite del `fuentes.yml`, contrato con `02 analysis` y `03 writing`) es otra cosa.

## 5. Maquinaria compartida y dependencias

| pieza | de dónde | para qué |
|---|---|---|
| red con reintentos, SHA-256, bytes mágicos | `core/py-common/red.py` (stdlib puro), por `PY_COMMON` de `config.py` | `lib/comun.py` descarga sin reimplementar nada (ola 2, F4; [decisiones §7.4](decisiones.md)) |
| el resolutor de la biblioteca | `core/py-common/biblioteca.py` | ¿existe?, ruta física, metadatos, texto por páginas (caché en `~/.cache/biblioteca_texto`) |
| logger, lock, detección de apps, backup rotado | `core/shell-lib` | la puerta `lib/escribir.sh`, para escribir en Calibre sin pisarse |
| raíz del espacio de trabajo | `core/env.sh` | `ingesta/config.sh` lo carga |
| la ficha de catalogación canónica | `scripts-biblioteca/catalogacion/` | `catalogar` escribe allí la ficha con id y su fila |

El contrato de lo que este repo consume lo escribe cada proveedor: `core/docs/consumidores.md`,
`scripts-biblioteca/docs/consumidores.md` y `02 analysis/docs/integracion-ecosistema.md` §2.

Las suites cargan `core/` directamente (ya no el envoltorio `scripts-biblioteca/lib_comun/`; ola 2,
F2 y F5) y toman la raíz de `core/env.py`. Los ledgers guardan rutas relativas a esa raíz (`lib/rutas.py`). `prompts/01 fuentes/` no es una dependencia de código, pero sí de
criterio: el mapeo RIS sigue `prompt_03_zotero.md` y la ficha provisional, `prompt_02_catalogar.md`.

## 6. Consumidores

Lo que otros repositorios usan de este y no puede cambiar sin avisarles. Cada uno lleva un puntero
aquí, no una copia.

| consumidor | qué usa | qué no cambia sin aviso |
|---|---|---|
| `02 analysis` (`02 analysis/pipeline/lib_proc/fuentes.py`, y a través de él `02 analysis/pipeline/documentos/main.py`) | el módulo `manifiesto/lib/manifiesto.py`, cargado **por ruta** desde `SCRIPTS_FUENTES` de `core/env.py`: `cargar(raiz)` (un diccionario con la lista `fuentes`) y `ruta(raiz, clave)` (la ruta física por el resolutor, o nada); el `fuentes.yml` de `02 analysis/data/raw/` | la ruta y el nombre del módulo; las dos funciones y su firma; las claves de cada entrada (`CLAVES_ENTRADA` de `manifiesto/config.py`, en especial `origen` y `anexo`); que `manifiesto/lib/` siga sin `__init__.py`, por eso se carga por ruta y no como paquete |
| `03 writing` (`03 writing/reporting/entorno.py`, función `manifiesto()`) | el mismo módulo, por la misma vía | lo mismo |
| `03 writing` (proyectos) | `manifiesto/main.py bib <carpeta>`: admite la carpeta del proyecto o su `fuentes/`; escribe el bloque generado de `<proyecto>/references.bib` y la `clave_bibtex` del manifiesto. El `fuentes.yml` va donde dicta `REGLAS_RAIZ` (`fuentes/` en un proyecto de la estructura única). `fichas` escribe en la carpeta de fichas del proyecto (fuentes/fichas/) el frontmatter y `00-indice_fichas.md`; `lecturas` lee el `lecturas.yml` del proyecto y escribe `<clave>-lectura-extraida.md` en su `destino` | el comando y sus opciones; el nombre del manifiesto; los nombres de archivo que escriben `fichas` y `lecturas`; las marcas de los bloques generados |
| `10 Class` (cursos de `10 Class/docencia`) | `ingesta/main.sh cursos` (antes `ingesta_cursos`) lee `docencia/cursos/*/05-recursos/` y escribe en `curso.yml` la lista `bibliografia:` con `calibre_id`, `titulo`, `autor`, `origen` y, si hay, `nota` | la carpeta que se escanea y las claves de `bibliografia:` (`10 Class/docs/estandar-docencia.md` las cita) |
| `meta/doctor` (`meta/doctor/lib/chequeos/`) | comprueba que `fichas/main.py` y `lecturas/main.py` existan, que `ingesta/fichas/` no retenga borradores, que ningún script de aquí resuelva rutas de libros por su cuenta, que los `fuentes.yml` cuadren con Calibre (`manifiesto/main.py todo`, que simula) y que no queden enlaces simbólicos hacia la biblioteca en los proyectos | `manifiesto/main.py todo` sin `--aplicar` no escribe y sale con 0 si todo cuadra; las rutas `fichas/main.py`, `lecturas/main.py` y `manifiesto/main.py` |
| `prompts/01 fuentes/` | cada prompt de los pasos 00–09 nombra el comando que lo ejecuta | los nombres de los comandos |

Este repo no importa nada de `02 analysis`: la red viene de `core/py-common/red.py` desde la ola 2 (F4).

La regla que todos cumplen: ningún proyecto escribe su propio descargador ni guarda copias de
documentos; si la fuente no existe todavía, se añade aquí ([ampliar.md](ampliar.md)).
