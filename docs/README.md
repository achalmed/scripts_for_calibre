---
tipo: readme
estado: activo
---
# docs/ — documentación de `scripts-biblioteca`: lo transversal a las suites, por lector

Cada suite se documenta en su propio `README.md`; aquí va lo que cruza varias: la operación del
ecosistema de lectura, la arquitectura del Método Documental (adquirir, ingerir, fichar, citar), cómo se
amplía, las decisiones y el historial. El método que ejecutan las suites de fuentes no se repite aquí: es
`prompts/00 metodo/METODO_DOCUMENTAL.md`, con un prompt por paso en `prompts/01 fuentes/`. Lo cumplido o superado está en `historial/` y
se lee para saber por qué, no para saber cómo.

## Por dónde empezar

| si eres… | empieza por |
|---|---|
| **quien lee y estudia** (KOReader, Zotero, Calibre) | [operacion.md](operacion.md) §1 y §2 → [`../koreader/README.md`](../koreader/README.md) |
| **quien cataloga o corrige metadatos** | [`../catalogacion/README.md`](../catalogacion/README.md) → [`../verificacion/README.md`](../verificacion/README.md) → [`../sincronizar-zotero/README.md`](../sincronizar-zotero/README.md) |
| **quien mantiene o amplía las suites** | [`../estado.md`](../estado.md) → [`../CLAUDE.md`](../CLAUDE.md) → [decisiones.md](decisiones.md) (§2: la puerta de escritura) → [operacion.md](operacion.md) §1.1 y §4 → el `README.md` y el `suite.yml` de la suite → `../tests/` |
| **quien prepara una campaña sobre la biblioteca** | [decisiones.md](decisiones.md) §4.8 y §2.9 (`../lib/adjuntos_zotero.py`) → [historial/campanas-sobre-la-biblioteca.md](historial/campanas-sobre-la-biblioteca.md) → `meta/docs/historial/diagnosticos/` |
| **quien adquiere o ficha** una fuente para un proyecto | [`../README.md`](../README.md) §Uso → `prompts/00 metodo/METODO_DOCUMENTAL.md` → el README de la suite del paso |
| **quien ingiere** lo que entró | [`../ingesta/README.md`](../ingesta/README.md) (§Cursos para el material de `10 Class`) → [`../catalogacion/README.md`](../catalogacion/README.md) |
| **quien amplía** (una fuente, una raíz, una sigla, una suite) | [arquitectura.md](arquitectura.md) → [ampliar.md](ampliar.md) |
| **otro repositorio** (`prompts`, `meta`, `02 analysis`, `03 writing`) | [consumidores.md](consumidores.md) (lo que se usa de aquí) → [arquitectura.md](arquitectura.md) §6 y [`../manifiesto/README.md`](../manifiesto/README.md) → `meta/docs/historial/MODELO_METADATOS.md` y `meta/docs/historial/SINCRONIZACION.md` (la frontera) |

## Cómo se mantiene

- Lo nuevo se escribe en el documento de su concepto; nunca un `.md` por cambio, fecha o sesión.
- La decisión y su porqué van a [decisiones.md](decisiones.md) (`### §N.M`), sin renumerar; lo
  pendiente, a [`../estado.md`](../estado.md) §Por hacer, con fecha y dueño.
- Las cantidades que cambian (libros, fichas, pares enlazados) no se escriben: se nombra la orden
  que las cuenta.
- Una campaña nueva deja su crónica en el mensaje de commit ([decisiones.md](decisiones.md) §4.6 y
  §4.8); la bitácora de `historial/` está cerrada.
- La tabla de abajo la genera `python3 core/docs.py indice scripts_for_calibre --aplicar` (tras la fusión, `scripts-biblioteca`` (desde
  `~/Documents`); no se edita a mano.

## Índice

<!-- docs:inicio -->
| documento | tipo | estado | qué es |
|---|---|---|---|
| [ampliar.md](ampliar.md) | `procedimiento` | `activo` | Ampliar: una fuente, una raíz de entrada, un paquete de anexos, una sigla o una suite |
| [arquitectura.md](arquitectura.md) | `doc` | `activo` | Arquitectura: dos adquisiciones, el recorrido de un documento y las piezas que lo mueven |
| [consumidores.md](consumidores.md) | `doc` | `activo` | Consumidores de scripts_for_calibre: lo que otros repos usan de aquí y lo que no se cambia sin avisarles |
| [decisiones.md](decisiones.md) | `decision` | `activo` | Decisiones de scripts-biblioteca: autoridad de los datos, escritura segura, organización y Método Documental |
| [operacion.md](operacion.md) | `doc` | `activo` | Operación del ecosistema de lectura y estudio (Calibre ⇄ KOReader ⇄ Zotero): qué es automático, qué es manual, cómo se verifica |
| [historial/README.md](historial/README.md) | `readme` | `activo` | docs/historial/ — lo cumplido: el ecosistema de lectura, las campañas, las refactorizaciones y la procedencia de las carpetas |
| [historial/campanas-sobre-la-biblioteca.md](historial/campanas-sobre-la-biblioteca.md) | `bitacora` | `hecho` | Campañas sobre la biblioteca: lo que se catalogó, normalizó y sincronizó en bloque, y con qué resultado |
| [historial/diseno-ecosistema-lectura-2026-08.md](historial/diseno-ecosistema-lectura-2026-08.md) | `plan` | `hecho` | Diseño del ecosistema de lectura sincronizado: Calibre ⇄ KOReader ⇄ Zotero |
| [historial/procedencia-de-las-carpetas.md](historial/procedencia-de-las-carpetas.md) | `bitacora` | `hecho` | Procedencia de las carpetas: de dónde vino cada suite del único lugar de fuentes |
| [historial/refactorizacion-modular.md](historial/refactorizacion-modular.md) | `bitacora` | `hecho` | Refactorización modular de metadatos_calibre y catalogacion_biblioteca: los defectos del código original y cómo se corrigieron |

<sub>Bloque generado por `core/docs.py indice` desde el frontmatter de docs/ (2026-10-05); no se edita a mano.</sub>
<!-- docs:fin -->
