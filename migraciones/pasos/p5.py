"""migraciones/pasos/p5.py — P5: `#genres` (16 disciplinas que duplican `tags`) pasa a etiquetas del vocabulario y la columna se retira
(modelo-de-metadatos.md §3.4). Cada libro conserva sus etiquetas y gana la de su disciplina si no la tiene."""

MAPA = {"Economia": "economia", "Estadistica": "estadistica", "Finanzas": "finanzas", "Filosofia": "filosofia",
        "Matematicas": "matematicas", "Politica": "politica_y_gobierno", "Ciencias de la Computación": "informatica",
        "Metodologia": "metodologia_investigacion", "Ciencias Sociales": "ciencias_sociales", "Historia": "historia",
        "Literatura": "literatura", "Educacion": "educacion", "Derecho": "derecho",
        "Divulgacion": "divulgacion_cientifica", "Ciencias": "ciencias_naturales", "Religion": "religion"}


def plan(c):
    col = dict(c.execute("select label, id from custom_columns").fetchall())
    t = f"custom_column_{col['genres']}"
    genero = dict(c.execute(f"select l.book, v.value from books_{t}_link l join {t} v on v.id=l.value").fetchall())
    etiquetas = {}
    for b, n in c.execute("select l.book, t.name from books_tags_link l join tags t on t.id=l.tag"):
        etiquetas.setdefault(b, set()).add(n)
    sin_mapa = sorted({g for g in genero.values() if g not in MAPA})
    if sin_mapa:
        raise SystemExit(f"P5: géneros sin etiqueta destino: {sin_mapa}")
    cambios, propuesta = {}, [("libro", "género", "etiqueta que gana")]
    for b, g in genero.items():
        destino = MAPA[g]
        if destino not in etiquetas.get(b, set()):
            cambios[str(b)] = sorted(etiquetas.get(b, set()) | {destino})
            propuesta.append((b, g, destino))
    return ({"campos": {"tags": cambios}, "columnas_borrar": ["#genres"]},
            f"{len(genero)} libros con género; {len(cambios)} ganan la etiqueta de su disciplina; se retira #genres", propuesta)
