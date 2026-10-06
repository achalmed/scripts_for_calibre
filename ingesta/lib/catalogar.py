#!/usr/bin/env python3
# catalogar.py — aplica pendientes.tsv a Calibre con calibredb por la puerta lib/escribir.* (nunca SQL de escritura) y registra:
#   ledger ingesta.tsv (fuente de verdad de la suite) + ficha y fila en catalogacion
#   (registro canónico del ecosistema). Python (no bash `read`) porque los TSV tienen campos vacíos.
# Idempotente: si el libro ya existe (mismo archivo por SHA-256, o mismo título añadido hoy en una
# corrida no registrada) se REUTILIZA su id; nunca se añade un duplicado.
# Uso: catalogar.py <cfg_json> [--aplicar] [--solo REGEX]   (REGEX sobre la ruta de origen)
import csv, hashlib, importlib.util, json, os, re, sqlite3, sys
from datetime import date
from pathlib import Path

cfg = json.loads(sys.argv[1]); aplicar = "--aplicar" in sys.argv
solo = re.compile(sys.argv[sys.argv.index("--solo") + 1]) if "--solo" in sys.argv else None
LED, PEND, BIB = Path(cfg["LEDGER"]), Path(cfg["PENDIENTES"]), Path(cfg["BIBLIOTECA"])
CAT = Path(cfg["CATALOGACION_DIR"]); FICHAS = Path(cfg["FICHAS_DIR"]); CIL = Path(cfg["CIL_DIR"])
ORDEN = {"alta": 3, "media": 2, "baja": 1}; MINIMO = ORDEN[cfg.get("CONFIANZA_MINIMA_AUTO", "media")]
HOY = date.today().isoformat()
sys.path.insert(0, cfg["PY_COMMON"])
import biblioteca as bib   # noqa: E402  resolutor único de core/py-common (FD2): rutas físicas solo desde aquí
_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # rutas del ledger relativas a DOCS_ROOT (F5)
_s = importlib.util.spec_from_file_location("rutas", _R); R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
_E = Path(__file__).resolve().parents[2] / "lib" / "escribir.py"   # la puerta de escritura en Calibre (F2)
_s = importlib.util.spec_from_file_location("escribir", _E); E = importlib.util.module_from_spec(_s); _s.loader.exec_module(E)

FRONTMATTER_CATALOGACION = """---
tipo: ficha_catalogacion
calibre_id: {bid}
zotero_key:
clave_bibtex:
proyecto:
verificacion:
  estado: pendiente
  metodo:
  fecha:
---

"""


def ficha_con_id(texto, bid):
    """Devuelve la ficha con `calibre_id` rellenado; si la ficha es anterior a FD2 (sin frontmatter) se lo antepone."""
    if texto.startswith("---\n"):
        return re.sub(r"^calibre_id:.*$", f"calibre_id: {bid}", texto, count=1, flags=re.M)
    return FRONTMATTER_CATALOGACION.format(bid=bid) + texto


def run(*args):
    return E.calibredb(BIB, *args)   # escritura solo con la puerta abierta (lib/escribir.sh)


def enum(col_id):
    con = sqlite3.connect(f"file:{BIB / 'metadata.db'}?mode=ro", uri=True)
    r = con.execute("select display from custom_columns where id=?", (col_id,)).fetchone(); con.close()
    return set(json.loads(r[0]).get("enum_values", [])) if r else set()


def buscar_existente(titulo, src):
    """(id, ruta) de un libro ya presente: mismo archivo (huella SHA-256, vía el resolutor) o mismo título añadido hoy."""
    if src.exists():
        r = bib.existe(archivo=str(src))
        if r["candidatos"]:
            c = r["candidatos"][0]; return str(c["calibre_id"]), c["ruta"]
    for c in bib.existe(titulo=titulo)["candidatos"]:
        d = bib.datos(c["calibre_id"])
        if d and d["anadido"] == HOY and d["ruta"] and Path(d["ruta"]).exists():
            print(f"  [!] id {d['calibre_id']}: mismo título añadido hoy, SHA distinto: se reutiliza"); return str(d["calibre_id"]), d["ruta"]
    return None, ""


def ruta_formato(bid):
    p = bib.ruta(bid)
    return R.a_texto(p) if p else ""   # relativa a DOCS_ROOT (F5)


