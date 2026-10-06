#!/usr/bin/env python3
# desde_bib.py — paso 02 para los trabajos de escritura: la metadata ya está en el `.bib` del proyecto, así que
# no se adivina desde el PDF (como hace identificar.py con normas e informes): se toma del .bib y se escribe
# pendientes.tsv + la ficha de catalogación con `clave_bibtex`. Después, `catalogar --aplicar` hace lo de siempre.
#
# Uso: desde_bib.py <cfg_json> <references.bib> --serie "Monografia 2026-07-18 - Ansiedad" [--tags "medicina, psychology"]
#      [--proyecto "<WRITING_DIR>/monographs/…"] [--archivo clave=ruta …]
# Empareja cada entrada con `entrada/<clave>.pdf` (nombre que da `main.py descargar --lista "ref|clave"`), o con la
# ruta dada en --archivo. Las entradas sin archivo se listan como pendientes de los pasos 00–01.
import csv, hashlib, json, re, sys, unicodedata
from datetime import date
from pathlib import Path

cfg = json.loads(sys.argv[1]); bib_path = Path(sys.argv[2]).expanduser()
args = sys.argv[3:]
def opt(n, d=""):
    return args[args.index(n) + 1] if n in args else d
SERIE = opt("--serie"); TAGS = opt("--tags"); PROYECTO = opt("--proyecto", "")
ARCHIVOS = {a.split("=", 1)[0]: a.split("=", 1)[1] for i, a in enumerate(args) if i and args[i - 1] == "--archivo"}
PEND = Path(cfg["PENDIENTES"]); FICHAS = Path(cfg["FICHAS_DIR"]); ENTRADA = FICHAS.parents[1] / "entrada"
HOY = date.today().isoformat()
sys.path.insert(0, cfg["PY_COMMON"]); import biblioteca as bib   # noqa: E402  grafía de norma:

TIPO = {"article": ("Journal Article", "Artículo de revista", "Journal Article"), "thesis": ("Thesis", "Monografía", "Thesis"),
        "phdthesis": ("Thesis", "Monografía", "Thesis"), "mastersthesis": ("Thesis", "Monografía", "Thesis"),
        "report": ("Report", "Informe técnico", "Report"), "techreport": ("Report", "Informe técnico", "Report"),
        "book": ("Book", "Libro", "Book"), "incollection": ("Book Section", "Capítulo de libro", "Book Section"),
        "online": ("Webpage", "Documento oficial", "Webpage"), "misc": ("Statute", "Normativa", "Statute")}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def limpio(s):
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "").replace("\\&", "&")).strip()


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    # al último guion completo: ni palabra partida ni guion final (M5, 2026-09-15; antes 157 fichas acababan en «-»)
    return s[:60].rsplit("-", 1)[0] if len(s) > 60 else s


def autores_calibre(campo):
    """«Apellido, Nombre and …» del .bib → «Nombre, Apellido & …» (grafía de la biblioteca); corporativos tal cual."""
    out = []
    for a in re.split(r"\s+and\s+", limpio(campo)):
        a = a.strip()
        if not a:
            continue
        if "," in a:
            ap, nom = [x.strip() for x in a.split(",", 1)]
            out.append(f"{nom}, {ap}" if nom else ap)
        else:
            out.append(a)
    return " & ".join(out)


def entradas(texto):
    for kind, key, body in re.findall(r"@(\w+)\{([^,]+),(.*?)\n\}", texto, re.S):
        f = {k.lower(): v for k, v in re.findall(r"(\w+)\s*=\s*[{\"](.+?)[}\"],?\n", body + "\n")}
        yield kind.lower(), key.strip(), f


def ficha_md(key, kind, f, p, sha, tz, clasif, item, autores, ident, editorial, tags, serie, idx):
    titulo = limpio(f.get("title", key))
    return f"""---
tipo: ficha_catalogacion
calibre_id:
zotero_key:
clave_bibtex: {key}
proyecto: {PROYECTO}
verificacion:
  estado: pendiente
  metodo:
  fecha:
---

> Ficha de catalogación de «{titulo}». Generada por `scripts_for_fuentes/ingesta/lib/desde_bib.py` el {HOY} desde `{bib_path.name}` del proyecto (formato de `prompts/skills/fuentes-documentales/references/paso-02-catalogar.md`). Confianza: **alta** (metadatos del .bib del autor).

## Origen

`{p}` · SHA-256 `{sha[:16]}…` · entrada BibTeX `@{kind}{{{key}}}`

## Zotero
| Campo | Valor |
|---|---|
| Item Type | {tz} |
| Title | {titulo} |
| Author | {autores} |
| Date | {f.get('year', '')} |
| Publication / Publisher | {editorial} |
| Volume / Issue / Pages | {limpio(f.get('volume', ''))} / {limpio(f.get('number', ''))} / {limpio(f.get('pages', ''))} |
| DOI / URL | {f.get('doi', '') or f.get('url', '')} |
| Language | {f.get('language', 'es')} |
| Tags | {tags} |

## Calibre
| Campo | Valor |
|---|---|
| Title | {titulo} |
| Authors | {autores} |
| Publisher | {editorial} |
| Pubdate | {f.get('year', '')} |
| Languages | spa |
| Identifiers | {ident} |
| Series | {serie} [{idx}] |
| Tags | {tags} |
| #clasificador | {clasif} |
| #item_type | {item} |

## Notas
- Metadatos tomados del `.bib` del proyecto `{PROYECTO}`; la clave BibTeX es la del trabajo (Better BibTeX la conserva).
"""


