# script_sincronizar_zotero

<!-- suite:inicio -->
**Suite `sincronizar_zotero`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Sincroniza en las dos direcciones los metadatos de los libros enlazados por #zotero_key entre Calibre y Zotero, con backups e integridad.

- Escribe en: calibre, zotero · simula por defecto: sí
- Depende de: calibredb, zotero.sqlite, core/shell-lib

Comandos:

```bash
main.sh                      # simula y reporta
main.sh --aplicar            # ambas apps cerradas
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-07); no se edita a mano.</sub>
<!-- suite:fin -->

Sincronizador **bidireccional** de metadatos entre la biblioteca **Calibre**
(`biblioteca/metadata.db`) y **Zotero** (`~/Zotero/zotero.sqlite`) para los
libros enlazados por el plugin **ZMI** (columna Calibre `#zotero_key` = clave
del item padre en Zotero). Deja los metadatos **completos y coherentes en
ambos lados**. Simulacion por defecto; escribe solo con `--aplicar`.

Es la pieza que faltaba en el flujo del ecosistema
**catalogar → normalizar → verificar → sincronizar → incrustar → fichas**
(ver `../script_verificar_metadatos`, `../script_normalizacion_metadatos`,
`../script_catalogacion_biblioteca` y
`prompts/01 fuentes/prompt_02_catalogar.md`,
que define el contrato de campos RIS de ZMI que esta herramienta implementa).

## Politica de sincronizacion (decidida por el usuario)

- **"Calibre manda"**: en conflicto de un campo bibliografico, gana Calibre
  (recien normalizado en 4 sesiones de limpieza). Se propaga a Zotero:
  titulo, fecha, editorial, ISBN, serie y numero de serie, paginas, edicion,
  idioma (normalizado), tags y abstract.
- **Calibre → Zotero solamente** para titulo y autores. Titulo y autor
  **JAMAS** se escriben en Calibre: Zotero enlaza los adjuntos por la ruta de
  carpeta `Autor/Titulo (id)` y cambiarlos romperia el vinculo.
- **Zotero → Calibre**: solo relleno de vacios (año en placeholder `0101`,
  ISBN ausente) y poblacion de las columnas espejo `#zotero_*`.
- **Reparacion**: rutas de adjuntos rotas en Zotero (carpetas ya renombradas)
  y la linea de ruta dentro del campo `Extra`.

### Reglas duras (no configurables)

- **Formato de autor por sistema, nunca homogenizar**: Zotero
  `Apellido, Nombre` (campos separados) / Calibre `Nombre, Apellido` (coma
  interna). El sync convierte al cruzar, no unifica.
- **Autores por comparacion semantica** (conjuntos de tokens): tolera el
  intercambio nombre/apellido que dejo la vieja herramienta `invertir_nombres`.
  Si Zotero tiene MAS autores (coautores/editores/traductores) se **conservan**
  y solo se reporta; nunca se borran co-creadores.
- **Etiquetas personales de Zotero intocables**: valoraciones `⭐`, emojis y
  `#hashtags` se preservan siempre. Las variantes ortograficas obsoletas de
  vocabulario (`Ciencias sociales`, `economía_ambiental`, `programming_R`, el
  typo `ecuacione s_lineales`) SI se reemplazan por la version limpia de
  Calibre para no reintroducir duplicados ya fusionados.
- **Idioma: Calibre manda SIEMPRE** (decision del usuario: Zotero quedo mal
  poblado, casi todo como ingles). Se escribe el codigo ISO 639-1 normalizado
  (`spa`→`es`, `English`→`en`); los codigos regionales validos se respetan.
- **Campo `Extra`**: se edita **linea a linea**; solo se actualiza la linea de
  ruta `{path}`, las lineas `CSL Variable: Value` se preservan.
- **Vacio en el origen nunca borra en el destino.** `Leido` y `Generos` de
  Calibre jamas se propagan.
- **El tipo de item se sincroniza de verdad**: manda el `Item type` de
  Calibre (`book` solo cuando realmente es libro; `presentation`, `manuscript`,
  `report`, `bookSection`, `journalArticle`...). El cambio migra los campos via
  `baseFieldMappings` de Zotero, lo que no cabe en el tipo nuevo se preserva en
  `Extra` como linea CSL, y los creadores pasan al rol primario del tipo
  (`presenter` en presentaciones). Para articulos, la serie de Calibre va a
  `publicationTitle` (contrato RIS `T2`).
