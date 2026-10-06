#!/usr/bin/env bash
set -euo pipefail
# main.sh — scripts_for_fuentes/ingesta (antes scripts_for_fuentes/ingesta; migrado el 2026-09-06). ingesta documental de Inteligencia Legislativa (orquestación únicamente).
#
#   ./main.sh recibir                 lista lo que hay en la zona de entrada y no está en el ledger
#   ./main.sh identificar             clasifica + extrae metadatos → pendientes.tsv + fichas/
#   ./main.sh catalogar [--aplicar] [--solo REGEX]   alta en Calibre (calibredb add + columnas) + registro en la suite de catalogación
#   ./main.sh zotero                  .ris para importar en Zotero (+ alta directa si el conector responde)
#   ./main.sh archivar [--aplicar]    retira el original y lo registra en el fuentes.yml de su proyecto (modo manifiesto; enlace/mover por compatibilidad)
#   ./main.sh bib <ref.bib> --serie … paso 02 de un trabajo de 03 writing: pendientes.tsv + fichas desde el .bib (archivos entrada/<clave>.pdf)
#   ./main.sh ocr [--aplicar]         cada X.ocr.pdf pasa a ser el FORMATO del libro de X.pdf (texto buscable); ambos al manifiesto
#   ./main.sh paquetes [--aplicar]    adjuntos de un paquete → carpeta data/ de su entrada (registrados en el manifiesto)
#   ./main.sh todo [--aplicar]        recibir → identificar → catalogar → zotero → archivar → paquetes
#   ./main.sh estado                  resumen del ledger y chequeos
#   ./main.sh cursos --escanear       material externo de los cursos → reportes/cursos/candidatos_<fecha>.tsv
#   ./main.sh cursos [--dry-run] [--tsv X]   simula la ingesta del TSV (último por defecto); --aplicar la aplica
# Simulación por defecto; --aplicar escribe. Logger y entorno de core/; toda escritura en Calibre pasa por la
# puerta ../lib/escribir.sh (Calibre cerrado, candado, respaldo verificado; ola 2, F2) y registra en la suite
# catalogacion (fichas + resumen_catalogacion.tsv = registro canónico). Nunca edita metadata.db a mano.
# Salidas: 0 bien · 1 comando o datos inválidos · 69 falta core/shell-lib · 74 sin respaldo verificado ·
# 75 Calibre abierto o candado ocupado (reintentar luego).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$SCRIPT_DIR/config.sh"
# shellcheck source=../lib/escribir.sh
source "$SCRIPT_DIR/../lib/escribir.sh"
_puerta_core   # env, logger, detección de apps, candado y respaldo de core/; sin core/shell-lib sale 69, nunca en silencio

