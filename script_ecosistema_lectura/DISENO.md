# DISEÑO — Ecosistema de lectura sincronizado: Calibre ⇄ KOReader ⇄ Zotero

#diseño · Estado: **investigación completada, fases 1 hechas, fases 2+ por implementar**
Fecha: 2026-08-09 · Basado en inspección real de las tres instalaciones (no en supuestos).

## 1. Hallazgos de la investigación

### Identidad del mismo documento en los tres sistemas (punto 9 del pedido)

**Calibre es el hub de identidad.** Los dos puentes ya existen y están probados:

| Puente | Mecanismo | Estado |
|---|---|---|
| Calibre ↔ Zotero | columna `#zotero_key` (clave del ítem padre en Zotero), poblada por ZMI y mantenida por `script_sincronizar_zotero` | ✅ en producción |
| Calibre ↔ KOReader | **MD5 parcial de KOReader** (md5 de bloques de 1 KB en offsets 0 y 1024·4^i; verificado bit a bit contra `statistics.sqlite3`), cacheado en `#ko_md5` | ✅ en producción |
| KOReader ↔ Zotero | **join en Calibre** (`#ko_md5` ⋈ `#zotero_key`) — no necesita puente propio | ✅ por construcción |

DOI/ISBN/título+autor quedan como *fallback* solo para **enlazar pares nuevos**
(libros sin `#zotero_key`), siempre con reporte y confirmación (Fase 4). Nunca
se empareja por título solo.

### Read Time de Zotero (punto 2) — RESUELTO por inspección

- **Quién lo genera:** el plugin **Ethereal Style** (`zoterostyle@polygon.org`,
  perfil activo `0xh8512f.default`). No es un campo nativo de Zotero.
- **Dónde vive:** en `~/Zotero/zotero.sqlite`, tabla `itemNotes`: son **notas
  hijas de un ítem contenedor "Addon Item"** (itemID 4534). Hay **174 registros**.
- **Estructura exacta** (verificada):

  ```html
  <div class="zotero-note znv1">57R2ZVBM
  {"readingTime":{"page":8,"data":{"0":10,"6":10}}}</div>
  ```

  Línea 1 = **clave del ítem** al que pertenece el registro (== `#zotero_key`).
  `data` = mapa **página → segundos leídos**. Read Time total = Σ valores.
  `page` = total de páginas del documento.
- **Lectura desde Linux:** consulta SQLite en modo solo-lectura — segura incluso
  con Zotero abierto.
- **Escritura:** posible pero delicada (editar la nota + subir `items.version`
  para no romper el sync de Zotero). Se **pospone** (Fase 5, opcional) y solo
  con Zotero cerrado + backup.

### Progreso en Zotero (punto 4)

Ethereal Style **no guarda un % de progreso** equivalente al de KOReader. El
lector de Zotero guarda la última página vista por adjunto (a investigar en
`syncedSettings`/estado del lector en Fase 2 — **no inventar el dato**). Hasta
entonces, el progreso tiene una sola fuente (KOReader) y no hay conflicto posible.

### Lo que YA está resuelto por herramientas existentes

