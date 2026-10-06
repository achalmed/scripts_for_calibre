---
tipo: readme
estado: activo
---
# docs/historial/ — lo cumplido: el ecosistema de lectura, las campañas, las refactorizaciones y la procedencia de las carpetas

Se lee para saber por qué algo es como es, no para saber cómo se usa (NORMATIVA §15.6). Nada de aquí
es normativo; lo vigente está en `../operacion.md`, `../arquitectura.md`, `../decisiones.md`, el README de cada
suite y `../../CLAUDE.md`.

| documento | qué es |
|---|---|
| `diseno-ecosistema-lectura-2026-08.md` | hallazgos de la inspección de las tres instalaciones (2026-08-09), la opción elegida (motor local de scripts + timers) y las fases 1–4, todas cumplidas |
| `campanas-sobre-la-biblioteca.md` | las operaciones en bloque sobre la biblioteca: libros sin autor, normalización, primera sincronización, autores, títulos y duplicados |
| `refactorizacion-modular.md` | los defectos del código original de `metadatos_calibre` y `catalogacion_biblioteca` y cómo se corrigieron |
| `procedencia-de-las-carpetas.md` | de dónde vino cada carpeta del Método Documental cuando `scripts_for_fuentes` se volvió el único lugar de fuentes (2026-09); lo vigente, `../../README.md` §Estructura |

Otras bitácoras: la del marco legal (dónde fue a parar su código y por qué el dato se quedó) está en
[`../decisiones.md`](../decisiones.md) §5.4 y en `git log -- manifiestos/marco_legal/README.md`; la de los `.ris`
retirados, en `ingesta/salida_ris/obsoletos_2026-09-30/por-que-obsoletos.md` (fuera de git).
