---
tipo: readme
estado: activo
---
# ingesta/ — de la zona de entrada a la biblioteca: identifica, cataloga en Calibre, exporta RIS y archiva en el fuentes.yml del proyecto

<!-- suite:inicio -->
**Suite `ingesta`** · objetivo *fuentes* · estado *activo* · bash · interfaz cli

De la zona de entrada a la biblioteca: identifica, cataloga en Calibre, exporta RIS para Zotero, archiva en el fuentes.yml del proyecto, OCR, paquetes de anexos y el material externo de los cursos.

- Escribe en: calibre, vault, archivos · simula por defecto: sí
- Entrada: scripts_for_fuentes/entrada/
- Depende de: calibredb, exiftool, pdftotext, pdfinfo, core/shell-lib, catalogacion_biblioteca, manifiesto
- Método Documental: pasos 02 y 03

Comandos:

```bash
main.sh recibir · main.sh identificar · main.sh zotero
main.sh catalogar [--aplicar] [--solo REGEX]
main.sh bib <ref.bib> --serie «…» [--tags …] [--proyecto RUTA] [--archivo clave=ruta]
main.sh archivar [--aplicar] [--mover] · main.sh todo [--aplicar]
main.sh paquetes|ocr [--aplicar]
main.sh estado
main.sh cursos --escanear · main.sh cursos [--dry-run] [--tsv ARCHIVO] · main.sh cursos --aplicar [--tsv ARCHIVO]
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suite:fin -->

`scripts_for_fuentes/entrada/` es la zona de aterrizaje: **recibe** documentos y esta suite los
procesa. También barre como raíces de entrada `02 analysis/data/raw` y `03 writing`
(`INBOX_RAICES`, solo PDF bajo carpetas de fuentes). El almacén permanente es
`~/Documents/biblioteca` (Calibre, autoridad bibliográfica) y Zotero guarda las citas. Cada PDF o
DOCX que entra se vuelve un libro de Calibre con metadatos y ficha, y un ítem de Zotero por RIS;
en el proyecto de origen queda solo su entrada en el `fuentes.yml` (modos de archivar:
`../docs/arquitectura.md` §2). Fronteras con `02 analysis`:
`02 analysis/docs/integracion-ecosistema.md` §2.

## Uso

Simulación por defecto; `--aplicar` escribe. Desde esta carpeta:

```
./main.sh recibir                     ¿qué hay en la zona de entrada sin catalogar?
./main.sh identificar                 clasifica → pendientes.tsv + fichas/<sha8>_<slug>.md
./main.sh catalogar [--solo REGEX]    simula; --aplicar escribe en Calibre (Calibre cerrado)
./main.sh zotero                      salida_ris/ingesta_<fecha>.ris, desde Calibre
./main.sh archivar [--aplicar]        retira el original y lo registra (ARCHIVAR_MODO; --mover borra sin manifiesto en esa corrida)
./main.sh paquetes [--aplicar]        anexos de un paquete → data/ del documento principal
./main.sh ocr [--aplicar]             X.ocr.pdf, X_ocr_buscable.pdf, X_texto.pdf → formato de X
./main.sh bib <references.bib> --serie "…" [--tags "…"] [--proyecto RUTA] [--archivo clave=ruta …]
                                      paso 02 de un trabajo de 03 writing, desde su .bib (entrada/<clave>.pdf o --archivo)
