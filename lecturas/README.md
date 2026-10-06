---
tipo: readme
estado: activo
---
# lecturas/ — pasajes con número de página por concepto, desde el lecturas.yml del proyecto (paso 07)

<!-- suite:inicio -->
**Suite `lecturas`** · objetivo *fuentes* · estado *activo* · python · interfaz cli

Pasajes con número de página por concepto, extraídos del texto de cada libro de lecturas.yml; una ficha de lectura por ítem con el frontmatter único.

- Escribe en: vault · simula por defecto: sí
- Depende de: python3, pdftotext, core/py-common/biblioteca.py, fichas
- Método Documental: paso 07

Comandos:

```bash
main.py <lecturas.yml>              # simula
main.py <lecturas.yml> --aplicar
main.py <lecturas.yml> --aplicar --unico todo.md
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-04); no se edita a mano.</sub>
<!-- suite:fin -->

## Qué es

La lista curada de (`calibre_id`, conceptos, patrones) que un informe necesita vive en el
`lecturas.yml` del proyecto, no dentro de un script (sucede al `06_lecturas_biblioteca.py` de un
informe de datafw: `../docs/historial/procedencia-de-las-carpetas.md`). Por cada ítem lee el texto del libro por el resolutor, busca los patrones (regex sin tildes, insensible a mayúsculas) y escribe
una ficha `lectura` con los pasajes hallados, lista para que el prompt 07 (`prompts/01 fuentes/prompt_07_extraer_ideas.md`)
complete las secciones.

## Uso

```bash
cd ~/Documents/scripts_for_fuentes/lecturas
python3 main.py "../../escritura/reports/<slug>/fuentes/lecturas.yml"                  # simula: ítems, páginas, pasajes
python3 main.py "../../escritura/reports/<slug>/fuentes/lecturas.yml" --aplicar        # escribe <clave>-lectura-extraida.md
python3 main.py "../../escritura/reports/<slug>/fuentes/lecturas.yml" --aplicar --unico todo.md --solo 1068   # además un solo Markdown; solo ese id
python3 main.py "../../escritura/reports/<slug>/fuentes/lecturas.yml" --destino "../../escritura/reports/<slug>/fuentes/lecturas"   # --destino DIR y --proyecto RUTA mandan sobre el spec
```

`lecturas.yml`:

```yaml
proyecto: escritura/reports/<slug>      # ruta relativa a ~/Documents, no el id (opcional; si falta, la carpeta del spec)
destino: fuentes/fichas                  # relativo al proyecto (opcional; por defecto fuentes/fichas)
lecturas:
  - calibre_id: 1068
    clave_bibtex: marx1848manifiesto     # opcional: si falta se deriva <apellido><año><palabra>
    etiqueta: "Marx y Engels, Manifiesto comunista: el Estado como junta de la burguesía"
    patrones: ["negocios comunes", "junta que administra"]
    max: 6
```

Con el spec en `fuentes/` hay que fijar `proyecto:` (la ruta) o `destino:` en el spec, o pasar
`--proyecto RUTA` o `--destino DIR` en la orden: sin nada de eso el destino se cuenta desde
`fuentes/` y queda en fuentes/fuentes/fichas; un `proyecto:` con el id del proyecto no resuelve
(`../estado.md` §Por hacer).

## Qué escribe y qué no

- Por ítem, `<destino>/<clave_bibtex>-lectura-extraida.md` con el frontmatter único (`tipo: lectura`) y las siete
  secciones de la norma vacías; los pasajes van entre las marcas `<!-- lecturas: … -->` y **se regeneran al reejecutar**;
  lo redactado fuera de las marcas se conserva.
- Con `--unico`, además un Markdown combinado (el formato del script original de datafw).
- Solo lectura sobre Calibre (`core/py-common/biblioteca.py`: `datos`, `texto`); no toca `lecturas.yml` ni Calibre.

## Estructura

`main.py` (orquestación) · `config.py` (contexto antes y después, máximo por patrón, sufijo, destino por defecto, marcas,
secciones) · `lib/lecturas.py` (clave derivada, búsqueda, bloque entre marcas, escritura). El frontmatter lo escribe
`fichas/lib/ficha.py` (la suite `fichas`), cargado por ruta.

## Límite honesto

- **La página es el índice del PDF desde 1** (`pdftotext`), no la impresa: el analista la confirma al fichar (paso 05).
- **Solo encuentra lo que el patrón dice**: no interpreta; un concepto sin patrón que lo nombre no aparece.
- **Sin texto legible no hay pasajes** (escaneado sin OCR): el ítem se reporta y se salta.
- **La clave derivada es provisional**: fija `clave_bibtex` en el spec cuando Zotero (o `manifiesto bib`) la asigne; si no,
  el nombre del archivo cambiará.
- Depende de `pdftotext` y de la caché de texto del resolutor.