def main():
    if aplicar:
        E.exigir_puerta()
    led_rows = list(csv.DictReader(open(LED, encoding="utf-8"), delimiter="\t")) if LED.exists() else []
    hechos = {r["sha256"] for r in led_rows}; led_por_sha = {r["sha256"]: r for r in led_rows}; origenes = {r["origen"] for r in led_rows}
    ENUM_CLASIF, ENUM_ITEM = enum(43), enum(39)
    n = om = 0; filas_led, filas_cat = [], []
    for r in csv.DictReader(open(PEND, encoding="utf-8"), delimiter="\t"):
        if solo and not solo.search(r["origen"]): continue
        if r["sha256"] in hechos:
            if r["origen"] not in origenes:      # el mismo archivo ya está en Calibre desde otra ruta: se registra la copia para enlazarla
                o = led_por_sha[r["sha256"]]
                if aplicar: filas_led.append([HOY, r["sha256"], r["origen"], o["titulo"], o["autores"], o["tipo_zotero"], o["clasificador"], o["fecha_doc"], o["editorial"], o["tags"], o["calibre_id"], o["ruta_calibre"], o.get("zotero_key", ""), "catalogado"])
                print(f"  [=] copia de id {o['calibre_id']} «{o['titulo'][:50]}»: {r['origen'][-60:]} → se enlazará"); n += 1
            continue
        if ORDEN.get(r["confianza"], 1) < MINIMO:
            om += 1; print(f"  omitido (confianza {r['confianza']}): {r['titulo'][:70]}"); continue
        src = R.resolver(r["origen"], CIL)
        clasif = r["clasificador"] if r["clasificador"] in ENUM_CLASIF or not ENUM_CLASIF else cfg.get("CLASIFICADOR_DEFECTO", "Informe")
        item = next((e for e in (r["tipo_zotero"], r["item_type"].title(), r["item_type"]) if e in ENUM_ITEM), "Report" if "Report" in ENUM_ITEM else r["item_type"])
        bid, ruta = buscar_existente(r["titulo"], src)
        if not aplicar:
            print(f"  SIM  {'reutilizar id ' + bid if bid else 'add'} «{r['titulo'][:64]}» · {r['autores']} · {clasif}/{item} · serie={r.get('serie','')}[{r.get('serie_index','')}] · tags={r['tags']}"); n += 1; continue
        if bid:
            print(f"  [=] ya en Calibre (id {bid}): se completan columnas y registro sin duplicar")
        else:
            out = run("add", "--title", r["titulo"], "--authors", r["autores"], "--tags", r["tags"], "--languages", "spa", "--automerge", "ignore", str(src))
            m = re.search(r"(?:Added book ids?|ID de libros? a[ñn]adidos?|ids?)\s*:\s*([0-9]+)", out.stdout + out.stderr, re.I)
            if not m:
                print(f"  [ERROR] add falló: {r['origen']} → {(out.stdout + out.stderr).strip()[:160]}"); continue
            bid = m.group(1); ruta = ruta_formato(bid)
        # una sola llamada con todos los campos (7 llamadas por libro eran ~40 min para 200 documentos)
        campos = ["--field", f"#clasificador:{clasif}", "--field", f"#item_type:{item}", "--field", f"title:{r['titulo']}", "--field", f"authors:{r['autores']}"]
        if r.get("editorial"): campos += ["--field", f"publisher:{r['editorial']}"]
        if r.get("fecha"): campos += ["--field", f"pubdate:{r['fecha']}-01-01 05:00:00+00:00"]   # medianoche local, como el resto de la biblioteca
        if r.get("identificador"): campos += ["--field", f"identifiers:{r['identificador']}"]
        if r.get("tags"): campos += ["--field", f"tags:{r['tags']}"]
        if r.get("serie"): campos += ["--field", f"series:{r['serie']}", "--field", f"series_index:{r.get('serie_index') or 1}"]
        sm = run("set_metadata", bid, *campos)
        if sm.returncode: print(f"  [WARN] set_metadata {bid}: {(sm.stdout + sm.stderr).strip()[:160]}")
        filas_led.append([HOY, r["sha256"], r["origen"], r["titulo"], r["autores"], r["tipo_zotero"], clasif, r["fecha"], r["editorial"], r["tags"], bid, ruta, "", "catalogado"])
        filas_cat.append([bid, r["autores"], r["titulo"], r["tipo_zotero"], clasif, r["editorial"], r["fecha"], r["identificador"], r["idioma"], r["tags"], r["confianza"], f"ingesta CIL {HOY}; {r['nota']}"])
        f_src = FICHAS / r["ficha"]
        if r.get("ficha") and f_src.is_file():   # sin ficha provisional, `FICHAS / ""` es la carpeta misma
            # la ficha canónica vive en catalogacion/fichas con su calibre_id; ingesta/fichas es temporal (D7)
            (CAT / "fichas" / f"{bid}_{r['ficha'].split('_', 1)[1]}").write_text(ficha_con_id(f_src.read_text(encoding="utf-8"), bid), encoding="utf-8")
            f_src.unlink()
        print(f"  [✓] id={bid} «{r['titulo'][:64]}» → {ruta}"); n += 1
    if aplicar and filas_led:
        with open(LED, "a", encoding="utf-8", newline="") as fh: csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(filas_led)
        with open(CAT / "resumen_catalogacion.tsv", "a", encoding="utf-8", newline="") as fh: csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(filas_cat)
        run("backup_metadata")   # solo los OPF de los libros tocados (dirty), no los 4 500
    print(f"[catalogar] {n} procesado(s) · {om} omitido(s) por confianza · {'APLICADO' if aplicar else 'simulación'}")


if __name__ == "__main__":
    main()
