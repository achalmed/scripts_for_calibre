# scripts_for_calibre

![Calibre](https://img.shields.io/badge/Calibre-v7%2B-blue) ![bash](https://img.shields.io/badge/bash-script-green) ![exiftool](https://img.shields.io/badge/exiftool-opcional-orange)

#readme

Colección de herramientas modulares (Bash + Python) alrededor de la biblioteca
**Calibre** (`~/Documents/biblioteca`): catalogación y normalización de
metadatos, verificación contra bases bibliográficas, incrustación en PDF y la
**plomería de sincronización** que une Calibre con **KOReader** (lectura) y
**Zotero** (referencias/citas).

Este repo es una de las 7 piezas del ecosistema personal. El contrato
arquitectónico global —capas, responsabilidades, dependencias, sincronización—
vive en `~/Documents/meta/` (`ARQUITECTURA.md`, `SINCRONIZACION.md`,
`MODELO_METADATOS.md`); el `doctor/` de esa carpeta diagnostica el conjunto.

> 📖 **Guía práctica del ecosistema de lectura/estudio** (qué es automático, qué
> es manual, chuleta de comandos, solución de problemas):
> [`GUIA_ECOSISTEMA.md`](GUIA_ECOSISTEMA.md).

## Las 7 suites (y una migrada)

| Suite | Rol | Escribe | Estado |
|---|---|---|---|
| `script_catalogacion_biblioteca/` | Cataloga libros **sin autor** (`Unknown`/`Desconocido`): fichas duales Zotero+Calibre por libro y aplicación de metadatos vía `calibredb`. | metadata.db (vía `calibredb`) | **Campaña terminada** (2026-07-27); herramienta reutilizable |
| `script_normalizacion_metadatos/` | Migraciones que normalizaron en bloque **etiquetas, Géneros, Item type y Clasificador** de ~4 484 libros desde los metadatos existentes. | metadata.db (SQLite directo) | **Campaña terminada** (2026-07-28); registro histórico (ver su README §Reproducibilidad) |
| `script_verificar_metadatos/` | Verifica metadatos contra **OpenLibrary/Crossref** (ISBN o título+autor) y reporta discrepancias. **Solo lectura.** | — (nunca escribe) | Herramienta de auditoría, a demanda |
| `script_metadatos_calibre/` | Incrustador **canónico** de metadatos en PDF (OPF → InfoDict + XMP-dc vía exiftool), registro de PDFs como formato en Calibre, y limpieza de `zotero_metadata.json` huérfanos. | PDFs (exiftool) / metadata.db (`add_format`) | Activo; incrustador único (el de `scripts_for_zotero` quedó deprecado, auditoría A7) |
| `script_sincronizar_zotero/` | Sincroniza **bidireccionalmente** metadatos/etiquetas entre Calibre y Zotero para los libros enlazados por ZMI (`#zotero_key`). Política "Calibre manda"; rellena vacíos, repara adjuntos, puebla `#zotero_*`. | metadata.db + zotero.sqlite | Activo; orquestado a diario (04:30) |
| `script_koreader_estudio/` | KOReader → Calibre: progreso, estado, minutos y fechas de lectura (`#barra`, `#estado_estudio`…), enlace clicable a apuntes (`#apuntes`), migración de sidecars a hash y respaldo continuo a `~/.dotfiles/koreader-data/`. | metadata.db (columnas `ko_*`) | Activo; **timer 30 min** |
| *(ingesta de material de cursos)* | Migrada el 2026-09-06 a `~/Documents/scripts_for_fuentes/ingesta_cursos/` (único lugar de fuentes); usa `lib_comun`, el lock y `script_catalogacion_biblioteca` de aquí. |
| `script_ecosistema_lectura/` | Zotero (Ethereal Style) → Calibre: tiempo (`#zot_tiempo`), progreso (`#zot_progreso`), `#tiempo_estudio`; **orquesta** `script_sincronizar_zotero` y reporta libros sin `#zotero_key`. | metadata.db (columnas `zot_*`) | Activo; **timers** (lectura 30 min; metadatos 04:30) |

Dirección de cada dato y autoridad de cada campo: `MODELO_METADATOS.md` y
`SINCRONIZACION.md` en `~/Documents/meta/`. Regla de oro: los relojes de
lectura (KOReader vs Zotero) nunca se copian entre sí; el único canal
bidireccional (metadatos) es asimétrico (Calibre gana todo diff; Zotero solo
rellena vacíos).

## Código compartido: `lib_comun/`

Módulos de única responsabilidad consumidos por varias suites (auditoría M1),
para no duplicar plomería:

| Módulo | Aporta | Consumido por |
|---|---|---|
| `lib_comun/logger.sh` | logger canónico `[LEVEL] YYYY-MM-DD HH:MM:SS - msg` | catalogacion, sincronizar, verificar |
| `lib_comun/detectar_apps.sh` | `calibre_abierto()` / `zotero_abierto()` (detección robusta `ps -eo comm`) | sincronizar, koreader_estudio, ecosistema_lectura |
| `lib_comun/lock.sh` | `tomar_lock_calibre()` (flock sobre `.lock_calibre_write`) | sincronizar, koreader_estudio, ecosistema_lectura |
| `lib_comun/backup_rotado.sh` | `backup_metadata_db RUTA DIR N` (cp + rotación) | koreader_estudio, ecosistema_lectura |

Las suites hacen `source "$PROJECT_DIR/../lib_comun/<módulo>.sh"`.

## Estándares comunes

Se siguen las convenciones del ecosistema (`~/Documents/meta/ARQUITECTURA.md`
**§5**). En resumen:

1. **Patrón de suite**: `main.sh` (orquestación) + `config.sh` (todo lo
   tunable) + `lib/` (módulos de única responsabilidad) + `README.md` honesto.
   Los tunables nuevos van al `config.sh`, nunca hardcodeados en `lib/`.
2. **Simulación por defecto**; escritura solo con `--aplicar` (o `--apply` en
   las migraciones). Correr siempre en simulación antes de un cambio masivo.
3. **Backups rotados** antes de escribir un almacén (5 para metadata.db; 2
   pares para el sincronizador bidireccional), en el `backups/` de la suite.
4. **Locking**: todo escritor de metadata.db toma `.lock_calibre_write`
   (flock, `lib_comun/lock.sh`); detección de apps con `ps -eo comm`.
5. **Idioma español** en código nuevo, docs y CLI.
6. **Sanity-check sin efectos**: `bash -n <archivo>.sh`.

Artefactos de ejecución (`*/backups/`, `*/reportes/`, `.lock_calibre_write`,
`estado/` runtime) están gitignorados: rotan/cambian en cada pasada.

## Requisitos

- Calibre con `calibredb` y `calibre-debug` en el PATH.
- `python3` (biblioteca estándar) y `sqlite3`.
- **exiftool** solo para `script_metadatos_calibre` (incrustar en PDF):
  ```bash
  sudo apt install libimage-exiftool-perl   # Debian/Ubuntu
  brew install exiftool                     # macOS
  ```
- Pensadas para ejecutarse **sin sudo**.

## Licencia

MIT License — usar, modificar y distribuir libremente.

## Autor

Edison Achalma B.Sc. Econ.
