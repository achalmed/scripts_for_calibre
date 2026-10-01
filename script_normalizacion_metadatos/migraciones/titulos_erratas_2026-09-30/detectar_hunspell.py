"""detectar_hunspell.py — tildes y erratas de títulos en español con el diccionario hunspell es-ES (SOLO LECTURA).

    calibre-debug detectar_hunspell.py -- <metadata.db> <salida.tsv>

Complementa a detectar.py, que solo conoce las tildes que la biblioteca ya escribe en otro título. Aquí manda
el diccionario es-ES que trae Calibre (/opt/calibre/resources/dictionaries/es-ES). Por cada palabra no
reconocida (minúscula; se saltan siglas, números y palabras de menos de 3 letras):
  T  tilde única: una sola variante con una tilde o con ñ es palabra → título propuesto con ella.
  T? varias variantes válidas (público/publicó) → revisar a mano.
  E  sin variante con tilde: posible errata o palabra fuera del diccionario (nombres, inglés, tecnicismos)
     → se dan las sugerencias de hunspell, revisar a mano.
Límite honesto: una errata que forma otra palabra válida («constates») no se detecta.
"""
import re
import sqlite3
import sys

from calibre_extensions import hunspell

DIC = "/opt/calibre/resources/dictionaries/es-ES/es-ES"
TILDE = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}


def variantes(w):
    out = set()
    for i, ch in enumerate(w):
        if ch in TILDE:
            out.add(w[:i] + TILDE[ch] + w[i + 1:])
        if ch == "n":
            out.add(w[:i] + "ñ" + w[i + 1:])
        if ch == "u":
            out.add(w[:i] + "ü" + w[i + 1:])
    return out


def main(db, salida):
    d = hunspell.Dictionary(DIC + ".dic", DIC + ".aff")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    libros = c.execute("select b.id, b.title from books b join books_languages_link l on l.book = b.id"
                       " join languages g on g.id = l.lang_code where g.lang_code = 'spa' order by b.id").fetchall()
    cache = {}
    n = {"T": 0, "T?": 0, "E": 0}
    with open(salida, "w", encoding="utf-8") as f:
        f.write("# libro\ttítulo\ttítulo propuesto (solo T)\tseñales (T tilde única · T? varias · E posible errata)\n")
        for libro, titulo in libros:
            nuevo, senales = titulo, []
            for m in re.finditer(r"[^\W\d_]+", titulo):
                w = m.group(0)
                if len(w) < 3 or (w.isupper() and len(w) <= 6):
                    continue
                wl = w.lower()
                if wl not in cache:
                    if d.recognized(wl) or d.recognized(w):
                        cache[wl] = None
                    else:
                        ok = sorted(v for v in variantes(wl) if d.recognized(v) or d.recognized(v.capitalize()))
                        cache[wl] = ("T", ok[0]) if len(ok) == 1 else ("T?", "/".join(ok)) if ok else \
                            ("E", "/".join(list(d.suggest(wl))[:3]))
                r = cache[wl]
                if not r:
                    continue
                clase, prop = r
                n[clase] += 1
                if clase == "T":
                    rep = prop[0].upper() + prop[1:] if w[0].isupper() else prop
                    nuevo = re.sub(rf"(?<![^\W\d_]){re.escape(w)}(?![^\W\d_])", rep, nuevo, count=1)
                senales.append(f"{clase}:{w}→{prop}")
            if senales:
                f.write(f"{libro}\t{titulo}\t{nuevo}\t{' '.join(senales)}\n")
    print(f"{len(libros)} títulos en español · T {n['T']} · T? {n['T?']} · E {n['E']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[-2:]))
