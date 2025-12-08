#!/usr/bin/env bash
# ==============================================================================
# OJO, README: Cuando se envia archivos desde calibre a otro dispositivo 
# este ya incrusta metadatos en el pdf o epub, decice cual usar, scrip o calibre.
# Funciona recursivaente y aplica a pdf con archiv .opf generado por calibre
# Funciona usanso exiftool, instalar primero.
#
# incrustar-metadatos-calibre.sh
# 
# Descripción: Script para incrustar metadatos de Calibre (metadata.opf) 
#              en archivos PDF de manera recursiva
# Autor: Edison Achalma
# Fecha: $(date +%Y-%m-%d)
# ==============================================================================

# Configuración de bash (sin -e para no detener el script ante errores menores)
set -uo pipefail

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================

# Directorio raíz (usar el argumento o directorio actual)
ROOT="${1:-$(pwd)}"

# Contadores para estadísticas
OK=0                    # PDFs procesados correctamente
ERROR=0                 # PDFs con errores
SKIP=0                  # PDFs sin metadata.opf o sin metadatos válidos
TOTAL_OPF=0            # Total de metadata.opf encontrados

# Arrays para almacenar casos problemáticos
declare -a ERRORES_LISTA
declare -a METADATOS_INCOMPLETOS
declare -a PDFS_SIN_METADATA

# Archivo de log temporal
LOG_FILE="/tmp/calibre_metadata_$(date +%Y%m%d_%H%M%S).log"

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

# Función para limpiar y sanitizar texto XML
# Convierte entidades HTML y elimina espacios extras
sanitize_xml() {
    local texto="$1"
    echo "$texto" | sed -e 's/&lt;/</g' \
                        -e 's/&gt;/>/g' \
                        -e 's/&amp;/\&/g' \
                        -e 's/&quot;/"/g' \
                        -e 's/&apos;/'"'"'/g' \
                        -e 's/&#39;/'"'"'/g' | xargs || echo ""
}

# Función para extraer valor de un campo XML
# Parámetros: $1=nombre_campo, $2=archivo_opf
extraer_campo() {
    local campo="$1"
    local archivo="$2"
    local valor=""
    
    case "$campo" in
        "title")
            valor=$(grep -m1 '<dc:title>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:title>//;s/<\/dc:title>.*//' || echo "")
            ;;
        "author")
            # Intenta primero con opf:file-as, luego con el contenido directo
            valor=$(grep -m1 '<dc:creator' "$archivo" 2>/dev/null | \
                   sed -e 's/.*opf:file-as="//;s/".*//' || echo "")
            if [ -z "$valor" ]; then
                valor=$(grep -m1 '<dc:creator' "$archivo" 2>/dev/null | \
                       sed -e 's/.*<dc:creator[^>]*>//;s/<\/dc:creator>.*//' || echo "")
            fi
            ;;
        "tags")
            valor=$(grep '<dc:subject>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:subject>//;s/<\/dc:subject>.*//' | \
                   paste -sd ";" - || echo "")
            ;;
        "publisher")
            valor=$(grep -m1 '<dc:publisher>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:publisher>//;s/<\/dc:publisher>.*//' || echo "")
            ;;
        "language")
            valor=$(grep -m1 '<dc:language>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:language>//;s/<\/dc:language>.*//' || echo "")
            ;;
        "date")
            valor=$(grep -m1 '<dc:date>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:date>//;s/<\/dc:date>.*//' || echo "")
            ;;
        "description")
            valor=$(grep -m1 '<dc:description>' "$archivo" 2>/dev/null | \
                   sed -e 's/.*<dc:description>//;s/<\/dc:description>.*//' || echo "")
            ;;
    esac
    
    sanitize_xml "$valor"
}

# Función para validar que existen metadatos mínimos
validar_metadatos() {
    local title="$1"
    local author="$2"
    
    if [ -z "$title" ] && [ -z "$author" ]; then
        return 1
    fi
    return 0
}

# ==============================================================================
# VERIFICACIONES PREVIAS
# ==============================================================================

# Verificar que existe exiftool
if ! command -v exiftool &> /dev/null; then
    echo "❌ ERROR: exiftool no está instalado."
    echo "   Instálalo con: sudo apt-get install libimage-exiftool-perl"
    exit 1
fi

# Verificar que el directorio raíz existe
if [ ! -d "$ROOT" ]; then
    echo "❌ ERROR: El directorio '$ROOT' no existe."
    exit 1
fi

# ==============================================================================
# INICIO DEL PROCESAMIENTO
# ==============================================================================