CMD="${1:-estado}"; shift || true
SOLO=""; prev=""
for a in "$@"; do [[ "$prev" == "--solo" ]] && SOLO="$a"; prev="$a"; case "$a" in --aplicar) APPLY_CHANGES=true ;; --mover) ARCHIVAR_MODO="mover" ;; -h|--help) awk 'NR>2 && /^#/ {print; next} NR>2 {exit}' "$0"; exit 0 ;; esac; done
[[ -f "$LEDGER" ]] || printf 'fecha\tsha256\torigen\ttitulo\tautores\ttipo_zotero\tclasificador\tfecha_doc\teditorial\ttags\tcalibre_id\truta_calibre\tzotero_key\testado\n' > "$LEDGER"
cfg_json() {  # variables de config.sh ya expandidas por bash → JSON para los módulos Python
  SERIE_MARCO_LEGAL_PREFIJO="$SERIE_MARCO_LEGAL_PREFIJO" SERIE_CIL_PREFIJO="$SERIE_CIL_PREFIJO" SERIE_INFORME_PREFIJO="$SERIE_INFORME_PREFIJO" AUTOR_DESCONOCIDO="$AUTOR_DESCONOCIDO" \
  INSTITUCION_POR_CARPETA_JSON="$INSTITUCION_POR_CARPETA_JSON" SIGLAS_JSON="$SIGLAS_JSON" \
  INBOX_RAICES="$(printf "%s\n" "${INBOX_RAICES[@]}")" MANIFIESTO_MARCO_LEGAL="$MANIFIESTO_MARCO_LEGAL" CIL_DIR="$CIL_DIR" FICHAS_DIR="$FICHAS_DIR" PENDIENTES="$PENDIENTES" LEDGER="$LEDGER" RIS_DIR="$RIS_DIR" BIBLIOTECA="$BIBLIOTECA" \
  CATALOGACION_DIR="$CATALOGACION_DIR" DATAFW_DIR="$DATAFW_DIR" PROMPTS_DIR="$PROMPTS_DIR" \
  CONFIANZA_MINIMA_AUTO="$CONFIANZA_MINIMA_AUTO" CLASIFICADOR_DEFECTO="$CLASIFICADOR_DEFECTO" ITEM_TYPE_DEFECTO="$ITEM_TYPE_DEFECTO" \
  ARCHIVAR_MODO="$ARCHIVAR_MODO" TAGS_POR_CARPETA_JSON="$TAGS_POR_CARPETA_JSON" IDIOMA_DEFECTO="$IDIOMA_DEFECTO" \
  PAQUETES_JSON="$PAQUETES_JSON" MANIFIESTO_DIR="$MANIFIESTO_DIR" PY_COMMON="$PY_COMMON" \
  python3 -c 'import json,os; ks="INBOX_RAICES MANIFIESTO_MARCO_LEGAL SERIE_MARCO_LEGAL_PREFIJO SERIE_CIL_PREFIJO SERIE_INFORME_PREFIJO AUTOR_DESCONOCIDO INSTITUCION_POR_CARPETA_JSON SIGLAS_JSON CIL_DIR FICHAS_DIR PENDIENTES LEDGER RIS_DIR BIBLIOTECA CATALOGACION_DIR DATAFW_DIR PROMPTS_DIR CONFIANZA_MINIMA_AUTO CLASIFICADOR_DEFECTO ITEM_TYPE_DEFECTO ARCHIVAR_MODO TAGS_POR_CARPETA_JSON IDIOMA_DEFECTO PAQUETES_JSON MANIFIESTO_DIR PY_COMMON".split(); print(json.dumps({k: os.environ.get(k, "") for k in ks}))'
}

candidatos() {  # archivos regulares (no symlink) en INBOX_DIRS y en INBOX_RAICES
  for d in "${INBOX_DIRS[@]}"; do [[ -d "$CIL_DIR/$d" ]] && find "$CIL_DIR/$d" -type f -regextype posix-extended -iregex ".*\.($EXTENSIONES)$" ! -path "*/00_manifiesto/*" ! -name "*.ocr.pdf"; done
  for g in "${INBOX_GLOBS[@]:-}"; do [[ -n "$g" ]] || continue; for d in "$CIL_DIR"/$g; do [[ -d "$d" ]] && find "$d" -type f -regextype posix-extended -iregex ".*\.($EXTENSIONES)$" ! -name "*.ocr.pdf"; done; done
  # Raíces externas (datafw): ya catalogado = enlace, así que -type f las salta solo.
  for r in "${INBOX_RAICES[@]:-}"; do
    [[ -n "$r" && -d "$r" ]] || continue
    find "$r" -type f -regextype posix-extended -iregex ".*\.(${INBOX_RAICES_EXTENSIONES:-$EXTENSIONES})$" \
         ${INBOX_RAICES_SOLO:+-regex "$INBOX_RAICES_SOLO"} ${INBOX_RAICES_EXCLUIR:+! -regex "$INBOX_RAICES_EXCLUIR"}
  done
  return 0
}

cmd_recibir() {
  local n=0; while IFS= read -r f; do
    local sha; sha=$(sha256sum "$f" | cut -c1-64)
    grep -q "$sha" "$LEDGER" && continue
    printf '  %s\n' "${f#"$CIL_DIR"/}"; n=$((n+1)); done < <(candidatos)
  log_info "recibir: $n documento(s) en la zona de entrada sin catalogar"
}

