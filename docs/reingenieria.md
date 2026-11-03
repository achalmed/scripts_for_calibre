---
tipo: doc
estado: activo
forma: explicacion
titulo: "Reingeniería de Biblioteca Studio (2026-11-02): de nueve tablas a un gestor bibliográfico con portadas, ficha editorial y bandejas de trabajo"
creado: 2026-11-02
---
# Reingeniería de Biblioteca Studio: diagnóstico, distribución y decisiones

Encargo del autor del 2026-11-02 (§3.6 de la instrucción maestra de la reingeniería de los diez studios): Biblioteca
Studio debe parecer un gestor de biblioteca y un centro de investigación documental, con la biblioteca de Calibre en
el centro; no una tabla de archivos. El catálogo con portadas es la vista principal; la ficha del libro se lee de
manera editorial; las bandejas de trabajo y el Método Documental van aparte; y toda escritura sigue los seis pasos de
la puerta (Calibre cerrado, candado, respaldo verificado, aplicar, verificar la integridad, liberar), que la ventana
muestra sin reimplementarlos. Este documento es el diagnóstico de la ventana 2.0 (`rediseno.md`), la distribución
nueva y sus decisiones (B1–B12). Lo construido, cómo se verificó y lo que quedó fuera, en §4 y §5.

## 1. Diagnóstico de la ventana 2.0 (leído en el código, `respaldo/antes-reingenieria-2026-11-02`)

Capturas de antes: `docs/figuras/antes/biblioteca-studio-{oscuro,claro,paleta}.png`.

### 1.1 Qué hace cada pieza hoy

| pieza | dónde | qué hace de verdad |
|---|---|---|
| el índice | `lib/indice.py` | lee `metadata.db` y `zotero.sqlite` en solo lectura y deja un JSON con título, autores, carpeta, formatos, clave de Zotero, clave para citar, fichas y nota. **Correcto**, y es contrato de los complementos; pero no trae año, serie, etiquetas, editorial, idioma, identificadores, tipo ni lectura de KOReader |
| la vista Libros | `studio/biblioteca_app/controladores/libros.py`, `Main.qml` | una `TablaDatos` (título, autores, Calibre, Zotero, clave, fichas, nota) con cinco filtros de coherencia es la vista principal |
| el libro | `ResumenLibro` (retirado) | un panel de detalles con la portada a tamaño completo (el `cover.jpg` sin miniatura), las claves y los formatos; sin metadatos editoriales ni estado de lectura |
| las etapas | `studio/biblioteca_app/controladores/etapas.py`, `studio/biblioteca_app/servicios/datos.py` | ocho tablas más (Adquirir, Entrada, Catalogar, Fichas, Manifiestos, Sincronizar, Puerta, Tareas) con su elemento. Correctas como datos de trabajo |
| las operaciones | `studio/biblioteca_app/servicios/operaciones.py`, `studio/biblioteca_app/controladores/operaciones.py` | cada una es la CLI de su suite: F5 simula, Ctrl+Intro aplica tras un diálogo con la orden exacta. **Correcto**: la ventana no escribe |
| la puerta | `studio/biblioteca_app/servicios/puerta.py`, `studio/biblioteca_app/controladores/puerta.py` | dice si Calibre o Zotero están abiertos y si el candado está ocupado, y deshabilita Aplicar; los respaldos y los timers en tablas. No se ve qué paso de la puerta dio o falló una aplicación |

### 1.2 Lo incompleto y lo que no se comporta

- **La distribución es la de Dolphin**: navegación · tabla · detalles en seis pestañas · consola. Nueve vistas al mismo
  nivel: la biblioteca es una tabla más entre las de los ledgers.
- **Sin catálogo**: ni portadas, ni búsqueda por campo (título, autor, año, serie, etiqueta, identificador, clave), ni
  filtros por colección, autor, año o tipo. El filtro de texto busca en las columnas visibles.
- **La ficha no es editorial**: no hay metadatos completos (editorial, año, idioma, serie, identificadores, etiquetas,
  descripción), ni estado en Zotero y en KOReader con su progreso.
- **Las bandejas de trabajo están escondidas** en los filtros de Libros (Sin Zotero, Sin clave…) y en las tablas de las
  etapas; lo pendiente de clasificar y las fichas incompletas no se ven como trabajo.
- **Los seis pasos de la puerta no se ven**: el diálogo dice «la puerta vuelve a comprobarlo»; tras aplicar solo queda
  el código de salida y la salida en el panel inferior.
- **«Abrir la carpeta» y «abrir el archivo»** pasan por `xdg-open`; con `gui-comun` 3.0, `escritorio.mostrarEnDolphin`
  señala el archivo y `escritorio.abrirConAplicacion` lo abre con su aplicación.
- **Datos ficticios**: ninguno en la ventana; la muestra de pruebas no tiene portadas.

### 1.3 Riesgos

