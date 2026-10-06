#!/usr/bin/env python3
# archivar.py — retira el original de la zona de entrada una vez que su copia está en Calibre (idéntica por cmp y
# 'catalogado' en el ledger). Modo «manifiesto» (FD4, por defecto): se borra y queda registrado en el fuentes.yml de su
# proyecto; «enlace»: se sustituye por un enlace simbólico (anterior a FD4); «mover»: solo se borra (zona de aterrizaje).
import csv, filecmp, importlib.util, json, os, sys
from pathlib import Path
cfg = json.loads(sys.argv[1]); aplicar = "--aplicar" in sys.argv; modo = "mover" if "--mover" in sys.argv else cfg.get("ARCHIVAR_MODO", "manifiesto")
LED = Path(cfg["LEDGER"]); CIL = Path(cfg["CIL_DIR"]); n = 0
if cfg.get("MANIFIESTO_DIR"):
    sys.path.insert(0, cfg["MANIFIESTO_DIR"]); from lib import manifiesto as MAN   # noqa: E402
else:
    MAN = None
raices_tocadas = set()
_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # rutas del ledger relativas a DOCS_ROOT (F5)
_s = importlib.util.spec_from_file_location("rutas", _R); R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
_E = Path(__file__).resolve().parents[2] / "lib" / "escribir.py"   # la puerta de escritura en Calibre (F2)
_s = importlib.util.spec_from_file_location("escribir", _E); E = importlib.util.module_from_spec(_s); _s.loader.exec_module(E)
rows = list(csv.reader(open(LED, encoding="utf-8"), delimiter="\t"))

# Calibre renombra la carpeta del libro cuando cambian título o autor: la ruta del ledger (y los enlaces
# que apuntan a ella) caducan. Antes de archivar se refrescan las rutas por id y se reparan los enlaces rotos.
ids = sorted({r[10] for r in rows[1:] if len(r) > 10 and r[10].isdigit()})
actual = {}
if ids:
    out = E.calibredb(cfg["BIBLIOTECA"], "list", "-s", " or ".join(f"id:{i}" for i in ids), "-f", "formats", "--for-machine")
    try:
        for b in json.loads(out.stdout or "[]"):
            fm = [f for f in (b.get("formats") or []) if f.lower().endswith(".pdf")] or (b.get("formats") or [])
            if fm: actual[str(b["id"])] = R.a_texto(fm[0])   # relativa a DOCS_ROOT (F5)
    except Exception as e:
        print(f"  [WARN] no se pudieron refrescar las rutas desde Calibre: {e}")
rep = 0
for r in rows[1:]:
    if len(r) < 14 or r[10] not in actual: continue
    if r[11] != actual[r[10]]: r[11] = actual[r[10]]
    src = R.resolver(r[2], CIL)
    if src.is_symlink() and not src.exists():          # enlace roto → se vuelve a apuntar a la copia actual
        if aplicar: src.unlink(); os.symlink(R.resolver(r[11], CIL), src)
        rep += 1; print(f"  [↻] enlace {'reparado' if aplicar else 'a reparar'}: {r[2][-70:]}")
if rep: print(f"  rutas refrescadas; {rep} enlace(s) roto(s) {'reparado(s)' if aplicar else 'por reparar'}")

# Enlaces rotos hacia la biblioteca en CUALQUIER raíz de entrada (también los de adjuntos en data/): se reapuntan por el id de la carpeta «(NNNN)»
import re, sqlite3
BIB = Path(cfg["BIBLIOTECA"]); raices = [CIL] + [Path(r) for r in (cfg.get("INBOX_RAICES") or "").split("\n") if r.strip()]
try:
    con = sqlite3.connect(f"file:{BIB / 'metadata.db'}?mode=ro", uri=True); paths = {r[0]: r[1] for r in con.execute("select id, path from books")}; con.close()
except Exception: paths = {}
gen = 0
for root in raices:
    if not root.is_dir(): continue
    for p in root.rglob("*"):
        if not p.is_symlink() or p.exists(): continue
        m = re.search(r"/biblioteca/[^/]+/[^/]+ \((\d+)\)/(.*)$", os.readlink(p))
        if not m or int(m.group(1)) not in paths: continue
        real = BIB / paths[int(m.group(1))]; resto = m.group(2)
        if resto.startswith("data/"): nuevo = real / resto
        else:
            fm = sorted(real.glob("*.pdf")) or sorted(f for f in real.iterdir() if f.is_file() and f.suffix not in (".opf", ".jpg"))
            nuevo = fm[0] if fm else None
        if nuevo and nuevo.exists():
            if aplicar: p.unlink(); os.symlink(nuevo, p)
            gen += 1
if gen: print(f"  {gen} enlace(s) roto(s) hacia la biblioteca {'reapuntado(s)' if aplicar else 'por reapuntar'} por id de libro")
for r in rows[1:]:
    if len(r) < 14 or r[13] != "catalogado": continue
    # El origen es relativo al CIL, o absoluto si vino de una raíz externa
    # (datafw). En ambos casos el enlace queda EN SU SITIO: nada se mueve.
    src, dst = R.resolver(r[2], CIL), R.resolver(r[11], CIL)
    if src.is_symlink() or not src.is_file(): continue
    if not dst.is_file(): print(f"  [WARN] copia de Calibre ausente: {dst}"); continue
    if not filecmp.cmp(src, dst, shallow=False): print(f"  [WARN] difiere del original (¿convertido?): {r[2]}"); continue
    if not aplicar: print(f"  SIM  {r[2]} → {modo} → {dst.relative_to(cfg['BIBLIOTECA']) if str(dst).startswith(cfg['BIBLIOTECA']) else dst}"); n += 1; continue
    en_entrada = "/scripts_for_fuentes/entrada/" in str(src)      # zona de aterrizaje: se borra sin manifiesto (el proyecto hace el suyo con --bib)
    # PRIMERO el manifiesto, DESPUES el borrado: si registrar falla, el original
    # sigue en su sitio (el 2026-09-11 dos PDF de una tesis se borraron sin quedar
    # registrados porque el orden era el inverso).
    if modo == "manifiesto" and MAN is not None and not en_entrada:
        raiz = MAN.raiz_de(src); MAN.agregar(raiz, MAN.origen_de(raiz, src), int(r[10]), sha=r[1]); raices_tocadas.add(raiz)
    src.unlink()
    if modo == "enlace": os.symlink(dst, src)
    r[13] = "archivado"; n += 1; print(f"  [✓] {modo}: {r[2]}")
if aplicar: csv.writer(open(LED, "w", encoding="utf-8", newline=""), delimiter="\t", lineterminator="\n").writerows(rows)
for raiz in sorted(raices_tocadas): print(f"  manifiesto actualizado: {raiz / MAN.config.NOMBRE}")
print(f"[archivar] {n} documento(s) · {'APLICADO' if aplicar else 'simulación'}")
