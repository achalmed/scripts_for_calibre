---
tipo: doc
titulo: "Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero): qué es automático, qué es manual, cómo se verifica"
genero: guia
estado: activo
---
# Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero)

La referencia práctica del ecosistema de lectura. Por qué es así: `decisiones.md` y el diseño
cumplido en `historial/diseno-ecosistema-lectura-2026-08.md`; cada herramienta tiene su README con
el detalle. **Esta página responde: ¿qué es automático, qué hago yo, y qué comando uso para cada
cosa?**

> **Ecosistema de aprendizaje:** esta guía es la dueña de la *plomería* (timers, sync, `#apuntes`).
> Cómo se integra con los apuntes de estudio (learning-skill), las fichas de investigación
> (`prompts/01 fuentes/`) y el vault (`meta/`) está en el mapa único
> `prompts/docs/dominios/aprendizaje.md`; cómo se lee cada material, en
> `prompts/docs/dominios/lectura.md`.

## 1. Lo AUTOMÁTICO (no tienes que hacer nada)

| Timer (systemd usuario) | Cadencia | Qué hace | Se salta si… |
|---|---|---|---|
| `koreader-calibre-sync` | cada 30 min | KOReader → Calibre: progreso, estado, minutos, fechas, barra; y **respalda** stats+sidecars al repo `~/.local/share/koreader-respaldo/` (commit git local; FG3) | Calibre abierto |
| `ecosistema-lectura` | cada 30 min | Zotero → Calibre: `#zot_tiempo`, `#zot_progreso`, `#zot_ultima` | Calibre abierto |
| `ecosistema-metadatos` | diario 04:30 | etiquetas + metadatos bidireccionales (`../script_sincronizar_zotero/`) | Calibre O Zotero abiertos, o sin cambios en las bases |

- «Se salta» no es un error: **reintenta en la siguiente pasada**. Si dejas la laptop apagada a las
  04:30, `Persistent=true` la corre al encender.
- Los tres comparten un candado (`LOCK_CALIBRE` de `core/env.sh`, en `$XDG_STATE_HOME/biblioteca/`):
  nunca escriben a la vez; ocupado, salen 75 y reintentan.
- Todo escribe por la puerta (`../lib/escribir.sh`): con la app cerrada y un respaldo verificado y
  rotado en `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/` (`calibre/` y, para
  `sincronizar_zotero`, también `zotero/`).

**Tu única rutina real: lee en KOReader o Zotero, organiza en Calibre. Fin.**

### 1.1 Dónde viven las unidades y cómo se instalan

Las seis unidades (`koreader-calibre-sync`, `ecosistema-lectura`, `ecosistema-metadatos`, cada una
`.service` + `.timer`) están en `~/.config/systemd/user/` como archivos normales, no como enlaces.
Las escribe `../systemd/instalar.sh --aplicar` a partir de las plantillas versionadas de
`../systemd/`: `@RAIZ@` se renderiza como `%h/<ruta del repo bajo el HOME>`, el PATH es el mínimo del
sistema (sin anaconda) y `SuccessExitStatus=75`; después `daemon-reload` y `enable --now`. Sin
`--aplicar` simula; `--verificar` dice si lo instalado es la plantilla; `--desinstalar --aplicar`
hace lo inverso. `--instalar-timer` y `--desinstalar-timer` de las suites lo delegan. `~/.dotfiles`
no gestiona estas unidades: si el repo cambia de carpeta o de máquina, se reinstala con la
herramienta.

```bash
../systemd/instalar.sh                     # simula: qué cambiaría frente a lo instalado
../systemd/instalar.sh --aplicar           # instala y activa los tres timers
../systemd/instalar.sh --verificar         # 0 si lo instalado = las plantillas renderizadas
```

Fuera del repo quedan solo las copias renderizadas; la fuente es siempre `../systemd/`.

## 2. Lo MANUAL (los únicos gestos que te tocan)

