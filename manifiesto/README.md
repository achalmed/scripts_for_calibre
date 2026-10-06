---
tipo: readme
estado: activo
---
# manifiesto/ — el fuentes.yml de cada proyecto en vez de enlaces simbólicos a la biblioteca (paso 09)

<!-- suite:inicio -->
**Suite `manifiesto`** · objetivo *fuentes* · estado *activo* · python · interfaz cli

El fuentes.yml de cada proyecto en vez de enlaces simbólicos a la biblioteca: genera, verifica contra Calibre, resuelve rutas, retira enlaces y escribe el references.bib (APA 7) desde Calibre.

- Escribe en: vault · simula por defecto: sí
- Depende de: python3, core/py-common/biblioteca.py
- Método Documental: paso 09

Comandos:

```bash
main.py generar <carpeta> [--aplicar] [--bib ref.bib --asignar clave=id]
main.py verificar <carpeta>…
main.py ruta <carpeta> <origen|calibre_id> · main.py raiz <archivo>
main.py quitar-enlaces <carpeta> [--aplicar]
main.py bib <carpeta> [--aplicar] [--salida references.bib]
main.py todo [--aplicar]
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suite:fin -->

## Qué es

Regla 1 del Método Documental: un proyecto dice **qué** usa (`calibre_id`, `zotero_key`, `clave_bibtex`), no **dónde**
está. Esta suite construye y mantiene ese manifiesto: lo genera desde los enlaces hacia la biblioteca que aún haya, el
ledger de `ingesta` y el manifiesto previo; lo verifica contra Calibre; resuelve la ruta física para los scripts que la
necesiten; retira los enlaces simbólicos que el manifiesto ya cubre; y escribe el `references.bib` del proyecto (APA 7
vía biblatex) desde Calibre. Lo usan `ingesta` (archivar, paquetes, ocr), `datafw`, `escritura` y el doctor; lo que esos
repositorios usan y no cambia sin aviso está en [`../docs/arquitectura.md`](../docs/arquitectura.md) §6.

## Uso

```bash
cd ~/Documents/scripts_for_fuentes/manifiesto
python3 main.py generar "../../escritura/reports/<slug>/fuentes"                     # simula; --aplicar escribe fuentes.yml
python3 main.py generar "../../escritura/reports/<slug>/fuentes" --bib ref.bib --asignar clave=id   # una entrada por clave del .bib
python3 main.py verificar "../../escritura/reports/<slug>/fuentes"                   # cada entrada existe en Calibre y tiene archivo
python3 main.py ruta "../../escritura/reports/<slug>/fuentes" 10024                  # ruta física por el resolutor; código 1 si no resuelve
python3 main.py quitar-enlaces "../../escritura/reports/<slug>/fuentes" --aplicar    # borra los enlaces que el manifiesto ya cubre
python3 main.py bib "../../escritura/reports/<slug>/fuentes" --aplicar               # references.bib + clave_bibtex en el manifiesto
python3 main.py raiz "../../escritura/reports/<slug>/fuentes/normas/ley.pdf"         # qué carpeta lleva el manifiesto de ese archivo
python3 main.py todo                                                                   # generar en todas las raíces vigiladas; con --aplicar, además verificar
```

## Qué escribe y qué no

| comando | escribe | dónde |
|---|---|---|
| `generar --aplicar` | `fuentes.yml`: `proyecto`, `generado` y una entrada por fuente (origen, calibre_id, zotero_key, clave_bibtex, título, autores, serie, anexo, sha256, uso, nota); conserva `clave_bibtex`, `uso` y `nota` escritos a mano | la raíz que dicta `REGLAS_RAIZ`: `fuentes/` de un informe (o `01_fuentes/` sin migrar), `datafw/data/raw/`, la carpeta de una monografía, ensayo, tesis o artículo; si ninguna aplica, la carpeta del archivo |
| `generar --bib` | lo mismo, una entrada por clave del `.bib`, localizada en Calibre por DOI, URL o título (o fijada con `--asignar clave=id`) | ídem |
| `bib --aplicar` | el bloque generado de `references.bib` (entre marcadores; lo escrito fuera se conserva) y la `clave_bibtex` de cada entrada del manifiesto | `references.bib` en la carpeta del proyecto (la que contiene `fuentes/`, o la del manifiesto si no está en `fuentes/`), o `--salida` |
| `quitar-enlaces --aplicar` | borra los enlaces simbólicos hacia la biblioteca que el manifiesto ya cubre | la carpeta dada |
| `verificar`, `ruta`, `raiz`, y todo sin `--aplicar` | nada | — |

Solo lectura sobre Calibre (`core/py-common/biblioteca.py`); nunca toca `metadata.db` ni los archivos de la biblioteca.

## Estructura

`main.py` (orquestación) · `config.py` (nombre del manifiesto, `REGLAS_RAIZ`, `RAICES_VIGILADAS`, orden de claves, claves
manuales, `SIGLAS` de autores corporativos) · `lib/manifiesto.py` (leer, generar, verificar, resolver) · `lib/bibtex.py`
(BibLaTeX desde Calibre: tipo por `#item_type`/`#clasificador`, `shortauthor` con la sigla, `shorttitle` con el número
de la norma).

## Límite honesto

- **No sabe para qué usa el proyecto cada fuente**: `uso` y `nota` se escriben a mano; `generar` solo los conserva.
- **Sin año en Calibre, APA escribe «s. f.»**: `bib` avisa y se corrige `pubdate` en Calibre, nunca en el `.bib`.
- **Informes y libros se fechan por año** (calibredb guarda 01-02 UTC al fijar solo el año); la fecha completa, solo en normas.
- **Siglas cerradas**: solo las de `config.SIGLAS`; una institución sin sigla se cita entera (`prompts/00 metodo/normas_apa7.md` §7; su equivalente en el `.bib`, §14).
- **El modo `enlace` es del pasado**: el resolutor da la ruta; si un script sigue leyendo un enlace simbólico, es deuda de
  ese script, no de esta suite.
- **`todo` recorre solo `RAICES_VIGILADAS`** (`entrada/`, `datafw/data/raw`, `escritura`): un proyecto fuera de ahí
  se genera a mano.
