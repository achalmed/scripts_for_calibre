---
tipo: readme
estado: activo
---
# zotero-series/ — organiza una colección de Zotero en subcolecciones por el campo Series (script «Run JavaScript», v2.0)

<!-- suite:inicio -->
**Suite `zotero-series`** · objetivo *biblioteca* · estado *activo* · - · interfaz cli

Organiza los ítems de una colección de Zotero en subcolecciones según su campo Series (script «Run JavaScript», v2.0); el único que sigue vivo de scripts_for_zotero.

- Escribe en: zotero · simula por defecto: no
- Entrada: colección de Zotero (CONFIG.nombreColeccionPrincipal, por defecto Calibre)
- Depende de: zotero
- Nota: sin main.sh: se ejecuta pegándolo en la consola de Zotero; modoSimulacion: false por defecto (ponerlo en true la primera vez); corre después de sincronizar-zotero, nunca antes

Comandos:

```bash
cat series_organizer.js | xclip -selection clipboard   # al portapapeles; pegar en Zotero → Herramientas → Desarrollador → Ejecutar JavaScript
node -e 'const A=Object.getPrototypeOf(async function(){}).constructor; new A(require("fs").readFileSync(process.argv[1],"utf8")); console.log("sintaxis ok")' series_organizer.js   # solo sintaxis, como la consola de Zotero; node --check no sirve
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-06); no se edita a mano.</sub>
<!-- suite:fin -->

> El único script vivo de `scripts_for_zotero` (repo retirado el 2026-08-09, hallazgo A3 de
> `meta/docs/historial/diagnosticos/AUDITORIA.md`). Es compatible con la sincronización Calibre ⇄ Zotero porque
> solo reorganiza colecciones: no toca metadatos ni etiquetas. Se corre **después** de
> `scripts-biblioteca/script_sincronizar_zotero`, nunca antes.

Script de JavaScript para Zotero (v2.0) que **organiza automáticamente los ítems de una colección en
subcolecciones según su campo "Series"**. Por ejemplo, si tienes 10 libros de la serie "Economía
Asiática", el script crea una subcolección llamada "Economía Asiática" dentro de tu colección
principal y mueve ahí esos 10 ítems.

## Qué es

Si importas tu biblioteca desde Calibre (u otra fuente que mantiene el campo "Series" en sus
metadatos), terminas con cientos de ítems sueltos en una sola colección. Este script los reorganiza
automáticamente en subcolecciones por serie, sin perder notas, anotaciones ni archivos adjuntos
(porque mueve el ítem padre completo, no toca sus hijos individualmente). En esta biblioteca la
serie de Calibre llega a Zotero por el sync (`series` en el ítem; `publicationTitle` en artículos),
así que el script solo tiene sentido sobre una colección ya sincronizada (el contrato del sync,
en `scripts-biblioteca/sincronizar-zotero/README.md`).

Requisitos: Zotero 6 o superior con la consola de Ejecutar JavaScript habilitada; ningún plugin
adicional; una colección existente cuyo nombre coincida con `CONFIG.nombreColeccionPrincipal` (por
defecto `"Calibre"`).

## Uso

```bash
cat series_organizer.js | xclip -selection clipboard   # copiar el script al portapapeles
node -e 'const A=Object.getPrototypeOf(async function(){}).constructor;
  new A(require("fs").readFileSync(process.argv[1],"utf8")); console.log("sintaxis ok")' \
  series_organizer.js                                  # sintaxis tras editarlo; no lo ejecuta