| Cuándo | Qué haces |
|---|---|
| Terminaste de LEER un libro | En KOReader: menú del libro → estado → **Terminado** (o marca `Leído` en Calibre). Eso dispara ✅ Finalizado + fecha |
| Estado de ESTUDIO (≠ lectura) | Edita a mano la columna **`#estudio`** (⬜/📖/🔁/✅). Ningún script la toca |
| Creamos una nota de clase nueva | `../script_koreader_estudio/main.sh --apuntes <id_libro> "<ruta.md>" "<texto>"` (escribe al invocarse, con Calibre cerrado; el asistente lo hace en la sesión de estudio) |
| Quieres publicar los respaldos al remoto | `git -C ~/.local/share/koreader-respaldo push` (los commits locales ya están hechos) |
| Llevar a Zotero los libros que no están | `../script_ecosistema_lectura/main.sh --enlazar --ris` → importar el `.ris` en Zotero (enlazar archivos) → `--enlazar --aplicar` (escribe las claves «adjunto») → los de ISBN o título, pegar la clave en ZKey |
| Ver los apuntes desde Calibre | Selecciona el libro → panel **Detalles del libro** (derecha) → clic en «📝 …» (abre en **Obsidian**) o «abrir como archivo» (MarkText). El **doble clic** sobre el libro siempre abre el PDF: es el comportamiento normal de Calibre, no un error |

## 3. Chuleta de comandos

```bash
cd "$SCRIPTS_CALIBRE/script_koreader_estudio"        # SCRIPTS_CALIBRE: core/env.sh --print
./main.sh                              # KOReader → Calibre: simulación (ver qué haría)
./main.sh --aplicar                    # forzar una pasada YA (Calibre cerrado)
./main.sh --apuntes ID RUTA "TEXTO"    # enlazar apuntes .md a un libro
./main.sh --migrar-sdr                 # ya ejecutada; solo si aparecieran .sdr nuevos

cd "$SCRIPTS_CALIBRE/script_ecosistema_lectura"
./main.sh                              # Zotero → Calibre: simulación
./main.sh --aplicar                    # forzar pasada YA (Calibre cerrado; Zotero da igual)
./main.sh --metadatos                  # ensayo de etiquetas/metadatos (simulación)
./main.sh --metadatos --aplicar        # correr YA la sync de etiquetas/metadatos (AMBOS cerrados)
./main.sh --enlazar [--ris] [--aplicar] # informe de libros sin #zotero_key; .ris; claves «adjunto»

../systemd/instalar.sh --aplicar       # los tres timers (simula sin --aplicar)
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
- Las columnas se actualizan **al cerrar el libro en KOReader** (ahí vuelca sus datos) y en la
  siguiente pasada del timer. No es instantáneo: es fiable.
- Restaurar en laptop nueva: receta en `~/.local/share/koreader-respaldo/README.md`.
- Deshacer una escritura: la puerta guarda `metadata_*.db` (los 5 últimos) y, en
  `sincronizar_zotero` y `adjuntos_zotero`, `zotero_*.sqlite` (los 3 últimos) en
  `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/{calibre,zotero}/`; copiar el que toque encima de la
  base, con la app cerrada. Los respaldos anteriores a la ola 2a están en
  `$RESPALDOS_DIR/biblioteca/<suite>/` (con `SHA256SUMS`).
- Los `reportes/` de cada suite (un TSV o MD por pasada) no rotan solos: se podan los de más de 30
  días en las fases de higiene; el último de cada tipo se conserva.

## 5. Lo que NO debes hacer

- No edites a mano las columnas `ko_*`, `zot_*`, `#leído` tras Terminado, ni
  `#tiempo_estudio`/`#barra`/`#estado_estudio` (composites: se recalculan). Las tuyas son:
  **`#estudio`**, **`#apuntes`** (vía comando), etiquetas, series.
- No borres `~/.config/koreader/hashdocsettings/` (son tus progresos) ni el candado de
  `$XDG_STATE_HOME/biblioteca/`.
- No muevas el repo de carpeta sin reinstalar los timers (`../systemd/instalar.sh --aplicar`).
- No ejecutes los `.js` de `scripts_for_zotero` (salvo `series_organizer`): sus transformaciones
  están absorbidas por la política de `../script_sincronizar_zotero/` y el sync nocturno las
  revertiría.
