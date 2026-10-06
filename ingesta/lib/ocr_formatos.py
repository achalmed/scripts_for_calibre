#!/usr/bin/env python3
# ocr_formatos.py — los X.ocr.pdf (salida de datafw/pipeline/documentos ocr) no son documentos nuevos: son el
# mismo documento con capa de texto. Cada uno pasa a ser el FORMATO PDF del libro de Calibre de X.pdf (sustituye
# al escaneo); el .ocr.pdf y el original X.pdf se retiran y quedan registrados en el fuentes.yml de su proyecto (FD4;
# en modo «enlace» quedan como enlaces a la copia de Calibre).
# Uso: ocr_formatos.py <cfg_json> [--aplicar] -- archivo.ocr.pdf ...
import csv, importlib.util, json, os, re, sys
from pathlib import Path
cfg = json.loads(sys.argv[1]); aplicar = "--aplicar" in sys.argv
MODO = cfg.get("ARCHIVAR_MODO", "manifiesto")
if cfg.get("MANIFIESTO_DIR"):
    sys.path.insert(0, cfg["MANIFIESTO_DIR"]); from lib import manifiesto as MAN   # noqa: E402
else:
    MAN = None
ocrs = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
LED = Path(cfg["LEDGER"]); CIL = Path(cfg["CIL_DIR"]); BIB = Path(cfg["BIBLIOTECA"])
_E = Path(__file__).resolve().parents[2] / "lib" / "escribir.py"   # la puerta de escritura en Calibre (F2)
_s = importlib.util.spec_from_file_location("escribir", _E); E = importlib.util.module_from_spec(_s); _s.loader.exec_module(E)
_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # rutas del ledger relativas a DOCS_ROOT (F5)
_s = importlib.util.spec_from_file_location("rutas", _R); R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
def run(*a): return E.calibredb(BIB, *a)   # escritura solo con la puerta abierta (lib/escribir.sh)
if aplicar: E.exigir_puerta()
rows = list(csv.reader(open(LED, encoding="utf-8"), delimiter="\t")); cab = rows[0]
por_base = {}
for r in rows[1:]:
    if len(r) < 14 or not r[10]: continue
    por_base.setdefault(Path(r[2]).name, r)
n = sin = 0
for o in ocrs:
    o = Path(o)
    if o.is_symlink() or not o.is_file(): continue
    # X.ocr.pdf, X_ocr_buscable.pdf, X_ocr.pdf, X_texto.pdf → versión con texto (pasa a ser el formato);  X_escaneado.pdf → solo enlace
    mv = re.match(r"^(.*?)(\.ocr|_ocr_buscable|_ocr|_texto|_escaneado)$", o.stem)
    if not mv: continue
    base = mv.group(1) + o.suffix; con_texto = mv.group(2) != "_escaneado"; r = por_base.get(base)
    if not r:
        sin += 1; print(f"  [?] sin libro en el ledger para {o.name}: catalogue primero {base}"); continue
    bid, ruta = r[10], R.resolver(r[11], CIL)
    if not aplicar: print(f"  SIM  id {bid}: {'formato PDF ←' if con_texto else 'solo enlace de'} {o.name}; enlaces: {o.name} y {base}"); n += 1; continue
    if con_texto:
        out = run("add_format", bid, str(o))
        if out.returncode: print(f"  [ERROR] add_format {bid}: {(out.stdout + out.stderr).strip()[:160]}"); continue
    lst = run("list", "--search", f"id:{bid}", "--fields", "formats", "--for-machine")
    try: ruta = Path((json.loads(lst.stdout)[0].get("formats") or [str(ruta)])[0])
    except Exception: pass
    # FD4: sin enlaces; el OCR y el original quedan registrados en el fuentes.yml de su proyecto (modo «enlace» solo por compatibilidad)
    src = R.resolver(r[2], CIL)
    if MODO == "enlace":
        o.unlink(); os.symlink(ruta, o)
        if src.is_file() and not src.is_symlink(): src.unlink(); os.symlink(ruta, src)
    else:
        for f in (o, src):
            if f.is_symlink() or f.is_file():
                if MAN is not None:
                    raiz = MAN.raiz_de(f); MAN.agregar(raiz, MAN.origen_de(raiz, f), int(bid), sha=r[1] if f == src else "", nota="" if f == src else "versión OCR: formato del mismo libro")
                f.unlink()
    r[11] = R.a_texto(ruta); r[13] = "archivado"; n += 1; print(f"  [✓] id {bid}: formato OCR de {o.name}; {'enlazados' if MODO == 'enlace' else 'en el manifiesto'} {o.name} y {base}")
if aplicar: csv.writer(open(LED, "w", encoding="utf-8", newline=""), delimiter="\t", lineterminator="\n").writerows(rows)
print(f"[ocr] {n} formato(s) · {sin} sin libro · {'APLICADO' if aplicar else 'simulación'}")
