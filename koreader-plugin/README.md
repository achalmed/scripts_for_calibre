---
tipo: readme
estado: activo
---
# koreader-plugin/ — el complemento «Ecosistema» de KOReader: el libro abierto en Calibre, Zotero y sus apuntes

## Qué es

Un complemento de KOReader (`ecosistema.koplugin`) que, para el libro abierto, pone en el menú de
herramientas del lector un submenú **Ecosistema**:

| entrada | qué hace |
|---|---|
| Qué es este libro | `calibre_id` (de la carpeta `<Título> (<id>)/`), título, autores, clave de Zotero, clave para citar, cuántas fichas lo citan y si ya tiene nota de lectura |
| Abrir en Calibre | `xdg-open calibre://show-book/_hex_-<hex del nombre de la biblioteca>/<id>` |
| Abrir en Zotero | `xdg-open zotero://select/library/items/<zotero_key>` |
| Abrir en Biblioteca Studio | `xdg-open biblioteca-studio://libro/<id>` (el esquema lo registra Biblioteca Studio) |
| Copiar la clave para citar | la clave de Better BibTeX al portapapeles de KOReader |
| Pasar mis resaltados a los apuntes | vista previa y, si se confirma, **añade** al final de la nota de lectura un bloque `## Resaltados de KOReader · AAAA-MM-DD` con los resaltados que aún no estén en ella; si la nota no existe, la crea con el encabezado del tipo `lectura` del vault |
| Sincronizar con Calibre ahora | vuelca los ajustes del libro y pide `systemctl --user start --no-block koreader-calibre-sync.service` |

Todo sale del **índice** que genera `lib/indice.py --aplicar` en `$XDG_STATE_HOME/biblioteca/indice.json`
(sin esa variable, `~/.local/state/biblioteca/indice.json`); el complemento solo lo lee, y lo relee
cuando cambia en el disco. Las rutas de la biblioteca, del repo y de las notas vienen de ahí: el
código no lleva ninguna.

**La puerta de escritura se respeta**: el complemento no escribe en la base de Calibre. Lo único que
escribe es la nota de lectura del libro (la ruta `nota` del índice), y solo añadiendo al final. Si el
libro no tenía apuntes enlazados, pide el enlace a `<repo>/koreader/main.sh --apuntes <id> "<nota>"
"Apuntes de lectura"`, que escribe por la puerta; si sale 75 o con error porque Calibre está abierto,
avisa que la nota se enlazará desde Biblioteca Studio y sigue. Las órdenes externas corren en
segundo plano y su resultado se sondea con `UIManager:scheduleIn`: nada bloquea la interfaz.

Cada resaltado queda como cita con su página (la de referencia si el libro la tiene, `pageref`; si
no, `pageno`) y, debajo, la nota si la tiene:

```markdown
## Resaltados de KOReader · 2026-10-31

> El texto resaltado,
> en tantas líneas como tenga.
> — p. 12

**Nota:** lo que escribí sobre él.
```

Un resaltado cuenta como «ya pasado» si su texto (con los espacios y saltos unidos) aparece ya en la
nota, aunque sea fuera de una cita: repetir la orden no duplica nada.

Estructura: `ecosistema.koplugin/_meta.lua` (nombre y descripción), `ecosistema.koplugin/main.lua`
(menú, avisos, llamadas al sistema), `ecosistema.koplugin/ecosistema_logica.lua` (lo puro, sin
KOReader: índice, decodificador JSON, identificación del libro, enlaces, entrecomillado para la
terminal y el bloque sin duplicados), `pruebas.lua`, `prueba_koreader.sh` e `instalar.sh`.

## Uso

Se instala enlazando `ecosistema.koplugin` en la carpeta de complementos de KOReader
(`~/.config/koreader/plugins/`; `instalar.sh` la deduce de `KOREADER_STATS` de `core/env.sh`, y
`QKO_KOREADER_CONFIG` la cambia):

```bash
koreader-plugin/instalar.sh                        # SIMULA: dice qué enlace crearía
koreader-plugin/instalar.sh --aplicar              # crea el enlace; reiniciar KOReader
koreader-plugin/instalar.sh --quitar               # simula quitarlo
koreader-plugin/instalar.sh --quitar --aplicar     # quita el enlace (nunca una carpeta real)
```

En KOReader: abrir un libro de la biblioteca → menú principal → herramientas → **Ecosistema**.
Antes, que el índice exista y esté al día: `lib/indice.py --aplicar`.

Pruebas:

```bash
luajit koreader-plugin/pruebas.lua             # o /usr/lib/koreader/luajit: lógica pura + índice real (solo lectura)
koreader-plugin/prueba_koreader.sh             # KOReader de verdad, sin pantalla, con KO_HOME temporal
LUA_PATH="/usr/lib/koreader/?.lua;;" /usr/lib/koreader/luajit -bl <archivo>.lua > /dev/null   # sintaxis
```

`prueba_koreader.sh` arranca el `reader.lua` de KOReader con `KO_HOME`, `HOME` y `XDG_STATE_HOME`
temporales en `$XDG_CACHE_HOME/ecosistema-koplugin-koreader/`, SDL en modo `dummy` y un PDF de
muestra dentro de una biblioteca, un índice y un `koreader/main.sh` falsos (este último sale 75); un
parche de usuario (`patches/2-…`) recorre el menú, inyecta dos resaltados, confirma la vista previa
y anota en una bitácora; `xdg-open` y `systemctl` se anotan en vez de ejecutarse. No toca
`~/.config/koreader/`, ni la biblioteca, ni Calibre, ni systemd.

## Límite honesto

- **Depende del índice**: si `lib/indice.py --aplicar` no corrió después de catalogar un libro, el
  complemento no lo conoce y lo dice; tampoco ve una clave de Zotero o unos apuntes enlazados después
  de generado el índice (el enlace hecho desde el propio complemento se recuerda solo en memoria).
- **El libro se reconoce por su carpeta** `<Título> (<id>)/`: un archivo abierto desde una copia
  fuera de la biblioteca solo se acepta si la carpeta coincide con la del índice.
- **La detección de duplicados es por texto**: un resaltado corto que ya aparezca en la nota como
  parte de otra frase cuenta como pasado; un resaltado cuyo texto se corrigió en KOReader después de
  pasarlo se vuelve a pasar. Los resaltados de imagen de un PDF (sin texto) no se pasan.
- **El enlace en Calibre necesita Calibre cerrado**: con Calibre abierto la puerta sale 75 y el enlace
  queda para Biblioteca Studio; el complemento no reintenta.
- **«Abrir en…» solo lanza `xdg-open`**: si Calibre, Zotero o Biblioteca Studio no tienen registrado
  su esquema de URL, no pasa nada visible y el complemento no puede saberlo.
- **La sincronización es la del timer**: si Calibre está abierto, la pasada se salta; el progreso de
  la sesión en curso llega cuando KOReader vuelca el libro (el complemento lo pide antes).
- **Probado con KOReader v2026.03 en Linux** (escritorio, SDL): la prueba sin pantalla no ejercita
  la interfaz táctil ni otros dispositivos, y no se ha cargado sobre la configuración real.
