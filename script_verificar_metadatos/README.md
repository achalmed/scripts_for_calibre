---
tipo: readme
estado: activo
---
# script_verificar_metadatos/ — coteja Calibre con OpenLibrary y Crossref (solo lectura)

<!-- suite:inicio -->
**Suite `verificar_metadatos`** · objetivo *biblioteca* · estado *activo* · bash · interfaz cli

Coteja los metadatos de Calibre contra bases bibliográficas públicas y escribe un informe de discrepancias; nunca modifica la biblioteca.

- Escribe en: ninguno · simula por defecto: sí
- Depende de: CORE_PYTHON (urllib; sin curl), core/shell-lib, lib/leer.sh

Comandos:

```bash
main.sh                      # informe en reportes/
main.sh --modo isbn
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-05); no se edita a mano.</sub>
<!-- suite:fin -->

Coteja los metadatos de Calibre con bases bibliográficas públicas (OpenLibrary y, de respaldo,
Crossref) y deja un **informe de discrepancias** para corregir a mano. Es de **solo lectura**: lee
`metadata.db` en modo `ro` (`../lib/leer.sh`) y nunca escribe en Calibre, así que no hace falta
cerrarlo. Sirve para
casos como una editorial vacía o falsa (`ePubLibre` es la web del reempaquetado, no la editorial),
el año de otra edición o un número de páginas erróneo.

## Uso

```bash
main.sh --limite 5        # prueba rápida sobre 5 libros con identificador
main.sh                   # modo isbn: todos los libros con identificador
main.sh --modo titulo     # además busca por título y autor los que no lo tienen
main.sh --ids 425,739     # solo esos libros
main.sh --help            # opciones; --verbose da trazas
```

Cada pasada deja en `reportes/` un `discrepancias_<fecha>.tsv` (`id, campo, valor_calibre,
valor_fuente, fuente, confianza`) y un `discrepancias_<fecha>.md` para leer. `confianza` es `exacta`
en las búsquedas por identificador y `aprox:<ratio>` en las de título y autor. Tras corregir en
Calibre, `calibredb backup_metadata --all` (Calibre cerrado) para que ZMI y Zotero vean el cambio.

Requisitos: el Python de `core` (`CORE_PYTHON`; solo biblioteca estándar, HTTP por `urllib`) e
internet; ni clave de API, ni `curl`, ni `sqlite3`. El contacto del «polite pool» de Crossref llega
por la variable de entorno `CROSSREF_MAILTO` (sin ella, la consulta va sin `mailto`); ningún correo
vive en el código.

## Alcance y criterios

Solo se puede verificar lo que tiene identificador; el material de aula inédito no existe en ninguna
base y no se busca. Cuántos libros tienen ISBN (`CALIBRE_DB` la resuelve `core/env.sh`):

```bash
sqlite3 -readonly "$CALIBRE_DB" "SELECT count(DISTINCT book) FROM identifiers WHERE type='isbn'"
```

El modo `titulo` busca además por título y autor los publicados sin identificador, y cuando
OpenLibrary no encuentra nada consulta Crossref, que suele aportar un DOI que no teníamos (`doi
(encontrado)` en el informe).

Criterios, en `lib/verificador.py`:

- **año**: se marca solo si ambos existen y difieren;
- **editorial**: si Calibre está vacío, o si difieren claramente (ni subcadena ni similitud ≥ 0,6);
- **páginas**: solo si la diferencia pasa de 5;
- **título y autor**: se muestran como contexto, **jamás como sugerencia de cambio**, porque Zotero
  enlaza los adjuntos por la ruta `Autor/Título (id)`;
- en modo `titulo`, un candidato es «el mismo libro» solo con similitud de título ≥
  `FUZZY_TITLE_THRESHOLD`.

## Estructura

`main.sh` (orquestación) · `config.sh` (biblioteca, endpoints, `USE_CROSSREF`, `RATE_LIMIT_SECONDS`,
`HTTP_TIMEOUT`, `FUZZY_TITLE_THRESHOLD`, tipos de identificador) · `lib/`: `cli.sh` (opciones y
dependencias), `db.sh` (el único lugar que lee `metadata.db`), `verificador.py` (red y comparación
difusa), `report.sh` (rutas de salida y resumen) · `reportes/` es runtime ignorado.

## Límite honesto

- **Nunca escribe en Calibre**: las correcciones se aplican a mano.
- **Solo cubre lo que tiene identificador** o, en modo `titulo`, lo que una base pública indexa.
- **Depende de internet y de cuotas ajenas**: Google Books queda solo de referencia porque su cuota
  anónima responde `429`; Crossref se desactiva con `USE_CROSSREF="false"`.
- **Por debajo del umbral de similitud un candidato se descarta** para no dar falsos positivos,
  aunque fuera el libro correcto.
