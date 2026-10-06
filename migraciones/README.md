---
tipo: readme
estado: activo
---
# migraciones/ — la migración de metadatos de la biblioteca por campañas (ola 2b, P0–P9)

<!-- suite:inicio -->
**Suite `migraciones`** · objetivo *biblioteca* · estado *activo* · python · interfaz cli

Campañas de la migración de metadatos de Calibre (P1–P9): plan desde una copia, ensayo y deshacer probados sobre otra copia, y aplicación por la puerta.

- Escribe en: calibre · simula por defecto: sí
- Entrada: metadata.db (copias en $XDG_CACHE_HOME/migraciones/)
- Depende de: calibre
- Nota: el registro de cada campaña (plan.json, propuesta.tsv, resumen.md) queda en migraciones/<paso>-<fecha>/ (en minúsculas); el respaldo y deshacer.sh, en $RESPALDOS_DIR/biblioteca/migraciones/

Comandos:

```bash
python3 main.py P1             # plan + ensayo sobre copia + deshacer probado; no toca la base real
python3 main.py P1 --aplicar   # además la aplica por la puerta y deja deshacer.sh en $RESPALDOS_DIR
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-10-06); no se edita a mano.</sub>
<!-- suite:fin -->

Cada paso de `meta/programa/03-arquitectura/modelo-de-metadatos.md` §7 es un módulo de `pasos/` que lee una copia de
`metadata.db` y devuelve su plan. `campana.py` lo ensaya sobre otra copia (verificación de cada valor leído de vuelta,
carpetas de libro intactas salvo en los pasos que las mueven, deshacer probado byte a byte) y solo con `--aplicar` lo
escribe en la base real por la puerta (`lib/escribir.py aplicar-campana`).

## Uso

```bash
python3 migraciones/main.py P1             # simula: plan, ensayo y deshacer probado
python3 migraciones/main.py P1 --aplicar   # aplica por la puerta (Calibre cerrado, candado, respaldo verificado)
```

## Estructura

| archivo | qué es |
|---|---|
| `main.py` | el ciclo de una campaña: plan, ensayo, verificación, deshacer, aplicación |
| `leer_campos.py` | lee por la API de Calibre (solo lectura) los valores escritos, para verificarlos |
| `pasos/pN.py` | el plan de cada paso |
| `<paso>-<fecha>/` (p. ej. `p8-2026-10-06/`) | el registro de cada campaña: `plan.json`, `propuesta.tsv`, `resumen.md` |

## Límite honesto

- La verificación lee de vuelta cada valor escrito, pero no juzga si el valor es el correcto: eso lo decide el paso
  y se revisa en `propuesta.tsv`.
- El deshacer devuelve toda la base a la foto de antes de la campaña: lo escrito después por los timers se pierde.
