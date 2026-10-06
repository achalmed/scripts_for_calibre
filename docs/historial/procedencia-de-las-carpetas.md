---
tipo: bitacora
titulo: "Procedencia de las carpetas: de dónde vino cada suite del único lugar de fuentes"
estado: hecho
---
# Procedencia de las carpetas

> **Origen.** Esta tabla era la columna «Antes vivía en» de la sección Estructura del
> `README.md`, que respondía «¿por qué está esto aquí?» con historia en vez de con función
> (`meta/diagnosticos/DIAGNOSTICO_DOCUMENTACION_2026-09.md`). Lo vigente: `../../README.md`
> §Estructura y [`../arquitectura.md`](../arquitectura.md). La decisión que la explica:
> [`../decisiones.md`](../decisiones.md) §5.2.

| carpeta | de dónde vino | cuándo |
|---|---|---|
| `main.py`, `config.py`, `lib/comun.py` | nació aquí como suite `fuentes` | 2026-09-06 |
| `fuentes/congreso/` | el localizador de normas del CIL del despacho (`localizar_normas.py` del marco legal) | 2026-09-06 |
| `fuentes/articulo/` | nació aquí (FD5) | 2026-09-07 |
| `entrada/` | sustituyó como zona de aterrizaje a las carpetas de investigación del CIL (M10 D6 y D8) | 2026-09-15 |
| `ingesta/` | `CIL/00_ingesta` del despacho | 2026-09-06 |
| `ingesta_cursos/` | `scripts_for_calibre/script_ingesta_recursos` | 2026-09-06 |
| `fichas/` | nació aquí (FD2) | 2026-09-07 |
| `lecturas/` | generaliza el `06_lecturas_biblioteca.py` de un informe de datafw (2026-08) (FD2) | 2026-09-07 |
| `manifiesto/` | nació aquí (FD4) | 2026-09-07 |
| `manifiestos/marco_legal/` | `CIL/02_investigacion/marco_legal/00_manifiesto`; su bitácora propia está en su README | 2026-09-06 |
| `registro/marco-legal-pendientes.md` | el `PENDIENTES.md` del marco legal, que pasó por `manifiestos/marco_legal/` | 2026-09-20 |

Las referencias que apuntaban a las rutas antiguas se actualizaron en la misma mudanza; el detalle
está en `meta/PROGRESO.md` (la fase de «único lugar de fuentes», 2026-09-06) y en el historial
de git de este repo.
