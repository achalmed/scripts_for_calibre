#!/usr/bin/env bash
# =============================================================================
#  manifiestos/marco_legal/generar_manifiesto.sh — Fusiona los TSV parciales de `parciales/` en un unico `manifiesto.tsv`
#
# Cada busqueda de URLs escribe su propio archivo en `parciales/` para no
# pisarse con las demas. Este script los une, separa las lineas FALLIDO
# (documentos que no se pudieron localizar) y deduplica por carpeta+archivo.
#
# Uso:  ./generar_manifiesto.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARCO_LEGAL="${MARCO_LEGAL:-}"   # carpeta de PDF del marco legal; la del CIL se disolvió en M10 D6 (los PDF están en Calibre)
[[ -n "$MARCO_LEGAL" ]] || { echo "MARCO_LEGAL no definida: el marco legal vive en Calibre desde M10 D6; indique una carpeta local si quiere regenerar" >&2; exit 1; }
PARCIALES="${SCRIPT_DIR}/parciales"
MANIFIESTO="${SCRIPT_DIR}/manifiesto.tsv"
NO_LOCALIZADOS="${SCRIPT_DIR}/no_localizados.tsv"

if [[ ! -d "$PARCIALES" ]] || ! compgen -G "${PARCIALES}/*.tsv" > /dev/null; then
  echo "No hay archivos parciales en $PARCIALES" >&2
  exit 1
fi

# --- manifiesto: todo lo verificado, deduplicado por carpeta+archivo ---------
{
  printf 'carpeta\tarchivo\turl\tfuente\tnota\n'
  cat "${PARCIALES}"/*.tsv \
    | grep -v $'^FALLIDO\t' \
    | grep -v '^carpeta	archivo' \
    | grep -v '^[[:space:]]*$' \
    | awk -F'\t' '!vistos[$1"/"$2]++' || true   # grep sin coincidencias no es un error
} > "$MANIFIESTO"

# --- documentos que no se pudieron localizar --------------------------------
{
  printf 'estado\tdocumento\tmotivo\n'
  cat "${PARCIALES}"/*.tsv | grep $'^FALLIDO\t' | cut -f1-3 || true   # sin fallidos, grep sale 1
} > "$NO_LOCALIZADOS"

n_ok=$(( $(wc -l < "$MANIFIESTO") - 1 ))
n_no=$(( $(wc -l < "$NO_LOCALIZADOS") - 1 ))

echo "Manifiesto generado : $MANIFIESTO  ($n_ok documentos)"
echo "No localizados      : $NO_LOCALIZADOS  ($n_no documentos)"
echo
echo "Documentos por bloque:"
tail -n +2 "$MANIFIESTO" | cut -f1 | sort | uniq -c | sort -k2
