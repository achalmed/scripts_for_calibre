---
tipo: readme
estado: activo
---
# fichas/ — validar, cotejar contra el libro e indexar las fichas del Método Documental (pasos 05 y 09)

<!-- suite:inicio -->
**Suite `fichas`** · objetivo *fuentes* · estado *activo* · python · interfaz cli

Fichas del Método Documental: valida el formato único, coteja textuales y paráfrasis contra el texto del libro, rellena claves desde fuentes.yml y genera el índice.

- Escribe en: vault · simula por defecto: sí
- Depende de: python3, core/py-common/biblioteca.py, manifiesto
- Método Documental: pasos 05 y 09

Comandos:

```bash
main.py validar <carpeta>
main.py verificar <carpeta> [--aplicar] [--desfase N]
main.py claves|grafia <carpeta> [--aplicar]
main.py indice <carpeta> --aplicar
main.py estado <carpeta>
main.py migrar <carpeta> --formato hibrida
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suite:fin -->

## Qué es

Aplica `prompts/00 metodo/fichas_formato_y_voz.md` a las fichas de un proyecto: comprueba el frontmatter único, el
nombre y las secciones por tipo (`validar`); coteja la cita literal de una ficha textual (o el «Origen literal» de una
paráfrasis) contra el texto del libro en Calibre y deja escrito el veredicto (`verificar`); rellena `calibre_id` y
`zotero_key` desde el `fuentes.yml` del proyecto (`claves`); genera `00-indice_fichas.md` (`indice`); resume por estado
(`estado`); y migra fichas anteriores al formato único (`migrar`, `grafia`). No inventa nada: la norma es el documento y
`config.py` la transcribe (claves, tipos, categorías, patrones de nombre, secciones, tolerancias).

## Uso

```bash
cd ~/Documents/scripts_for_fuentes/fichas
python3 main.py validar "../../03 writing/reports/<slug>/fuentes/fichas"                 # frontmatter, nombre, secciones; código 1 si hay faltas (--json: detalle)
python3 main.py verificar "../../03 writing/reports/<slug>/fuentes/fichas" --desfase 0   # simula el cotejo; --aplicar escribe verificacion.*; --tolerancia N cambia el ±2
python3 main.py claves "../../03 writing/reports/<slug>/fuentes/fichas" --aplicar        # calibre_id y zotero_key desde el fuentes.yml
python3 main.py indice "../../03 writing/reports/<slug>/fuentes/fichas" --aplicar        # 00-indice_fichas.md
python3 main.py estado "../../03 writing/reports/<slug>/fuentes/fichas"                  # código 1 si hay «observada» o «pendiente» en uso
python3 main.py migrar "../../03 writing/<tipo>/<slug>/notes/fichas" --formato hibrida   # simula; --aplicar con respaldo y UNDO antes
```

## Qué escribe y qué no

| comando | escribe | dónde |
|---|---|---|
| `validar`, `estado` | nada | — |
| `verificar --aplicar` | `verificacion.estado`, `verificacion.metodo`, `verificacion.fecha` del frontmatter | la propia ficha |
| `claves --aplicar` | `calibre_id` y `zotero_key` vacíos, tomados por `clave_bibtex` del `fuentes.yml` de la raíz del proyecto (`--fuentes` para otro); retira la nota «pendiente de los pasos 00–03» del cuerpo | la propia ficha |
| `indice --aplicar` | `00-indice_fichas.md` (por tipo, conteo por estado) | la carpeta indicada |
| `grafia --aplicar`, `migrar --aplicar` | reescriben el frontmatter (y `migrar --formato hibrida` reparte una ficha en fuente + textuales + paráfrasis) | las fichas dadas; las dos dejan antes un respaldo `tar.gz` y su `UNDO.sh` en `$RESPALDOS_DIR/biblioteca/fuentes/fichas/` (ola 2, F5) |

Nunca escribe en Calibre: el texto del libro lo lee el resolutor (`core/py-common/biblioteca.py`, caché de `pdftotext`
en `~/.cache/biblioteca_texto`). Al escribir una ficha las claves salen siempre en el orden de `config.CLAVES` y los
valores vacíos se escriben vacíos (`zotero_key:`), como exige la norma; el cuerpo no se toca salvo en `claves` y `migrar`.

## Estructura

`main.py` (orquestación: un `cmd_*` por comando) · `config.py` (la norma transcrita: claves, tipos, categorías, patrones
de nombre, secciones, tolerancias) · `lib/ficha.py` (leer, escribir, validar) · `lib/verificar.py` (cotejo) ·
`lib/grafia.py` (claves en snake_case) · `lib/migrar.py` (formatos `catalogacion` e `hibrida`).

## Límite honesto

- **Solo coteja texto literal**: `verificada_script` exige la cadena carácter por carácter (normalizados espacios, guiones
  de corte de línea, comillas tipográficas y elipsis) en la página declarada más `--desfase`; hallada en otra página o no
  hallada es `observada`, con el detalle. Una paráfrasis coteja su «Origen literal»; una síntesis solo comprueba que todas
  sus fichas de entrada estén verificadas. El juicio de fidelidad es del autor (`verificada_autor`).
- **La página declarada es la impresa** y el PDF puede ir desfasado: se prueba la declarada, ±2 (`TOLERANCIA_PAGINAS`) y
  por último todo el documento, que nunca da «verificada».
- **Sin texto no hay cotejo**: un libro sin capa de texto en Calibre (escaneado, o del Congreso sin OCR) sale `observada`.
- **`validar` avisa, no rechaza**, cuando falta una sección; solo el frontmatter y el nombre son faltas.
- **`migrar` es de un solo uso** para fichas anteriores al formato único: la ficha híbrida desaparece al aplicar y lo que
  no encaja va a «Observaciones».