```

`node --check` no sirve: el script termina en un `return await` de nivel superior, que la consola de
Zotero acepta porque envuelve el código en una función asíncrona y Node rechaza. La orden de arriba
hace lo mismo que Zotero, construir esa función, sin llamarla.

1. Abre Zotero y haz una copia de seguridad (Archivo → Exportar biblioteca → Zotero RDF con
   archivos).
2. Ve a **Herramientas → Desarrollador → Ejecutar JavaScript**.
3. Pega el contenido completo de `series_organizer.js`.
4. **Antes de ejecutar**, revisa y ajusta la sección `CONFIG` al inicio del script (tabla de abajo);
   la primera vez, `modoSimulacion: true`.
5. Haz clic en **Run** (Ejecutar).
6. Revisa la consola de desarrollador para ver el detalle completo del proceso, fase por fase.

### Opciones de configuración (`CONFIG`)

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `nombreColeccionPrincipal` | `"Calibre"` | Nombre exacto de la colección a procesar. Debe coincidir tal cual aparece en Zotero. |
| `modoSimulacion` | `false` | Si es `true`, el script solo **muestra** qué haría, sin modificar nada. Ideal para probar antes de aplicar cambios reales. |
| `modoVerboso` | `true` | Si es `true`, muestra el detalle de cada elemento procesado en la consola. |
| `prefijoSeries` | `""` | Texto que se antepone al nombre de cada subcolección creada (ej. `"Serie: "`). |
| `mantenerEnColeccionPrincipal` | `false` | Si es `true`, los ítems se **copian** a la subcolección pero permanecen también en la colección principal. Si es `false`, se **mueven** (se quitan de la principal). |
| `limitePrueba` | `0` | Límite de ítems a procesar por ejecución. `0` = sin límite. Útil para probar con pocos ítems primero (ej. `10`). |

### Flujo del script (4 fases)

1. **Recopilación de elementos**: obtiene todos los ítems "regulares" (no notas ni adjuntos sueltos)
   de la colección principal.
2. **Agrupación por series**: lee el campo `series` de cada ítem y los agrupa en un mapa en memoria
   por nombre de serie.
3. **Creación/actualización de subcolecciones**: por cada serie única, busca si ya existe una
   subcolección con ese nombre; si no existe, la crea. Luego mueve (o copia, según
   `mantenerEnColeccionPrincipal`) los ítems correspondientes.
4. **Verificación final**: cuenta cuántos elementos quedaron en cada subcolección y cuántos
   permanecen en la colección principal, para que puedas confirmar que el proceso se completó
   correctamente.

Al final se imprime un resumen con tiempo total de ejecución, número de series procesadas,
subcolecciones creadas/reutilizadas, elementos movidos, elementos sin serie y errores encontrados.

## Estructura

`series_organizer.js` (todo el script: cabecera, `CONFIG`, las cuatro fases y el resumen) ·
`suite.yml` (manifiesto) · este README. Sin `main.sh`, `config` ni `lib/`: la configuración es el
bloque `CONFIG` dentro del propio script.

## Solución de problemas

| Problema | Causa probable / Solución |
|---|---|
| `No se encontró la colección "Calibre"` | El nombre en `CONFIG.nombreColeccionPrincipal` no coincide exactamente con el de Zotero. El mensaje de error lista las colecciones disponibles para que copies el nombre correcto. |
| `No se encontraron elementos con series` | Ninguno de los ítems en la colección tiene el campo "Series" lleno. Verifica los metadatos de tus ítems. |
| Aparecen advertencias de "No se detectan elementos en la subcolección" | Puede deberse a una recarga de caché de Zotero; vuelve a revisar la subcolección manualmente en la interfaz. |
| El script va lento | Es normal con bibliotecas grandes, ya que cada movimiento de ítem usa su propia transacción. Considera usar `limitePrueba` para procesar por partes. |

## Límite honesto

- **Modifica permanentemente la estructura de colecciones**; no hay deshacer: la copia de seguridad
  previa es la única vuelta atrás, y el proceso es reversible solo a mano (mover los ítems de
  vuelta).
- **`modoSimulacion` es `false` por defecto**: la simulación hay que pedirla editando el script;
  también puede combinarse `modoSimulacion: false` con `limitePrueba: 10` para un ensayo real
  acotado.
- **Solo agrupa por el campo `series` del ítem**: los ítems sin serie se cuentan y se dejan donde
  están; no infiere series desde el título ni desde Calibre. Los artículos sincronizados llevan la
  serie en `publicationTitle`, que el script no lee: quedan siempre sin serie.
- **No se ejecuta fuera de Zotero**: fuera de él solo se comprueba la sintaxis (Uso); no hay timer,
  ni `--dry-run`, ni lo invoca ninguna otra suite.
- **Transacciones por ítem** (añadir a la subcolección y, si se mueve, quitar de la principal):
  lento en colecciones grandes; no es seguro lanzarlo dos veces a la vez.