def main():
    ya = {}
    if PEND.exists():
        for r in csv.DictReader(open(PEND, encoding="utf-8"), delimiter="\t"):
            ya[r["sha256"]] = r
    cab = ["sha256", "origen", "autores", "titulo", "tipo_zotero", "clasificador", "item_type", "editorial", "fecha", "identificador", "idioma", "tags", "confianza", "nota", "ficha", "serie", "serie_index"]
    nuevas, sin = [], []
    for idx, (kind, key, f) in enumerate(entradas(bib_path.read_text(encoding="utf-8")), 1):
        p = Path(ARCHIVOS.get(key, "")) if key in ARCHIVOS else next((q for q in (ENTRADA / f"{key}.pdf", ENTRADA / f"{key}.PDF") if q.exists()), None)
        if not p or not p.exists():
            sin.append(key); continue
        sha = sha256(p)
        if sha in ya:
            print(f"  [=] {key}: ya en pendientes ({ya[sha]['titulo'][:50]})"); continue
        tz, clasif, item = TIPO.get(kind, ("Document", "Documento oficial", "Document"))
        autores = autores_calibre(f.get("author", "") or f.get("organization", "") or f.get("institution", "") or cfg.get("AUTOR_DESCONOCIDO", "Unknown"))
        editorial = limpio(f.get("journal", "") or f.get("journaltitle", "") or f.get("publisher", "") or f.get("institution", "") or f.get("organization", "") or f.get("school", ""))
        ident = f"doi:{f['doi'].lower()}" if f.get("doi") else (f"url:{f['url']}" if f.get("url") else "")
        titulo = limpio(f.get("title", key))
        # Normas (Ley, Decreto Legislativo…) citadas desde un .bib como @misc/@online: grafía de la biblioteca (misma que la
        # ingesta del CIL): título «Ley N.° 27933. …», autor institucional, identificador norma:, Normativa/Statute.
        norma = bib.norma_id(f"{limpio(f.get('author', ''))} {titulo} {limpio(f.get('note', ''))} {limpio(f.get('shorttitle', ''))}")
        if norma and kind in ("misc", "online", "legislation", "report"):
            tipo_n, num = norma.rsplit("_", 1)
            rot = {"ley": "Ley", "decreto_legislativo": "Decreto Legislativo", "decreto_supremo": "Decreto Supremo", "decreto_de_urgencia": "Decreto de Urgencia",
                   "resolucion_ministerial": "Resolución Ministerial", "decreto_ley": "Decreto Ley"}.get(tipo_n, tipo_n.replace("_", " ").title())
            cuerpo = re.sub(r"^\s*(ley|decreto\s+\w+|resoluci[oó]n\s+\w+)\s*n[.º°o]*\s*[\w-]+[.,:]?\s*", "", titulo, flags=re.I).strip() or titulo
            titulo = f"{rot} N.° {num.upper() if '-' in num else num}. {cuerpo[:1].upper() + cuerpo[1:]}"
            autores = "Congreso de la República" if tipo_n in ("ley", "decreto_ley") else "Presidencia de la República"
            tz, clasif, item = "Statute", "Normativa", "Statute"
            ident = f"norma:{norma}"; editorial = editorial or "Diario Oficial El Peruano"
        ficha = f"{sha[:8]}_{slug(titulo)}.md"
        FICHAS.mkdir(parents=True, exist_ok=True)
        (FICHAS / ficha).write_text(ficha_md(key, kind, f, p, sha, tz, clasif, item, autores, ident, editorial, TAGS, SERIE, idx), encoding="utf-8")
        nuevas.append([sha, str(p), autores, titulo, tz, clasif, item, editorial, f.get("year", ""), ident, "Spanish", TAGS, "alta", f"desde {bib_path.name} ({PROYECTO}); clave {key}", ficha, SERIE, str(idx)])
        print(f"  [+] {key}: «{titulo[:60]}» · {autores[:40]} · {tz} · {ident}")
    if nuevas:
        nuevo = not PEND.exists()
        with open(PEND, "a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            if nuevo: w.writerow(cab)
            w.writerows(nuevas)
    print(f"[bib] {len(nuevas)} entrada(s) a pendientes.tsv · {len(sin)} sin archivo en {ENTRADA.name}/: {', '.join(sin) or '—'}")
    print("      siguiente: ./main.sh catalogar --solo entrada [--aplicar] · archivar --aplicar · manifiesto generar --bib")


if __name__ == "__main__":
    main()
