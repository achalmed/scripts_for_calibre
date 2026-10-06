"""P4 — etiquetas en español y en `snake_case` según las equivalencias de modelo-de-metadatos.md §4.2 y §4.3.

Solo se aplican las equivalencias que el modelo fija una a una (las 14 en inglés, las que llevan espacio y las
variantes de grafía); las etiquetas de un solo libro y las mayúsculas sin equivalencia fijada quedan como están
(necesitan revisión con el vocabulario UNESCO, §4.4). Una etiqueta que cambia de nombre se une a la que ya existe."""

EQUIVALENCIAS = {
    "econometrics": "econometria", "finance": "finanzas", "political_science": "ciencia_politica",
    "economic_history": "historia_economica", "programming_r": "lenguaje_r", "ethics": "etica",
    "sociology": "sociologia", "psychology": "psicologia", "social_science": "ciencias_sociales",
    "machine_learning": "aprendizaje_automatico", "data_science": "ciencia_de_datos",
    "data_mining": "mineria_de_datos", "benchmarking": "evaluacion_comparativa",
    "estilo editorial": "estilo_editorial", "series de tiempo": "series_tiempo",
    "filtro Hodrick-Prescott": "filtro_hodrick_prescott", "indice de precios": "indice_precios",
    "IPC": "indice_precios", "unidad monetaria": "unidad_monetaria", "nuevo sol": "unidad_monetaria",
    "inti": "unidad_monetaria", "ciclo economico": "ciclo_economico", "pobreza monetaria": "pobreza_monetaria",
    "linea de pobreza": "linea_pobreza", "FGT": "pobreza", "encuestas de hogares": "encuestas_hogares",
    "encuestas complejas": "muestreo_complejo", "ENAHO": "enaho", "cuentas nacionales": "cuentas_nacionales",
    "PBI trimestral": "pbi_trimestral", "power_BI": "power_bi",
    "delegacion-facultades-2026": "delegacion_facultades_2026", "comunicacion": "comunicaciones",
}


def plan(c):
    etiquetas = {}
    for b, n in c.execute("select l.book, t.name from books_tags_link l join tags t on t.id=l.tag"):
        etiquetas.setdefault(b, set()).add(n)
    cambios, propuesta = {}, [("libro", "antes", "después")]
    for b, ts in etiquetas.items():
        nuevas = {EQUIVALENCIAS.get(t, t) for t in ts}
        if nuevas != ts:
            cambios[str(b)] = sorted(nuevas)
            propuesta.append((b, "; ".join(sorted(ts - nuevas)), "; ".join(sorted(nuevas - ts))))
    usadas = {t for ts in etiquetas.values() for t in ts} & set(EQUIVALENCIAS)
    return ({"campos": {"tags": cambios}},
            f"{len(cambios)} libros; {len(usadas)} etiquetas pasan a su equivalente en español y snake_case", propuesta)
