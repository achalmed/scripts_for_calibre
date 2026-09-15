# Catalogación de libros sin autor — biblioteca Calibre

<!-- suite:inicio -->
**Suite `catalogacion_biblioteca`** · objetivo *fuentes* · estado *activo* · bash · interfaz cli

Aplica a Calibre los metadatos catalogados en resumen_catalogacion.tsv (autor «Nombre, Apellidos», vocabulario cerrado, serie, identificadores); registro canónico de lo catalogado.

- Escribe en: calibre · simula por defecto: sí
- Entrada: resumen_catalogacion.tsv (lo alimentan ingesta e ingesta_cursos)
- Depende de: calibredb, core/shell-lib
- Método Documental: paso 02

Comandos:

```bash
main.sh                      # simula sobre resumen_catalogacion.tsv
main.sh --aplicar            # escribe (Calibre cerrado, lock)
main.sh --aplicar --ids 10265,10266
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-09-15); no se edita a mano.</sub>
<!-- suite:fin -->

> Fichas de catalogación (dual Zotero + Calibre) para los 113 libros sin autor
> de `~/Documents/biblioteca`, y herramienta modular `main.sh` que aplica esos
> metadatos a Calibre vía `calibredb` (simulación por defecto).
>
> **Hogar canónico de la salida del prompt 1.** El formato de cada ficha lo define
> `~/Documents/prompts/01 fuentes/prompt_02_catalogar.md` (antes `prompt_para_zotero_1`)
> (repo `prompts`); esta suite es donde esa salida **se guarda**
> (`fichas/`), **se registra** (`resumen_catalogacion.tsv`, fuente de verdad) y
> **se aplica** a Calibre. La campaña de los 113 sin autor está cerrada, pero la
> herramienta es **reutilizable para cualquier libro nuevo** (ver
> [«Reutilización para libros nuevos»](#-reutilización-para-libros-nuevos-flujo-prompt--ficha--tsv--calibre)).
> Mapa del ecosistema y contrato de complementariedad prompt ⇄ scripts:
> `~/Documents/prompts/ECOSISTEMA_APRENDIZAJE.md`.

#catalogacion #calibre #zotero

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Estado](#-estado-2026-07-27)
- [Requisitos](#%EF%B8%8F-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Arquitectura](#%EF%B8%8F-arquitectura)
- [Bugs Corregidos](#-bugs-corregidos)
- [Solución de Problemas](#-solución-de-problemas)
- [Cómo Contribuir](#-cómo-contribuir--agregar-nuevas-funcionalidades)
- [Notas y Advertencias](#%EF%B8%8F-notas-y-advertencias)

## 📖 Descripción

La biblioteca Calibre tenía 113 libros sin autor identificado (90 bajo
`Unknown`, 22 bajo `Desconocido`, 1 bajo `Varios autores`). Cada uno fue
catalogado leyendo la portada/página legal de su PDF, siguiendo el prompt
oficial `~/Documents/prompts/01 fuentes/prompt_02_catalogar.md`.

Componentes:

| Elemento | Descripción |
|---|---|
| `fichas/` | Una ficha Markdown por libro (`<id_calibre>_<slug>.md`) con el frontmatter único (`tipo: ficha_catalogacion`, `calibre_id`, `zotero_key`; norma `prompts/00 metodo/fichas_formato_y_voz.md`) y secciones Origen · Zotero · Calibre · Notas. Migradas al formato único el 2026-09-07 (FD3); las nuevas las escribe `scripts_for_fuentes/ingesta` |
| `resumen_catalogacion.tsv` | Tabla resumen (una fila por libro) — **fuente de verdad** para `main.sh` |
| `main.sh` + `config.sh` + `lib/` | Herramienta que aplica el TSV a Calibre con `calibredb set_metadata` |

### 🔁 Reutilización para libros nuevos (flujo prompt → ficha → TSV → Calibre)

La campaña de los 113 está cerrada, pero el circuito sirve para **cualquier alta
nueva**. Por cada libro nuevo ya importado en Calibre (con su `id`):

1. **Cataloga** leyendo su portada/página legal con el prompt 1; genera la ficha
   dual (tablas Zotero + Calibre, tags oficiales, nombre de archivo).
2. **Guarda** la ficha en `fichas/<id_calibre>_<slug>.md` (este formato exacto).
3. **Registra** una fila en `resumen_catalogacion.tsv` (columnas: `id · autores ·
   titulo · tipo_zotero · clasificador · editorial · fecha · identificador ·
   idioma · tags · confianza · nota`). El TSV cubre solo ese subconjunto; los
   campos ricos (`#edition`, `#pages`, `#genres`, `#sub_tipo`) se ponen a mano y
   quedan intactos (un campo vacío del TSV nunca borra metadatos existentes).
