---
tipo: readme
estado: activo
---
# calibre-plugin/ — el complemento «Ecosistema» de Calibre: el libro elegido en Zotero, su clave y sus apuntes

## Qué es

Un complemento de interfaz de Calibre (`ecosistema/`, Python y Qt de Calibre) que pone un botón **Ecosistema** con
un menú para el libro elegido:

| entrada | qué hace |
|---|---|
| Qué es este libro… | `calibre_id`, título, autores, clave de Zotero, clave para citar, fichas que lo citan y su nota de lectura |
| Abrir en Zotero | `zotero://select/library/items/<zotero_key>` |
| Abrir en Biblioteca Studio | `biblioteca-studio://libro/<id>` (el esquema lo registra `studio/install.sh`) |
| Abrir la nota de lectura | la ruta `nota` del índice, si existe |
| Copiar la clave para citar | la clave de Better BibTeX al portapapeles |
| Marcar para verificar | añade `id⇥título⇥fecha` a `$XDG_STATE_HOME/biblioteca/por-verificar.tsv` |

**Solo lee** (`docs/decisiones.md`, la puerta de escritura): el título y los autores salen de la API de Calibre;
la clave de Zotero, la clave para citar, las fichas y la nota, del índice que escribe `lib/indice.py --aplicar` en
`$XDG_STATE_HOME/biblioteca/indice.json`. Lo único que escribe es la cola de texto de «Marcar para verificar», fuera
de la base. El código no lleva rutas: salen del índice.

## Uso

```bash
calibre-plugin/instalar.sh             # simula
calibre-plugin/instalar.sh --aplicar   # empaqueta dist/ecosistema.zip y lo instala (Calibre cerrado)
calibre-plugin/instalar.sh --quitar --aplicar
```

Después, en Calibre: Preferencias → Barras de herramientas y menús → la barra principal → añadir «Ecosistema».

## Cómo se prueba

Con una configuración de Calibre aparte, nunca la real:

```bash
CALIBRE_CONFIG_DIRECTORY="$XDG_CACHE_HOME/calibre-prueba" calibre-plugin/instalar.sh --aplicar
CALIBRE_CONFIG_DIRECTORY="$XDG_CACHE_HOME/calibre-prueba" calibre-customize -l | grep -A1 Ecosistema
```
