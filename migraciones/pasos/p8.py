"""migraciones/pasos/p8.py — P8: una forma por editorial (los 9 grupos de grafía de meta/programa/00-descubrimiento/diagnostico-calibre.md §4).

Cada variante se renombra a la forma completa y con tildes (Calibre funde las que coinciden). La editorial no forma
parte de la carpeta del libro: nada se mueve. Los `series_index` repetidos (99 pares) no están aquí: decidir qué
número es el correcto exige mirar cada obra."""

FORMAS = {
    "Universidad del Pacifico": "Universidad del Pacífico",
    "Alianza": "Alianza Editorial", "Alianza Editorial Sa": "Alianza Editorial",
    "Siglo XXI": "Siglo XXI Editores", "Siglo XXI Ediciones": "Siglo XXI Editores",
    "Pearson Educacion": "Pearson Educación",
    "The MIT Press": "MIT Press",
    "Deusto": "Ediciones Deusto",
    "Brontes S.L.": "Ediciones Brontes", "EDICIONES BRONTES S.L.": "Ediciones Brontes",
    "Ediciones Paidos Iberica": "Paidós Ibérica", "Paidos Iberica Ediciones S a": "Paidós Ibérica",
    "Universidad de Sevilla": "Editorial Universidad de Sevilla",
}


def plan(c):
    libros = c.execute("select l.book, p.name from books_publishers_link l join publishers p on p.id=l.publisher").fetchall()
    esperado, propuesta = {}, [("libro", "antes", "después")]
    for b, n in libros:
        if n in FORMAS:
            esperado[str(b)] = FORMAS[n]
            propuesta.append((b, n, FORMAS[n]))
    presentes = {n for _, n in libros if n in FORMAS}
    return ({"items_renombrar": {"publisher": {v: FORMAS[v] for v in sorted(presentes)}}, "esperado": {"publisher": esperado}},
            f"{len(presentes)} grafías de editorial en {len(esperado)} libros pasan a su forma única", propuesta)
