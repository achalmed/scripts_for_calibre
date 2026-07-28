# script_verificar_metadatos

Verifica los metadatos de la biblioteca **Calibre** contra bases
bibliográficas públicas (**OpenLibrary**) y genera un **reporte de
discrepancias** para que las corrijas a mano. Es de **solo lectura**: nunca
escribe en Calibre.

## Qué problema resuelve

Muchos registros arrastran datos imperfectos: editorial vacía o incorrecta
(p. ej. `ePubLibre`, que es la web de reempaquetado del ebook y **no** la
editorial real), año de una edición distinta, número de páginas erróneo.
Esta herramienta consulta el ISBN (u otro identificador) de cada libro,
compara campo a campo y te dice **solo dónde difieren**, sin tocar nada.

**Nunca sugiere cambiar título ni autor**: en esta biblioteca Zotero enlaza
los ítems por la ruta de la carpeta (`Autor/Título (id)`), así que cambiar
esos dos campos rompería el vínculo. El título y el autor de la fuente se
muestran únicamente como *contexto informativo*.

## Alcance realista (por qué no verifica los 4 484 libros)

Solo los libros con identificador registrado son verificables contra una
base bibliográfica:

| Situación | Aprox. | ¿Verificable? |
| --- | --- | --- |
| Con ISBN | 132 | Sí (exacto) |
| Con Google/Amazon/Goodreads | ~90 | Sí (exacto) |
| Handouts, exámenes, working papers, PDFs sueltos | ~4 300 | No existen en ninguna base |

Los ~4 300 documentos de aula inéditos **no están catalogados en ningún
sitio**, así que buscarlos sería costoso y de rendimiento casi nulo. Por eso
el modo por defecto (`isbn`) se limita a lo verificable. El modo `titulo`
añade una búsqueda aproximada por título+autor para los libros publicados
que no tengan ISBN (útil para los ~228 `Book` sin identificador), marcando
siempre el nivel de confianza.

## Arquitectura (patrón modular del repo)

```
script_verificar_metadatos/
├── main.sh              # orquestación únicamente
├── config.sh            # TODO lo editable: rutas, endpoints, umbrales
├── lib/
│   ├── logger.sh        # logging centralizado (INFO/WARN/ERROR/DEBUG)
│   ├── cli.sh           # parseo de flags, --help, chequeo de dependencias
│   ├── db.sh            # ÚNICO lugar que lee metadata.db (sqlite3)
│   ├── verificador.py   # núcleo: red (urllib) + comparación difusa
│   └── report.sh        # rutas de salida y resumen final
└── reportes/            # discrepancias_<fecha>.{tsv,md} (generado)
```

Cada campo ajustable vive en `config.sh` (endpoints, `RATE_LIMIT_SECONDS`,
`HTTP_TIMEOUT`, `FUZZY_TITLE_THRESHOLD`, tipos de identificador). Los módulos
de `lib/` nunca codifican rutas.

## Requisitos

- `curl`, `python3` (solo biblioteca estándar), `sqlite3`
- Conexión a internet (OpenLibrary). No requiere clave de API.
- No necesita cerrar Calibre (solo lee `metadata.db`).

## Uso

```bash
./main.sh --limite 5       # prueba rápida sobre 5 libros con ISBN
./main.sh                  # modo isbn: todos los libros con identificador
./main.sh --modo titulo    # además busca por título+autor los que no tengan
./main.sh --ids 425,739    # solo esos ids (depuración)
./main.sh --help           # ayuda completa
```

### Salida

Dos ficheros con marca de tiempo en `reportes/`:

- `discrepancias_<fecha>.tsv` — legible por máquina
  (`id, campo, valor_calibre, valor_fuente, fuente, confianza`).
- `discrepancias_<fecha>.md` — tabla legible para revisar.

`confianza` es `exacta` para búsquedas por identificador y `aprox:<ratio>`
para coincidencias por título+autor.

## Criterios de comparación (en `lib/verificador.py`)

- **año**: se marca solo si ambos existen y difieren.
- **editorial**: se marca si Calibre está vacío (oportunidad de rellenar) o
  si difiere claramente (ni subcadena ni similitud ≥ 0,6).
- **páginas**: se marca solo si la diferencia es > 5 (evita ruido entre
  ediciones).
- **título/autor**: se reportan como *informativo* cuando difieren; jamás
  como sugerencia de cambio.

En modo `titulo`, un candidato de la fuente se acepta como "el mismo libro"
solo si la similitud de título ≥ `FUZZY_TITLE_THRESHOLD` (0,80); por debajo
se descarta para no generar falsos positivos.

## Notas

- **Proveedores**: OpenLibrary es el primario (libros). En `--modo titulo`,
  cuando OpenLibrary no encuentra nada se consulta **Crossref** como respaldo
  (indexa artículos de revista, working papers y libros por DOI); de ahí salen
  los `Report` y `Journal Article` que OpenLibrary no ve, y a menudo un **DOI
  que no teníamos** (`doi (encontrado)` en el reporte). Se desactiva con
  `USE_CROSSREF="false"` en `config.sh`. Google Books queda solo de referencia
  (su cuota anónima suele devolver `429`).
- Ninguna corrección se aplica automáticamente: revisa el reporte y edita en
  Calibre lo que consideres. Tras editar en Calibre, recuerda regenerar los
  OPF (`calibredb backup_metadata --all`) para que ZMI/Zotero lo vean.
