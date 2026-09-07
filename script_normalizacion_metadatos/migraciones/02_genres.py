#!/usr/bin/env python3
"""Deriva el campo Generos (#genres) a partir de las etiquetas ya asignadas.

Solo escribe en libros cuyo Generos esta VACIO; los ya definidos no se tocan.
Uso: genres.py [--apply]
"""
import os
import sqlite3
import sys
from collections import Counter

DB = os.environ.get("CALIBRE_DB", os.path.expanduser("~/Documents/biblioteca/metadata.db"))  # FS2: sin ruta literal

# tag -> genero. Las etiquetas NEUTRAS (formato/metodologia) no votan.
NEUTRAL = {
    "apa", "vancouver", "referencia", "manual", "diccionario", "solucionario",
    "problemas", "problemas_resueltos", "resolucion_problemas", "talon_aquiles",
    "metodologia_investigacion", "diseno_investigacion", "recursos_educativos",
}

MAP = {}


def add(genero, tags):
    for t in tags.split():
        MAP[t] = genero


add("Estadistica", """
    estadistica estadistica_bayesiana inferencia_estadistica probability
    probabilidad_estadistica muestreo distribuciones_muestrales regresion
    econometrics fundamentos_econometria microeconometria macroeconometria
    econometria_bayesiana econometria_financiera series_tiempo datos_panel
    eviews stata
""")

add("Matematicas", """
    matematicas matematicas_i matematicas_ii matematicas_iii matematicas_aplicadas
    matematica_economistas fundamentos_matematicas historia_matematicas
    algebra algebra_lineal aritmetica trigonometria geometria geometria_analitica
    conicas vectores superficies calculo calculo_diferencial calculo_integral
    analisis_matematico analisis_real varias_variables integracion funciones
    funciones_analiticas variable_compleja transformaciones_conformes
    teoria_residuos series_fourier ecuaciones_diferenciales
    ecuaciones_diferenciales_parciales numeros_reales numeros_complejos
    numeros_enteros teoria_numeros teoria_conjuntos matematica_discreta
    combinatoria logica_matematica pensamiento_logico razonamiento_matematico
    olimpiadas_matematicas precalculo logaritmos metodos_numericos
    analisis_numerico aproximacion_numerica programacion_numerica
    optimizacion optimizacion_dinamica control_optimo investigacion_operativa
""")

add("Finanzas", """
    finance finanzas_corporativas finanzas_internacionales mercados_financieros
    teoria_portafolio derivados_financieros renta_fija renta_variable
    opciones_reales economia_financiera matematicas_financieras banca
    analisis_financiero gestion_riesgos contabilidad contabilidad_financiera
    contabilidad_costos
""")

add("Economia", """
    macroeconomic macroeconomia macroeconomia_avanzada macroeconomia_dinamica
    teoria_macroeconomica microeconomia teoria_economica teoria_juegos
    organizacion_industrial teoria_regulacion informacion_asimetrica
    crecimiento_economico crisis_economica ciclos_economicos inflacion desempleo
    politica_economica politica_fiscal politica_monetaria finanzas_publicas
    presupuesto_publico economia_general economia_politica economia_internacional
    comercio_internacional balanza_pagos economia_regional economia_desarrollo
    economia_descriptiva economia_ambiental economia_laboral economia_asiatica
    economia_marxista economia_heterodoxa recursos_naturales
    evaluacion_privada evaluacion_social evaluacion_impacto
    formulacion_proyectos proyectos_inversion investigacion_mercados
    modelamiento_economico
""")

add("Historia", "economic_history historia historia_pensamiento_economico")

add("Politica", """
    political_science gestion_publica gerencia_social siga_siaf administracion
    gestion_procesos recursos_humanos
""")

add("Ciencias Sociales", """
    sociology social_science ciencias_sociales anthropology psychology
    investigacion_social socioeconomia pobreza
""")

add("Derecho", "derecho derecho_economico derecho_internacional derecho_laboral legislacion")

add("Filosofia", "filosofia epistemologia ethics ontology psicoanalisis")

add("Educacion", """
    pedagogia didactica aprendizaje educacion_secundaria preuniversitario
    capacitacion pisa
""")

add("Literatura", """
    literatura ensayos redaccion redaccion_academica escritura argumentacion
    linguistica musica cultura_popular humor
""")

add("Ciencias de la Computación", """
    programming_r python matlab latex informatica algoritmos introduccion_algoritmos
    fundamento_programacion programacion c_plus_plus visual_basic power_BI ofimatica
    machine_learning inteligencia_artificial data_science data_mining ciberseguridad
    criptografia desarrollo_web economia_computacional simulacion
""")

add("Ciencias", """
    fisica fisica_matematica mecanica mecanica_cuantica cinematica termodinamica
    electromagnetismo medicina aeronautica ingenieria
""")

add("Divulgacion", "divulgacion_cientifica curiosidades")

# Desempate: el genero mas informativo (menos frecuente en esta biblioteca) gana.
PRECEDENCIA = [
    "Religion", "Derecho", "Filosofia", "Educacion", "Literatura", "Historia",
    "Ciencias", "Ciencias de la Computación", "Ciencias Sociales", "Politica",
    "Estadistica", "Matematicas", "Finanzas", "Economia", "Divulgacion",
]

apply = "--apply" in sys.argv
con = sqlite3.connect(DB)
cur = con.cursor()

# libros sin genero definido
rows = cur.execute("""
    SELECT b.id, GROUP_CONCAT(t.name, ' ')
    FROM books b
    JOIN books_tags_link l ON l.book = b.id
    JOIN tags t ON t.id = l.tag
    WHERE NOT EXISTS (SELECT 1 FROM books_custom_column_32_link g WHERE g.book = b.id)
    GROUP BY b.id
""").fetchall()

asignados, sin_voto = [], []
for bid, tags in rows:
    votos = Counter()
    for t in tags.split():
        if t in NEUTRAL:
            continue
        g = MAP.get(t)
        if g:
            votos[g] += 1
    if not votos:
        sin_voto.append((bid, tags))
        continue
    top = max(votos.values())
    finalistas = [g for g, n in votos.items() if n == top]
    genero = min(finalistas, key=PRECEDENCIA.index)
    asignados.append((bid, genero))

print("Distribucion propuesta de Generos:")
for g, n in Counter(x[1] for x in asignados).most_common():
    print(f"  {n:5d}  {g}")
print(f"\n  {len(asignados)} libros a asignar | {len(sin_voto)} sin etiqueta clasificable")

# etiquetas sin mapear (diagnostico)
huerfanas = Counter()
for _, tags in sin_voto:
    for t in tags.split():
        if t not in MAP and t not in NEUTRAL:
            huerfanas[t] += 1
if huerfanas:
    print("  etiquetas sin mapear:", dict(huerfanas))

if apply:
    def gid(v):
        r = cur.execute("SELECT id FROM custom_column_32 WHERE value=?", (v,)).fetchone()
        if r:
            return r[0]
        cur.execute("INSERT INTO custom_column_32(value) VALUES (?)", (v,))
        return cur.lastrowid

    cache = {}
    for bid, g in asignados:
        if g not in cache:
            cache[g] = gid(g)
        cur.execute(
            "INSERT OR IGNORE INTO books_custom_column_32_link(book, value) VALUES (?, ?)",
            (bid, cache[g]),
        )
    con.commit()
    print("APLICADO")
else:
    print("SIMULACION (usar --apply para escribir)")
con.close()
