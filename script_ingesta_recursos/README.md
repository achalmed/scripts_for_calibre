# script_ingesta_recursos — material externo de los cursos → Calibre (F5.4)

Los cursos docentes (`10 Class/areas/*/course_*`) acumulaban en `06_RECURSOS/` y `08_INVESTIGACION/`
PDF de terceros (libros, lecturas, manuales, diapositivas de otros docentes). La regla del ecosistema es que
**todo material bibliográfico vive en Calibre** y el curso lo cita por `calibre_id`. Esta suite lo aplica.

```bash
./main.sh --escanear                  # reportes/candidatos_<fecha>.tsv: una fila por PDF con decisión propuesta
./main.sh [--tsv ARCHIVO]             # simula la ingesta (calibredb add que se ejecutaría)
./main.sh --aplicar [--tsv ARCHIVO]   # Calibre cerrado · lock compartido · backup de metadata.db · calibredb add
```

- **Decisión por fila** (`ingestar` · `omitir` · `revisar`), deducida de la carpeta y del autor del PDF
  (`lib/clasificar.sh`): referencias, lecturas, talleres, unidades y diapositivas de otros autores → `ingestar`;
  trabajos de estudiantes, plantillas, administración, ejercicios propios y cualquier PDF cuyo autor sea Edison
  → `omitir`; el resto → `revisar`. Edita la columna `decision` del TSV antes de `--aplicar`.
- **Al ingestar** (`lib/ingestar.sh`): `calibredb add -t título -a autor -T "academic_class,recurso_curso,curso:<id>"`,
  registro en el `temario.yml` del curso (`bibliografia: [{calibre_id, titulo, autor, origen}]`) y retiro del
  original a `ORIGINALES_DIR` (por defecto `meta/reparaciones/F5.4_biblioteca_2026-09-06/originales/`, reversible).
- Autor `Desconocido` cuando el PDF no lo declara o es genérico: lo completa después la campaña de
  `script_catalogacion_biblioteca`.
- Config en `config.sh`; `lib_comun/` aporta logger, `calibre_abierto`, `tomar_lock_calibre` y `backup_metadata_db`.