./main.sh todo [--aplicar]            recibir → … → archivar → paquetes → estado
./main.sh estado                      ledger y chequeos (el comando por defecto)
```
La ayuda es `./main.sh <comando> -h`. Antes de `catalogar --aplicar` se revisa `pendientes.tsv`:
lo que queda por debajo de `CONFIANZA_MINIMA_AUTO` (`config.sh`) se omite hasta revisar su ficha
con `prompts/01 fuentes/prompt_02_catalogar.md`. Un escaneado sin texto necesita OCR previo
(`02 analysis/pipeline/documentos/main.py ocr`; lo del Congreso, `ocrmypdf -l spa`).

## Estructura

| ruta | qué es |
|---|---|
| `main.sh` | orquestación: un comando por paso; con `--aplicar`, abre la puerta de escritura antes de tocar Calibre |
| `config.sh` | todo lo editable: raíces de entrada, series, instituciones, siglas, etiquetas por carpeta, paquetes, modo de archivar, confianza mínima |
| `lib/identificar.py` | clasifica y extrae metadatos (solo lectura) → `pendientes.tsv` y fichas provisionales |
| `lib/catalogar.py` | alta en Calibre y registro en `catalogacion` (ficha con id + fila) |
| `lib/ris.py` | el `.ris` de lo que aún no tiene `zotero_key`, desde Calibre por el resolutor |
| `lib/archivar.py` | refresca rutas por id, comprueba la copia y retira el original según el modo |
| `lib/paquetes.py` · `lib/ocr_formatos.py` · `lib/desde_bib.py` | paquetes de anexos, variantes OCR y alta desde un `.bib` |
| `ingesta.tsv` | el ledger, fuente de verdad: sha256 → calibre_id → zotero_key → estado |
| `pendientes.tsv` | candidatos identificados (columnas de `resumen_catalogacion.tsv` sin id) |
| `fichas/` | fichas provisionales, fuera de git (borradores); `catalogar --aplicar` las lleva a `scripts-biblioteca/catalogacion/fichas/` |
| `salida_ris/` · `reportes/` | RIS e informes de ejecución, fuera de git (los respaldos de `metadata.db` los deja la puerta en `$RESPALDOS_DIR/biblioteca/fuentes/metadata`, fuera del repo) |

Toda escritura en Calibre pasa por la puerta `../lib/escribir.sh`/`.py` (F2): `core/shell-lib` o 69; Calibre
cerrado y candado `LOCK_CALIBRE` o 75; respaldo verificado o 74. RIS: mapeo de `prompts/01 fuentes/prompt_03_zotero.md`;
metadatos de normas: `../manifiestos/marco_legal/manifiesto.tsv`.

## Cómo queda cada documento en Calibre

| Campo | Regla |
|---|---|
| **Serie** | **la carpeta de origen**: `marco_legal/03_congreso` → `Marco legal 03 - Congreso` (índice = orden del `manifiesto.tsv`; sin fila → 90+); `03 writing/reports/<slug>/01_fuentes` → `Informe <slug> - Fuentes`; `data/raw/<inst>/<paquete>` → `datafw <inst> - <paquete>` |
| **Autor** | la **institución**, nunca el `Author` del PDF: sigla inicial del archivo (`inei_…`, `endes2024_…`), sufijo sectorial de la norma (`ds_004_2019_jus` → MINJUS), sigla interna (`…_minjus_…`), carpeta (`INSTITUCION_POR_CARPETA_JSON`), raíz datafw; anónimo = `Unknown` |
| **Título** | normas: `Ley N.° 28587. Proteccion al consumidor…`, `Decreto Supremo N.° 040-2014-PCM. Reglamento…`, `Texto Único Ordenado de la Ley N.° 27444. …`; documentos: `Directiva N.° 02-2023-DGP/CR. Gestión documental`, `Código civil D.Leg. 295 16a edición oficial`; informes: descripción del archivo en frase (sin la sigla: ya es el autor) o el `Title` del PDF si es real (los EN MAYÚSCULAS pasan a frase). Nunca `SIGLA — …` |
| **Fecha** | año del nombre de archivo (`_2019_`, `_2026_t1`), luego `CreationDate`, luego el texto; se ignoran años futuros (`PEN 2036`) |
| **Etiquetas** | solo del vocabulario cerrado, por carpeta (`TAGS_POR_CARPETA_JSON`) |
| `#clasificador` / `#item_type` | Normativa/Statute, Documento oficial/Document, Informe técnico/Report, Informe/Report, Libro/Book |
| Variantes | `X_ocr_buscable.pdf`, `X_texto.pdf`, `X.ocr.pdf` no son libros: son el formato con texto del libro de `X.pdf` (`main.sh ocr`); `X_escaneado.pdf` se retira al manifiesto |

Todo se escribe en **una** llamada `set_metadata` por libro y `backup_metadata` solo regenera los
OPF tocados (`../docs/decisiones.md` §2.2).

