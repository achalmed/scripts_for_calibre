"""migraciones/pasos/p3.py — P3a: `#clasificador` como vocabulario de **unidad docente** (modelo-de-metadatos.md §3.3), parte mecánica.

Los valores docentes pasan a los 12 del vocabulario nuevo (sesion, tema, capitulo, lectura, apuntes, modulo, unidad,
semana, silabo, taller, ejercicios, evaluacion) según la tabla del modelo; los valores que no son docentes se
conservan tal cual (vaciarlos exige comprobar libro por libro que el dato ya está en `#item_type` o `#sub_tipo`:
P3b, aparte). De la enumeración salen solo los valores docentes absorbidos y los que nadie usa."""
import json

ABSORBE = {
    "sesion": ["Sesión", "Clase", "Notas de sesion", "Notas de sesión"], "tema": ["Tema"],
    "capitulo": ["Capítulo", "Parte"],
    "lectura": ["Lectura", "Lectura obligatoria", "Artículo complementario", "Material complementario"],
    "apuntes": ["Apuntes de clase", "Apuntes de historia", "Apuntes de estudio", "Handout"],
    "modulo": ["Módulo"], "unidad": ["Unidad"], "semana": ["Semana"], "silabo": ["Sílabus", "Programa"],
    "taller": ["Taller"],
    "ejercicios": ["Ejercicio", "Ejercicios resueltos", "Solucionario", "Guía de estudio", "Recurso educativo"],
    "evaluacion": ["Evaluación"],
}
NUEVO = list(ABSORBE)
VIEJO_A_NUEVO = {v: k for k, vs in ABSORBE.items() for v in vs}


def plan(c):
    col = dict(c.execute("select label, id from custom_columns").fetchall())
    disp = json.loads(c.execute("select display from custom_columns where label='clasificador'").fetchone()[0])
    viejos = disp["enum_values"]
    t = f"custom_column_{col['clasificador']}"
    valor = dict(c.execute(f"select l.book, v.value from books_{t}_link l join {t} v on v.id=l.value").fetchall())
    cambios, propuesta = {}, [("libro", "antes", "después")]
    for b, v in valor.items():
        if v in VIEJO_A_NUEVO:
            cambios[str(b)] = VIEJO_A_NUEVO[v]
            propuesta.append((b, v, VIEJO_A_NUEVO[v]))
    usados_no_docentes = sorted({v for v in valor.values() if v not in VIEJO_A_NUEVO})
    final = NUEVO + usados_no_docentes
    salen = [v for v in viejos if v not in final]
    presentes = sorted({v for v in valor.values() if v in VIEJO_A_NUEVO})
    return ({"enum_antes": {"clasificador": list(dict.fromkeys(viejos + NUEVO))},
             "items_renombrar": {"#clasificador": {v: VIEJO_A_NUEVO[v] for v in presentes}},
             "esperado": {"#clasificador": cambios},
             "enum_despues": {"clasificador": final}},
            f"{len(cambios)} libros pasan al vocabulario docente; {len(usados_no_docentes)} valores no docentes se conservan; "
            f"salen de la enumeración {len(salen)} valores", propuesta)