echo "════════════════════════════════════════════════════════════════"
echo "  📚 INCRUSTADOR DE METADATOS CALIBRE → PDF"
echo "════════════════════════════════════════════════════════════════"
echo "  Directorio raíz: $ROOT"
echo "  Fecha/hora: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Log: $LOG_FILE"
echo "════════════════════════════════════════════════════════════════"
echo

# Iniciar log
{
    echo "Inicio del procesamiento: $(date)"
    echo "Directorio: $ROOT"
    echo "----------------------------------------"
} > "$LOG_FILE" || {
    echo "⚠️  No se pudo crear el archivo de log"
}

# Buscar todos los directorios que contienen metadata.opf
echo "🔍 Buscando archivos metadata.opf..."
mapfile -t OPF_DIRS < <(find "$ROOT" -type f -name "metadata.opf" -print0 2>/dev/null | xargs -0 -n1 dirname 2>/dev/null | sort -u)

TOTAL_OPF=${#OPF_DIRS[@]}

if [ $TOTAL_OPF -eq 0 ]; then
    echo "⚠️  No se encontraron archivos metadata.opf en '$ROOT'"
    exit 0
fi

echo "✓ Encontrados $TOTAL_OPF directorios con metadata.opf"
echo

# ==============================================================================
# PROCESAMIENTO DE CADA DIRECTORIO
# ==============================================================================

contador=0
for dir in "${OPF_DIRS[@]}"; do
    # Incrementar contador de forma segura
    contador=$((contador + 1))
    
    opf="$dir/metadata.opf"
    autor_carpeta=$(basename "$dir" 2>/dev/null || echo "desconocido")
    
    echo "📁 [$contador/$TOTAL_OPF] Procesando: $autor_carpeta"
    echo "   Ruta: $dir"
    
    # Verificar que el archivo metadata.opf existe y es legible
    if [ ! -f "$opf" ] || [ ! -r "$opf" ]; then
        echo "   ⚠️  No se puede leer metadata.opf, saltando..."
        SKIP=$((SKIP + 1))
        echo >> "$LOG_FILE" 2>/dev/null
        echo "ARCHIVO NO LEGIBLE: $opf" >> "$LOG_FILE" 2>/dev/null
        echo "----------------------------------------" >> "$LOG_FILE" 2>/dev/null
        echo
        continue
    fi
    
    # Extraer metadatos del archivo .opf
    title=$(extraer_campo "title" "$opf" || echo "")
    author=$(extraer_campo "author" "$opf" || echo "")
    tags=$(extraer_campo "tags" "$opf" || echo "")
    publisher=$(extraer_campo "publisher" "$opf" || echo "")
    language=$(extraer_campo "language" "$opf" || echo "")
    date=$(extraer_campo "date" "$opf" || echo "")
    
    # Validar que hay metadatos mínimos
    if ! validar_metadatos "$title" "$author"; then
        echo "   ⚠️  Metadatos incompletos (sin título ni autor)"
        METADATOS_INCOMPLETOS+=("$dir")
        SKIP=$((SKIP + 1))
        {
            echo "METADATOS INCOMPLETOS: $dir"
            echo "  Título: '$title'"
            echo "  Autor: '$author'"
            echo "----------------------------------------"
        } >> "$LOG_FILE" 2>/dev/null
    fi
    
    # Mostrar metadatos extraídos
    echo "   📄 Metadatos encontrados:"
    [ -n "$title" ] && echo "      • Título: $title"
    [ -n "$author" ] && echo "      • Autor: $author"
    [ -n "$publisher" ] && echo "      • Editorial: $publisher"
    [ -n "$tags" ] && echo "      • Etiquetas: $tags"
    [ -n "$language" ] && echo "      • Idioma: $language"
    [ -n "$date" ] && echo "      • Fecha: $date"
    
    # Buscar todos los PDFs en este directorio (solo nivel actual, no recursivo)
    mapfile -t pdfs < <(find "$dir" -maxdepth 1 -type f -iname "*.pdf" 2>/dev/null | sort)
    
    if [ ${#pdfs[@]} -eq 0 ]; then
        echo "   ℹ️  No se encontraron archivos PDF"
        PDFS_SIN_METADATA+=("$dir (sin PDFs)")
        SKIP=$((SKIP + 1))
        {
            echo "SIN PDFs: $dir"
            echo "----------------------------------------"
        } >> "$LOG_FILE" 2>/dev/null
        echo
        continue
    fi
    
    echo "   📑 Procesando ${#pdfs[@]} PDF(s)..."
    
    # Procesar cada PDF
    for pdf in "${pdfs[@]}"; do
        nombre_pdf=$(basename "$pdf" 2>/dev/null || echo "unknown.pdf")
        echo -n "      → $nombre_pdf ... "
        
        # Verificar que el PDF existe y es escribible
        if [ ! -f "$pdf" ] || [ ! -w "$pdf" ]; then
            echo "✗ ERROR (no escribible)"
            ERROR=$((ERROR + 1))
            ERRORES_LISTA+=("$pdf (no escribible)")
            echo
            continue
        fi
        
        # Construir comando exiftool dinámicamente
        cmd=(exiftool -q -overwrite_original)
        
        # Agregar campos solo si tienen valor
        [ -n "$title" ] && cmd+=(-Title="$title")
        [ -n "$author" ] && cmd+=(-Author="$author")
        [ -n "$publisher" ] && cmd+=(-PDF:Producer="$publisher")
        [ -n "$tags" ] && cmd+=(-Keywords="$tags")
        [ -n "$language" ] && cmd+=(-Language="$language")
        [ -n "$date" ] && cmd+=(-CreateDate="$date")
        
        # Limpiar campos no deseados
        cmd+=(-Creator= -CreatorTool=)
        
        # Agregar archivo PDF
        cmd+=("$pdf")
        
        # Ejecutar exiftool y capturar el código de salida
        error_output=$(mktemp)
        if "${cmd[@]}" 2>"$error_output" >/dev/null; then
            echo "✓ OK"
            OK=$((OK + 1))
            {
                echo "ÉXITO: $pdf"
                echo "  Título: $title"
                echo "  Autor: $author"
                echo "----------------------------------------"
            } >> "$LOG_FILE" 2>/dev/null
        else
            echo "✗ ERROR"
            ERROR=$((ERROR + 1))
            ERRORES_LISTA+=("$pdf")
            {
                echo "ERROR: $pdf"
                echo "  Directorio: $dir"
                echo "  Comando: ${cmd[*]}"
                echo "  Salida de error:"
                cat "$error_output" 2>/dev/null
                echo "----------------------------------------"
            } >> "$LOG_FILE" 2>/dev/null
        fi
        rm -f "$error_output" 2>/dev/null
    done
    
    echo
done

# ==============================================================================
# REPORTE FINAL
# ==============================================================================

echo "════════════════════════════════════════════════════════════════"
echo "  📊 REPORTE FINAL"
echo "════════════════════════════════════════════════════════════════"
echo "  ✓ PDFs procesados correctamente:  $OK"
echo "  ✗ PDFs con errores:                $ERROR"
echo "  ⏭️  Directorios omitidos:           $SKIP"
echo "  📁 Total directorios encontrados:  $TOTAL_OPF"
echo "════════════════════════════════════════════════════════════════"

# Mostrar casos problemáticos si existen
if [ "${#ERRORES_LISTA[@]}" -gt 0 ] 2>/dev/null; then
    echo
    echo "❌ PDFs CON ERRORES (${#ERRORES_LISTA[@]}):"
    echo "────────────────────────────────────────────────────────────────"
    for item in "${ERRORES_LISTA[@]}"; do
        echo "   • $item"
    done
fi

if [ "${#METADATOS_INCOMPLETOS[@]}" -gt 0 ] 2>/dev/null; then
    echo
    echo "⚠️  DIRECTORIOS CON METADATOS INCOMPLETOS (${#METADATOS_INCOMPLETOS[@]}):"
    echo "────────────────────────────────────────────────────────────────"
    for item in "${METADATOS_INCOMPLETOS[@]}"; do
        echo "   • $item"
    done
fi

if [ "${#PDFS_SIN_METADATA[@]}" -gt 0 ] 2>/dev/null; then
    echo
    echo "ℹ️  DIRECTORIOS SIN PDFs (${#PDFS_SIN_METADATA[@]}):"
    echo "────────────────────────────────────────────────────────────────"
    for item in "${PDFS_SIN_METADATA[@]}"; do
        echo "   • $item"
    done
fi

echo
echo "════════════════════════════════════════════════════════════════"
echo "  📝 Log completo guardado en: $LOG_FILE"
echo "  ⏰ Finalizado: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  ⏱️  Tiempo de procesamiento: $SECONDS segundos"
echo "════════════════════════════════════════════════════════════════"

# Código de salida basado en éxitos (no falla si hay errores, solo informa)
if [ $OK -gt 0 ]; then
    exit 0
else
    exit 1
fi
