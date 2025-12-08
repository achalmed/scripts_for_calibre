#!/bin/bash

# =============================================
# CERRA CALIBRE
# EJECUTAR SIN SUDO
# EJECUTAR DENTRO DE LA CARPETA DEL AUTOR
# Añade PDFs como formato adicional en Calibre
# (los PDFs ya están físicamente en la carpeta del libro)
# =============================================

# 1. Detecta automáticamente la raíz de la biblioteca Calibre
#    (estás dentro de la carpeta del autor → subimos un nivel)
LIBRARY_PATH="$(cd .. && pwd)"
echo "Biblioteca: $LIBRARY_PATH"
echo "Autor: $(basename "$PWD")"
echo "========================================"

# Contadores para el resumen final
added=0        # PDFs que se añadieron por primera vez ahora
already=0      # El libro ya tenía algún PDF (no hace falta volver a añadir)
nopdf=0        # Carpetas que no tenían ningún PDF
realerror=0    # Errores de verdad (muy raro que pase)

# 2. Recorre todas las carpetas de libros del autor actual
for carpeta in */; do
    [[ "$carpeta" == "*" ]] && break                # no hay carpetas → salir
    carpeta="${carpeta%/}"                           # quita la barra final

    # 3. Extrae el ID de Calibre del nombre de la carpeta (ej: "Libro (1234)")
    if [[ $carpeta =~ \(([0-9]+)\)$ ]]; then
        ID="${BASH_REMATCH[1]}"
    else
        continue                                     # carpeta sin ID → ignorar
    fi

    # 4. Busca todos los PDFs que haya dentro de esa carpeta del libro
    mapfile -t pdfs < <(find "$carpeta" -type f -iname "*.pdf" 2>/dev/null)

    # Si no hay PDFs en esa carpeta → contar y pasar al siguiente libro
    if [[ ${#pdfs[@]} -eq 0 ]]; then
        ((nopdf++))
        continue
    fi

    # 5. Procesa cada PDF encontrado
    for pdf in "${pdfs[@]}"; do
        nombre=$(basename "$pdf")
        printf "ID %-5s → %-55s " "$ID" "$nombre"

        # 6. Añade el PDF como formato adicional al libro con ese ID
        if calibredb add_format --library-path "$LIBRARY_PATH" "$ID" "$pdf" --dont-replace >/dev/null 2>&1; then
            echo "AÑADIDO"
            ((added++))
        # 7. Si ya existía algún PDF en ese libro → no hacemos nada
        elif calibredb show_metadata --library-path "$LIBRARY_PATH" "$ID" 2>/dev/null | grep -iq pdf; then
            echo "ya tenía PDF"
            ((already++))
        # 8. Solo aquí es un error de verdad (casi nunca pasa)
        else
            echo "ERROR REAL"
            ((realerror++))
        fi
    done
done

# =============================================
# RESUMEN FINAL
# =============================================
echo "========================================"
echo "Añadidos         : $added"
echo "Ya tenían PDF    : $already"
echo "Sin PDF          : $nopdf"
echo "Errores reales   : $realerror"
echo "¡Terminado! Abre Calibre y disfruta tus ODP + PDF"
echo "========================================"