| riesgo | mitigación |
|---|---|
| leer `metadata.db` con Calibre abierto o mientras una suite escribe | solo lectura (`mode=ro`), como `lib/indice.py`; si la base está ocupada, se cae a `immutable` y se dice en la barra |
| miles de portadas en memoria | miniaturas bajo demanda (proveedor de imágenes asíncrono), leídas de `cover.jpg` en solo lectura y guardadas en la caché del studio con un tope de tamaño; la cuadrícula es virtual |
| tocar la biblioteca real en las pruebas | la muestra (`studio/muestra.py`) con portadas generadas; ninguna prueba aplica una suite que escriba |
| romper el contrato del índice | `lib/indice.py` no cambia: el catálogo completa el índice leyendo `metadata.db` por su cuenta, en solo lectura |
| reimplementar la puerta | la ventana no abre la puerta: lee la salida de la CLI (`── Backup:` y los `✗` de `lib/escribir.*`) y, al final, pide la integridad a `lib/escribir.py integridad` y mira si el candado quedó libre |

## 2. Referencias y distribución

| referencia | qué se toma |
|---|---|
| **Calibre** | la cuadrícula de portadas y la lista compacta, la búsqueda por campo (`autor:`, `serie:`), el panel del libro |
| **Zotero** | la colección a la izquierda y el ítem a la derecha; la clave para citar visible y copiable |
| **Koha, Tellico, Readest** | la ficha editorial (portada grande, título, mención de responsabilidad, pie de imprenta, serie, identificadores, materias) y el progreso de lectura |
| **centros de documentación** | las bandejas de trabajo (por catalogar, sin control de autoridad) separadas del catálogo |

```
┌ Catálogo · Bandejas · Método Documental · Coherencia │ [buscar: título autor año serie etiqueta id clave] │ ▦ ☰ │ puerta ┐
│ Filtros            │ ▦ ▦ ▦ ▦ ▦ ▦  portadas (o la lista compacta)           │ Ficha editorial: portada grande,  │
│ colección (serie)  │ ▦ ▦ ▦ ▦ ▦ ▦  título · autor · año · Z · clave · KO % │ metadatos, identificadores, clave, │
│ autor · año · tipo │ ▦ ▦ ▦ ▦ ▦ ▦                                           │ Zotero, KOReader, fichas y nota    │
└ barra de estado ─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Decisiones

- **B1. `VentanaBase` de `gui-comun` 3.0 con cuatro áreas** (Ctrl+1–4): Catálogo (la principal), Bandejas, Método
  Documental (las etapas Adquirir … Manifiestos) y Coherencia (Sincronizar, Puerta, Tareas automáticas).
- **B2. El catálogo lee Calibre en solo lectura** (`studio/biblioteca_app/servicios/catalogo.py`): título, autores,
  año, serie y número, etiquetas, editorial, idiomas, identificadores, tipo (`item_type` o `clasificador`), páginas,
  descripción y la lectura de KOReader (`#ko_progfloat`, `#ko_status`, `#ko_tiempo`, `#ko_lastmod`), por etiqueta de
  columna, nunca por número. Lo une al índice (clave de Zotero, clave para citar, fichas, nota). `lib/indice.py` no cambia.
- **B3. Portadas en miniatura** (`image://portadas/<id>`): un proveedor de imágenes asíncrono lee `cover.jpg` en solo
  lectura, lo escala y guarda la miniatura en `$XDG_CACHE_HOME/biblioteca-studio/portadas/` (clave: libro y fecha del
  archivo); la caché se poda a un tope (por omisión 200 MB). Sin portada, un sustituto con el título y el autor.
- **B4. Cuadrícula y lista compacta** (Ctrl+G alterna), con orden por título, autor, año o recién añadidos.
- **B5. Búsqueda avanzada**: palabras sueltas buscan en título, autores, serie, etiquetas y claves; `titulo:`, `autor:`,
  `año:` (o un rango `año:1990-2000`), `serie:`, `etiqueta:`, `id:` (un identificador o el número de Calibre) y `clave:`
  buscan en su campo; las comillas agrupan.
- **B6. Filtros por colección (la serie), autor, año (por décadas) y tipo**, con sus contadores, combinables con la búsqueda.
- **B7. La ficha editorial** (panel derecho del catálogo): portada grande, título, autores, pie de imprenta (editorial,
  año, idioma, páginas), serie, identificadores, etiquetas, descripción; la clave para citar (copiar); Zotero (enlazado o
  no); KOReader (estado, progreso, tiempo y última lectura); fichas y nota; abrir el documento con su aplicación,
  mostrarlo en Dolphin, abrir en Calibre y en Zotero.
- **B8. Las bandejas de trabajo**: pendientes de clasificar (la zona de entrada sin catalogar y los libros sin tipo),
  fichas incompletas (libros sin ficha canónica y fichas sin verificar), sin clave para citar, sin Zotero, sin portada;
  cada una con sus libros (con portada) y la operación que la vacía.
- **B9. Los seis pasos de la puerta, visibles** (`studio/biblioteca_app/servicios/pasos.py`): antes de aplicar, el
  estado de los dos primeros (app cerrada, candado libre); durante, la salida de la CLI marca el respaldo verificado y
  cualquier fallo; al terminar, la integridad (`lib/escribir.py integridad`, solo lectura) y el candado libre. La
  ventana no abre ni cierra la puerta.
