# 📚 GUÍA DE USO — Ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero)

#guía · La referencia práctica de todo lo montado el 2026-08-09. El diseño
técnico vive en [`script_ecosistema_lectura/DISENO.md`](script_ecosistema_lectura/DISENO.md);
cada herramienta tiene su README con el detalle. **Esta página responde: ¿qué es
automático, qué hago yo, y qué comando uso para cada cosa?**

> **Ecosistema de aprendizaje:** esta guía es la dueña de la *plomería*
> (timers, sync, `#apuntes`). Cómo se integra con los apuntes de estudio
> (`learning-skill`), las fichas de investigación (`prompts_for_zotero`) y el
> vault (`meta/`) está en el mapa único:
> [`ECOSISTEMA_APRENDIZAJE.md`](../git-awesome-ai-prompts/ECOSISTEMA_APRENDIZAJE.md).

---

## 1. Lo AUTOMÁTICO (no tienes que hacer nada)

| Timer (systemd usuario) | Cadencia | Qué hace | Se salta si… |
|---|---|---|---|
| `koreader-calibre-sync` | cada 30 min | KOReader → Calibre: progreso, estado, minutos, fechas, barra; y **respalda** stats+sidecars a `~/.dotfiles/koreader-data/` (commit git local) | Calibre abierto |
| `ecosistema-lectura` | cada 30 min | Zotero → Calibre: `#zot_tiempo`, `#zot_progreso`, `#zot_ultima` | Calibre abierto |
| `ecosistema-metadatos` | diario 04:30 | etiquetas + metadatos bidireccionales (`script_sincronizar_zotero`) | Calibre O Zotero abiertos, o sin cambios en las bases |

- "Se salta" no es un error: **reintenta en la siguiente pasada**. Si dejas la
  laptop apagada a las 04:30, `Persistent=true` la corre al encender.
- Los tres comparten un candado (`.lock_calibre_write`): nunca escriben a la vez.
- Todo escribe con backup previo rotado (carpeta `backups/` de cada script).

**Tu única rutina real: lee en KOReader o Zotero, organiza en Calibre. Fin.**

---

## 2. Lo MANUAL (los únicos gestos que te tocan)

| Cuándo | Qué haces |
|---|---|
| Terminaste de LEER un libro | En KOReader: menú del libro → estado → **Terminado** (o marca `Leído` en Calibre). Eso dispara ✅ Finalizado + fecha |
| Estado de ESTUDIO (≠ lectura) | Edita a mano la columna **`#estudio`** (⬜/📖/🔁/✅). Ningún script la toca |
| Creamos una nota de clase nueva | `script_koreader_estudio/main.sh --apuntes <id_libro> "<ruta.md>" "<texto>"` (Claude lo hace en la sesión de estudio) |
| Quieres publicar los respaldos al GitHub | `cd ~/.dotfiles && ./main.sh sync-push` (los commits locales ya están hechos) |
| Enlazar libros nuevos a Zotero | `script_ecosistema_lectura/main.sh --enlazar` → revisa el TSV → pega la clave en la columna ZKey del libro |
| Ver los apuntes desde Calibre | Selecciona el libro → panel **Detalles del libro** (derecha) → clic en «📝 …» (abre en **Obsidian**) o «abrir como archivo» (MarkText). ⚠ El **doble clic** sobre el libro siempre abre el PDF: es el comportamiento normal de Calibre, no un error |

---

## 3. Chuleta de comandos

```bash
# ── KOReader → Calibre (script_koreader_estudio) ──────────────────────────
cd ~/Documents/scripts_for_calibre/script_koreader_estudio
./main.sh                    # simulación (ver qué haría)
./main.sh --aplicar          # forzar una pasada YA (Calibre cerrado)
./main.sh --apuntes ID RUTA "TEXTO"   # enlazar apuntes .md a un libro
./main.sh --migrar-sdr       # (ya ejecutada; solo si aparecieran .sdr nuevos)

# ── Zotero → Calibre + orquestación (script_ecosistema_lectura) ───────────
cd ~/Documents/scripts_for_calibre/script_ecosistema_lectura
./main.sh                    # simulación lectura Zotero
./main.sh --aplicar          # forzar pasada YA (Calibre cerrado; Zotero puede estar abierto)
./main.sh --metadatos            # ensayo de etiquetas/metadatos (simulación)
./main.sh --metadatos --aplicar  # correr YA la sync de etiquetas/metadatos (AMBOS cerrados)
./main.sh --enlazar              # reporte de libros sin #zotero_key

# ── Timers (en cualquiera de los dos main.sh) ─────────────────────────────
./main.sh --instalar-timer / --desinstalar-timer
```

---

## 4. ¿Está funcionando? (verificación y problemas)

```bash
systemctl --user list-timers | grep -E "koreader|ecosistema"   # ¿cuándo corren?
journalctl --user -u koreader-calibre-sync -n 20               # última pasada KOReader
journalctl --user -u ecosistema-lectura -n 20                  # última pasada Zotero
journalctl --user -u ecosistema-metadatos -n 30                # última orquestación
git -C ~/.dotfiles log --oneline -5 -- koreader-data           # respaldos recientes
```

- **"Calibre está abierto; reintentará"** en el journal = normal, no es fallo.
- Las columnas se actualizan **al cerrar el libro en KOReader** (ahí vuelca sus
  datos) y en la siguiente pasada del timer. No es instantáneo: es fiable.
- Restaurar en laptop nueva: receta en `~/.dotfiles/koreader-data/README.md`.
- Deshacer una escritura: cada script guarda `backups/metadata_*.db` (los 5
  últimos); copiar encima de `biblioteca/metadata.db` con Calibre cerrado.

## 5. Lo que NO debes hacer

- No edites a mano las columnas `ko_*`, `zot_*`, `#leído` tras Terminado, ni
  `#tiempo_estudio`/`#barra`/`#estado_estudio` (composites: se recalculan).
  Las tuyas son: **`#estudio`**, **`#apuntes`** (vía comando), etiquetas, series.
- No borres `~/.config/koreader/hashdocsettings/` (son tus progresos) ni los
  `.lock` de `scripts_for_calibre/`.
- No muevas los scripts de carpeta sin reinstalar los timers (`--instalar-timer`).