## Paquetes: anexos en la carpeta `data/` del documento principal

`PAQUETES_JSON` declara por raíz familias `{principal, adjuntos}` (regex sobre el nombre): en
`data/raw/mef/presupuesto/<aprobado|proyecto>/<año>` la Ley (o el PL) es el libro y sus `Anexo_*` van a la
carpeta `data/` del libro (que Calibre no registra), cada uno anotado en `02 analysis/data/raw/fuentes.yml`
con su `anexo`. Sin texto de la ley (`sin_principal`), el primer anexo hace de formato hasta `add_format`.
`identificar` salta los anexos (`[adj]`) y registra como copia lo que ya está en el ledger (`[copia]`).
Series de `02 analysis/data/raw`: `datafw <institución>` y, con etapa y año, `datafw <inst> - <carpeta> <etapa>`.

## Cursos: material externo de `10 Class` (`main.sh cursos`)

PDF **externos** de `05-recursos/` de `10 Class/docencia/cursos/*` → Calibre, con `bibliografia:
[{calibre_id, titulo, autor, origen}]` en el `curso.yml` (contrato con `10 Class`, `../docs/arquitectura.md`
§6). Era `ingesta_cursos` (fundida en F3). `cursos --escanear` escribe `reportes/cursos/candidatos_<fecha>.tsv`;
`cursos [--dry-run] [--tsv X]` simula sin escribir nada; `cursos --aplicar` va por la puerta. Sale 5 sin
`pdfinfo`/`python3`/`calibredb` y 3 sin TSV. Decisiones del TSV: `ingestar` (alta con título en frase y autor
canónico o `Unknown`, sin etiquetas; original a `ORIGINALES_DIR` = `$RESPALDOS_DIR/biblioteca/fuentes/originales-cursos`;
fila en `reportes/cursos/catalogar_*`), `duplicado` (enlaza el curso al libro existente), `omitir`, `revisar`.
Duplicado, autor y título los decide `core/py-common/biblioteca.py`; el libro entra a medias a propósito y lo
completa `scripts-biblioteca/catalogacion/`.

## Límite honesto

- **Los metadatos salen del nombre del archivo y de la carpeta** (sigla inicial, sufijo
  sectorial, año, `INSTITUCION_POR_CARPETA_JSON`): un archivo mal nombrado da una ficha mala; por
  eso `pendientes.tsv` se revisa antes de `--aplicar`, y lo que queda por debajo de
  `CONFIANZA_MINIMA_AUTO` no se cataloga sin revisión humana.
- **Nunca edita `metadata.db` ni `zotero.sqlite`**: todo pasa por `calibredb` a través de la puerta
  (Calibre cerrado, candado, respaldo verificado); con Calibre abierto o el candado ocupado sale 75 sin
  aplicar nada. `tests/test_puerta.py` falla si un archivo del repo llama a `calibredb` fuera de la puerta.
- **Zotero se alimenta por RIS**: el `.ris` de `salida_ris/` se importa a mano; el alta por el
  conector local es un intento sin garantía. Los `.ris` anteriores al 2026-09-30 no se importan
  (`salida_ris/obsoletos_2026-09-30/`, `../docs/decisiones.md` §2.7).
- **`fichas/` de esta carpeta es provisional**: la ficha que cuenta es la que `catalogar` escribe
  con `calibre_id` en `scripts-biblioteca/catalogacion/fichas/`.
- **La serie `Informe <slug> - Fuentes` solo se asigna bajo `01_fuentes/`**: un PDF identificado bajo la
  carpeta canónica `fuentes/` de un informe queda sin serie (`../estado.md` §Por hacer); con
  `bib --serie` la serie se da a mano.
- **`paquetes` solo ve las raíces que declara `PAQUETES_JSON`** (`$ANALYSIS_DIR/data/raw/mef/presupuesto/…`);
  una raíz inexistente da un aviso y se salta.
- **En las raíces externas solo entran PDF** bajo carpetas data/raw, `entrada`, `01_fuentes`,
  `fuentes` o `referencias` (`INBOX_RAICES_SOLO`); un `.xlsx` de `02 analysis` es dato de
  procesamiento, no un documento que se lea.
