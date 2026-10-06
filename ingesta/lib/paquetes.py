#!/usr/bin/env python3
# paquetes.py — adjuntos de un paquete a la carpeta `data/` de su entrada + enlace.
#
# Un PAQUETE es una carpeta cuyos documentos forman UNA entrada de Calibre con
# adjuntos, no una entrada por archivo: los anexos del presupuesto del MEF son
# entre 13 y 24 por Ley, y catalogarlos sueltos daría ~192 entradas para ~10
# documentos (decisión de Edison, 2026-09-06).
#
# El documento PRINCIPAL se cataloga por el flujo normal (identificar →
# catalogar). Este módulo hace lo que falta: copia los adjuntos a la carpeta
# `data/` de esa entrada —la misma que usa datafw/pipeline/replicacion, que
# Calibre no registra en metadata.db, así que no altera la base bibliográfica— y
# retira cada adjunto dejándolo registrado (con su ruta dentro de data/) en el fuentes.yml de su proyecto, igual que
# `archivar` (FD4). En modo «enlace» lo sustituye por un enlace simbólico (anterior a FD4).
#
# Nada se borra sin haber comprobado antes que la copia existe y es idéntica.
import csv, filecmp, hashlib, importlib.util, json, os, shutil, sys
from datetime import date
from pathlib import Path

cfg = json.loads(sys.argv[1]); aplicar = "--aplicar" in sys.argv
MODO = cfg.get("ARCHIVAR_MODO", "manifiesto")
if cfg.get("MANIFIESTO_DIR"):
    sys.path.insert(0, cfg["MANIFIESTO_DIR"]); from lib import manifiesto as MAN   # noqa: E402
else:
    MAN = None


def retirar(archivo, bid, anexo="", sha="", nota=""):
    """Registra el archivo en el manifiesto de su proyecto y lo borra (modo manifiesto)."""
    if MAN is not None:
        raiz = MAN.raiz_de(archivo); MAN.agregar(raiz, MAN.origen_de(raiz, archivo), int(bid), anexo=anexo, sha=sha, nota=nota)
    Path(archivo).unlink()
LED = Path(cfg["LEDGER"]); BIB = Path(cfg["BIBLIOTECA"]); CIL = Path(cfg["CIL_DIR"])
CARPETA_ADJUNTOS = "data"
try:
    PAQUETES = json.loads(cfg.get("PAQUETES_JSON") or "[]")
except json.JSONDecodeError as exc:
    print(f"  [ERROR] PAQUETES_JSON mal formado: {exc}"); sys.exit(1)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


import re
_E = Path(__file__).resolve().parents[2] / "lib" / "escribir.py"   # la puerta de escritura en Calibre (F2)
_s = importlib.util.spec_from_file_location("escribir", _E); E = importlib.util.module_from_spec(_s); _s.loader.exec_module(E)
_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # rutas del ledger relativas a DOCS_ROOT (F5)
_s = importlib.util.spec_from_file_location("rutas", _R); R = importlib.util.module_from_spec(_s); _s.loader.exec_module(R)
def run(*a): return E.calibredb(BIB, *a)   # escritura solo con la puerta abierta (lib/escribir.sh)
if aplicar: E.exigir_puerta()

def libro_sin_principal(fam, carpeta, adjuntos, aplicar):
    """No hay Ley/PL descargado: el primer anexo hace de formato y el resto va a data/ (el texto de la ley se añade luego con add_format)."""
    sp = fam.get("sin_principal"); anio = carpeta.name
    if not sp or anio not in sp.get("leyes", {}): return None
    titulo = sp["titulo"].format(ley=sp["leyes"][anio], anio=anio); fmt = adjuntos[0]
    if not aplicar: print(f"  SIM  libro «{titulo[:70]}» con formato {fmt.name} (sin principal)"); return "SIM"
    out = run("add", "--title", titulo, "--authors", sp["autor"], "--languages", "spa", "--automerge", "ignore", str(fmt))
    m = re.search(r"(?:Added book ids?|ID de libros? a[ñn]adidos?|ids?)\s*:\s*([0-9]+)", out.stdout + out.stderr, re.I)
    if not m: print(f"  [ERROR] add falló: {(out.stdout + out.stderr)[:160]}"); return None
    bid = m.group(1)
    run("set_metadata", bid, "--field", f"series:{sp['serie']}", "--field", f"series_index:{anio}", "--field", f"tags:{sp['tags']}", "--field", f"#clasificador:{sp['clasificador']}",
        "--field", f"#item_type:{sp['item_type']}", "--field", f"identifiers:norma:ley_{sp['leyes'][anio]}", "--field", f"pubdate:{int(anio) - 1}-01-01 05:00:00+00:00", "--field", "publisher:Diario Oficial El Peruano")
    lst = run("list", "--search", f"id:{bid}", "--fields", "formats", "--for-machine")
    ruta = json.loads(lst.stdout)[0]["formats"][0]
    fila = [date.today().isoformat(), sha256(fmt), R.a_texto(fmt), titulo, sp["autor"], "Statute", sp["clasificador"], str(int(anio) - 1), "Diario Oficial El Peruano", sp["tags"], bid, R.a_texto(ruta), "", "archivado"]
    filas.append(fila); por_sha[fila[1]] = fila
    if MODO == "enlace":
        tmp = fmt.with_suffix(fmt.suffix + ".sustituyendo"); fmt.rename(tmp); os.symlink(ruta, fmt); tmp.unlink()
    else:
        retirar(fmt, bid, sha=fila[1])
    print(f"  [✓] libro «{titulo[:60]}» id={bid} (formato: {fmt.name}; el texto de la ley se añadirá con add_format)")
    return fila


