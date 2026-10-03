---
tipo: bitacora
titulo: "Campañas sobre la biblioteca: lo que se catalogó, normalizó y sincronizó en bloque, y con qué resultado"
estado: hecho
---
# Campañas sobre la biblioteca: catalogación, normalización y sincronización en bloque

> Bitácora. Lo vigente está en el README de cada suite y en `../operacion.md`; las reglas que estas
> campañas dejaron, en `../decisiones.md`. Las cifras son las de su fecha y no se actualizan.

Una campaña es una operación de una sola vez sobre toda la biblioteca, aprobada por el autor, con
respaldo previo y, desde 2026-09-30, con su `deshacer.sh`. Su código y sus tablas viven en
`../../script_normalizacion_metadatos/migraciones/` o en la suite que la ejecutó.

## 1. Los libros sin autor (2026-07-27, `script_catalogacion_biblioteca`)

La biblioteca tenía 113 libros sin autor identificado (90 bajo `Unknown`, 22 bajo `Desconocido`, 1
bajo `Varios autores`). Cada uno se catalogó leyendo la portada o la página legal del PDF con el
prompt de catalogación (hoy `prompts/01 fuentes/prompt_02_catalogar.md`), y se aplicó con `main.sh
--aplicar`: 113 de 113, 0 errores. El enum `Clasificador` pasó de 68 a 76 valores. Una búsqueda web
posterior atribuyó 14 de los 75 `Unknown` restantes con evidencia citada en la ficha (sección
«ACTUALIZACIÓN») y en la columna `nota` del TSV; 61 quedaron anónimos por acuerdo.

Quedaron declarados entonces como pendientes manuales: el ingreso en Zotero de las fichas, el OCR de
los ids 440 y 445 (escaneos sin capa de texto) y la extensión corrupta del id 9887
(`.unenfoquegerencial` → `.pdf`). Los ids 8877 y 9590 se confirmaron como documentos distintos, no
duplicados. El primer uso del circuito para altas nuevas fue el 2026-08-30 (ids 9910–9913).

## 2. Normalización de etiquetas, géneros y tipos (2026-07-28, migraciones `01`–`09`)

Derivadas solo de los metadatos existentes (sin abrir PDF), sin tocar título ni autor, por SQLite
directo y con `--apply` para escribir:

| # | qué hizo |
|---|---|
| 01 | fusionó etiquetas duplicadas o con erratas (245 → 222) |
| 02 | derivó **Géneros** por voto de las etiquetas; desempate por el género menos frecuente |
| 03 | rellenó **Item type** desde el Clasificador con el mapeo dominante de alta confianza |
| 04 | material de examen o práctica → `Manuscript`; capítulo o parte → `Book Section`; documento de trabajo → `Report` |
| 05 | aplicó las etiquetas clasificadas por título de 739 libros que no tenían, validadas contra el vocabulario |
| 06 | Item type por señal determinista: serie de hermanos ya catalogados, o ISBN → `Book` (201 libros) |
| 07 | aplicó el Item type que propusieron subagentes con los criterios del prompt de catalogación (950 libros); Item type al 100 % |
| 08 | verificó en OpenLibrary y Crossref los inciertos; solo lectura, escribió una propuesta |
| 09 | aplicó la propuesta del 08: 48 reclasificados, 34 editoriales y 30 ISBN añadidos donde faltaban |

01–04 y 06 leen solo `metadata.db` y se pueden volver a correr; 05, 07, 08 y 09 leían TSV de un
scratchpad de sesión que ya no existe (su ruta sigue escrita en cada script), así que hoy no
encuentran sus insumos: se conservan por la lógica de validación que documentan.

## 3. Primera sincronización completa Calibre ⇄ Zotero (2026-07-28, `script_sincronizar_zotero`)

Corrida aplicada y verificada sobre 4 420 pares: 9 414 escrituras a Zotero (3 032 cambios de tipo
con migración de campos, idioma normalizado, etiquetas saneadas, estrellas en ambas direcciones, 286
resúmenes, 66 rutas de adjunto reparadas, 40 títulos, 38 autores `Unknown`, editoriales y fechas),
44 917 celdas espejo `#zotero_*` en Calibre y 4 451 ítems con `synced=0` para subir. La
re-simulación dio 0 escrituras. Quedaron 13 claves huérfanas y un adjunto fantasma para revisión
manual.

## 4. Grafías de autores (2026-09-30, `grafias_autores_2026-09-30/`)

La única campaña que toca autores. Corrigió 80 grafías fuera de «Nombre, Apellidos» y 10 listas de
autores, por la API de Calibre (`rename_items`, como «Gestionar autores»), que mueve carpeta y
archivos, y reescribió en la misma operación las rutas `attachments:` y los creadores de Zotero.
Resultado: 64 carpetas, 36 enlaces de Zotero, 50 ítems, 0 enlaces rotos. Diagnóstico:
`meta/diagnosticos/GRAFIAS_AUTORES_CALIBRE_2026-09.md`.

## 5. Títulos (2026-09-30 y 2026-10-01, `titulos_*/`)

Ocho campañas con el patrón de la de autores (foto previa de rutas, Calibre y Zotero en la misma
operación, simulacro sobre copia, `deshacer.sh`); título y `title_sort` a la vez porque
`set_metadata` no recalcula el segundo. Erratas leídas en la portada, tildes en lote (con detectores
propios y el diccionario hunspell es-ES de Calibre), idioma de títulos y libros, fascículos y
títulos genéricos distinguidos por sesión, parte, año o curso.
`titulos_zotero_2026-10-01/empujar_zotero.py` igualó los títulos que Zotero tenía desfasados, y a
raíz de ello `sincronizar_zotero` compara el título exacto (`../decisiones.md`). Resultado: 0
enlaces de Zotero rotos y 0 títulos distintos entre Calibre y Zotero. Diagnóstico:
`meta/diagnosticos/TITULOS_CALIBRE_2026-09.md`.

## 6. Duplicados y repaso final (2026-10-01, `duplicados_2026-10-01/`, `repaso_final_2026-10-01/`)

`auditar.py` (solo lectura) halló los candidatos; `aplicar.py` mandó a las papeleras de Calibre y de
Zotero 472 ítems RIS repetidos y 13 libros duplicados; `pendientes.py` cerró los casos sueltos. El
repaso final encontró 8 títulos y 6 duplicados más comparando huellas por página. Nada se borró para
siempre. Al revisar la papelera se restauró el 619, que tenía anotaciones a mano propias
(`restaurados.tsv`). Estado al cierre: 3 984 libros, todos enlazados, 0 enlaces rotos y 0 formatos
sin archivo. Diagnóstico: `meta/diagnosticos/DUPLICADOS_BIBLIOTECA_2026-10.md`.
