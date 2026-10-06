---
tipo: doc
titulo: "Citar en el ecosistema: Zotero manda en citas y metadatos, Calibre en los archivos"
genero: guia
estado: activo
---
# Citar en el ecosistema

El lugar único donde se dice **cómo se cita** en `escritura`, el SGDP, Obsidian y LibreOffice. Los
demás repos apuntan aquí y no lo copian. Las normas de estilo (APA 7) siguen en
`prompts/00 metodo/normas_apa7.md`; el porqué del cambio, en [decisiones.md](decisiones.md) §1.6;
lo pendiente, en [`../estado.md`](../estado.md) §Por hacer.

## 1. Quién manda en qué (decisión de Edison, 2026-10-06)

| dato | autoridad | cómo se pide |
|---|---|---|
| metadatos (autor, título, año, editorial, tipo), la referencia y la cita | **Zotero** | sus complementos: Better BibTeX (LaTeX, Obsidian), el procesador de texto (LibreOffice), la API local (SGDP) |
| la clave de cita | **Better BibTeX**, campo `citationKey` de cada ítem | igual en todas partes: `\textcite{clave}`, `[@clave]`, la clave del SGDP |
| el archivo (PDF, EPUB) y su ubicación | **Calibre** | `calibre_id`; la ruta, `core/py-common/biblioteca.py` |

El puente entre los dos es la ruta del adjunto: Zotero enlaza cada archivo de la biblioteca por
`attachments:<Autor>/<Título> (<calibre_id>)/<archivo>` (la ruta base de los adjuntos enlazados es
`BIBLIOTECA_DIR`), así que de una clave de Zotero sale su `calibre_id` y viceversa, sin tabla
aparte. La normativa general (N 9.6, «ninguna obra se cita sin `calibre_id`») se actualizará: el
recordatorio está en `meta/estado.md` §Por hacer.

**Mientras dure la transición**, el sincronizador nocturno (`../sincronizar-zotero/`, timer
`ecosistema-metadatos`, 04:30) sigue la política anterior: en conflicto **Calibre gana y sobrescribe
a Zotero** (título, fecha, editorial, idioma, tipo…). Una corrección hecha solo en Zotero se pierde
esa noche. Hasta que se decida la política nueva ([`../estado.md`](../estado.md) §Por hacer),
corregir en los dos o pausar ese timer.

## 2. LaTeX (`escritura`): la exportación automática de Better BibTeX

La fuente de los `.bib` es **una** exportación automática de toda la biblioteca, en formato Better
BibLaTeX y «Mantener actualizado», en la ruta `ZOTERO_BIB` de `core/env.sh`
(`$ZOTERO_DIR/exportaciones/zotero.bib`; `core/env.sh --print | grep ZOTERO_BIB` la muestra).

Se configura una sola vez en la interfaz de Zotero (no hay forma de hacerlo con Zotero cerrado):

1. Crear la carpeta: `mkdir -p "$(dirname "$ZOTERO_BIB")"` (con `core/env.sh` cargado).
2. Zotero → **Archivo → Exportar biblioteca…** → formato **Better BibLaTeX**; marcar **Mantener
   actualizado** (*Keep updated*); sin «Exportar notas» ni «Exportar archivos» → Aceptar.
3. Guardar como `zotero.bib` en esa carpeta (el nombre importa: los documentos lo piden así).
4. Comprobar en Ajustes → Better BibTeX → **Exportaciones automáticas** que figura la biblioteca
   con esa ruta y «Al cambiar».
5. **Claves estables**: decidir la fórmula antes de fijar (hoy `auth.lower + shorttitle(3, 3) + year`;
   las de autor corporativo salen largas, p. ej. `congresodelarepublica…`); después, seleccionar todos
   los ítems → clic derecho → Better BibTeX → **Fijar clave de cita** (*Pin citation key*), y en
   Ajustes → Better BibTeX → Clave de cita, fijar automáticamente las nuevas (*autoPinDelay* > 0),
   para que corregir un título o un año no cambie una clave ya citada.

En un documento:

```latex
\addbibresource{zotero.bib}          % la exportación; scripts/build.sh pone su carpeta en BIBINPUTS
\textcite{avilaComoSeEscribe2003}    % la clave de Better BibTeX
```

`escritura/scripts/build.sh` añade la carpeta de `ZOTERO_BIB` a `BIBINPUTS` después del proyecto y
de `bib/`: un `references.bib` del proyecto sigue mandando. Biber lee la exportación entera pero
solo procesa lo citado.