# ledger: sha256 → fila (para localizar la entrada de Calibre del principal)
filas = list(csv.reader(open(LED, encoding="utf-8"), delimiter="\t"))
por_sha = {r[1]: r for r in filas[1:] if len(r) >= 14}

total_ok = total_pend = 0
for pk in PAQUETES:
    raiz = Path(pk["raiz"])
    if not raiz.is_dir():
        print(f"  [WARN] raíz de paquete inexistente: {raiz}"); continue
    for carpeta in sorted(d for d in raiz.iterdir() if d.is_dir()):
        archivos = sorted(f for f in carpeta.iterdir() if f.is_file() and not f.is_symlink() and not f.name.startswith("."))
        if not archivos: continue
        for fam in pk.get("familias", []):
            rp, ra = re.compile(fam["principal"], re.I), re.compile(fam["adjuntos"], re.I)
            principales = [f for f in archivos if rp.search(f.name) and f.suffix.lower() == ".pdf"]
            adjuntos = [f for f in archivos if ra.search(f.name)]
            etiqueta = f"{raiz.name}/{carpeta.name}"
            if not adjuntos: continue
            fila = None
            if principales:
                principal = principales[0]
                # el principal puede estar ya en Calibre desde otra ruta (marco legal del CIL) o como enlace tras archivar
                fila = por_sha.get(sha256(principal))
                if not fila:
                    enl = principal if principal.is_symlink() else None
                    print(f"  [PEND] {etiqueta}: el principal ({principal.name[:40]}) aún no está en Calibre"); total_pend += len(adjuntos); continue
            else:
                enlaces = [f for f in carpeta.iterdir() if f.is_symlink() and rp.search(f.name)]
                if enlaces:   # principal ya archivado (es un enlace a Calibre): se localiza por su nombre en el ledger
                    fila = next((r for r in filas[1:] if len(r) >= 14 and Path(r[2]).name == enlaces[0].name and r[10]), None)
                if not fila:
                    fila = libro_sin_principal(fam, carpeta, adjuntos, aplicar)
                    if fila == "SIM": total_ok += len(adjuntos); continue
                    if not fila: print(f"  [PEND] {etiqueta}: sin documento principal ({len(adjuntos)} adjuntos)"); total_pend += len(adjuntos); continue
                    adjuntos = adjuntos[1:]
            # ruta ACTUAL del libro (Calibre renombra la carpeta al cambiar título/autor; el ledger puede estar desfasado)
            lst = run("list", "--search", f"id:{fila[10]}", "--fields", "formats", "--for-machine")
            try:
                fmts = json.loads(lst.stdout)[0].get("formats") or []
                if fmts: fila[11] = R.a_texto(fmts[0])
            except Exception: pass
            destino_dir = R.resolver(fila[11], CIL).parent / CARPETA_ADJUNTOS
            for a in adjuntos:
                dst = destino_dir / a.name
                if dst.is_file() and filecmp.cmp(a, dst, shallow=False):
                    pass
                elif not aplicar:
                    print(f"  SIM  {etiqueta}/{a.name} → {destino_dir.name}/ de «{Path(fila[11]).parent.name[:50]}»"); total_ok += 1; continue
                else:
                    destino_dir.mkdir(parents=True, exist_ok=True); shutil.copy2(a, dst)
                    if not filecmp.cmp(a, dst, shallow=False):
                        print(f"  [ERROR] la copia difiere: {a.name}"); dst.unlink(missing_ok=True); continue
                if not aplicar: total_ok += 1; continue
                if MODO != "enlace":
                    retirar(a, fila[10], anexo=a.name, nota="adjunto del paquete"); total_ok += 1; continue
                tmp = a.with_suffix(a.suffix + ".sustituyendo"); a.rename(tmp)
                try:
                    os.symlink(dst, a)
                    if not filecmp.cmp(a, dst, shallow=False): raise OSError("el enlace no devuelve el mismo contenido")
                    tmp.unlink(); total_ok += 1
                except OSError as exc:
                    if a.is_symlink(): a.unlink()
                    tmp.rename(a); print(f"  [ERROR] {a.name}: {exc} — archivo restaurado")
            print(f"  [✓] {etiqueta}: {len(adjuntos)} adjuntos en data/ de «{Path(fila[11]).parent.name[:60]}»")

if aplicar:
    csv.writer(open(LED, "w", encoding="utf-8", newline=""), delimiter="\t", lineterminator="\n").writerows(filas)
print(f"[paquetes] {total_ok} adjunto(s) colocados · {total_pend} en espera · "
      f"{'APLICADO' if aplicar else 'simulación'}")
