---
tipo: guia_ia
estado: activo
---
# CLAUDE.md — scripts_for_calibre

Guía para el asistente. En español con tildes, como todo el ecosistema. `AGENTS.md` es un enlace a
este archivo. Léase antes: `estado.md` (dónde está el repo), `README.md` (qué es, uso, estructura) y
`docs/README.md` (el mapa de la documentación, por lector). Concreta la guía de `~/Documents/CLAUDE.md`
para este repo y solo dice lo que aquella no dice.

## Reglas que no se negocian

- **Una sola puerta de escritura** (normativa 9.1, RQ-PRE-06; `docs/decisiones.md` §2.5). Solo
  `lib/escribir.sh`, `lib/escribir.py` y `lib/escribir_zotero.py` escriben en `metadata.db` o en
  `zotero.sqlite`: Calibre cerrado, candado (`LOCK_CALIBRE`/`LOCK_ZOTERO` de `core/env.sh`; ocupado
  sale 75) y respaldo verificado, en ese orden. Después, `calibredb_escribe`, la API de Calibre
  (`set_campos`) o las primitivas `z_*`. Calibre **nunca** por SQL (§2.7). Un escritor nuevo entra
  por la puerta o no existe: `tests/test_puerta.py` lo hace fallar.
- **Las bases reales son intocables en las pruebas.** Todo ensayo va sobre copias
  (`tests/calibre_apoyo.py`: biblioteca espejo, HOME y candado propios); las bases reales se leen
  solo con `mode=ro`. Nunca se ejecuta `add_format` contra el espejo (copiaría sobre un enlace a un
  PDF real).
- **La prueba antes del código** (R-2 de la ola 1): un cambio en un sincronizador vivo deja verde
  `python3 -m pytest scripts_for_calibre/tests` (< 2 min) contra la referencia; un defecto se fija
  primero como `xfail` estricto.
- **Calibre manda en los metadatos bibliográficos**; Zotero solo rellena vacíos y puebla el espejo
  `#zotero_*`; vacío en el origen nunca borra en el destino (`sincronizar-zotero/README.md`).
- **Título y autor jamás se escriben en Calibre** por sincronización ni verificación: Zotero enlaza
  los adjuntos por `Autor/Título (id)`. Excepciones: la catalogación (antes de que haya ítem en
  Zotero) y una campaña que reescriba Zotero en la misma operación (`lib/adjuntos_zotero.py`).
- **Los relojes de lectura no se copian entre sí**: `#ko_tiempo` (KOReader), `#zot_tiempo` (Zotero),
  `#tiempo_estudio` los suma. No hay deduplicación que implementar.
- **Simulación por defecto y `--aplicar` explícito**, en todas las suites (también
  `metadatos_calibre`). Un cambio masivo se ensaya con `--limite N` o `--ids` antes del total.
- **Columnas manuales que ningún script toca:** `#estudio`, `#apuntes` (solo vía `--apuntes`),
  etiquetas y series. Las `ko_*`, `zot_*`, `#leído` tras Terminado y las compuestas las escriben las
  suites: no se editan a mano.
- **Las columnas se resuelven por etiqueta**, nunca por número de `custom_column_N`.
- **Rutas por `core/env.sh`** (`BIBLIOTECA_DIR`, `ZOTERO_DB`, `KOREADER_STATS`, `CORE_PYTHON`…): ni
  `$HOME/Documents` ni la carpeta de inicio literal; lecturas de SQLite desde Bash con `lib/leer.sh`
  (los timers no llevan `sqlite3` en el PATH).
- **Los timers son plantillas en `systemd/`** y se instalan con `systemd/instalar.sh` (simula por
  defecto; `--verificar` compara lo instalado). No se tocan las unidades de `~/.config/systemd/user`
  a mano. Los timers corren cada 30 min sobre este repo: cada commit deja sus `main.sh` funcionando.
- **Respaldos y estado fuera del repo**: `$XDG_STATE_HOME/biblioteca/`. `reportes/` es runtime
  ignorado; lo generado (bloques `suite:`/`suites:`/`docs:`) no se edita a mano.
- **`lib_comun/` no se amplía, ni se borra ni se renombra**: lo consume `scripts_for_fuentes`
  hasta que `core` lo retire (C4).
- **`catalogacion/fichas/` y su TSV son el registro de esa suite**: las fichas las
  escribe `scripts_for_fuentes/ingesta`; aquí se aplican al catálogo. `proyecto:` es un id.
- **Dónde va cada cosa nueva**: en la raíz solo `README.md`, `CLAUDE.md`, `AGENTS.md`, `estado.md` y
  `LICENSE`; el porqué a `docs/decisiones.md` (`### §N.M`, sin renumerar), lo pendiente a
  `estado.md` §Por hacer con fecha y dueño, el uso de una suite a su README, lo que otro repo usa de
  aquí a su documento de `docs/` (consumidores). Lo hecho en una sesión va al commit, no a un archivo.
- Nada del despacho ni correos en el repo (es público): el contacto de Crossref llega por
  `CROSSREF_MAILTO`.

## Cómo se verifica un cambio

```bash
python3 -m pytest scripts_for_calibre/tests                  # caracterización, puerta, entorno (< 2 min)
python3 core/archivos.py validar scripts_for_calibre --linea-base "$PWD/meta/programa/05-piloto/linea-base/validador.json"
python3 core/suites.py validar                               # los suite.yml contra core/suite.schema.yml
python3 core/docs.py verificar scripts_for_calibre           # ¿docs/README.md al día?
bash -n scripts_for_calibre/koreader/main.sh  # sintaxis; un archivo por invocación
scripts_for_calibre/systemd/instalar.sh --verificar          # ¿lo instalado = las plantillas?
systemctl --user list-timers | grep -E "koreader|ecosistema" # los tres timers, próxima pasada
```

Deshacer una escritura: copiar el respaldo de `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/` sobre
la base, con la app cerrada.

## Detalles que cuesta redescubrir

- **Calibre se excluye por un socket abstracto por usuario**: dos `calibredb` a la vez fallan
  («Another calibre program…»); por eso las pruebas corren bajo `unshare -rn`. Mientras corren, un
  timer real puede ver procesos de Calibre y saltarse la pasada: es normal.
- **Trampas de Calibre 9 y de las columnas `#ko_*`** (`set_custom`, `field()` frente a
  `raw_field()`, `#ko_progfloat` en fracción 0–1): `koreader/README.md`.
- **KOReader ↔ Calibre se emparejan por el MD5 parcial de KOReader** (`#ko_md5`); los sidecars
  viven en `~/.config/koreader/hashdocsettings/`, así que renombrar en Calibre no rompe nada.
- **El Read Time de Zotero** es una nota del ítem «Addon Item» de Ethereal Style en `itemNotes`; se
  lee en solo lectura, seguro con Zotero abierto.
- **`--metadatos` solo corre si alguna base cambió** desde la última orquestación aplicada.
- **`IFS=$'\t'` colapsa campos vacíos de un TSV en Bash**: la catalogación usa `\037`.
- **Los `.js` de `scripts_for_zotero`** (salvo `series_organizer`) revierten la política del sync.