4. **Simula** `./main.sh`, luego **aplica** `./main.sh --aplicar` con **Calibre
   cerrado** (empieza por `--solo-alta` si hay filas de confianza media/baja).
5. **Zotero**: ingresa la parte Zotero de la ficha (manual o ZMI). Opcional:
   incrusta en el PDF con `../script_metadatos_calibre/`.

Primer uso tras la campaña: **2026-08-30**, ids **9910–9913** (Blanchard,
*Macroeconomía* 7.ª ed.; Brancaccio & Bibi, *Anti-Blanchard*; Mendoza & Herrera,
*Macroeconomía* PUCP; Guardia, *César Guardia Mayorga*) — fichas y filas ya
presentes en `fichas/` y en el TSV.

## 📌 Estado (2026-07-27)

**APLICADO.** 113/113 fichas generadas y escritas en Calibre con
`./main.sh --aplicar` (0 errores). El enum `Clasificador` se amplió de 68 a 76
valores (`Libro`, `Informe`, `Informe técnico`, `Documento oficial`,
`Normativa`, `Guía de estudio`, `Recurso educativo`, `Artículo de revista`).
El autor `Desconocido` desapareció (22 libros con autor real); quedan 75 bajo
`Unknown`, genuinamente anónimos (apuntes, diapositivas), ya con título, tipo,
clasificador y tags correctos. Confianza: 22 alta, 52 media, 39 baja; 38 con
autor identificado.

Pendiente manual: ingreso en Zotero (fichas), OCR de ids 440/445, renombrar
formato corrupto del id 9887 (`.unenfoquegerencial` → `.pdf`).

Notas posteriores (2026-07-27):
- ids 8877/9590 **no** son duplicados: mismo tema (números índice), documentos
  distintos — confirmado por el usuario.
- ids 9904/9905 (subidas z-library con autores/títulos sucios) corregidos:
  Rothbard, *Hombre, economía y Estado & Poder y mercado* (Mises Institute) y
  Mises, *Marxismo desenmascarado*.
- Identificación por búsqueda web de los 75 `Unknown`: **hecha**. 14 atribuidos
  con evidencia verificable (URL citada en cada ficha, sección "ACTUALIZACIÓN")
  y aplicados a Calibre; 1 descartado (id 447: la única evidencia era Studocu,
  que no acredita autoría); **61 quedan anónimos**, como se acordó. Los ítems
  identificados llevan la fuente en la columna `nota` del TSV.

## ⚙️ Requisitos

### Sistema Operativo

- Linux (probado en Calibre 9.x; Bash ≥ 5)

### Dependencias

- `calibredb` (Calibre) — escritura de metadatos. **Obligatoria**
- `sqlite3` + `python3` — lectura en vivo del enum `Clasificador`. Opcionales
  (sin ellas se usa la lista fija de respaldo en `config.sh`)

## 🚀 Instalación

```bash
cd ~/Documents/scripts_for_calibre/script_catalogacion_biblioteca
chmod +x main.sh
```

No hay más pasos: la configuración (ruta de la biblioteca, nombre del TSV,
enum de respaldo) vive en `config.sh`.

## 💻 Uso

### Sintaxis

```bash
./main.sh [OPCIONES]
```

### Opciones disponibles

| Flag | Descripción | Requerido |
|---|---|---|
| `--aplicar` | Ejecuta los cambios (requiere Calibre cerrado) | No |
| `--dry-run` | Fuerza simulación (modo por defecto) | No |
| `--solo-alta` | Procesa solo filas con `confianza=alta` | No |
| `--ids 10011,10012` | Procesa solo esas filas del TSV (libros recién ingresados; FD2) | No |
| `-v`, `--verbose` | Trazas por fila (DEBUG) | No |
| `-h`, `--help` | Ayuda | No |
| `--version` | Versión | No |

### Ejemplos de uso

```bash
# Simular todo (no modifica nada)
./main.sh

# Empezar por las 22 fichas seguras, aplicando de verdad
./main.sh --aplicar --solo-alta

# Aplicar todo con trazas
./main.sh --aplicar --verbose
```

### Flujo recomendado

1. Revisar fichas (empezar por confianza `baja` en el TSV).
2. Corregir `resumen_catalogacion.tsv` si algo no convence.
3. Simular: `./main.sh`.
4. **Cerrar Calibre** y aplicar: `./main.sh --aplicar`.
5. Ingresar la parte Zotero de cada ficha manualmente (o vía plugin ZMI).
6. Opcional: incrustar los metadatos en los PDFs con
   `../script_metadatos_calibre/`.

## 🗂️ Arquitectura

