---
tipo: readme
estado: activo
---
# studio/ — Biblioteca Studio, GUI PySide6 de las suites de la biblioteca: Calibre, Zotero y KOReader
<!-- suite:inicio -->
**Suite `biblioteca_studio`** · objetivo *biblioteca* · estado *activo* · python · interfaz gui

Aplicación de escritorio (PySide6) sobre las suites de la biblioteca: simular y aplicar cada paso del Método Documental, el libro de un vistazo y la puerta.

- Escribe en: calibre, zotero · simula por defecto: sí
- Depende de: PySide6, gui-comun, las suites de este repo (escriben por lib/escribir*, la puerta)
- Nota: No escribe por su cuenta: corre la CLI de cada suite, primero simulando; «Aplicar» se desactiva con Calibre o Zotero abiertos.

Comandos:

```bash
main.py
main.py biblioteca-studio://libro/48
main.py --smoke
install.sh
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-31); no se edita a mano.</sub>
<!-- suite:fin -->

## Qué es

La ventana de las suites de este repo con el marco común de los studios (`gui-comun`, acento sepia):

| página | qué hace |
|---|---|
| Inicio | cifras del índice, si Calibre o Zotero están abiertos, los candados y la búsqueda de un libro |
| Entrada · Adquirir · Catalogar y verificar · Sincronizar · Fichas y lecturas · Manifiestos | cada paso del Método Documental como tarjeta con «Simular» y «Aplicar» (`biblioteca_app/acciones.py`) |
| el libro | portada, autores, claves, fichas; abrir en Calibre, en Zotero, el archivo o la nota; copiar la clave |
| Puerta | candados, los respaldos de cada escritura (`$RESPALDOS_DIR/biblioteca/puerta/`) y los timers |

**No escribe por su cuenta**: cada tarjeta corre la CLI de su suite (la misma orden que en la terminal), primero
simulando; «Aplicar» pide confirmación y se desactiva si la aplicación de la base (Calibre o Zotero) está abierta.
Así la puerta de escritura sigue siendo una sola (`lib/escribir*`). Restaurar un respaldo sigue siendo a mano.

El libro de un vistazo y los complementos salen del índice de `lib/indice.py` (solo lee las bases;
`$XDG_STATE_HOME/biblioteca/indice.json`). El esquema `biblioteca-studio://libro/<id>` lo registra `install.sh`;
con la ventana abierta, un enlace nuevo va a ella (una sola instancia).

## Uso

```bash
python3 studio/main.py                                # desde biblioteca-studio/
python3 studio/main.py biblioteca-studio://libro/48   # abre el libro 48
studio/install.sh                                     # acceso directo en el menú y el esquema (con -n, simula)
studio/install.sh --quitar
```

Los complementos: `../calibre-plugin/`, `../koreader-plugin/`, `../zotero-plugin/`.

## Cómo se prueba

```bash
python3 -m pytest -q biblioteca-studio/tests/studio   # desde ~/Documents: la ventana sin pantalla, un índice falso
```