- **B10. El Método Documental como recorrido**: las etapas en fila con sus contadores, la tabla de la etapa elegida (los
  ledgers son tablas: aquí sí) y su operación con los pasos de la puerta.
- **B11. KDE**: abrir el documento y mostrarlo en Dolphin con `escritorio` de la base; estados de operación en las
  acciones (lectura, simulación, escritura, instalación).
- **B12. Atajos**: Ctrl+1–4 las áreas, Ctrl+F buscar, Ctrl+G cuadrícula o lista, F9 los filtros, Ctrl+R actualizar el
  índice, F5 simular, Ctrl+Intro aplicar tras confirmar, Ctrl+Mayús+C copiar la clave, Ctrl+K la paleta.

## 4. Lo construido y cómo se verificó

![El catálogo con portadas y la ficha editorial](figuras/biblioteca-studio-claro.png)

| pieza | dónde |
|---|---|
| la ventana y las áreas (B1, B11, B12) | `studio/biblioteca_app/qml/Main.qml` sobre `VentanaBase`; `studio/biblioteca_app/controladores/espacio.py` (área y etapa); `studio/biblioteca_app/aplicacion.py` (Ctrl+1–4, Ctrl+F, Ctrl+G, F9, `escritorio`, estados de operación) |
| lo editorial (B2) | `lib/indice.py` (`editorial`, solo lectura, aditiva) y `studio/biblioteca_app/servicios/catalogo.py` (`leer`) |
| las portadas (B3) | `studio/biblioteca_app/controladores/portadas.py` (`image://portadas/<id>`, caché con tope) |
| cuadrícula y lista (B4) | `studio/biblioteca_app/qml/componentes/Catalogo.qml`, `TarjetaLibro.qml`, `FilaLibro.qml` |
| búsqueda y filtros (B5, B6) | `catalogo.consulta`, `cumple`, `facetas`, `cumple_filtros`; `studio/biblioteca_app/qml/componentes/PanelFiltros.qml` |
| la ficha editorial (B7) | `Libros.ficha` (`studio/biblioteca_app/controladores/libros.py`); `studio/biblioteca_app/qml/componentes/FichaEditorial.qml` |
| las bandejas (B8) | `catalogo.bandejas`; `studio/biblioteca_app/qml/componentes/Bandejas.qml` |
| los pasos de la puerta (B9) | `studio/biblioteca_app/servicios/pasos.py`; `Operaciones.pasos` (`studio/biblioteca_app/controladores/operaciones.py`); `studio/biblioteca_app/qml/componentes/PasosPuerta.qml`, en la operación y en el diálogo de Aplicar |
| el Método Documental (B10) | `studio/biblioteca_app/qml/componentes/EspacioEtapas.qml` |

Verificación (2026-11-02, rama `wip/2026-11-02-reingenieria`):

- `tests/run.sh`: 47 pruebas sobre la muestra (búsqueda por campo, facetas, orden y bandejas; la ficha editorial; el
  catálogo leído en solo lectura sin tocar la fecha de la base; los pasos de una aplicación buena y de cada fallo de la
  puerta; la vista previa de la puerta con Calibre abierto; la integridad con `lib/escribir.py integridad` sobre la
  muestra; la ventana entera con sus áreas, la búsqueda y una miniatura real; cada componente QML con un libro abierto).
  Ninguna aplica una suite que escriba.
- `python3 -m pytest tests/calibre`: en verde salvo `test_fichas_con_proyecto_por_id`, que falla en `main` por 165
  fichas de la ingesta del 27 y 28 de octubre (`estado.md` §Por hacer); `test_puerta.py` exime a `studio/muestra.py`
  (fallaba en `main` desde la fase 5).
- La lectura de lo editorial sobre la biblioteca real, en solo lectura: unas décimas de segundo para leerla entera y
  una décima por búsqueda (`editorial` de `lib/indice.py`, medida con `time`).
- Capturas sobre la muestra, sin rutas de la máquina: `docs/figuras/biblioteca-studio-{claro,oscuro,lista,bandejas,
  metodo,aplicar,paleta}.png`; las de antes, en `docs/figuras/antes/`.

## 5. Lo que quedó fuera

- **Editar metadatos desde la ventana**: sigue siendo de las suites (catalogación, migraciones) por la puerta.
- **Cambiar o generar portadas**: solo se leen; la bandeja «Sin portada» las señala.
- **Los pasos de una aplicación real no se probaron con escritura**: las pruebas no aplican suites que escriban; la
  lectura de la salida se prueba con las líneas reales de `lib/escribir.*`. La primera aplicación de verdad la mira el
  autor (`estado.md` §Por hacer).
- **El catálogo se refresca solo** desde el 2026-11-03: un vigilante (`QFileSystemWatcher`) sobre `metadata.db` y su
  carpeta relee en solo lectura cuando la firma del archivo (y la de su diario) cambia, tras 1,5 s de calma; se apaga
  en Ver › Vigilar la biblioteca de Calibre.
