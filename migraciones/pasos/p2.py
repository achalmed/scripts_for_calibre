"""P2a — autores con coma literal (modelo-de-metadatos.md §7, P2, parte mecánica).

Calibre guarda la coma dentro del nombre de un autor como `|` (la coma separa autores en sus listas); 828 autores
entraron con la coma literal por SQL. Se reescriben por la API con el mismo nombre visible, y el ensayo exige que no
cambie ninguna carpeta de libro (si cambiara una, Zotero perdería el adjunto). La parte que sí necesita juicio
(autores de un token, `Unknown` que hay que revisar desde el PDF) no está aquí."""
MUEVE_CARPETAS = False


def plan(c):
    """Se renombra la fila del autor (`rename_items`): escribir los autores de cada libro no basta, porque Calibre
    reutiliza la fila que ya existe con la coma. Si la forma con `|` ya existe, Calibre funde las dos."""
    filas = c.execute("select id, name from authors where name like '%,%'").fetchall()
    libros = dict(c.execute("select l.author, count(*) from books_authors_link l group by l.author").fetchall())
    renombres = {str(i): n.replace(",", "|") for i, n in filas}
    propuesta = [("autor", "nombre", "libros")] + [(i, n, libros.get(i, 0)) for i, n in filas]
    return ({"autores_renombrar": renombres},
            f"{len(filas)} autores con coma literal en {sum(libros.get(i, 0) for i, _ in filas)} libros: la coma pasa a `|`, como la guarda Calibre",
            propuesta)


def verificar(db):
    import sqlite3
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    quedan = c.execute("select count(*) from authors a where name like '%,%' and exists"
                       "(select 1 from books_authors_link l where l.author=a.id)").fetchone()[0]
    c.close()
    return [f"{quedan} autores con coma literal siguen enlazados a libros"] if quedan else []