```
script_catalogacion_biblioteca/
├── main.sh                    # Punto de entrada — solo orquestación
├── config.sh                  # Configuración: rutas, defaults, enum de respaldo
├── resumen_catalogacion.tsv   # Datos de entrada (una fila por libro)
├── fichas/                    # 113 fichas de catalogación (datos, no código)
└── lib/
    ├── logger.sh              # Logging INFO/WARN/ERROR/DEBUG (WARN/ERROR → stderr)
    ├── validator.sh           # Dependencias, TSV existente, Calibre cerrado
    ├── cli.sh                 # parse_arguments + show_help
    ├── clasificador.sh        # Enum #clasificador: carga en vivo, tildes, validación
    └── metadata.sh            # Dominio: filas TSV → comandos calibredb + resumen
```

| Archivo | Responsabilidad |
|---|---|
| `main.sh` | Orquestar: parsear args → validar → cargar enum → procesar → resumen |
| `config.sh` | Todo valor editable (ruta biblioteca, TSV, defaults, enum snapshot) |
| `lib/logger.sh` | Formato de log único; stdout limpio para pipelines |
| `lib/validator.sh` | Fallar temprano y con mensaje claro antes de tocar nada |
| `lib/cli.sh` | Flags, ayuda, conflictos (`--aplicar` + `--dry-run`) |
| `lib/clasificador.sh` | Que Calibre nunca reciba un valor de enum inválido |
| `lib/metadata.sh` | Construcción de `-f campo:valor`, ejecución/simulación, contadores |

## 🐛 Bugs Corregidos

### Bug #1: `IFS=$'\t'` colapsaba campos vacíos del TSV

- **Descripción**: el tab es "IFS whitespace" en Bash; `read` fusiona tabs
  consecutivos y desalinea las columnas en filas con campos vacíos.
- **Impacto**: metadatos asignados al campo equivocado (p. ej. idioma como
  clasificador).
- **Corrección**: `tr '\t' '\037'` + `IFS=$'\037'` (separador no-blanco que
  preserva vacíos). Nota: GNU `tr` no acepta `\x1f`, solo octal.

### Bug #2: idioma `Portuguese` sin mapear a código ISO

- **Descripción**: `idioma_a_codigo` solo cubría Spanish/English; la fila 1615
  (tesis PUC-Rio) pasaba `languages:Portuguese` literal.
- **Impacto**: idioma inconsistente (nombre en vez de código `por`).
- **Corrección**: mapeo `Portuguese → por` en `map_language_to_code`.

### Bug #3: dependencias sin validar

- **Descripción**: el script original no comprobaba `calibredb`, `sqlite3` ni
  `python3` antes de ejecutar.
- **Impacto**: fallo a mitad de proceso con mensaje críptico.
- **Corrección**: `lib/validator.sh` valida todo antes de cualquier lógica
  (código de salida 5 si falta `calibredb`; aviso + lista de respaldo si
  faltan las opcionales).

## 🔧 Solución de Problemas

### Error: "Calibre está abierto"

Cierra la interfaz gráfica de Calibre; `calibredb` no puede escribir con la
biblioteca abierta. Solo aplica a `--aplicar` (la simulación siempre funciona).

### "Clasificadores fuera del enum de Calibre"

El valor no existe en la columna `Clasificador`. Añádelo en
Preferencias → Añadir columnas propias → `Clasificador` y re-ejecuta: el enum
se relee en cada ejecución.

### Error: "Permission denied"

```bash
chmod +x main.sh
```

## 🤝 Cómo Contribuir / Agregar Nuevas Funcionalidades

1. Crea un módulo `lib/nuevo_modulo.sh` con funciones de responsabilidad única
   (≤ 30 líneas por función).
2. Inclúyelo (`source`) en `main.sh`.
3. Añade las flags necesarias en `lib/cli.sh` y sus defaults en `config.sh`.
4. Verifica con `bash -n` (y `shellcheck` si está disponible).
5. Actualiza este README.

## ⚠️ Notas y Advertencias

- **La simulación es el modo por defecto**: sin `--aplicar` nunca se escribe.
- El TSV es la fuente de verdad: si corriges una ficha, refleja el cambio en
  el TSV antes de aplicar.
- Los campos vacíos del TSV **no borran** metadatos existentes: simplemente se
  omiten del comando.
- El enum real de Calibre y la lista oficial de clasificadores del prompt
  están desincronizados (el enum usa tildes y le faltan 8 valores);
  `lib/clasificador.sh` normaliza tildes y omite (reportando) lo que el enum
  rechazaría.
- Filas con `confianza=baja` (39) conviene revisarlas a mano antes de aplicar;
  ids 440 y 445 son escaneos sin capa de texto (pasar OCR y recatalogar), el
  id 9887 tiene extensión corrupta (`.unenfoquegerencial` → `.pdf`) y los ids
  8877/9590 son posibles duplicados.
- `shellcheck` no estaba disponible en el entorno al verificar; se comprobó
  `bash -n`, `--help`, `--version`, dry-run completo (113 comandos, paridad
  100 % con la versión anterior salvo el Bug #2) y códigos de salida 2 en
  flags inválidas/conflictivas.
