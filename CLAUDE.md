---
tipo: guia_ia
estado: activo
---
# CLAUDE.md — scripts_for_calibre

Guía para el asistente. En español, como todo el ecosistema. `AGENTS.md` es un enlace a este
archivo. Léase antes: `README.md` (qué es, uso, estructura), `docs/README.md` (el mapa por lector),
`docs/decisiones.md` (por qué y qué está pendiente), el `suite.yml` y el README de la suite que se
toque, y `meta/MODELO_METADATOS.md` §2 y §4 (autoridad por dato) cuando el cambio afecte a qué
sistema manda sobre un campo.

## Reglas que no se negocian

- **Calibre manda en los metadatos bibliográficos.** En conflicto gana Calibre y se propaga a Zotero
  (título, fecha, editorial, ISBN, serie, páginas, edición, idioma, tags, abstract). **Zotero solo
  rellena vacíos** en Calibre (año placeholder, ISBN ausente) y puebla las columnas espejo
  `#zotero_*`. Vacío en el origen nunca borra en el destino. Política completa:
  `script_sincronizar_zotero/README.md`.
- **Título y autor jamás se escriben en Calibre** (ni por sync ni por verificación): Zotero enlaza
  los adjuntos por la ruta `Autor/Título (id)` y cambiarlos rompe el vínculo. Solo van Calibre →
  Zotero. Las excepciones: `catalogacion_biblioteca` (los escribe, y vale antes de que el libro
  tenga ítem en Zotero) y una campaña que reescriba Zotero en la misma operación
  (`script_normalizacion_metadatos/migraciones/<tema>_<fecha>/`).
- **Los relojes de lectura nunca se copian entre sí.** `#ko_tiempo` es de KOReader, `#zot_tiempo` de
  Zotero (Ethereal Style); `#tiempo_estudio` es una composite que los suma. No existe deduplicación
  porque ningún segundo entra dos veces al mismo contador; no se implementa ninguna.
- **Un solo escritor de `metadata.db` a la vez.** Todo escritor toma el candado
  `.lock_calibre_write` de la raíz (`tomar_lock_calibre` de `core/shell-lib/lock.sh`; la ruta la
  fija `LOCK_CALIBRE` en `core/env.sh` y `core/env.py`; `config.sh` de `koreader_estudio` y de
  `ecosistema_lectura` la redeclaran como `LOCK_ESCRITURA_CALIBRE`, que tiene prioridad). Lo toman
  también `sincronizar_zotero` y las suites `ingesta` e `ingesta_cursos` de `scripts_for_fuentes`;
  los timers lo heredan por descriptor (`ECOSISTEMA_LOCK_HELD=1`). Hoy **no** lo toman
  `catalogacion_biblioteca` ni `metadatos_calibre register` (`docs/decisiones.md`, Pendientes P1):
  no se toman como modelo. Una suite nueva que escriba en Calibre lo toma o no existe.
- **Calibre cerrado para escribir; Zotero cerrado además para `sincronizar_zotero`.** Las suites lo
  comprueban (`detectar_apps.sh`) y abortan; un timer que se salta no es un fallo: reintenta.
- **Simulación por defecto y `--aplicar` explícito** (`--apply` en las migraciones `NN_*.py`). Fuera
  de la regla, y hay que avisar antes de correrlos: `metadatos_calibre embed|register` (escriben
  salvo `--dry-run`), `koreader_estudio --apuntes` y el `main.sh` de cada campaña (leer su
  cabecera). Backup rotado de `metadata.db` (5) o de ambas bases (en
  `script_sincronizar_zotero/estado/`) antes de escribir; `PRAGMA integrity_check` después. Un
  cambio masivo se ensaya con `--limite N` o `--ids` antes del total.
- **Columnas manuales que ningún script toca:** `#estudio` (estado de estudio, distinto del de
  lectura), `#apuntes` (solo vía `--apuntes`), etiquetas y series. Las `ko_*`, `zot_*`, `#leído`
  tras Terminado, `#tiempo_estudio`, `#barra` y `#estado_estudio` las escriben las suites: no se
  editan a mano.
