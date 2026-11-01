---
tipo: readme
estado: activo
---
# zotero-plugin/ — la extensión «Ecosistema» de Zotero: el libro en Calibre y sus fichas, y el organizador por series

## Qué es

Un complemento de Zotero (arquitectura de Zotero 7 y posteriores: `manifest.json` + `bootstrap.js`) con dos piezas:

1. **La sección «Ecosistema» del panel del ítem.** Para un ítem normal (o, con un adjunto o una nota hija
   seleccionados, para su padre) muestra el `calibre_id`, que saca de la ruta del adjunto enlazado
   (`attachments:<Autor>/<Título> (<calibre_id>)/<archivo>`, la misma expresión que `lib/indice.py`); si el libro
   sigue en la biblioteca según el índice; cuántas fichas de `catalogacion/fichas/` lo citan, y si tiene nota de
   lectura (el archivo existe). Botones: **Abrir en Calibre** (`calibre://show-book/_hex_-<hex del nombre de la
   carpeta de la biblioteca>/<id>`), **Abrir en Biblioteca Studio** (`biblioteca-studio://libro/<id>`) y **Abrir la
   nota de lectura**. Sin `calibre_id`, la sección lo dice.
2. **«Organizar por series…»**, en Herramientas y en el menú contextual de una colección. Hace lo mismo que
   [`../zotero-series/series_organizer.js`](../zotero-series/series_organizer.js) (mover los ítems padre de la
   colección a una subcolección por su campo Series, sin tocar hijos, metadatos ni etiquetas), pero **simula
   siempre primero**: arma el plan, muestra una vista previa (subcolecciones nuevas y reutilizadas, cuántos ítems van
   a cada una, cuántos quedan sin serie) y solo escribe si se acepta; cancelar es la simulación.

La sección solo **lee**: el índice JSON que escribe `python3 lib/indice.py --aplicar` en
`$XDG_STATE_HOME/biblioteca/indice.json` (sin `XDG_STATE_HOME`, `~/.local/state/biblioteca/indice.json`); nunca abre
`metadata.db` ni la base de Zotero por su cuenta. El índice se relee solo cuando cambia su fecha en el disco.

**Excepción declarada a la puerta única de escritura.** «Organizar por series» escribe en Zotero (crea
subcolecciones y cambia la pertenencia de los ítems a colecciones) desde dentro de Zotero, con su API
(`Zotero.Collection`, `addItems`, `removeItems`, una transacción por serie), igual que el guion de consola al que
reemplaza. No pasa por `lib/escribir_zotero.py` porque esa puerta exige Zotero cerrado y esta orden solo existe con
Zotero abierto. Lo que la acota: solo toca colecciones (nunca metadatos, etiquetas, adjuntos ni `metadata.db`),
simula por defecto y pide confirmación con la vista previa delante. La sección del panel no escribe nada.

## Uso

```bash
cd scripts-biblioteca/zotero-plugin
node pruebas.mjs        # prueba las funciones puras y lee (solo lee) el índice real si existe
./build.sh --dry-run    # qué empaquetaría, sin escribir
./build.sh              # comprueba la sintaxis con node y escribe dist/ecosistema-<versión>.xpi (dist/ no va a git)
```

Instalar: Zotero → **Herramientas → Complementos** → engranaje → **Instalar complemento desde archivo…** → elegir
`dist/ecosistema-<versión>.xpi`. Una versión nueva se instala igual, encima de la anterior.

Usar:

- **Sección**: seleccionar un ítem; la sección «Ecosistema» aparece en el panel derecho (y su icono en la barra
  lateral del panel). Si dice «no hay índice», correr antes `python3 lib/indice.py --aplicar`.
- **Organizar por series**: seleccionar la colección (p. ej. `Calibre`) → clic derecho → **Organizar por series…**
  (o Herramientas → Organizar por series…) → leer la vista previa → **Aceptar** escribe, **Cancelar** solo simula.
  Antes de la primera vez, copia de seguridad de Zotero (Archivo → Exportar biblioteca). Corre después de
  `sincronizar-zotero`, nunca antes, como el guion de consola.
- **Opciones** (el bloque `CONFIG` del guion de consola), en Ajustes → Avanzado → Editor de configuración:
  `extensions.ecosistema.prefijoSeries` (texto antes del nombre de cada subcolección, `""`),
  `extensions.ecosistema.mantenerEnColeccionPrincipal` (`false` mueve; `true` copia) y
  `extensions.ecosistema.limite` (ítems por vez; `0` = todos).

