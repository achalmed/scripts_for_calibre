---
tipo: readme
estado: activo
---
# studio/ — Biblioteca Studio, la ventana (QML + Kirigami sobre gui-comun 2.x) de las suites de la biblioteca: Calibre, Zotero y KOReader
<!-- suite:inicio -->
**Suite `biblioteca_studio`** · objetivo *biblioteca* · estado *activo* · python · interfaz gui

Ventana de la biblioteca (QML + Kirigami sobre gui-comun 2.x): los libros del índice con sus claves, la tabla de lo que maneja cada etapa del Método Documental (adquirir, entrada, catalogar, fichas, manifiestos), las comprobaciones de coherencia Calibre ⇄ KOReader ⇄ Zotero, la puerta y las tareas automáticas; cada operación es la CLI de su suite: F5 simula, Ctrl+Intro aplica tras confirmar.

- Escribe en: calibre, zotero · simula por defecto: sí
- Depende de: /usr/bin/python3 con PySide6 del sistema (python3-pyside6.*) y Kirigami (qml6-module-org-kde-kirigami), gui-comun 2.3 (módulo QML GuiComun), las suites de este repo (escriben por lib/escribir*, la puerta)
- Nota: No escribe por su cuenta: corre la CLI de cada suite, primero simulando (F5); «Aplicar» (Ctrl+Intro) confirma con la orden exacta y se desactiva con Calibre o Zotero abiertos o el candado ocupado.

Comandos:

```bash
main.py
main.py biblioteca-studio://libro/48
main.py --smoke
install.sh
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-11-02); no se edita a mano.</sub>
<!-- suite:fin -->

## Qué es

La ventana de las suites de este repo con el espacio de trabajo de la familia de studios (`gui-comun` 2.x; el diseño, en
[../docs/rediseno.md](../docs/rediseno.md)): menú, barra corta, navegación, centro, detalles, panel inferior, barra de
estado y paleta de órdenes (Ctrl+Alt+I · Ctrl+K). Nueve vistas en tres secciones (Ctrl+1 … Ctrl+9), cada una con **la
tabla de lo que maneja** y **sus operaciones** (las de la lista de la barra o del menú Método): la elegida se corre con
**Simular (F5)**, la orden de la suite sin `--aplicar`, y con **Aplicar (Ctrl+Intro)**, con `--aplicar` tras un diálogo
que muestra la orden exacta, las bases que toca y el estado de la puerta.

| vista | centro | operaciones | detalles |
|---|---|---|---|
| **Libros** (Biblioteca; filtros Todos · Sin Zotero · Sin clave para citar · Sin ficha · Sin nota enlazada) | los libros del índice de `lib/indice.py` (título, autores, Calibre, Zotero, clave para citar, fichas, nota), filtrables con Ctrl+F | Actualizar el índice (también Ctrl+R) | Resumen (portada, claves, formatos, nota; Abrir en Calibre, en Zotero, el archivo, la nota, Copiar la clave) · Fichas |
| **Adquirir** · **Entrada** · **Catalogar** · **Fichas** · **Manifiestos** (Método Documental) | el ledger de descargas; la zona de entrada cruzada con los ledgers de ingesta (recibido · identificado · catalogado); las filas de `resumen_catalogacion.tsv`; las fichas canónicas con su verificación; los proyectos con `fuentes.yml` | las de `fuentes`, `ingesta`, `catalogacion`, `verificacion`, `migraciones`, `fichas`, `lecturas` y `manifiesto` (las tarjetas de antes) | Elemento (los campos de la fila; la ficha o el manifiesto en texto) · Operación (qué hace, la orden, lo que pide, la puerta) · Plan (la última simulación) · Registro (la última aplicación) |
| **Sincronizar** · **Puerta** · **Tareas automáticas** (Coherencia) | las comprobaciones de coherencia calculadas del índice y los ledgers (sin correr nada); los respaldos de la puerta; los tres timers de usuario | los sincronizadores (`sincronizar-zotero`, `koreader`, `lectura`, `lib/enlazar_notas.py`, `metadatos-pdf`); `systemd/instalar.sh` | los mismos; en Puerta, los candados y cómo deshacer |

**La ventana no escribe en ninguna base**: cada operación es la CLI de su suite, la misma de la terminal, que pasa por la
única puerta (`../lib/escribir.*`: aplicación cerrada, candado y respaldo verificado). Aplicar se deshabilita con Calibre
o Zotero abiertos o el candado ocupado (la barra de estado lo dice). La salida corre en el panel inferior (F4), Esc
cancela, y el plan y el registro de cada operación quedan en la caché del studio. El libro de los complementos
(`biblioteca-studio://libro/<id>`) se selecciona en Libros; con la ventana abierta, un enlace nuevo va a ella.

