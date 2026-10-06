---
tipo: readme
estado: activo
---
# migraciones/ — la migración de metadatos de la biblioteca por campañas (ola 2b, P0–P9)

<!-- suite:inicio -->
<!-- suite:fin -->

Cada paso de `meta/programa/03-arquitectura/modelo-de-metadatos.md` §7 es un módulo de `pasos/` que lee una copia de
`metadata.db` y devuelve su plan. `campana.py` lo ensaya sobre otra copia (verificación de cada valor leído de vuelta,
carpetas de libro intactas salvo en los pasos que las mueven, deshacer probado byte a byte) y solo con `--aplicar` lo
escribe en la base real por la puerta (`lib/escribir.py aplicar-campana`).

## Uso

```bash
python3 migraciones/campana.py P1             # simula: plan, ensayo y deshacer probado
python3 migraciones/campana.py P1 --aplicar   # aplica por la puerta (Calibre cerrado, candado, respaldo verificado)
```

## Estructura

| archivo | qué es |
|---|---|
| `campana.py` | el ciclo de una campaña: plan, ensayo, verificación, deshacer, aplicación |
| `leer_campos.py` | lee por la API de Calibre (solo lectura) los valores escritos, para verificarlos |
| `pasos/pN.py` | el plan de cada paso |
| `<paso>_<fecha>/` | el registro de cada campaña: `plan.json`, `propuesta.tsv`, `resumen.md` |

## Límite honesto

- La verificación lee de vuelta cada valor escrito, pero no juzga si el valor es el correcto: eso lo decide el paso
  y se revisa en `propuesta.tsv`.
- El deshacer devuelve toda la base a la foto de antes de la campaña: lo escrito después por los timers se pierde.