- **Escribir en SQLite directo deja los OPF rancios**: tras cualquier escritura que no pase por
  `calibredb`, `calibredb backup_metadata --all` con Calibre cerrado (solo reescribe OPF); nunca
  `embed_metadata`, que modifica el archivo del libro.
- **`lib_comun/` no se amplía.** Son envoltorios de `core/shell-lib` y `core/py-common` (FS2); el
  código nuevo carga `core/env.sh` o `core/env.py` y sus módulos directamente, sin `$HOME/Documents`
  ni rutas de máquina. El único logger propio (`script_metadatos_calibre/lib/logger.sh`) es a su vez
  envoltorio del de `core/`.
- **Los timers se instalan con la herramienta**, no a mano: `--instalar-timer` escribe las unidades
  en `~/.config/systemd/user/` desde las plantillas `script_koreader_estudio/lib/systemd/` y
  `script_ecosistema_lectura/lib/systemd/`; si una suite cambia de carpeta se reinstala.
  `~/.dotfiles` no las gestiona.
- **Lo generado no se edita**: bloques `<!-- suite:inicio -->` y `<!-- suites:inicio -->` de los README
  (`core/suites.py generar --aplicar`), `docs/README.md` (`core/docs.py indice`); `reportes/`, `backups/`,
  `estado/` y el lock son runtime ignorado.
- **`script_catalogacion_biblioteca/fichas/` y `resumen_catalogacion.tsv` son el registro de esa suite**
  (D12): las fichas nuevas las escribe `scripts_for_fuentes/ingesta/lib/catalogar.py` con su
  `calibre_id`; aquí solo se aplican al catálogo y se corrige el TSV cuando una ficha cambia.
- Español con tildes en código, mensajes y docs; nada del despacho ni identificadores de cliente.

## Cómo se verifica un cambio

```bash
python3 core/archivos.py validar scripts_for_calibre        # A01–A14 y D01–D12, desde ~/Documents
python3 core/suites.py validar                               # los suite.yml contra core/suite.schema.yml
python3 core/suites.py generar                               # ¿bloques e índice desfasados? (simula)
python3 core/docs.py verificar scripts_for_calibre           # ¿docs/README.md al día?
bash -n scripts_for_calibre/script_koreader_estudio/main.sh  # sintaxis; un archivo por invocación
python3 -m py_compile scripts_for_calibre/script_koreader_estudio/lib/sync_koreader.py
scripts_for_calibre/script_koreader_estudio/main.sh          # simulación: qué escribiría
scripts_for_calibre/script_sincronizar_zotero/main.sh --limite 20   # simula; informe en reportes/
systemctl --user list-timers | grep -E "koreader|ecosistema" # los tres timers, próxima pasada
journalctl --user -u ecosistema-metadatos -n 30              # la última orquestación
meta/doctor/main.sh --breve                                  # salud del ecosistema (0 · 1 · 2)
```

No hay pruebas automáticas: un cambio se prueba en simulación sobre pocos ids, se aplica con la app
cerrada, se lee el informe en `reportes/` y se abre Calibre a mirar. Deshacer una escritura: copiar el
`backups/metadata_*.db` correspondiente sobre `biblioteca/metadata.db` con Calibre cerrado.

## Detalles que cuesta redescubrir

- **`calibredb set_custom`** (no `set_custom_column`) escribe columnas en Calibre 9. En plantillas
  composite `field()` devuelve el valor formateado (`'4.35%'`): aritmética con `raw_field()`;
  `substr(s, 0, 0)` devuelve la cadena entera (por eso `#barra` trata n=0 y n=10 aparte).
- **`#ko_progfloat` guarda fracción 0–1**, no porcentaje: convención heredada del plugin KOReader Sync
  y respetada por compatibilidad; `#ko_progint` es el 0–100.