cmd_identificar() { mapfile -t files < <(candidatos); python3 "$SCRIPT_DIR/lib/identificar.py" "$(cfg_json)" "${files[@]}"; }

cmd_catalogar() {
  [[ -f "$PENDIENTES" ]] || { log_error "no hay pendientes.tsv: corra 'identificar'"; return 1; }
  local extra=(); $APPLY_CHANGES && extra+=(--aplicar); [[ -n "${SOLO:-}" ]] && extra+=(--solo "$SOLO")
  $APPLY_CHANGES && puerta_calibre_abrir_o_salir ingesta "$BIBLIOTECA"
  python3 "$SCRIPT_DIR/lib/catalogar.py" "$(cfg_json)" "${extra[@]}"
}

cmd_zotero() {
  local ris="$RIS_DIR/ingesta_$(date +%Y%m%d_%H%M%S).ris"
  python3 "$SCRIPT_DIR/lib/ris.py" "$LEDGER" "$ris"
  if curl -s --max-time 3 "$ZOTERO_CONNECTOR/connector/ping" >/dev/null 2>&1; then log_info "Zotero abierto: importe $ris (Archivo → Importar) o use el conector"; else log_info "Zotero cerrado: importe $ris al abrirlo; luego pegue la clave en #zotero_key (ZMI) para que el sync nocturno enlace"; fi
}

cmd_paquetes() {
  log_info "paquetes: adjuntos → carpeta data/ de su entrada de Calibre"
  [[ "$APPLY_CHANGES" == true ]] && puerta_calibre_abrir_o_salir ingesta "$BIBLIOTECA"
  python3 "$SCRIPT_DIR/lib/paquetes.py" "$(cfg_json)" $([[ "$APPLY_CHANGES" == true ]] && echo --aplicar)
}
cmd_ocr() {
  local extra=(); $APPLY_CHANGES && extra+=(--aplicar)
  $APPLY_CHANGES && puerta_calibre_abrir_o_salir ingesta "$BIBLIOTECA"
  mapfile -t ocrs < <(for d in "${INBOX_DIRS[@]}"; do [[ -d "$CIL_DIR/$d" ]] && find "$CIL_DIR/$d" -type f \( -name "*.ocr.pdf" -o -name "*_ocr_buscable.pdf" -o -name "*_ocr.pdf" -o -name "*_texto.pdf" -o -name "*_escaneado.pdf" \); done; for g in "${INBOX_GLOBS[@]:-}"; do [[ -n "$g" ]] || continue; for d in "$CIL_DIR"/$g; do [[ -d "$d" ]] && find "$d" -type f \( -name "*.ocr.pdf" -o -name "*_ocr_buscable.pdf" -o -name "*_ocr.pdf" -o -name "*_texto.pdf" -o -name "*_escaneado.pdf" \); done; done; for r in "${INBOX_RAICES[@]:-}"; do [[ -n "$r" && -d "$r" ]] && find "$r" -type f -regextype posix-extended -name "*.ocr.pdf" ${INBOX_RAICES_SOLO:+-regex "$INBOX_RAICES_SOLO"}; done)
  python3 "$SCRIPT_DIR/lib/ocr_formatos.py" "$(cfg_json)" "${extra[@]}" -- "${ocrs[@]}"
}

cmd_archivar() {
  local extra=(); $APPLY_CHANGES && extra+=(--aplicar); [[ "$ARCHIVAR_MODO" == "mover" ]] && extra+=(--mover)
  python3 "$SCRIPT_DIR/lib/archivar.py" "$(cfg_json)" "${extra[@]}"
}