Verificar las claves de un documento (solo lee; usa la exportación o, si aún no existe, una copia
de `zotero.sqlite`):

```bash
python3 escritura/scripts/claves_zotero.py <maestro.tex|proyecto>
```

Clasifica lo que falta en «solo en un `.bib` del proyecto» (las claves que generó
`manifiesto bib` desde Calibre, para las que propone la clave de Zotero del mismo `calibre_id`) y
«en ninguna parte». `manifiesto/main.py bib` y los `references.bib` generados siguen funcionando
para los documentos existentes hasta migrarlos.

## 3. Obsidian: Zotero Integration

Instalado y activo: **Zotero Integration** de mgmeyers (`obsidian-zotero-desktop-connector`), que
habla con Better BibTeX con Zotero abierto. Su configuración es
`.obsidian/plugins/obsidian-zotero-desktop-connector/data.json` (enlace a `~/.dotfiles`, se edita
con Obsidian cerrado y en un commit propio de `dotfiles`); su plantilla de nota de lectura,
`meta/integrations/zotero/research note.md` (frontmatter único del vault, `clave_bibtex: {{citekey}}`,
anotaciones por color).

Configuración propuesta (no aplicada; pendiente en [`../estado.md`](../estado.md)):

- En la exportación «Create research note», `"cslStyle": "apa"` en vez de
  `chicago-fullnote-bibliography`, para que `{{bibliography}}` salga en APA 7 como en todo lo demás.
- Formatos de cita (hoy `"citeFormats": []`):

  ```json
  "citeFormats": [
    { "name": "Cita Pandoc", "format": "pandoc", "brackets": true },
    { "name": "Cita APA", "format": "formatted-citation", "cslStyle": "apa" },
    { "name": "Referencia APA", "format": "formatted-bibliography", "cslStyle": "apa" }
  ]
  ```

- En la plantilla, `calibre_id` desde la ruta del primer adjunto, en vez de dejarlo en blanco:

  ```
  calibre_id: {% for a in attachments %}{% if loop.first and a.path %}{{ a.path | replace(r/^.*\((\d+)\)\/[^\/]*$/, "$1") }}{% endif %}{% endfor %}
  ```

  Probarlo con una obra antes de darlo por bueno: si la ruta no lleva `(<id>)/`, el filtro deja la
  ruta entera y hay que borrarla.

- El complemento Pandoc (`obsidian-pandoc`) apunta a un `pandoc` y a una carpeta de salida que no
  existen en esta máquina; si se usa para exportar con citas: `--citeproc --bibliography=<ZOTERO_BIB>`
  en `extraArguments`.

## 4. LibreOffice: el complemento de Zotero

El complemento oficial (Zotero LibreOffice Integration) está registrado en el perfil de
LibreOffice. Necesita Java dentro de LibreOffice; si la barra de Zotero de Writer no responde:

1. `sudo apt install libreoffice-java-common` (no está instalado).
2. LibreOffice → Herramientas → Opciones → LibreOffice → Avanzado → **Usar un entorno de
   ejecución de Java**, con el JRE del sistema seleccionado → reiniciar LibreOffice.
3. Si aún no aparece: Zotero → Ajustes → **Citar → Procesadores de texto → Reinstalar el
   complemento de LibreOffice**.

En cada documento, la primera vez: Zotero → **Preferencias del documento** → estilo **American
Psychological Association 7th edition** e idioma **Español (España)**, lo mismo que usa el SGDP
(`ZOTERO_ESTILO=apa`, `ZOTERO_IDIOMA=es-ES` de `sgdp/.env.example`). La copia rápida de Zotero
(Ajustes → Exportar) está en APA con `es-MX`: conviene `es-ES` para que todo salga igual.

## 5. SGDP

Lo resuelve el propio SGDP en solo lectura, por la API local de Zotero o una copia de
`zotero.sqlite`: `sgdp/backend/app/servicios/zotero.py` y `sgdp/docs/decisiones.md` §Biblioteca y
citas.

## 6. Verificar

```bash
core/env.sh --print | grep ZOTERO                                     # ZOTERO_DIR, ZOTERO_DB, ZOTERO_BIB
test -s "$ZOTERO_BIB" && grep -c '^@' "$ZOTERO_BIB"                   # la exportación existe y tiene entradas
python3 escritura/scripts/claves_zotero.py <maestro.tex|proyecto>     # 0: todas las claves están en Zotero
```