Comprobar tras editar:

```bash
for f in bootstrap.js prefs.js content/*.js pruebas.mjs; do node --check "$f"; done
python3 -m json.tool manifest.json >/dev/null && echo "manifest válido"
```

## Estructura

| archivo | qué hace |
|---|---|
| `manifest.json` | WebExtension con `applications.zotero` (id `ecosistema@scripts-biblioteca`, de Zotero 7.0 a 10.*) |
| `bootstrap.js` | `install`, `startup`, `onMainWindowLoad`, `onMainWindowUnload`, `shutdown`, `uninstall`; registra `chrome://ecosistema/` y carga `content/` |
| `content/puras.js` | lo que decide, sin Zotero ni disco: calibre_id de una ruta, hex UTF-8, URLs, ruta del índice, resumen del libro, plan y vista previa de series |
| `content/ecosistema.js` | lo que toca Zotero: leer el índice (`IOUtils`), la sección (`Zotero.ItemPaneManager.registerSection`), los menús (`Zotero.MenuManager`; en Zotero 7, por DOM y quitados al descargar la ventana) y la escritura de series |
| `locale/es-ES/ecosistema.ftl` | los textos de la cabecera, la barra lateral y el menú (Fluent); `en-US` es copia: la extensión habla en español |
| `prefs.js` | las tres preferencias por defecto |
| `build.sh` | empaqueta el `.xpi` en `dist/` |
| `pruebas.mjs` | `node:test` sobre `content/puras.js` y lectura del índice real |

## Límite honesto

- **`update_url` es obligatorio** aunque no haya actualizaciones automáticas: Zotero rechaza el complemento sin él
  («applications.zotero.update_url not provided») y, si se instala a mano en el perfil, lo borra. Apunta a propósito a
  `https://example.invalid/…` (un dominio que nunca resuelve): las versiones nuevas se instalan a mano.
- **`strict_max_version` es `10.*`**: el Zotero instalado se identifica como 10.0.x; con `8.*` lo declararía
  incompatible. Al pasar a 11 hay que subirlo y probar.
- **Probado de verdad** solo en Zotero 10.0.7 (Firefox 140 ESR), en un perfil y una carpeta de datos temporales,
  sin pantalla (Xvfb) y con un índice de prueba: instalación, sección pintada en el panel, menús, textos Fluent,
  vista previa, cancelar sin escribir, aceptar escribiendo, desactivar y reactivar limpios. **No** se probó con el
  perfil real ni con la biblioteca real, ni en Zotero 7 (la rama de menús por DOM, sin `MenuManager`, no se ejecutó
  nunca). `pruebas.mjs` no carga Zotero: prueba solo `content/puras.js`.
- **Biblioteca Studio** solo abre si el sistema tiene un manejador para `biblioteca-studio://` (lo registra
  `studio/install.sh`); si no, la extensión avisa «Handler not found». Lo mismo con `calibre://`, que registra Calibre.
- **El índice puede ir atrasado**: la sección dice lo que tenía el índice la última vez que corrió
  `lib/indice.py --aplicar` (lo corren el timer de KOReader y Biblioteca Studio). Un libro recién catalogado puede
  salir «no» hasta entonces. Las fichas se cuentan por su `calibre_id:`; la nota de lectura es la de `#apuntes` o
  `notas/<clave>.md`, y solo se ofrece si el archivo existe.
- **El `calibre_id` solo sale de adjuntos enlazados** cuya carpeta inmediata termina en `(<id>)`; un PDF guardado
  dentro de Zotero (`storage:`) o una ruta sin ese número da «sin calibre_id».
- **Organizar por series no se deshace**: la copia de seguridad previa es la única vuelta atrás (los ítems se
  pueden devolver a mano). Solo agrupa por el campo `series` de ítems regulares; los artículos llevan la serie en
  `publicationTitle` y quedan siempre sin serie, como en el guion. Una orden a la vez (la segunda espera aviso).
- **La vista previa muestra 25 series**; el detalle completo (con los títulos) va a la salida de depuración de
  Zotero (Ayuda → Solución de problemas → Salida de depuración).
- **La sección se pinta al verse**: Zotero difiere el dibujo asíncrono hasta que la sección entra en pantalla; hasta
  entonces dice «Buscando el libro en el índice…».
