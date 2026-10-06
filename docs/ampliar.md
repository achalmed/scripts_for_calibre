---
tipo: procedimiento
titulo: "Ampliar: una fuente, una raíz de entrada, un paquete de anexos, una sigla o una suite"
genero: guia
estado: activo
---
# Ampliar

Qué se toca, y en qué orden, para que el repo adquiera o ingiera algo que hoy no sabe. Todo
cambio se ensaya en simulación (sin `--aplicar`) y se lee el plan antes de escribir. La forma del
recorrido está en [arquitectura.md](arquitectura.md).

## Una fuente nueva de documentos

Una fuente es una carpeta `fuentes/<nombre>/` con dos archivos; `main.py` la descubre sola (toda
carpeta con `localizar.py`):

- **`config.py`**: `NOMBRE`, `DESCRIPCION`, `TIPOS` (lo que `main.py fuentes` imprime como
  «acepta») y lo que el localizador necesite: patrones de URL, endpoints, tiempos de espera.
  Una credencial va por variable de entorno, nunca escrita en el archivo.
- **`localizar.py`**: una función `localizar(referencia, cfg)` que devuelva un diccionario con
  `url` y `fuente` (y, si los sabe, `tipo`, `numero` y `titulo`, que dan nombre al archivo y a la
  fila del ledger), o con `error` explicando qué se intentó.

Nada más: la red con reintentos, la validación por bytes mágicos, el hash, el ledger y la CLI los
pone `lib/comun.py`. Se prueba en este orden:

```bash
python3 main.py fuentes                          # aparece, con su descripción y sus tipos
python3 main.py localizar <nombre> "<ref>"       # solo lectura: ¿encuentra la URL?
python3 main.py descargar <nombre> "<ref>"       # escribe en entrada/ y en el ledger
```

Solo acceso abierto: una fuente no usa credenciales institucionales, proxies ni nada que esquive
un muro de pago. Las fuentes previstas están en [`../estado.md`](../estado.md) §Futuro. La
fuente nueva se añade a la descripción de `suite.yml` (raíz) y se regenera su bloque (última
sección).

## Una raíz de entrada para `ingesta`

Cuando un documento nace en otra carpeta del espacio de trabajo y debe catalogarse donde está:

1. `ingesta/config.sh`: la carpeta en `INBOX_RAICES` y, si hace falta, el patrón de subcarpetas
   en `INBOX_RAICES_SOLO` (solo entran rutas que casen) y lo que se excluye en
   `INBOX_RAICES_EXCLUIR`.
2. `manifiesto/config.py`: la regla en `REGLAS_RAIZ` que dice qué carpeta lleva el `fuentes.yml`
   de esos archivos, y la raíz en `RAICES_VIGILADAS` si `manifiesto todo` y el doctor deben
   recorrerla.
3. Ensayo: `ingesta/main.sh recibir`, `identificar` y `catalogar` sin `--aplicar`;
   `python3 manifiesto/main.py raiz <archivo>` dice dónde iría su manifiesto.

En una raíz externa solo se ingieren documentos de consulta (PDF): un `.xlsx` de `datafw` es
dato de procesamiento y no se cataloga.

## Un paquete de anexos

Cuando una carpeta trae un documento principal con muchos anexos (el presupuesto del MEF), se
declara en `PAQUETES_JSON` de `ingesta/config.sh`: la `raiz` (cada subcarpeta directa es un
paquete) y sus `familias`, cada una con `principal` y `adjuntos` como expresiones sobre el
**prefijo** del nombre de archivo (una subcadena atrapa anexos que mencionan la ley). Si falta el
texto principal, `sin_principal` dice con qué título, autor y serie crear el libro. Se ensaya con
`ingesta/main.sh paquetes` sin `--aplicar`.

## Una institución o una sigla

- Para que `identificar` reconozca al autor por el nombre de archivo: la sigla en `SIGLAS_JSON`
  y, si se decide por carpeta, la institución en `INSTITUCION_POR_CARPETA_JSON`
  (`ingesta/config.sh`). Las etiquetas por carpeta, en `TAGS_POR_CARPETA_JSON`, solo con valores
  del vocabulario cerrado de etiquetas de la biblioteca (lo custodia `scripts-biblioteca`).
- Para que `references.bib` lleve `shortauthor`: la sigla en `SIGLAS` de `manifiesto/config.py`.
  Solo siglas conocidas; una institución sin sigla se cita entera
  (`prompts/00 metodo/normas_apa7.md`).

## Un paso del formato de ficha

`fichas/config.py` transcribe `prompts/00 metodo/fichas_formato_y_voz.md`: si la norma cambia
(una clave, un tipo, una sección, un patrón de nombre), primero cambia la norma en `prompts` y
después su transcripción aquí; nunca al revés.

## Una suite nueva

Una carpeta con `main.py` (o `main.sh`), `config.py` (o `config.sh`), `lib/`, `suite.yml` y
`README.md`. El `suite.yml` sigue `core/suite.schema.yml` (`core/suites.py plantilla <carpeta>`
lo esboza) y la raíz y el logger salen de `core/`. Después, desde `~/Documents`:

```bash
python3 core/suites.py validar                   # el suite.yml contra el esquema
python3 core/suites.py generar                   # simula los bloques suite:/suites: y el índice
python3 core/suites.py generar --aplicar         # los escribe
```

La suite nueva se añade a la tabla de [arquitectura.md](arquitectura.md) §3 (qué escribe) y, si otro
repositorio la usa, a su §6 (Consumidores).
