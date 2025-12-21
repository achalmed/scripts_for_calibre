# Calibre PDF Tools

![Calibre](https://img.shields.io/badge/Calibre-v7%2B-blue) ![bash](https://img.shields.io/badge/bash-script-green) ![exiftool](https://img.shields.io/badge/exiftool-required-orange) 

#readme

Scripts en Bash muy útiles para quienes usan **Calibre** con PDFs externos y quieren mantener todo perfectamente organizado y con metadatos incrustados.

## Scripts incluidos

| Script | Nombre del archivo | ¿Qué hace? | Cuándo usarlo |
|--------|---------------------|------------|---------------|
| 1 | `add-pdf-to-calibre.sh` | Añade automáticamente todos los PDFs que estén físicamente en las carpetas de los libros como formato adicional en Calibre (sin duplicarlos) | Después de descargar PDFs complementarios (ODT → PDF, versiones impresas, etc.) y colocarlos en las carpetas de los libros |
| 2 | `incrustar-metadatos-calibre.sh` | Lee el `metadata.opf` de cada libro y usa **exiftool** para incrustar título, autor, editorial, etiquetas, idioma, etc. en los PDFs | Antes de enviar los PDFs a un lector, tablet, teléfono o nube (así los metadatos se ven fuera de Calibre) |

## Requisitos

- Calibre instalado y con `calibredb` en el PATH
- **exiftool** (solo para el segundo script)  
  ```bash
  sudo apt install libimage-exiftool-perl    # Debian/Ubuntu
  brew install exiftool                      # macOS
  ```
- Los scripts están pensados para ejecutarse **sin sudo**

## Uso rápido

### 1. add-pdf-to-calibre.sh → Añadir PDFs como formato adicional

1. Entra con tu terminal dentro de la carpeta de un autor de tu biblioteca Calibre  
   (ejemplo: `/home/yo/Calibre/Author Name/`)
2. Ejecuta el script (estando dentro de la carpeta del autor):

```bash
~/scripts/add-pdf-to-calibre.sh
# o ./add-pdf-to-calibre.sh si está en la misma carpeta
```

El script:
- Detecta automáticamente la raíz de la biblioteca (sube un nivel)
- Recorre todos los libros del autor
- Añade cada PDF encontrado como formato adicional (con `--dont-replace`)
- Te da un resumen final muy claro

> Ideal para cuando conviertes ODT → PDF o descargas versiones “bonitas” y las dejas en la carpeta del libro.

### 2. incrustar-metadatos-calibre.sh → Incrustar metadatos en PDFs

Puedes ejecutarlo en toda tu biblioteca o en una subcarpeta:

```bash
# Toda la biblioteca
~/scripts/incrustar-metadatos-calibre.sh "/ruta/a/tu/biblioteca/Calibre"

# Solo un autor o colección
~/scripts/incrustar-metadatos-calibre.sh "/ruta/a/tu/biblioteca/Calibre/Autor Favorito"
```

El script:
- Busca recursivamente todos los `metadata.opf`
- Extrae título, autor, etiquetas, editorial, idioma, fecha…
- Usa **exiftool** para escribirlos directamente en los PDFs (sin crear copias)
- Genera un log detallado en `/tmp/` y un reporte final muy completo

> Perfecto antes de copiar PDFs al móvil, Kindle (sin jailbreak), tablet, etc.

## Ejemplo de flujo de trabajo recomendado

```bash
# 1. Descargas/conviertes PDFs y los dejas en las carpetas de los libros
# 2. Añades los PDFs a Calibre (para que aparezcan como formato disponible)
cd "/mi/biblioteca/Calibre/George Orwell"
~/scripts/add-pdf-to-calibre.sh

# 3. (Opcional pero muy recomendado) Incrustas los metadatos en los PDFs
~/scripts/incrustar-metadatos-calibre.sh "/mi/biblioteca/Calibre"
```

¡Listo! Tus PDFs aparecen en Calibre y además llevan todos los metadatos incrustados.

## Licencia

MIT License – puedes usar, modificar y distribuir libremente.

## Autor

Creado con ❤️ por la comunidad hispanohablante de Calibre  
Segundo script originalmente por Edison Achalma (2024-2025)

---

¡Star ★ el repo si te ha sido útil!
 