## Estructura

| archivo | qué es |
|---|---|
| `main.py` | el punto de entrada, sin lógica (`/usr/bin/python3`); una sola instancia (`QLocalServer`) |
| `biblioteca_app/aplicacion.py` | arma la aplicación: controladores, el registro de acciones (menú, barra, menú contextual, paleta, atajos: cada operación una sola vez) y `biblioteca_app/qml/Main.qml` |
| `biblioteca_app/servicios/` | sin Qt: `operaciones` (el catálogo: cada una con su orden, su bandera de aplicar, en qué base escribe, lo que pide), `puerta` (procesos, candados, respaldos, timers), `datos` (el índice, los ledgers, las fichas, los manifiestos, la coherencia) |
| `biblioteca_app/modelos/` | las filas de las tablas, sin Qt (los modelos de Qt son los de `gui_comun.modelos`) |
| `biblioteca_app/controladores/` | lo que QML ve: `espacio` (vista, barra de estado, rutas), `libros`, `etapas` (las tablas y el elemento), `operaciones` (la actual, Simular y Aplicar por `gui_comun.tareas`, plan y registro), `puerta`, `ajustes` |
| `biblioteca_app/qml/` | `Main.qml` sobre `GuiComun.VentanaStudio` y los componentes propios (`componentes/`) |
| `biblioteca_app/recursos/marca.svg` | el icono del lanzador: la única marca del studio |
| `muestra.py` | la biblioteca de muestra (libros ficticios con `calibredb`, Zotero mínimo, ledgers y fichas) de las pruebas y las capturas; nunca la real |
| `capturar.py` | las capturas de la documentación sobre la muestra, con `HOME` temporal |
| `install.sh` | el acceso directo del menú y el esquema `biblioteca-studio://` (`gui_comun.lanzador`) |

## Uso

```bash
/usr/bin/python3 studio/main.py                               # desde biblioteca-studio/, en la sesión real
/usr/bin/python3 studio/main.py biblioteca-studio://libro/48   # abre el libro 48 (lo piden los complementos)
QT_QPA_PLATFORM=offscreen /usr/bin/python3 studio/main.py --smoke     # construye la interfaz y sale
studio/install.sh                                             # acceso directo en el menú y el esquema (con -n, simula)
/usr/bin/python3 studio/capturar.py docs/figuras/biblioteca-studio-oscuro.png --esquema <LliphiOscuro.colors> --vista entrada --pestana 3
tests/run.sh                                                  # desde biblioteca-studio/: servicios, controladores, cada QML y --smoke sobre la muestra
```

Los complementos: `../calibre-plugin/`, `../koreader-plugin/`, `../zotero-plugin/` (no cambian con la ventana).

## Límite honesto

- **Las suites de Python corren con `CORE_PYTHON`** (`/usr/bin/python3`, el mismo de los timers); una suite que necesite
  otro intérprete se cambia en `biblioteca_app/servicios/operaciones.py`, no en la ventana.
- **La vista Manifiestos se lee al mostrarse** (recorre `escritura` y los datos crudos de `datafw`): su contador aparece
  entonces.
- **La tabla Entrada lista la zona de entrada y las filas de `pendientes.tsv`** (también las de `datafw/data/raw`, aunque
  el archivo ya no exista: «sin archivo»); lo que `ingesta estado` imprime.
- **El plan y el registro se guardan por operación**, no por corrida: cada simulación reemplaza el plan anterior.
- **Las operaciones con entrada de texto** parten el texto como la terminal (`shlex`): las comillas valen.
- **Restaurar un respaldo sigue siendo a mano** (vista Puerta, pestaña Elemento).
