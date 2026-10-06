---
tipo: guia_ia
estado: activo
---
# CLAUDE.md — scripts-biblioteca

Guía para el asistente. En español con tildes. `AGENTS.md` es un enlace a este archivo. Léase antes: `estado.md`,
`README.md`, `docs/README.md` (mapa por lector), `prompts/00 metodo/METODO_DOCUMENTAL.md` (los diez pasos que ejecutan
las suites de fuentes) y el README de la suite que se toque. Concreta `~/Documents/CLAUDE.md` para este repo.

## Reglas que no se negocian

- **Una sola puerta de escritura** (normativa 9.1, RQ-PRE-06; `docs/decisiones.md` §2.5): solo `lib/escribir.sh`,
  `lib/escribir.py` y `lib/escribir_zotero.py` escriben en `metadata.db` o en `zotero.sqlite`, con la app cerrada,
  candado (`LOCK_CALIBRE`/`LOCK_ZOTERO` de `core/env`; ocupado sale 75) y respaldo verificado, en ese orden. Después,
  `calibredb_escribe`/`calibredb_escribir`, la API de Calibre (`set_campos`) o las primitivas `z_*`. Calibre **nunca**
  por SQL (§2.7). Un escritor nuevo entra por la puerta o no existe: `tests/*/test_puerta.py` lo hacen fallar.
- **Las bases reales son intocables en las pruebas**: todo ensayo va sobre copias (`tests/calibre/calibre_apoyo.py`,
  la caja de arena de `tests/fuentes/conftest.py`); las reales se leen solo con `mode=ro`. Los temporales de las
  pruebas van al disco (`$XDG_CACHE_HOME/pytest/`), nunca a `/tmp` (es RAM).
- **La prueba antes del código**: un cambio en un sincronizador vivo deja verde `tests/calibre` contra la
  referencia de git; un defecto se fija primero como `xfail` estricto.
- **Calibre manda en los metadatos bibliográficos**; Zotero solo rellena vacíos; vacío en el origen nunca borra en
  el destino. **Título y autor jamás se escriben en Calibre** por sincronización ni verificación (Zotero enlaza los
  adjuntos por `Autor/Título (id)`), salvo la catalogación y una campaña que reescriba Zotero en la misma operación.
- **Los relojes de lectura no se copian entre sí**: `#ko_tiempo`, `#zot_tiempo`; `#tiempo_estudio` los suma.
- **Una sola biblioteca y subir no es catalogar**: ningún proyecto guarda copias ni enlaces a PDF (referencia por
  `calibre_id`, `zotero_key`, `clave_bibtex`; la ruta la da `core/py-common/biblioteca.py`); antes de `calibredb add`
  se deduplica por huella y título; no se inventan grafías de autor ni etiquetas fuera del vocabulario cerrado.
- **La ficha canónica vive en `catalogacion/fichas/`** (D12): `ingesta/fichas/` es borrador temporal fuera de git.
- **Lo que otros repos usan es contrato**: `manifiesto/` (módulo cargado por ruta, `main.py bib`), los nombres que
  escriben `fichas` y `lecturas`, `bibliografia:` del `curso.yml` (`docs/consumidores.md`, `docs/arquitectura.md` §6).
- **Simulación por defecto y `--aplicar` explícito** en todas las suites; un cambio masivo se ensaya con `--limite`
  o `--ids`. Las columnas se resuelven por etiqueta, nunca por número de `custom_column_N`.
- **Rutas por `core/env`** (`BIBLIOTECA_DIR`, `ZOTERO_DB`, `SCRIPTS_BIBLIOTECA`…); ledgers con rutas relativas a
  `DOCS_ROOT` (`lib/rutas.py`); lecturas de SQLite desde Bash con `lib/leer.sh`. Nada personal ni del despacho en el
  repo (es público): el contacto de Crossref y Unpaywall llega por `CROSSREF_MAILTO` y `FUENTES_CORREO_CONTACTO`.
- **Los timers son plantillas en `systemd/`** y se instalan con `systemd/instalar.sh` (simula; `--verificar` compara);
  corren cada 30 min sobre este repo: cada commit deja sus `main.sh` funcionando.
- **Los PDF del Congreso** pasan por `ocrmypdf -l spa`; nunca se copia texto del original.
- **Dónde va cada cosa nueva**: en la raíz solo `README.md`, `CLAUDE.md`, `AGENTS.md`, `estado.md`, `LICENSE` y
  lo de la suite `fuentes`; el porqué a `docs/decisiones.md` (`### §N.M`, sin renumerar), lo pendiente a `estado.md`
  §Por hacer con fecha y dueño, el uso de una suite a su README. Lo hecho en una sesión va al commit.

## Cómo se verifica un cambio

```bash
python3 -m pytest scripts-biblioteca/tests/calibre        # caracterización, puerta, entorno (sobre copias)
python3 -m pytest scripts-biblioteca/tests/fuentes        # caja de arena de ingesta, fichas, manifiesto
python3 core/archivos.py validar scripts-biblioteca --linea-base "$PWD/meta/programa/05-piloto/linea-base/validador.json"
python3 core/suites.py validar && python3 core/docs.py verificar scripts-biblioteca
scripts-biblioteca/systemd/instalar.sh --verificar        # ¿lo instalado = las plantillas?
( cd scripts-biblioteca && python3 manifiesto/main.py todo )   # todos los fuentes.yml vigilados, simula
```

Deshacer una escritura: copiar el respaldo de `$XDG_STATE_HOME/biblioteca/respaldos/<suite>/` sobre la base, con
la app cerrada.

## Detalles que cuesta redescubrir

- **Calibre se excluye por un socket abstracto por usuario**: dos `calibredb` a la vez fallan; las pruebas corren
  bajo `unshare -rn`. Si corre otro `calibre*`, las pruebas de escritura de `fuentes` se saltan (75).
- **KOReader ↔ Calibre se emparejan por el MD5 parcial** (`#ko_md5`); trampas de Calibre 9 y de `#ko_*`:
  `koreader/README.md`. El Read Time de Zotero es una nota de Ethereal Style, leída en solo lectura.
- **`--metadatos` solo corre si alguna base cambió** desde la última orquestación aplicada.
- **`ingesta/main.sh` toma el primer argumento como comando** (`estado` por defecto); la ayuda es `<comando> -h`.
- **Los ledgers son la verdad**: `fuentes_descargadas.tsv` e `ingesta/ingesta.tsv`; `catalogar` es idempotente por
  SHA-256; las variantes OCR son formatos, no libros; los anexos de un paquete van a `data/` del principal.
- **`lecturas` da la página del PDF desde 1**; «hallada en otra página» es `observada`, nunca `verificada`.
- **`IFS=$'\t'` colapsa campos vacíos de un TSV en Bash**: la catalogación usa `\037`.
- **`manifiestos/marco_legal/` es dato, no suite**; **los `.js` de `zotero/`** (solo `series_organizer`) se pegan
  a mano en la consola de Zotero.