- **Valoracion en estrellas sincronizada**: Calibre `rating` (2-10) ⇄ tag de
  estrellas de Zotero (`⭐`-`⭐⭐⭐⭐⭐`), en ambas direcciones; Calibre manda en
  conflicto.

## Arquitectura (patron modular del repo)

```
script_sincronizar_zotero/
├── main.sh              # orquestacion unicamente
├── config.sh            # TODO lo editable: rutas, columna clave, politica
├── lib/
│   ├── logger.sh        # logging (identico al canonico del repo)
│   ├── cli.sh           # flags, --help, chequeo de dependencias
│   ├── validator.sh     # apps cerradas + backups + integrity_check
│   └── sincronizador.py # nucleo: lee ambas bases, planifica, reporta, aplica
├── reportes/            # sync_<fecha>.{tsv,md} (generado)
└── estado/              # backups/ + ultimo_sync.json (snapshot para diffs)
```

## Seguridad de escritura

- **Calibre y Zotero deben estar CERRADOS** para `--aplicar`. La herramienta
  lo verifica (`pgrep`) y aborta si alguno esta abierto.
- **Backup previo** de ambas bases en `estado/backups/` antes de tocar nada.
- Escrituras a Zotero por **SQL directo** (metodo no soportado oficialmente por
  Zotero, el mismo terreno que ZMI): cada item modificado queda con `synced=0`
  y `dateModified` actualizado, para que tu cuenta zotero.org **suba** los
  cambios en el siguiente sync.
- Tras aplicar: `PRAGMA integrity_check` en ambas bases y regeneracion de los
  OPF de Calibre (`calibredb backup_metadata --all`) para que ZMI y los
  incrustadores de PDF (`script_metadatos_calibre`) no lean metadatos rancios.
- Si el integrity_check falla, la herramienta te dice que restaures los backups.

## Uso

```bash
./main.sh                    # SIMULACION completa: solo genera reportes
./main.sh --limite 20        # simulacion sobre 20 pares (prueba)
./main.sh --ids 2,3075       # solo esos libros de Calibre (depuracion)
./main.sh --limite 20 --aplicar   # aplicar SOLO a 20 pares (canario)
./main.sh --aplicar          # aplicar a los 4420 pares (apps cerradas)
```

**Recomendado la primera vez**: cerrar ambas apps, correr
`./main.sh --limite 20 --aplicar`, abrir Zotero y verificar esos 20 items,
y solo entonces la corrida completa.

### Salida

- `reportes/sync_<fecha>.tsv` — una fila por accion
  (`book_id, zotero_key, campo, accion, antes, despues`).
- `reportes/sync_<fecha>.md` — resumen por accion + claves huerfanas.
- Las acciones `reporte (...)` NO se aplican: son para tu revision manual
  (conflictos de idioma, autores donde Zotero es mas completo, adjuntos que
  no se pudieron recalcular).

## Estado actual de la biblioteca (APLICADO 2026-07-28)

Corrida completa aplicada y verificada: 4420 pares · 9414 escrituras a Zotero
(3032 cambios de tipo con migracion de campos, idioma normalizado a `es`/`en`,
tags saneados, estrellas en ambas direcciones, 286 abstracts, 66 rutas de
adjunto reparadas, 40 titulos, 38 autores `Unknown`, editoriales y fechas) ·
44917 celdas espejo pobladas en Calibre (zotero_* al 100%) · idempotente
(re-simulacion: 0 escrituras) · 4451 items con `synced=0` listos para subir a
zotero.org · 13 claves huerfanas y 1 adjunto fantasma (libro 1667 borrado,
duplicado del 28) para revision manual.

## Herramientas relacionadas (complementarias, no duplicar)

- `../script_verificar_metadatos` — motor de diff reutilizado como base.
- `scripts_for_zotero/` (`capitalizar_tags`, `traducir_tags_español`,
  `invertir_nombres`): herramientas viejas cuyas transformaciones de tags y
  nombres quedan **absorbidas** por la politica de este sync; ejecutarlas
  sueltas reintroduce divergencia. `series_organizer` puede correr despues
  como organizador de subcolecciones.
