---
tipo: registro
titulo: "Campaña P2 de la migración de metadatos (2026-10-06)"
creado: 2026-10-06
---
# P2 — 2026-10-06

- 828 autores con coma literal en 1398 libros: se guardan como Calibre los espera
- valores: 1398
- enumeraciones: —
- columnas que se retiran: —
- ensayo sobre copia: verificación sin errores; deshacer probado (la copia volvió byte a byte)
- aplicada en la base real el 2026-10-06: verificación sin errores
- respaldo y deshacer: `$RESPALDOS_DIR/biblioteca/migraciones/P2_2026-10-06/`

## Segunda pasada (rename_items) — no se aplica

- La primera pasada (escribir los autores de cada libro) no cambió ningún nombre: Calibre reutiliza la fila de
  autor que ya existe con la coma. Su efecto en la base es nulo (los valores leídos de vuelta son los mismos).
- Renombrar la fila (`rename_items`) cambiaría la carpeta de **1 383 libros** en el ensayo sobre copia: Calibre
  construye la carpeta con el nombre guardado. El modelo exige 0 carpetas movidas para estos 828 autores; la
  verificación lo impidió y la base real no se tocó.
- Decisión del director (2026-10-06): los 828 autores siguen con la coma literal, que no cambia su nombre visible.
  Convertirlos exige mover carpetas y reescribir `attachments:` en Zotero (la vía de P2b y P7, con
  `lib/adjuntos_zotero.py`), una campaña aparte que solo vale si otra razón obliga a mover esas carpetas.
