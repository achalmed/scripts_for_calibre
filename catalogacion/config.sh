#!/usr/bin/env bash
# catalogacion/config.sh — Central configuration for aplicar-metadatos
# Every user-editable value lives here; lib/ modules never hardcode paths.

# shellcheck disable=SC2034  # variables are consumed by main.sh and lib/ modules

readonly VERSION="1.0.0"
readonly TOOL_NAME="aplicar-metadatos"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../core/env.sh"   # rutas: core/env (K6, P217)

# Calibre library that will receive the metadata (BIBLIOTECA_DIR de core/env).
readonly CALIBRE_LIBRARY="$BIBLIOTECA_DIR"

# Input TSV (one row per book). Resolved relative to the project directory.
readonly TSV_BASENAME="resumen_catalogacion.tsv"

# Expected TSV columns (tab-separated, header row included):
#   id  autores  titulo  tipo_zotero  clasificador  editorial  fecha
#   identificador  idioma  tags  confianza  nota

# --- Runtime option defaults (overridden by CLI flags in lib/cli.sh) ---
APPLY_CHANGES=false   # false = simulation; true only with --aplicar
ONLY_HIGH_CONFIDENCE=false
ONLY_IDS=""           # --ids 10011,10012 → solo esas filas (FD2, 2026-09-07); vacío = todas
VERBOSE=false

# --- Fallback enum for the #clasificador custom column -----------------
# Snapshot taken from metadata.db on 2026-07-27. Used only when the live
# read via sqlite3/python3 is not possible (see lib/clasificador.sh).
readonly CLASIF_ENUM_FALLBACK="|Actividad|Apuntes de clase|Apuntes de estudio|Apuntes de historia|Artículo complementario|Bibliografía|Capítulo|Capítulo de libro|Caso práctico|Clase|Compendio|Cronograma|Diapositiva|Documento de trabajo|Estudios economicos|Ejercicio|Ejercicios resueltos|Entregable|Evaluación|Extracto|Final|Folleto|Foro|Grabación|Guía|Handout|Infografía|Lectura|Lectura obligatoria|Lectura recomendada|Laboratorio|Lineamientos|Mapa conceptual|Material complementario|Monografía|Módulo|Notas de sesion|Número|Parte|Parcial|Práctica|Práctica dirigida|Práctica calificada|Presentación|Problemas|Problemas resueltos|Programa|Proyecto|Prueba|Quiz|Reading|Resolución|Resumen|Resumen ejecutivo|Semana|Sesión|Serie|Sílabus|Slide|Solucionario|Taller|Tarea|Tema|Trabajo práctico|Transcripción|Tutorial|Unidad|Video clase|"
