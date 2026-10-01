---
tipo: doc
titulo: "Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero): qué es automático, qué es manual, cómo se verifica"
estado: activo
---
# Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero)

La referencia práctica de todo lo montado el 2026-08-09 (hasta DOC6 se llamaba `GUIA_ECOSISTEMA.md` y
vivía en la raíz del repo). El diseño técnico y sus fases cumplidas están en
`historial/diseno-ecosistema-lectura-2026-08.md`; cada herramienta tiene su README con el detalle.
**Esta página responde: ¿qué es automático, qué hago yo, y qué comando uso para cada cosa?**

> **Ecosistema de aprendizaje:** esta guía es la dueña de la *plomería* (timers, sync, `#apuntes`).
> Cómo se integra con los apuntes de estudio (learning-skill), las fichas de investigación
> (`prompts/01 fuentes/`) y el vault (`meta/`) está en el mapa único
> `prompts/ECOSISTEMA_APRENDIZAJE.md`; cómo se lee cada material, en `prompts/ECOSISTEMA_LECTURA.md`.

## 1. Lo AUTOMÁTICO (no tienes que hacer nada)

| Timer (systemd usuario) | Cadencia | Qué hace | Se salta si… |
|---|---|---|---|
| `koreader-calibre-sync` | cada 30 min | KOReader → Calibre: progreso, estado, minutos, fechas, barra; y **respalda** stats+sidecars al repo `~/.local/share/koreader-respaldo/` (commit git local; FG3) | Calibre abierto |
| `ecosistema-lectura` | cada 30 min | Zotero → Calibre: `#zot_tiempo`, `#zot_progreso`, `#zot_ultima` | Calibre abierto |
| `ecosistema-metadatos` | diario 04:30 | etiquetas + metadatos bidireccionales (`../script_sincronizar_zotero/`) | Calibre O Zotero abiertos, o sin cambios en las bases |

- «Se salta» no es un error: **reintenta en la siguiente pasada**. Si dejas la laptop apagada a las
  04:30, `Persistent=true` la corre al encender.
- Los tres comparten un candado (`.lock_calibre_write` en la raíz del repo; `LOCK_CALIBRE` en
  `core/env.sh`): nunca escriben a la vez.
- Todo escribe con backup previo rotado (carpeta `backups/` de cada script).

**Tu única rutina real: lee en KOReader o Zotero, organiza en Calibre. Fin.**

### 1.1 Dónde viven las unidades y cómo se instalan

Comprobado el 2026-09-20: las seis unidades (`koreader-calibre-sync`, `ecosistema-lectura`,
`ecosistema-metadatos`, cada una `.service` + `.timer`) están en `~/.config/systemd/user/` como
archivos normales, no como enlaces. Las escribe `--instalar-timer` de cada suite a partir de las
plantillas versionadas en `../script_koreader_estudio/lib/systemd/` y
`../script_ecosistema_lectura/lib/systemd/`: el `.service` se renderiza sustituyendo `@MAIN@` por la
ruta absoluta del `main.sh` de la suite y el `.timer` se copia tal cual; después `daemon-reload` y
`enable --now`. `--desinstalar-timer` hace lo inverso. `~/.dotfiles` no gestiona estas unidades (no
tiene paquete systemd): si una suite cambia de carpeta o de máquina, se reinstala con la herramienta.

```bash
../script_koreader_estudio/main.sh --instalar-timer        # koreader-calibre-sync (30 min)
../script_ecosistema_lectura/main.sh --instalar-timer      # ecosistema-lectura (30 min) + ecosistema-metadatos (04:30)
../script_koreader_estudio/main.sh --desinstalar-timer     # detiene y borra las unidades de esa suite
diff ../script_koreader_estudio/lib/systemd/koreader-calibre-sync.timer ~/.config/systemd/user/koreader-calibre-sync.timer
```

Fuera del repo quedan solo las copias renderizadas; la fuente es siempre la carpeta `systemd/` dentro
del `lib/` de cada suite.

## 2. Lo MANUAL (los únicos gestos que te tocan)

