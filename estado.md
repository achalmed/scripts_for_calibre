---
tipo: estado
estado: activo
actualizado: 2026-10-05
---
# estado.md — scripts_for_calibre

El estado único del repo (normativa-documental §3.2): lo hecho reciente, lo que está en curso y lo
pendiente, con fecha y dueño. Las decisiones vigentes viven en [docs/decisiones.md](docs/decisiones.md).
El encargo de la ola 2a es `meta/programa/06-olas/ola-02-reingenieria.md` §2 (K1–K9).

## Hecho

| fecha | qué | dónde se ve |
|---|---|---|
| 2026-10-05 | Ola 2a, K1: caracterización de los tres sincronizadores vivos (simulación y `--aplicar`) contra copias de `metadata.db` y `zotero.sqlite`, comparada con la referencia `467c8a7`; fija el defecto del relleno de `pubdate` (xfail estricto) | `python3 -m pytest scripts_for_calibre/tests` (< 2 min) |

## En curso

- 2026-10-05 · ola 2a, K2: una sola puerta de escritura (`lib/escribir.{py,sh}`) (dueño: agente «calibre»)

## Por hacer

- 2026-10-05 · K2–K9 de la ola 2a (dueño: agente «calibre»): ver el encargo.
