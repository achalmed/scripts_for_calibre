---
tipo: bitacora
titulo: "Refactorización modular de metadatos_calibre y catalogacion_biblioteca: los defectos del código original y cómo se corrigieron"
estado: hecho
---
# Refactorización modular: los defectos del código original

> Bitácora. Lo vigente está en `../../script_metadatos_calibre/README.md` y
> `../../script_catalogacion_biblioteca/README.md`; lo que cuesta redescubrir, en `../../CLAUDE.md`.

Dos suites nacieron de scripts sueltos y se reescribieron con el patrón `main.sh` + `config.sh` +
`lib/` (2026-06 y 2026-07). Al hacerlo se corrigieron estos defectos.

## `script_metadatos_calibre` (de `incrustar_metadatos_a_pdf_desde_opf.sh` y `anadir_pdfs_a_opf.sh`)

1. **Éxitos falsos.** Sin `set -e`, un fallo de `exiftool` contaba como éxito. Ahora `set -uo
   pipefail` y cada operación lleva su contador.
2. **Metadatos vacíos sobre el PDF.** Con un OPF incompleto seguía y vaciaba campos del PDF. Ahora
   la carpeta se marca inválida y se salta.
3. **Autores con comillas truncados** por el delimitador del `sed`. Ahora `extract_opf_field()`
   captura hasta la comilla siguiente.
4. **Log perdido en silencio** si `/tmp` no era escribible. Ahora `log_init()` lo comprueba y avisa.
5. **`register` sin validar la biblioteca** (`cd ..` a ciegas). Ahora `validate_calibre_library()`
   exige `metadata.db`.
6. **Errores reales contados como «ya tenía PDF».** Ahora solo se consulta si el libro ya tenía PDF
   cuando `calibredb add_format` falla, para distinguir duplicado de error.

La auditoría A7 (2026-08-10) absorbió aquí el incrustador rival de `scripts_for_zotero`: `embed`
escribe también XMP Dublin Core desde los mapas de `config.sh` y nació `limpiar-json` para sus
sidecars.

## `script_catalogacion_biblioteca`

1. **`IFS=$'\t'` colapsaba campos vacíos del TSV** y desalineaba columnas. Ahora `tr '\t' '\037'` +
   `IFS=$'\037'` (GNU `tr` solo acepta el octal).
2. **`Portuguese` sin código ISO.** Ahora `map_language_to_code` lo lleva a `por`.
3. **Dependencias sin validar.** Ahora `lib/validator.sh` comprueba `calibredb` (salida 5 si falta)
   y avisa si faltan `sqlite3` o `python3`, que solo sirven para leer el enum en vivo.

La verificación de entonces fue `bash -n`, `--help`, `--version`, el dry-run completo (113 comandos,
paridad con la versión anterior salvo el defecto 2) y los códigos de salida 2 en opciones inválidas;
`shellcheck` no estaba disponible.
