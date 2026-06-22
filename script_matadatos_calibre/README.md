# calibre-metadata-manager

> Herramienta de línea de comandos que unifica dos operaciones esenciales
> para tu biblioteca Calibre: **incrustar metadatos** de los archivos `.opf`
> directamente en los PDFs (vía `exiftool`) y **registrar PDFs** como
> formatos adicionales en los registros de Calibre (vía `calibredb`).

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [Arquitectura](#-arquitectura)
- [Bugs Corregidos](#-bugs-corregidos)
- [Solución de Problemas](#-solución-de-problemas)
- [Cómo Contribuir](#-cómo-contribuir)
- [Notas y Advertencias](#-notas-y-advertencias)

---

## 📖 Descripción

Este proyecto reemplaza y unifica dos scripts independientes en un sistema
modular con un único punto de entrada (`main.sh`). Las dos operaciones
disponibles son:

| Operación  | Qué hace                                                                                                                               |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `embed`    | Lee `metadata.opf` de Calibre e incrusta sus campos en los PDFs del mismo directorio usando `exiftool`                                 |
| `register` | Añade los PDFs físicamente presentes en las carpetas de libro como formato adicional en la base de datos de Calibre usando `calibredb` |
| `all`      | Ejecuta `embed` → `register` en secuencia                                                                                              |

Características adicionales respecto a los scripts originales:

- Modo **`--dry-run`**: previsualiza todos los cambios sin modificar nada.
- Modo **`--force`**: sobreescribe formatos PDF ya existentes en Calibre.
- **Menú interactivo** cuando no se pasan argumentos.
- **Log persistente** en `/tmp/calibre-metadata-manager_YYYYMMDD_HHMMSS.log`.
- **6 bugs corregidos** del código original (ver sección [Bugs Corregidos](#-bugs-corregidos)).

---

## ⚙️ Requisitos

### Sistema operativo

- Linux (probado en Ubuntu 22.04+, Arch/Archcraft, Kubuntu)
- Compatible con macOS con ajustes menores en `sed` (GNU vs BSD)

### Dependencias

| Herramienta            | Versión mínima | Para qué                                   |
| ---------------------- | -------------- | ------------------------------------------ |
| `bash`                 | 4.0+           | Soporte de arrays asociativos y `mapfile`  |
| `exiftool`             | cualquiera     | Incrustar metadatos en PDFs (`embed`)      |
| `calibredb`            | 5.0+           | Registrar formatos en Calibre (`register`) |
| `find`                 | GNU coreutils  | Búsqueda recursiva de archivos             |
| `grep`, `sed`, `xargs` | GNU            | Extracción de campos del OPF               |

---

## 🚀 Instalación

### Paso 1: Clonar o copiar el proyecto

```bash
git clone https://github.com/achalmed/scripts_for_calibre.git
cd scripts_for_calibre/script_matadatos_calibre
```

O copiar directamente a tu ruta definitiva:

```bash
mkdir -p ~/Documents/scripts_for_calibre/script_matadatos_calibre
cp -r . ~/Documents/scripts_for_calibre/script_matadatos_calibre/
cd ~/Documents/scripts_for_calibre/script_matadatos_calibre
```

### Paso 2: Dar permisos de ejecución

```bash
chmod +x main.sh config.sh lib/*.sh
```

### Paso 3: Instalar dependencias

**Ubuntu / Kubuntu / Debian:**

```bash
sudo apt-get update
sudo apt-get install libimage-exiftool-perl calibre
```

**Arch Linux / Archcraft / Manjaro:**

```bash
sudo pacman -S perl-image-exiftool calibre
```

### Paso 4 (opcional): Crear un alias global

```bash
# En ~/.zshrc o ~/.config/fish/config.fish
alias calibre-meta='~/Documents/scripts_for_calibre/script_matadatos_calibre/main.sh'
```

---

## 💻 Uso

### Sintaxis

```bash
./main.sh COMANDO [OPCIONES]
./main.sh             # Sin argumentos → menú interactivo
```

### Comandos

| Comando    | Descripción                                   |
| ---------- | --------------------------------------------- |
| `embed`    | Incrustar metadatos OPF en PDFs               |
| `register` | Registrar PDFs en la base de datos de Calibre |
| `all`      | Ejecutar ambas operaciones en secuencia       |

### Opciones

| Flag                 | Descripción                                                      | Requerido |
| -------------------- | ---------------------------------------------------------------- | --------- |
| `-r, --root PATH`    | Directorio raíz donde buscar `metadata.opf` o carpetas de autor  | No        |
| `-l, --library PATH` | Ruta raíz de la biblioteca Calibre (debe contener `metadata.db`) | No        |
| `-v, --verbose`      | Mostrar mensajes de nivel DEBUG                                  | No        |
| `-n, --dry-run`      | Simular toda la operación sin modificar ningún archivo           | No        |
| `-f, --force`        | Sobreescribir formatos PDF existentes en Calibre                 | No        |
| `--version`          | Mostrar versión del script                                       | No        |
| `-h, --help`         | Mostrar ayuda completa                                           | No        |

### Ejemplos de uso

```bash
# Menú interactivo (recomendado la primera vez)
./main.sh

# Incrustar metadatos en todos los PDFs bajo ~/Calibre
./main.sh embed --root ~/Calibre

# Registrar PDFs de la carpeta del autor actual en Calibre
./main.sh register --library ~/Calibre

# Pipeline completo en modo simulación primero
./main.sh all --root ~/Calibre --library ~/Calibre --dry-run

# Pipeline completo real con salida detallada
./main.sh all --root ~/Calibre --library ~/Calibre --verbose

# Sobreescribir formatos ya registrados
./main.sh register --library ~/Calibre --force

# Ver la versión
./main.sh --version
```

### Flujo de trabajo recomendado

```bash
# 1. Cerrar Calibre (obligatorio para 'register')

# 2. Previsualizar con dry-run
./main.sh all --root ~/Calibre --library ~/Calibre --dry-run

# 3. Revisar el log generado
cat /tmp/calibre-metadata-manager_*.log

# 4. Ejecutar para real
./main.sh all --root ~/Calibre --library ~/Calibre --verbose

# 5. Abrir Calibre y verificar
```

---

## 🗂️ Arquitectura

```
script_matadatos_calibre/
├── main.sh                  # Punto de entrada único: orquesta todo el sistema
├── config.sh                # Constantes globales, códigos de salida y configuración
├── README.md                # Esta documentación
└── lib/
    ├── logger.sh            # Sistema de logging centralizado (INFO/WARN/ERROR/DEBUG)
    ├── validator.sh         # Validación de dependencias, rutas y permisos
    ├── cli.sh               # Parsing de argumentos y menú interactivo
    ├── embed_metadata.sh    # Lógica de incrustar OPF → PDF (operación 'embed')
    └── register_formats.sh  # Lógica de registrar PDFs en Calibre (operación 'register')
```

### Descripción de módulos

| Archivo                   | Responsabilidad única                                                 |
| ------------------------- | --------------------------------------------------------------------- |
| `main.sh`                 | Punto de entrada: carga módulos, inicializa log, despacha la acción   |
| `config.sh`               | Define constantes, códigos de salida y valores por defecto            |
| `lib/logger.sh`           | `log_info`, `log_warn`, `log_error`, `log_debug` con archivo de log   |
| `lib/validator.sh`        | Valida dependencias, rutas, permisos y biblioteca Calibre             |
| `lib/cli.sh`              | `parse_arguments()` y `show_interactive_menu()`                       |
| `lib/embed_metadata.sh`   | Extracción de OPF + construcción del comando exiftool + bucle de PDFs |
| `lib/register_formats.sh` | Extracción de IDs Calibre + llamadas a `calibredb add_format`         |

### Flujo de ejecución

```
main.sh
  │
  ├─ log_init()              ← lib/logger.sh
  ├─ parse_arguments() / show_interactive_menu()   ← lib/cli.sh
  │
  ├─[embed] run_embed_metadata()    ← lib/embed_metadata.sh
  │           └─ validate_dependencies(exiftool)
  │           └─ find metadata.opf recursivamente
  │           └─ extract_opf_field() × 6
  │           └─ embed_metadata_into_pdf() × N PDFs
  │
  └─[register] run_register_formats()  ← lib/register_formats.sh
                └─ validate_dependencies(calibredb)
                └─ validate_calibre_library()
                └─ process_author_folder()
                    └─ extract_calibre_book_id()
                    └─ add_pdf_format()
                    └─ book_already_has_pdf()  ← solo en caso de error
```

---

## 🐛 Bugs Corregidos

Los siguientes bugs fueron identificados en los scripts originales y corregidos
en esta versión refactorizada.

### Bug #1: `set -e` omitido silenciaba errores críticos

- **Script original**: `incrustar_metadatos_a_pdf_desde_opf.sh`
- **Problema**: El comentario justificaba omitir `-e` para "no detener ante errores menores", pero esto permitía que fallos de `exiftool` incrementaran `OK` en lugar de `ERROR`.
- **Impacto**: Reportaba éxitos falsos en el resumen final.
- **Corrección**: Se usa `set -uo pipefail` globalmente y cada operación captura explícitamente su código de retorno mediante variables de contador dedicadas.

### Bug #2: Proceso continuaba con metadatos vacíos

- **Script original**: `incrustar_metadatos_a_pdf_desde_opf.sh`, ~línea 175
- **Problema**: Al detectar metadatos incompletos, el script registraba la advertencia pero seguía procesando los PDFs del directorio con campos vacíos.
- **Impacto**: Sobreescribía metadatos existentes en los PDFs con cadenas vacías.
- **Corrección**: `process_book_folder()` retorna inmediatamente después de registrar el directorio como inválido.

### Bug #3: Extracción de autor fallaba con caracteres especiales

- **Script original**: función `extraer_campo`, caso `author`
- **Problema**: El `sed` usaba `"` como delimitador para extraer `opf:file-as`, lo que fallaba con comillas embebidas en nombres de autores.
- **Impacto**: El campo autor quedaba vacío o truncado para nombres con comillas.
- **Corrección**: `extract_opf_field()` usa el patrón `\([^"]*\)` con `sed -n ... p` para capturar hasta la siguiente comilla sin depender de delimitadores externos.

### Bug #4: Log file creado sin verificación

- **Script original**: línea ~48 de `incrustar_metadatos_a_pdf_desde_opf.sh`
- **Problema**: `LOG_FILE="/tmp/..."` asignaba la ruta sin verificar si era escribible. Las escrituras subsecuentes usaban `2>/dev/null` sin justificación, silenciando el fallo.
- **Impacto**: Se perdía todo el log de auditoría sin notificación.
- **Corrección**: `log_init()` intenta crear el archivo con `touch`, y si falla, hace `unset LOG_FILE` y notifica al usuario con `log_warn`. El `2>/dev/null` en `_log_write` está documentado explícitamente.

### Bug #5: `register` asumía directorio de trabajo sin validación

- **Script original**: `anadir_pdfs_a_opf.sh`, línea 10
- **Problema**: `LIBRARY_PATH="$(cd .. && pwd)"` ejecutaba `cd ..` sin comprobar si el directorio resultante era una biblioteca Calibre válida.
- **Impacto**: `calibredb` apuntaba a una ruta inválida, causando errores crípticos o potencial corrupción silenciosa.
- **Corrección**: `validate_calibre_library()` comprueba la existencia del archivo `metadata.db` en `LIBRARY_PATH` antes de cualquier operación.

### Bug #6: Errores reales enmascarados como "ya tenía PDF"

- **Script original**: `anadir_pdfs_a_opf.sh`, bloque `elif`, ~línea 42
- **Problema**: Si `calibredb add_format` fallaba por cualquier causa (permisos, ID inválido, etc.), el script consultaba si el libro "ya tenía PDF" y, si era así, lo contaba como `already` en lugar de `realerror`.
- **Impacto**: Errores genuinos quedaban ocultos en el conteo de `already`, subreportando fallos.
- **Corrección**: `add_pdf_format()` captura el exit code de `calibredb` por separado. Solo se llama a `book_already_has_pdf()` cuando `calibredb` falla (exit ≠ 0), y únicamente para distinguir "formato duplicado" de un error real.

---

## 🔧 Solución de Problemas

### Error: `exiftool: command not found`

```bash
# Ubuntu/Debian/Kubuntu:
sudo apt-get install libimage-exiftool-perl

# Arch/Archcraft/Manjaro:
sudo pacman -S perl-image-exiftool
```

### Error: `calibredb: command not found`

```bash
sudo apt-get install calibre
# o descarga desde https://calibre-ebook.com/download
```

### Error: `'...' does not contain 'metadata.db'`

Estás apuntando a una carpeta de autor en lugar de a la raíz de la biblioteca.
La raíz es el directorio que contiene directamente las carpetas de autores y el
archivo `metadata.db`.

```bash
# Incorrecto:
./main.sh register --library ~/Calibre/Achalma\ Edison

# Correcto:
./main.sh register --library ~/Calibre
```

### Error: `PDF is not writable`

```bash
chmod u+w /ruta/al/archivo.pdf
# O para toda la biblioteca:
find ~/Calibre -name "*.pdf" -exec chmod u+w {} \;
```

### Error: Calibre bloquea la base de datos

```bash
# Cerrar Calibre completamente antes de ejecutar 'register'
# Verificar que no hay procesos de Calibre en ejecución:
pgrep -l calibre
```

### Los metadatos no se ven en Calibre después de `embed`

`embed` modifica los metadatos internos del archivo PDF (visibles en lectores
de PDF y `exiftool -a archivo.pdf`), pero **no actualiza la base de datos de
Calibre**. Para actualizar los campos en Calibre, usa la función de Calibre
"Actualizar metadatos desde libro" después de incrustar.

---

## 🤝 Cómo Contribuir / Agregar Nuevas Funcionalidades

### Para añadir un nuevo módulo de operación:

1. Crea `lib/mi_operacion.sh` siguiendo el patrón de `embed_metadata.sh`:
   - Una función pública `run_mi_operacion()` como punto de entrada
   - Funciones auxiliares privadas con `_prefijo()`
   - Guard de doble-source al inicio

2. Añade `source "${SCRIPT_DIR}/lib/mi_operacion.sh"` en `main.sh`

3. Añade el nuevo comando en el `case` de `main()`:

   ```bash
   mi_operacion) run_mi_operacion || overall_status=$? ;;
   ```

4. Añade la opción en `show_interactive_menu()` y `show_help()` en `lib/cli.sh`

5. Actualiza este README

### Estándares de código aplicados en este proyecto

- Máximo ~25 líneas por función
- Nombres en inglés técnico: verbo + sustantivo (`extract_opf_field`, `validate_calibre_library`)
- Comentarios explican el **por qué**, no el **qué**
- Todo `2>/dev/null` tiene un comentario justificando la supresión
- Guards de doble-source en todos los módulos (`_MODULO_SH_LOADED`)
- Exit codes estandarizados definidos en `config.sh`

---

## ⚠️ Notas y Advertencias

### Sobre la operación `embed`

- Calibre **ya incrusta metadatos automáticamente** cuando envías un libro a un
  dispositivo. Si usas esa función de Calibre, el script `embed` es redundante
  para esos archivos. Úsalo solo para PDFs que Calibre nunca ha "enviado".

- La extracción de campos OPF usa `grep + sed` (sin `xmllint`) para evitar
  dependencias adicionales. Funciona correctamente para el formato OPF estándar
  que genera Calibre. OPFs con elementos multilinea o namespaces personalizados
  pueden no parsearse correctamente.

### Sobre la operación `register`

- **Calibre debe estar cerrado** durante la operación `register`. Si está
  abierto, `calibredb` puede fallar o, en casos raros, corromper la base de datos.

- El script detecta automáticamente si el directorio actual es una carpeta de
  autor (hijos con `(ID)` en el nombre) o una raíz de biblioteca. Esta heurística
  cubre el 99% de los casos de Calibre estándar.

### Sobre `--dry-run`

- Se recomienda **siempre** ejecutar con `--dry-run` antes de una operación
  masiva sobre una biblioteca grande. El log del dry-run muestra exactamente
  qué comandos se ejecutarían.

### Compatibilidad

- Requiere Bash 4.0+ por el uso de arrays asociativos (`declare -A`) y
  `mapfile`. La versión de Bash incluida en macOS (3.2) **no es compatible**.
  En macOS instala Bash 5 vía Homebrew: `brew install bash`.
