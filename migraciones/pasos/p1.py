"""P1 — `#item_type` con los 37 tipos de Zotero (modelo-de-metadatos.md §7).

Se añaden Preprint, Standard y Computer Program; Pamphlet pasa a Document (Zotero no lo tiene); los libros sin tipo
toman el de `#zotero_item_type` si lo hay o Document; las normas ISO, RFC y CCSDS pasan a Standard; se retiran de la
enumeración los valores que Zotero no tiene y nadie usa.
"""
import json
import re

ZOTERO = ["Artwork", "Audio Recording", "Bill", "Blog Post", "Book", "Book Section", "Case", "Computer Program",
          "Conference Paper", "Dataset", "Dictionary Entry", "Document", "Email", "Encyclopedia Article", "Film",
          "Forum Post", "Hearing", "Instant Message", "Interview", "Journal Article", "Letter", "Magazine Article",
          "Manuscript", "Map", "Newspaper Article", "Patent", "Podcast", "Preprint", "Presentation",
          "Radio Broadcast", "Report", "Standard", "Statute", "Thesis", "TV Broadcast", "Video Recording", "Webpage"]
# zotero_item_type (camelCase de Zotero) → etiqueta de la enumeración
CAMEL = {re.sub(r"[^a-z]", "", z.lower()): z for z in ZOTERO}
CAMEL.update({"tvbroadcast": "TV Broadcast", "computerprogram": "Computer Program"})
NORMA = re.compile(r"^(ISO(/IEC)?\s*\d|RFC\s*\d|CCSDS\s*\d)", re.I)


def plan(c):
    col = dict(c.execute("select label, id from custom_columns").fetchall())
    disp = json.loads(c.execute("select display from custom_columns where label='item_type'").fetchone()[0])
    viejos = disp["enum_values"]
    t = f"custom_column_{col['item_type']}"
    tipo = dict(c.execute(f"select l.book, v.value from books_{t}_link l join {t} v on v.id=l.value").fetchall())
    zt = {}
    if "zotero_item_type" in col:
        zt = dict(c.execute(f"select book, value from custom_column_{col['zotero_item_type']}").fetchall())
    cambios, propuesta = {}, [("libro", "título", "antes", "después", "motivo")]
    for bid, titulo in c.execute("select id, title from books"):
        antes = tipo.get(bid)
        despues, motivo = antes, ""
        if antes == "Pamphlet":
            despues, motivo = "Document", "Zotero no tiene Pamphlet"
        elif antes is None:
            z = CAMEL.get(re.sub(r"[^a-z]", "", (zt.get(bid) or "").lower()))
            despues, motivo = (z, "tipo de Zotero") if z else ("Document", "sin tipo")
        if NORMA.match(titulo or "") and despues != "Standard":
            despues, motivo = "Standard", "norma ISO, RFC o CCSDS"
        if despues != antes:
            cambios[str(bid)] = despues
            propuesta.append((bid, titulo, antes or "", despues, motivo))
    usados = set(tipo.values()) - {"Pamphlet"} | set(cambios.values())
    final = [z for z in ZOTERO] + sorted(v for v in usados if v not in ZOTERO)
    retirados = [v for v in viejos if v not in final]
    p = {"enum_antes": {"item_type": list(dict.fromkeys(viejos + ZOTERO))}, "campos": {"#item_type": cambios},
         "enum_despues": {"item_type": final}}
    return p, f"{len(cambios)} libros cambian de tipo; la enumeración queda en {len(final)} valores (retirados: {', '.join(retirados)})", propuesta
