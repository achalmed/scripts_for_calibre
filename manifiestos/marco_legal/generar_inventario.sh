#!/usr/bin/env bash
# manifiestos/marco_legal/generar_inventario.sh — Genera INVENTARIO.md: listado navegable de la biblioteca, a partir del
# manifiesto (para las notas) y del contenido real del disco (para tamanos).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARCO_LEGAL="${MARCO_LEGAL:-}"   # carpeta de PDF del marco legal; la del CIL se disolvió en M10 D6 (los PDF están en Calibre)
[[ -n "$MARCO_LEGAL" ]] || { echo "MARCO_LEGAL no definida: el marco legal vive en Calibre desde M10 D6; indique una carpeta local si quiere regenerar" >&2; exit 1; }
RAIZ="$(dirname "$SCRIPT_DIR")"
MANIFIESTO="${SCRIPT_DIR}/manifiesto.tsv"
SALIDA="${MARCO_LEGAL}/INVENTARIO.md"   # el inventario se lee en el CIL, junto al fuentes.yml del marco legal

declare -A TITULO=(
  [01_normativa_fundamental/01_constitucion]="A · Constitución"
  [01_normativa_fundamental/02_codigos]="A · Códigos"
  [02_leyes_organicas]="B · Leyes orgánicas"
  [03_congreso]="C · Congreso"
  [04_administracion_publica]="D · Administración pública"
  [05_contrataciones]="E · Contrataciones"
  [06_presupuesto]="F · Presupuesto"
  [07_economia]="G · Economía (sistemas administrativos)"
  [08_planeamiento]="H · Planeamiento"
  [09_inversion_publica]="I · Inversión pública"
  [10_control]="J · Control"
  [11_seguridad]="K · Seguridad"
  [12_educacion]="L · Educación"
  [13_salud]="M · Salud"
  [14_trabajo]="N · Trabajo"
  [15_ambiente]="O · Ambiente"
  [16_derechos_humanos]="P · Derechos humanos"
  [17_jurisprudencia]="Q · Jurisprudencia"
  [18_manuales]="R · Manuales"
  [19_informes_permanentes]="S · Informes permanentes"
  [20_desarrollo_productivo]="T · Desarrollo productivo (agrario, energía, vivienda, saneamiento)"
)
ORDEN=(01_normativa_fundamental/01_constitucion 01_normativa_fundamental/02_codigos
  02_leyes_organicas 03_congreso 04_administracion_publica 05_contrataciones
  06_presupuesto 07_economia 08_planeamiento 09_inversion_publica 10_control
  11_seguridad 12_educacion 13_salud 14_trabajo 15_ambiente 16_derechos_humanos
  17_jurisprudencia 18_manuales 19_informes_permanentes 20_desarrollo_productivo)

# FD4 (2026-09-07): los PDF ya no están en el marco legal (ni como enlaces); el manifiesto fuentes.yml dice qué libro de
# Calibre es cada uno y el resolutor da la ruta para medir el tamaño.
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"   # scripts_for_fuentes, por la ubicación de este archivo
MANIFIESTO_PY="${MANIFIESTO_PY:-$REPO/manifiesto/main.py}"
n_total=$(awk -F'\t' 'NR>1 && $2!=""' "$MANIFIESTO" | wc -l)
peso=$(python3 - "$MARCO_LEGAL" "$REPO/manifiesto/lib/manifiesto.py" <<'PY'
import importlib.util, sys
from pathlib import Path
s = importlib.util.spec_from_file_location("fuentes_manifiesto", sys.argv[2]); M = importlib.util.module_from_spec(s); s.loader.exec_module(M)
raiz = Path(sys.argv[1]); total = 0
for e in M.cargar(raiz)["fuentes"]:
    p = M.ruta(raiz, e["origen"])
    if p and p.exists(): total += p.stat().st_size
print(f"{total/1e6:.0f} MB en Calibre")
PY
)

{
  echo "# Inventario de la biblioteca normativa"
  echo
  echo "**${n_total} documentos PDF** · ${peso} · descargados el 31 de julio de 2026; viven en Calibre y este directorio los referencia por \`fuentes.yml\` (Calibre id de cada uno abajo; abrir con \`biblioteca.py abrir <id>\`)."
  echo
  echo "Generado por \`~/Documents/scripts_for_fuentes/manifiestos/marco_legal/generar_inventario.sh\`. No editar a mano."
  echo "Antes de citar, leer [PENDIENTES.md](PENDIENTES.md) — hay normas derogadas"
  echo "y textos sin consolidar identificados."
  echo
  for carpeta in "${ORDEN[@]}"; do
    n=$(awk -F'\t' -v c="$carpeta" '$1==c' "$MANIFIESTO" | wc -l)
    (( n == 0 )) && continue
    echo "## ${TITULO[$carpeta]}"
    echo
    echo "\`${carpeta}/\` — ${n} documentos"
    echo
    awk -F'\t' -v c="$carpeta" -v raiz="$MARCO_LEGAL" -v py="$MANIFIESTO_PY" '$1==c {
      cmd = "r=$(python3 \"" py "\" ruta \"" raiz "\" \"" $1 "/" $2 "\" 2>/dev/null); [ -n \"$r\" ] && du -h \"$r\" | cut -f1"
      cmd | getline tam; close(cmd)
      if (tam == "") tam = "AUSENTE"
      cmd2 = "python3 \"" py "\" ruta \"" raiz "\" \"" $1 "/" $2 "\" 2>/dev/null | grep -o \"([0-9]*)\" | tr -d \"()\""
      cmd2 | getline id; close(cmd2)
      printf "- %s — Calibre id `%s` · `%s`  \n", $2, (id == "" ? "?" : id), tam
      id = ""
      if ($5 != "") printf "  <sub>%s</sub>\n", $5
      tam = ""
    }' "$MANIFIESTO"
    echo
  done
} > "$SALIDA"
echo "Inventario generado: $SALIDA ($(wc -l < "$SALIDA") lineas)"
