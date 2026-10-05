---
tipo: readme
estado: activo
---
# docs/ — documentación de `scripts_for_calibre`: lo transversal a las suites, por lector

Cada suite se documenta en su propio `README.md`; aquí va lo que cruza varias: la operación del
ecosistema de lectura, las decisiones y el historial. Lo cumplido o superado está en `historial/` y
se lee para saber por qué, no para saber cómo.

## Por dónde empezar

| si eres… | empieza por |
|---|---|
| **quien lee y estudia** (KOReader, Zotero, Calibre) | [operacion.md](operacion.md) §1 y §2 → [`../script_koreader_estudio/README.md`](../script_koreader_estudio/README.md) |
| **quien cataloga o corrige metadatos** | [`../script_catalogacion_biblioteca/README.md`](../script_catalogacion_biblioteca/README.md) → [`../script_verificar_metadatos/README.md`](../script_verificar_metadatos/README.md) → [`../script_sincronizar_zotero/README.md`](../script_sincronizar_zotero/README.md) |
| **quien mantiene o amplía las suites** | [`../CLAUDE.md`](../CLAUDE.md) → [decisiones.md](decisiones.md) → [operacion.md](operacion.md) §1.1 y §4 → el `README.md` y el `suite.yml` de la suite |
| **quien prepara una campaña sobre la biblioteca** | [`../script_normalizacion_metadatos/README.md`](../script_normalizacion_metadatos/README.md) → [historial/campanas-sobre-la-biblioteca.md](historial/campanas-sobre-la-biblioteca.md) → `meta/docs/historial/diagnosticos/` |
| **otro repositorio** (`scripts_for_fuentes`, `prompts`, `meta`) | [consumidores.md](consumidores.md) (lo que se usa de aquí) → `meta/docs/historial/MODELO_METADATOS.md` y `meta/docs/historial/SINCRONIZACION.md` (la frontera) |

## Cómo se mantiene

- Lo nuevo se escribe en el documento de su concepto; nunca un `.md` por cambio, fecha o sesión.
- La decisión y su porqué van a [decisiones.md](decisiones.md), sin renumerar; lo pendiente, a su
  §Pendientes.
- Las cantidades que cambian (libros, fichas, pares enlazados) no se escriben: se nombra la orden
  que las cuenta.
- Una campaña nueva deja su crónica en su carpeta (cabecera del `main.sh`, tablas) y en el mensaje
  de commit ([decisiones.md](decisiones.md) §4.6); la bitácora de `historial/` está cerrada.
- La tabla de abajo la genera `python3 core/docs.py indice scripts_for_calibre --aplicar` (desde
  `~/Documents`); no se edita a mano.

## Índice

<!-- docs:inicio -->
| documento | tipo | estado | qué es |
|---|---|---|---|
| [consumidores.md](consumidores.md) | `doc` | `activo` | Consumidores de scripts_for_calibre: lo que otros repos usan de aquí y lo que no se cambia sin avisarles |
| [decisiones.md](decisiones.md) | `decision` | `activo` | Decisiones de scripts_for_calibre: autoridad de los datos, escritura segura, campañas y pendientes |
| [operacion.md](operacion.md) | `doc` | `activo` | Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero): qué es automático, qué es manual, cómo se verifica |
| [historial/README.md](historial/README.md) | `readme` | `activo` | docs/historial/ — lo cumplido: el diseño del ecosistema de lectura, campañas y refactorizaciones |
| [historial/campanas-sobre-la-biblioteca.md](historial/campanas-sobre-la-biblioteca.md) | `bitacora` | `hecho` | Campañas sobre la biblioteca: lo que se catalogó, normalizó y sincronizó en bloque, y con qué resultado |
| [historial/diseno-ecosistema-lectura-2026-08.md](historial/diseno-ecosistema-lectura-2026-08.md) | `plan` | `hecho` | Diseño del ecosistema de lectura sincronizado: Calibre ⇄ KOReader ⇄ Zotero |
| [historial/refactorizacion-modular.md](historial/refactorizacion-modular.md) | `bitacora` | `hecho` | Refactorización modular de metadatos_calibre y catalogacion_biblioteca: los defectos del código original y cómo se corrigieron |

<sub>Bloque generado por `core/docs.py indice` desde el frontmatter de docs/ (2026-10-04); no se edita a mano.</sub>
<!-- docs:fin -->
