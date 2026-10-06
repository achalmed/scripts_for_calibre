---
tipo: readme
estado: activo
---
# manifiestos/marco_legal/ — el dato del marco legal: de dónde sale cada norma y cómo se rearma su manifiesto

Dueña del manifiesto del marco legal peruano: por cada norma, la carpeta temática, el archivo, la URL,
la fuente y una nota. Los PDF no viven aquí: están en Calibre, en la serie «Marco legal NN - …».
`ingesta` lee `manifiesto.tsv` (`MANIFIESTO_MARCO_LEGAL` de `../../ingesta/config.sh`) para dar título,
serie e índice a las normas; localizar o descargar una norma nueva es
`main.py localizar · descargar congreso` (`../../README.md` §Uso). Por qué quedó así:
`../../docs/decisiones.md` §1.4.

## Uso

Ninguno de los dos scripts descarga nada, y los dos exigen `MARCO_LEGAL`, una carpeta local con los
PDF, porque el marco legal ya no está en disco:

```bash
MARCO_LEGAL=<carpeta> ./generar_manifiesto.sh   # une parciales/*.tsv en manifiesto.tsv; lo no localizado, a no_localizados.tsv
MARCO_LEGAL=<carpeta> ./generar_inventario.sh   # escribe INVENTARIO.md en esa carpeta
```

## Estructura

| ruta | qué es |
|---|---|
| `manifiesto.tsv` | el dato: carpeta, archivo, URL, fuente y nota de cada norma; deduplicado por carpeta y archivo |
| `parciales/` | un TSV por lote de búsqueda; entrada de `generar_manifiesto.sh` |
| `no_localizados.tsv` · `fallidos.tsv` | lo que no se encontró o no se pudo bajar, y por qué |
| `generar_manifiesto.sh` | fusiona y deduplica los parciales |
| `generar_inventario.sh` | listado navegable por carpeta temática, a partir del manifiesto |

Vigencia, derogaciones, bloqueos de descarga y PDF sin texto: `../../registro/marco-legal-pendientes.md`.
