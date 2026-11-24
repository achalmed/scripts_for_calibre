---
tipo: informe
estado: activo
---
# zotero-creadores-2026-11-23-b/ — la campaña ZOTERO-CREADORES (instituciones partidas en nombre y apellido)

- Ítems corregidos a un creador de un solo campo: 70.
- Las claves de cita no cambian.
- Segunda aplicación (23:39), con la aprobación del autor: los 70 que quedaban tras `zotero-creadores-2026-11-23/`. No queda
  ninguno partido por esta causa; «Venables» y «Smith», personas del mismo ítem que «R Core Team», siguen en dos campos.
- Comparada la base antes y después: cambian `items` e `itemCreators` de esos 70 y se añaden 56 filas a `creators`.
- Usos de sus 70 claves: ninguno en los archivos de texto de `~/Documents`, sin contar `biblioteca`, las carpetas `data`,
  `archivo` y `registro`, ni lo sensible (no se lee); las bases de Qillqa no se revisaron.
- Deshacer: `python3 migraciones/zotero_creadores.py --deshacer "$RESPALDOS_DIR/biblioteca/puerta/migraciones/zotero/zotero-creadores-2026-11-23-b-deshacer.json"`.