cmd_bib() {  # paso 02 para trabajos de 03 writing: metadatos desde el .bib del proyecto (archivos entrada/<clave>.pdf)
  local bib="${1:-}"; [[ -f "$bib" ]] || { log_error "uso: ./main.sh bib <references.bib> --serie \"…\" [--tags \"…\"] [--proyecto RUTA] [--archivo clave=ruta]"; exit 2; }
  python3 "$SCRIPT_DIR/lib/desde_bib.py" "$(cfg_json)" "$@"
}

cmd_cursos() {  # material externo de los cursos → Calibre + bibliografia: del curso.yml (antes ingesta_cursos; F3)
  local modo=simular tsv="" out d
  while [[ $# -gt 0 ]]; do case "$1" in
      --escanear) modo=escanear ;; --aplicar) modo=aplicar ;; --dry-run) modo=simular ;; --tsv) tsv="${2:-}"; shift ;;
      *) log_error "cursos: argumento desconocido: $1"; exit 2 ;; esac; shift; done
  for d in pdfinfo python3 "${CALIBREDB:-calibredb}"; do command -v "$d" >/dev/null || { log_error "falta dependencia: $d"; exit 5; }; done
  # shellcheck source=lib/cursos_clasificar.sh
  source "$SCRIPT_DIR/lib/cursos_clasificar.sh"
  # shellcheck source=lib/cursos_ingestar.sh
  source "$SCRIPT_DIR/lib/cursos_ingestar.sh"
  if [[ "$modo" == escanear ]]; then
    mkdir -p "$CURSOS_REPORTES_DIR"; out="$CURSOS_REPORTES_DIR/candidatos_$(date +%Y%m%d_%H%M%S).tsv"; escanear "$out"
    log_info "candidatos: $out"; awk -F'\t' 'NR>1{c[$1]++} END{for(k in c) printf "  %s=%d\n", k, c[k]}' "$out"; return 0
  fi
  [[ -n "$tsv" ]] || tsv="$(ls -t "$CURSOS_REPORTES_DIR"/candidatos_*.tsv 2>/dev/null | head -1 || true)"
  [[ -f "$tsv" ]] || { log_error "no hay TSV de candidatos; ejecuta: main.sh cursos --escanear"; exit 3; }
  if [[ "$modo" == aplicar ]]; then
    puerta_calibre_abrir_o_salir ingesta "$BIBLIOTECA"   # 75 Calibre abierto o candado ocupado · 74 sin respaldo verificado
    ingestar_tsv "$tsv" 1
  else
    ingestar_tsv "$tsv" 0
  fi
}

cmd_estado() {
  local total cat arch; total=$(($(wc -l < "$LEDGER")-1)); cat=$(grep -c $'\tcatalogado$' "$LEDGER" || true); arch=$(grep -c $'\tarchivado$' "$LEDGER" || true)
  log_info "ledger: $total documento(s) · catalogados $cat · archivados $arch · pendientes de Zotero $(awk -F'\t' 'NR>1 && $13=="" {c++} END{print c+0}' "$LEDGER")"
  local sin; sin=$(candidatos | while read -r f; do grep -q "$(sha256sum "$f" | cut -c1-64)" "$LEDGER" || echo x; done | wc -l); log_info "en zona de entrada sin catalogar: $sin"
  find "$CIL_DIR" -xtype l 2>/dev/null | head -5 | sed 's/^/  [enlace roto] /' || true
}

case "$CMD" in
  recibir) cmd_recibir ;; identificar) cmd_identificar ;; catalogar) cmd_catalogar ;; zotero) cmd_zotero ;; archivar) cmd_archivar ;; bib) cmd_bib "$@" ;; cursos) cmd_cursos "$@" ;; paquetes) cmd_paquetes ;;
  ocr)          cmd_ocr ;;
  todo) cmd_recibir; cmd_identificar; cmd_catalogar; cmd_zotero; cmd_archivar; cmd_paquetes; cmd_estado ;; estado) cmd_estado ;;
  *) log_error "comando desconocido: $CMD"; awk 'NR>2 && /^#/ {print; next} NR>2 {exit}' "$0"; exit 1 ;;
esac
