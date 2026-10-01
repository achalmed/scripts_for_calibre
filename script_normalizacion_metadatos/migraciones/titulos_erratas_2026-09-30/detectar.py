"""detectar.py — títulos de Calibre con tildes que faltan o erratas (SOLO LECTURA; insumo de una campaña).

    python3 detectar.py [--tsv <salida.tsv>]      (por defecto, la biblioteca de core/env.py)

Solo libros en español (`spa`). Tres señales, de más a menos segura:
  A. `-cion`/`-sion` final sin tilde («Educacion»): en español siempre es «-ción».
  B. palabra sin tilde cuya forma con tilde aparece en otro título de la biblioteca o en la lista semilla
     («Economia» si existe «Economía»); se excluyen los pares que son dos palabras válidas (esta/está,
     practica/práctica…).
  D. tilde sobrante: forma con tilde rara frente a la misma palabra sin tilde, muy frecuente («naciónal»).
  C. posible errata: palabra que aparece una sola vez y está a una letra de otra frecuente («tracendentes»
     ↔ «trascendentes»); se excluyen plurales y cambios de género. Es la señal ruidosa: se revisa a mano.
El título propuesto aplica A y B; C solo se marca. Con --tsv escribe filas con la forma del propuesta.tsv
de una campaña como esta (libro · título viejo · título propuesto · motivo); revisar antes de aplicar.
"""
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "core"))
import env  # noqa: E402

SEMILLA = ("Cálculo Economía Estadística Econometría Macroeconomía Microeconomía Metodología Teoría Análisis "
           "Matemática Matemáticas Política Políticas Económica Económico Económicas Económicos Básica Básico "
           "Numérico Numérica Lógica Física Química Biología Filosofía Psicología Sociología Geografía "
           "Álgebra Geometría Trigonometría Aritmética Didáctica Pedagogía Introducción Investigación Público "
           "Pública Técnicas Técnica Método Métodos Práctico Práctica Crítica Teórico Teórica Jurídico Jurídica "
           "Perú Lingüística Gramática Ingeniería Administración Gestión Educación Evaluación Programación "
           "Dinámica Términos Capítulo Edición Volumen Número Números Índice Índices Árbol Ética Estética").split()
# formas sin tilde que también son palabras correctas: no se marcan
AMBIGUAS = set("""el tu mi si se de te mas esta este estas estos ese esa como que cual quien donde cuando cuanto
solo aun cambiaria cambiarias continua periodo periodos practica practicas publica publico critica criticas critico ultimo calculo numero numeros
valido medico deposito animo estimulo genero titulo publicos limite limites indice
transito equivoco intimo termino terminos continuo""".split())
# llanas en -n/-s y adjetivos en -al: nunca llevan tilde; si aparecen con ella, es tilde sobrante (D)
NUNCA_TILDE = set("""volumen examen resumen origen imagen margen joven orden crimen dictamen certamen abdomen
nacional internacional cambiaria cambiarias""".split())
# verbos homógrafos que en primera posición de un título son casi siempre el sustantivo («Calculo de…»)
SUSTANTIVO_INICIAL = {"calculo", "numero", "numeros", "titulo", "indice", "limite", "limites", "termino", "terminos",
                      "genero", "practica", "practicas", "critica", "publico", "publica", "ultimo"}


def sin_tilde(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def palabras(t):
    return re.findall(r"[^\W\d_]+", t)


def distancia1(a, b):
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))


def flexion(a, b):
    a, b = sorted((a, b), key=len)
    return b in (a + "s", a + "es") or (len(a) == len(b) and a[:-1] == b[:-1] and {a[-1], b[-1]} <= set("aos"))


def main(argv):
    bib = Path(env.BIBLIOTECA_DIR)
    c = sqlite3.connect(f"file:{bib / 'metadata.db'}?mode=ro", uri=True)
    libros = c.execute("select b.id, b.title from books b join books_languages_link l on l.book = b.id"
                       " join languages g on g.id = l.lang_code where g.lang_code = 'spa' order by b.id").fetchall()
    c.close()
    # diccionario de tildes: lo que la propia biblioteca escribe con tilde, más la semilla
    con_tilde = Counter()
    for _, t in libros:
        for w in palabras(t):
            if sin_tilde(w) != w:
                con_tilde[w.lower()] += 1
    for w in SEMILLA:
        con_tilde[w.lower()] += 1
    plano = Counter(w.lower() for _, t in libros for w in palabras(t) if sin_tilde(w) == w)
    semilla = {w.lower() for w in SEMILLA}
    forma, sobrante = {}, {}
    for w, n in con_tilde.most_common():
        base = sin_tilde(w)
        # lo aprendido de la biblioteca vale si se repite y no es mucho más raro que su forma sin tilde
        if base in NUNCA_TILDE:
            sobrante[w] = base
        elif w in semilla or (n >= 2 and n * 10 >= plano[base]):
            forma.setdefault(base, w)
        elif plano[base] >= 20 * n and not re.search(r"[cs]i[óo]n(es)?$", w):
            sobrante[w] = base
    frec = Counter(sin_tilde(w.lower()) for _, t in libros for w in palabras(t))

    filas = []
    for libro, titulo in libros:
        nuevo, motivos = titulo, []
        for i, w in enumerate(palabras(titulo)):
            wl = w.lower()
            if sin_tilde(w) != w:
                if wl in sobrante:
                    motivos.append(f"D:{w}?{sobrante[wl]}")
                continue
            arreglo = None
            if re.fullmatch(r".{2,}[cs]ion", wl):
                arreglo, clase = wl[:-3] + "ión", "A"
            elif wl in forma and (wl not in AMBIGUAS or (i == 0 and wl in SUSTANTIVO_INICIAL)):
                arreglo, clase = forma[wl], "B"
            if arreglo:
                if w.isupper() and len(w) > 1:
                    arreglo = arreglo.upper()
                elif w[0].isupper():
                    arreglo = arreglo[0].upper() + arreglo[1:]
                nuevo = re.sub(rf"(?<![^\W\d_]){re.escape(w)}(?![^\W\d_])", arreglo, nuevo, count=1)
                motivos.append(f"{clase}:{w}→{arreglo}")
            elif len(wl) >= 6 and frec[wl] == 1:
                vecinas = [v for v, n in frec.items()
                           if n >= 3 and len(v) >= 6 and distancia1(wl, v) and not flexion(wl, v)]
                if vecinas:
                    motivos.append(f"C:{w}?{'/'.join(sorted(vecinas)[:3])}")
        if motivos:
            filas.append((libro, titulo, nuevo, " ".join(motivos)))

    cuenta = Counter(m.split(":")[0] for *_, ms in filas for m in ms.split())
    print(f"{len(libros)} títulos en español · {len(filas)} con señales · A (-ción) {cuenta['A']} · "
          f"B (tilde conocida) {cuenta['B']} · C (posible errata) {cuenta['C']} · D (tilde sobrante) {cuenta['D']}")
    if "--tsv" in argv:
        with open(argv[argv.index("--tsv") + 1], "w", encoding="utf-8") as f:
            f.write("# libro\ttítulo viejo\ttítulo propuesto\tmotivo (A -ción · B tilde conocida · C posible errata · D tilde sobrante)\n")
            for fila in filas:
                f.write("\t".join(map(str, fila)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