| Necesidad del pedido | Herramienta | Notas |
|---|---|---|
| Etiquetas bidireccionales Calibre ⇄ Zotero, unificación (`macroeconia`→`macroeconomia`), eliminación segura (puntos 6-7) | `script_sincronizar_zotero` | reglas ya decididas: Calibre manda en vocabulario; tags personales de Zotero (⭐, emojis, #hashtags) intocables |
| Metadatos por campo con fuente principal (punto 8, 10) | `script_sincronizar_zotero` | matriz completa en su README (título/autor solo Calibre→Zotero, idioma Calibre manda, etc.) |
| Progreso/estado/tiempo KOReader → Calibre (puntos 3-5) | `script_koreader_estudio` | timer cada 30 min |
| Series/orden de cursos, apuntes .md | Calibre (`#apuntes`, series) | hecho |

## 2. Arquitectura elegida (punto 15): **Opción B — motor local de scripts + timers systemd**

Sin plugin nuevo de Calibre. Razones: (a) dos de las tres patas ya existen como
scripts modulares probados con simulación/backup; (b) `calibredb`/`calibre-debug`
dan acceso completo sin GUI, mientras que un plugin exigiría Calibre abierto —
justo cuando la base está bloqueada para los demás; (c) mantenimiento mínimo.

```
   KOReader (sidecars hash + statistics.sqlite3)      Zotero (zotero.sqlite: notas readingTime)
              │  cada 30 min (timer, ya activo)                  │  cada 30 min (Fase 2, ro)
              ▼                                                  ▼
        script_koreader_estudio ──────► CALIBRE ◄────── script_ecosistema_lectura
                                (columnas #ko_*, #zot_*, composites, #apuntes)
                                           ▲
                                           │  bajo demanda / semanal, ambos cerrados
                              script_sincronizar_zotero (metadatos + tags, bidireccional)
```

## 3. El tiempo de lectura NO se duplica por diseño (punto 3)

Regla de oro: **cada aplicación es dueña de su propio reloj; Calibre agrega,
nunca copia tiempos entre relojes.**

- `#ko_tiempo` = minutos según KOReader (statistics.sqlite3). Ya existe.
- `#zot_tiempo` = minutos según Zotero/Ethereal Style (Σ `readingTime.data`). Fase 2.
- `#tiempo_estudio` = composite `#ko_tiempo + #zot_tiempo`. Fase 2.

Leer 30 min en KOReader solo incrementa el contador de KOReader; el de Zotero
jamás lo ve. No hay sesión que deduplicar porque **ningún segundo entra dos
veces al mismo contador** — la agregación es idempotente por construcción.
(Si algún día se activa la Fase 5 —escribir tiempo de KOReader dentro del
registro de Ethereal Style—, ahí sí se usará page_stat_data por sesión con
marca de agua de última exportación; por eso es opcional y va al final.)

## 4. Estados (punto 5): lectura ≠ estudio

- `#estado_estudio` (composite, automático) = estado de **lectura**:
  ⬜ Pendiente / 📖 En proceso / ✅ Finalizado / ⏸ Abandonado, desde `#ko_status`.
- `#estudio` (enum **manual**, creada 2026-08-09) = estado de **estudio**:
  ⬜ Pendiente / 📖 En proceso / 🔁 Repasar / ✅ Finalizado. El sync nunca la toca.
  Un libro puede estar «lectura 100 %» y «estudio en proceso».

## 5. Conflictos (punto 10)

| Dato | Regla |
|---|---|
| Progreso | max(progreso) con timestamp — hoy fuente única (KOReader), sin conflicto posible |
| Tiempo | agregación de relojes independientes; nunca sobrescribir ni copiar |
| Etiquetas | reglas vigentes de `script_sincronizar_zotero` (Calibre manda vocabulario; personales de Zotero intocables; vacío nunca borra) |
| Metadatos | matriz por campo de `script_sincronizar_zotero` |
| Estado lectura | manda KOReader (`#ko_status`); `#leído` manual solo promueve, nunca degrada |

## 6. Fases de implementación

- **Fase 1 — HECHA (2026-08-09):** KOReader→Calibre (progreso/estado/tiempo/fechas),
  barra y estado composite, `#apuntes` clicable, sidecars migrados a hash (con
  rescate de huérfanos renombrados), respaldo continuo versionado en
  `~/.dotfiles/koreader-data/` (texto: statistics.sql + luas; commit local
  automático, publicar con `dotfiles sync-push`), timer 30 min.
- **Fase 2 — HECHA (2026-08-09):** `script_ecosistema_lectura/` lee
  `zotero.sqlite` (ro) → `#zot_tiempo` + `#zot_ultima` en 122 libros enlazados
  (163 registros readingTime); composite `#tiempo_estudio` = ko + zot; timer
  propio cada 30 min con lock compartido (`.lock_calibre_write`) contra
  `script_koreader_estudio`.
  - **Fase 2b — HECHA (2026-08-09):** `#zot_progreso` = `(lastPageIndex+1) /
    readingTime.page` (135 registros de lector; 108 libros poblados). Los
    localizadores no numéricos (EPUB) se omiten — no se inventa. `#barra` y
    `#estado_estudio` ahora aplican **max(ko, zot)** y consideran `#zot_tiempo`.
- **Fase 3 — HECHA (2026-08-09):** `--metadatos` orquesta
  `script_sincronizar_zotero` (verificado sin prompts interactivos) solo con
  ambas apps cerradas + cambios detectados (mtime vs marca en `estado/`);
  timer diario 04:30 con `--aplicar` y lock compartido. Validado en simulación:
  4441 pares analizados en ~1 s.
- **Fase 4 — HECHA como reporte (2026-08-09):** `--enlazar` genera el TSV de
  los 41 libros sin `#zotero_key` (3 candidatos por título; el resto son hojas
  de ejercicios sin ítem en Zotero — correcto). La escritura del enlace queda
  manual por diseño (confirmación humana).
- **Fase 5 (opcional, riesgo):** exportar sesiones de KOReader al registro
  `readingTime` de Ethereal Style (Zotero cerrado, backup, bump de version,
  marca de agua anti-duplicación).

## 7. Seguridad (punto 14) — reglas vigentes en todas las fases

Simulación por defecto y `--aplicar` explícito · backup rotado antes de escribir ·
solo-lectura sobre bases ajenas salvo fase aprobada · locks `flock` · escrituras
solo con la app dueña cerrada · verificación post-cambio (conteos + apertura manual).