- **KOReader ↔ Calibre se emparejan por el MD5 parcial de KOReader** (bloques de 1 KB en offsets
  0 y 1024·4^i), cacheado en `#ko_md5`; los sidecars viven en `~/.config/koreader/hashdocsettings/`
  (modo `hash`, migrado el 2026-08-09), así que renombrar en Calibre no rompe nada.
- **KOReader vuelca sidecar y estadísticas al cerrar el libro**: el progreso de la sesión aparece en la
  pasada siguiente. Marcar *Terminado* en KOReader pone ✅, `#leído`, `#read_date` y `#ko_finish`;
  `#leído` a mano solo promueve, nunca degrada.
- **El Read Time de Zotero no es un campo nativo**: es una nota hija del ítem «Addon Item» del plugin
  Ethereal Style en `itemNotes` de `~/Zotero/zotero.sqlite` (`ITEMKEY` + JSON `readingTime`); se lee en
  modo solo lectura, seguro con Zotero abierto. Si hay varias notas por ítem gana la de `dateModified`
  más reciente. `#zot_progreso` solo se calcula cuando existen página y total: no se inventa.
- **`--metadatos` solo corre si alguna base cambió** desde la última pasada aplicada (mtime contra la
  marca en `script_ecosistema_lectura/estado/`); `--enlazar` solo escribe con `--aplicar` y solo los enlaces «adjunto» (el ítem enlaza el PDF del libro);
  los de ISBN o título se pegan a mano. El RIS de lo que falta en Zotero lo da `--enlazar --ris`.
- **El respaldo de KOReader excluye `settings.reader.lua` a propósito** (contiene credenciales `kosync`);
  el repo de datos es `KOREADER_RESPALDO_DIR` (`~/.local/share/koreader-respaldo/`), no `~/.dotfiles`.
- **`IFS=$'\t'` colapsa campos vacíos de un TSV en Bash**: `script_catalogacion_biblioteca` usa
  `tr '\t' '\037'` + `IFS=$'\037'`; GNU `tr` solo acepta el octal. El enum `Clasificador` real lleva
  tildes y le faltan valores del prompt: `script_catalogacion_biblioteca/lib/clasificador.sh` normaliza y
  omite reportando.
- **Los `.js` de `scripts_for_zotero` están absorbidos por la política de `sincronizar_zotero`**:
  ejecutarlos reintroduce divergencia (en especial `invertir_nombres.js`); solo `series_organizer`
  sigue vivo, como organizador de subcolecciones después del sync.
- **«Calibre está abierto; reintentará»** en el journal es normal; `Persistent=true` corre a las 04:30
  perdidas al encender.

## Dónde está cada cosa

| pregunta | documento |
|---|---|
| qué es automático, qué hago yo, comandos, verificación, qué no tocar | `docs/operacion.md` |
| por qué es así y qué está pendiente | `docs/decisiones.md` |
| por qué el ecosistema de lectura es así (fases 1–4) | `docs/historial/diseno-ecosistema-lectura-2026-08.md` |
| qué hizo cada campaña sobre la biblioteca y cómo se monta una | `docs/historial/campanas-sobre-la-biblioteca.md`, `script_normalizacion_metadatos/README.md` |
| autoridad por dato y dirección de cada sync | `meta/MODELO_METADATOS.md`, `meta/SINCRONIZACION.md` |
| política campo a campo Calibre ⇄ Zotero | `script_sincronizar_zotero/README.md` |
| columnas `#ko_*`, sidecars por hash, respaldo continuo | `script_koreader_estudio/README.md` |
| columnas `#zot_*`, fuente de datos en Zotero, orquestación | `script_ecosistema_lectura/README.md` |
| flujo ficha → TSV → Calibre y el registro de fichas | `script_catalogacion_biblioteca/README.md` |
| formato de una ficha de catalogación (prompt 02) | `prompts/01 fuentes/prompt_02_catalogar.md` |
| lock, logger, backup rotado, detección de apps | `core/shell-lib/`, `core/README.md` |
| contrato de suite y bloques generados | `core/suite.schema.yml`, `core/suites.py` |
| normativa de archivos y documentación | `meta/NORMATIVA_ARCHIVOS.md` §15 |
