---
tipo: readme
estado: activo
---
# sincronizar-zotero/ — metadatos Calibre ⇄ Zotero de los libros enlazados por #zotero_key

<!-- suite:inicio -->
**Suite `sincronizar_zotero`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Sincroniza en las dos direcciones los metadatos de los libros enlazados por #zotero_key entre Calibre y Zotero, con respaldos verificados e integridad.

- Escribe en: calibre, zotero · simula por defecto: sí
- Depende de: calibredb, zotero.sqlite, core/shell-lib, lib/escribir.sh (la puerta)

Comandos:

```bash
main.sh                      # simula y reporta
main.sh --aplicar            # ambas apps cerradas
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suite:fin -->

Sincronizador **bidireccional** de metadatos entre Calibre (`biblioteca/metadata.db`) y Zotero
(`~/Zotero/zotero.sqlite`) para los libros enlazados por la columna `#zotero_key` (la clave del ítem
padre en Zotero, que puebla ZMI o `../lectura/main.sh --enlazar`). Deja los
metadatos completos y coherentes en ambos lados. El contrato de campos RIS que implementa lo define
`prompts/01 fuentes/prompt_03_zotero.md`. Lo corre a diario el timer `ecosistema-metadatos`, a
través de `../lectura/main.sh --metadatos`.

## Uso

```bash
main.sh                       # simulación completa: solo reportes
main.sh --limite 20           # simulación sobre 20 pares
main.sh --ids 2,3075          # solo esos libros de Calibre
main.sh --limite 20 --aplicar # canario: aplica a 20 pares (Calibre y Zotero cerrados)
main.sh --aplicar             # todos los pares
main.sh --help                # opciones; --verbose da más detalle
```

Un cambio de política se prueba con el canario: aplicar a 20, abrir Zotero y mirar esos ítems, y
solo entonces la corrida completa. Cada pasada deja en `reportes/` un `sync_<fecha>.tsv` (una fila
por acción: `book_id, zotero_key, campo, accion, antes, despues`) y un `sync_<fecha>.md` (resumen y
claves huérfanas). Las acciones `reporte (...)` no se aplican: son para revisión manual.

## Política de sincronización

- **Calibre manda**: en conflicto gana Calibre y se propaga a Zotero: título, fecha, editorial,
  ISBN, serie y número, páginas, edición, idioma, etiquetas y resumen. El título se compara exacto;
  los demás campos, normalizados.
- **Título y autores, solo Calibre → Zotero**: jamás se escriben en Calibre, porque Zotero enlaza
  los adjuntos por la ruta `Autor/Título (id)`.
- **Zotero → Calibre, solo relleno de vacíos** (año de relleno `0101`, ISBN ausente) y las columnas
  espejo `#zotero_*`.
- **Reparación**: rutas de adjunto rotas en Zotero (carpetas renombradas) y la línea de ruta del
  campo `Extra`.

Reglas duras, no configurables:

- **El formato de autor es propio de cada sistema**: Calibre «Nombre, Apellido» (o separador `|`),
  Zotero `firstName`/`lastName`; se convierte al cruzar, no se unifica. Los autores se comparan como
  conjuntos de tokens; si Zotero tiene más creadores (coautores, editores, traductores) se conservan
  y se reporta.
- **Las etiquetas personales de Zotero no se tocan** (`⭐`, emojis, `#hashtags`); las variantes
  obsoletas del vocabulario sí se reemplazan por la versión limpia de Calibre.
- **Idioma: Calibre manda siempre**, como código ISO 639-1 (`spa` → `es`, `English` → `en`); los
  códigos regionales válidos se respetan.
- **`Extra` se edita línea a línea**: solo la línea de ruta; las líneas `CSL Variable: Value` se
  conservan.
- **Vacío en el origen nunca borra en el destino**; `Leído` y `Géneros` de Calibre no se propagan.
- **El tipo de ítem se sincroniza**: manda el `Item type` de Calibre; los campos migran por
  `baseFieldMappings` de Zotero, lo que no cabe va a `Extra` como línea CSL y los creadores pasan al
  rol primario del tipo. En artículos, la serie de Calibre va a `publicationTitle` (RIS `T2`).
- **Valoración**: `rating` de Calibre (2–10) ⇄ etiqueta de estrellas de Zotero, en ambos sentidos;
  Calibre manda en conflicto.

## Escritura segura

`--aplicar` entra por la puerta (`../lib/escribir.sh`, `../docs/decisiones.md` §2.5): comprueba por
el nombre del proceso que Calibre y Zotero estén cerrados, toma `LOCK_CALIBRE` (o lo hereda del
timer) y `LOCK_ZOTERO`, y deja un respaldo **verificado** de cada base en
`$XDG_STATE_HOME/biblioteca/respaldos/sincronizar_zotero/{calibre,zotero}/`. Después escribe Zotero
por SQL (`../lib/escribir_zotero.py`) dejando cada ítem tocado con `synced=0` y `dateModified` al día
para que la cuenta lo suba; Calibre **no** se escribe por SQL: el plan (rellenos de fecha, ISBN y
valoración, y el espejo `#zotero_*`, con las columnas resueltas por etiqueta) va a
`plan_calibre.json` y lo aplica la API de Calibre (`escribir.py aplicar-plan`, §2.7). Al final,
`PRAGMA integrity_check` en las dos bases (solo lectura) y `calibredb backup_metadata` de los libros
cambiados. Si la comprobación falla, nombra los respaldos que hay que restaurar.

## Estructura

`main.sh` (orquestación) · `config.sh` (rutas de `core/env.sh`, política) · `lib/`: `cli.sh`
(opciones, ayuda, dependencias), `validator.sh` (bases sanas, apps cerradas y la puerta),
`sincronizador.py` (núcleo: lee ambas bases, planifica, reporta, escribe Zotero y deja el plan de
Calibre) · `reportes/` es runtime ignorado; el estado (`ultimo_sync.json`, la foto para los diffs, y
`plan_calibre.json`) vive en `$XDG_STATE_HOME/biblioteca/sincronizar_zotero/`. Pruebas: la
caracterización de `../tests/` (copia perturbada y orquestación de las 04:30). El motor de
comparación partió del de `../verificacion`. La primera corrida completa (2026-07-28)
está en `../docs/historial/campanas-sobre-la-biblioteca.md` §3.

## Límite honesto

- **Zotero se escribe por SQL directo**, método no soportado por Zotero (el mismo terreno que ZMI);
  por eso exige ambas apps cerradas y deja `synced=0`.
- **Deshacer es restaurar los respaldos** de la puerta con las apps cerradas (los anteriores a la ola
  2a están en `$RESPALDOS_DIR/biblioteca/sincronizar_zotero/`).
- **Las acciones `reporte (...)` quedan para revisión manual**: conflictos de idioma, autores donde
  Zotero es más completo y adjuntos que no se pudieron recalcular.
- **Los `.js` de `scripts_for_zotero` quedan absorbidos** por esta política (`capitalizar_tags`,
  `traducir_tags_español`, `invertir_nombres`): ejecutarlos reintroduce divergencia; solo
  `series_organizer` es compatible, después del sync.