| Cuándo | Qué haces |
|---|---|
| Terminaste de LEER un libro | En KOReader: menú del libro → estado → **Terminado** (o marca `Leído` en Calibre). Eso dispara ✅ Finalizado + fecha |
| Estado de ESTUDIO (≠ lectura) | Edita a mano la columna **`#estudio`** (⬜/📖/🔁/✅). Ningún script la toca |
| Creamos una nota de clase nueva | `../script_koreader_estudio/main.sh --apuntes <id_libro> "<ruta.md>" "<texto>"` (el asistente lo hace en la sesión de estudio) |
| Quieres publicar los respaldos al remoto | `git -C ~/.local/share/koreader-respaldo push` (los commits locales ya están hechos) |
| Llevar a Zotero los libros que no están | `../script_ecosistema_lectura/main.sh --enlazar --ris` → importar el `.ris` en Zotero (enlazar archivos) → `--enlazar --aplicar` (escribe las claves «adjunto») → los de ISBN o título, pegar la clave en ZKey |
| Ver los apuntes desde Calibre | Selecciona el libro → panel **Detalles del libro** (derecha) → clic en «📝 …» (abre en **Obsidian**) o «abrir como archivo» (MarkText). El **doble clic** sobre el libro siempre abre el PDF: es el comportamiento normal de Calibre, no un error |

## 3. Chuleta de comandos

```bash
cd "$SCRIPTS_CALIBRE/script_koreader_estudio"        # SCRIPTS_CALIBRE la resuelve core/env.sh (core/env.sh --print)
./main.sh                              # KOReader → Calibre: simulación (ver qué haría)
./main.sh --aplicar                    # forzar una pasada YA (Calibre cerrado)
./main.sh --apuntes ID RUTA "TEXTO"    # enlazar apuntes .md a un libro
./main.sh --migrar-sdr                 # ya ejecutada; solo si aparecieran .sdr nuevos

cd "$SCRIPTS_CALIBRE/script_ecosistema_lectura"
./main.sh                              # Zotero → Calibre: simulación
./main.sh --aplicar                    # forzar pasada YA (Calibre cerrado; Zotero puede estar abierto)
./main.sh --metadatos                  # ensayo de etiquetas/metadatos (simulación)
./main.sh --metadatos --aplicar        # correr YA la sync de etiquetas/metadatos (AMBOS cerrados)
./main.sh --enlazar [--ris] [--aplicar] # informe de libros sin #zotero_key; .ris; claves «adjunto»

./main.sh --instalar-timer             # en cualquiera de los dos main.sh; --desinstalar-timer lo revierte
```

## 4. ¿Está funcionando? (verificación y problemas)

```bash
systemctl --user list-timers | grep -E "koreader|ecosistema"   # ¿cuándo corren?
journalctl --user -u koreader-calibre-sync -n 20               # última pasada KOReader
journalctl --user -u ecosistema-lectura -n 20                  # última pasada Zotero
journalctl --user -u ecosistema-metadatos -n 30                # última orquestación
git -C ~/.local/share/koreader-respaldo log --oneline -5       # respaldos recientes
```

- **«Calibre está abierto; reintentará»** en el journal = normal, no es fallo.
- Las columnas se actualizan **al cerrar el libro en KOReader** (ahí vuelca sus datos) y en la siguiente
  pasada del timer. No es instantáneo: es fiable.
- Restaurar en laptop nueva: receta en `~/.local/share/koreader-respaldo/README.md`.
- Deshacer una escritura: cada script guarda `backups/metadata_*.db` (los 5 últimos); copiar encima
  de `biblioteca/metadata.db` con Calibre cerrado.
- Los `reportes/` de cada suite (un TSV o MD por pasada) no rotan solos: se podan los de más de 30 días
  en las fases de higiene; el último de cada tipo se conserva.

## 5. Lo que NO debes hacer

- No edites a mano las columnas `ko_*`, `zot_*`, `#leído` tras Terminado, ni
  `#tiempo_estudio`/`#barra`/`#estado_estudio` (composites: se recalculan). Las tuyas son: **`#estudio`**,
  **`#apuntes`** (vía comando), etiquetas, series.
- No borres `~/.config/koreader/hashdocsettings/` (son tus progresos) ni el `.lock_calibre_write` de la
  raíz de `scripts_for_calibre/`.
- No muevas los scripts de carpeta sin reinstalar los timers (`--instalar-timer`).
- No ejecutes los `.js` de `scripts_for_zotero` (salvo `series_organizer`): sus transformaciones están
  absorbidas por la política de `../script_sincronizar_zotero/` y el sync nocturno las revertiría.
