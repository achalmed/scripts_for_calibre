---
tipo: readme
estado: activo
---
# fuentes/congreso/ — normas y documentos del Congreso de la República

Conector de la suite `fuentes` para normas y documentos del Congreso: `localizar.py` encuentra la
URL por número de norma y `config.py` guarda patrones, periodos y tiempos de espera. Se usa con
`main.py localizar congreso` y `main.py descargar congreso`; cómo se añade otro conector:
`../../docs/ampliar.md`.

## Advertencia: la capa de texto de los PDF oficiales del Congreso está corrupta

Hallazgo del 31 de julio de 2026 al analizar los tres reglamentos del Congreso bicameral. Los PDF
oficiales usan fuentes sin mapa `ToUnicode`: al copiar texto se obtiene un cifrado (donde dice
«modificar o derogar las existentes» se copia `PRGL¾FDURGHURJDUODVH[LVWHQWHV`). Se probaron tres
extractores y se contrastaron entre sí:

| método | resultado |
|---|---|
| `pdftotext` | texto cifrado y sin espacios en los tramos afectados |
| `mutool` | texto limpio pero pierde el 11 % (líneas enteras) |
| **`ocrmypdf -l spa`** | limpio y completo: el que hay que usar |

Validación cruzada: descifrar el texto de `pdftotext` (desplazamiento ASCII +29, con vocales acentuadas
y la ligadura «fi» mapeadas aparte) coincide con el OCR. Límite conocido: los números romanos del
Título Preliminar salen mal (I, II → «Il»; III → «lll»).

Regla para todo documento del Congreso que entre a la biblioteca: pasar `ocrmypdf -l spa` (paso `ocr`
de la ingesta: `ingesta/main.sh ocr --aplicar` convierte `X.ocr.pdf` en formato del libro de `X.pdf`)
y nunca copiar y pegar del PDF original a un proyecto de ley, dictamen u oficio. Los textos OCR de los
cuatro reglamentos (unicameral 2025, Congreso 2026, Diputados, Senado) son el formato TXT de los libros
10086, 10095, 10090 y 10103. Memoria de vigencia y bloqueos de descarga: `registro/marco-legal-pendientes.md`.
