"""lectura_base/lib/exportar.py — la vuelta: llevar a una herramienta los subrayados que tiene la base y ella no.

Candidata: una anotación viva, con libro, hoja y rectángulos (Zotero, KOReader y Okular la ubican por su posición), sin
presencia viva en el destino. El plan se calcula siempre (simular); escribir depende del destino:

- **Zotero** (`ESCRIBE`): por la puerta (`lib/escribir.puerta` con Zotero cerrado, el candado y el respaldo verificado;
  `lib/escribir_zotero.z_anadir_anotacion`), en el adjunto PDF del libro; tras el commit, `integrity_check`.
- **KOReader** (`ESCRIBE`, aprobado por el autor el 2026-11-17, §9.7): en el `.lua` del libro (`metadata.pdf.lua`), solo
  si KOReader ya abrió ese PDF y está cerrado; respaldo verificado, escritura atómica y relectura antes de reemplazar.
- **Okular** (`ESCRIBE`, aprobado el 2026-11-17): en su docdata (lo crea si falta), con Okular cerrado y el mismo respaldo;
  nunca en el PDF (cambiaría su MD5 de KOReader).
- **Yachay** (`ESCRIBE` desde el 2026-11-17, ya con su cliente y el token del autor): por su API (`cliente.resaltar`), con
  el origen de la anotación y su `uid` como `origen_id`, que Yachay usa para no duplicar. Admite un subrayado sin
  rectángulos (solo el texto); los de una hoja girada quedan en la base, como en las demás.

Lo escrito se apunta como presencia (`base.registrar_presencias`): la próxima lectura de esa herramienta lo reconoce como
la misma anotación y no la duplica.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from lectura_base.lib import base
from lectura_base.lib.biblioteca import Resolutor, giros, medidas

ESCRIBE = {"zotero", "koreader", "okular", "yachay"}
PENDIENTES: dict[str, str] = {}             # destinos que se simulan pero aún no se escriben
DESTINOS = ("zotero", "koreader", "okular", "yachay")


def candidatas(destino: str, ruta: Path | None = None, ids: set[int] | None = None) -> list[dict]:
    """Las anotaciones de la base que el destino no tiene, de los libros `ids` (todos si None)."""
    with base.lector(ruta) as c:
        if c is None:
            return []
        filas = c.execute("SELECT * FROM anotaciones WHERE borrada IS NULL AND calibre_id IS NOT NULL AND id NOT IN "
                          "(SELECT anotacion_id FROM presencias WHERE origen = ? AND ausente IS NULL) ORDER BY calibre_id, hoja",
                          (destino,)).fetchall()
        salida = [base.anotacion_publica(c, a) for a in filas if ids is None or a["calibre_id"] in ids]
    if destino != "yachay":
        salida = [a for a in salida if a["hoja"] and a["rects"]]
    return salida


def ubicables(cands: list[dict], resolutor: Resolutor) -> tuple[list[dict], list[str]]:
    """Solo lo que cada herramienta pondría en el mismo lugar: ni una hoja girada (cada una mide ahí a su modo) ni
    rectángulos fuera de la hoja. Lo demás queda en la base, con su aviso."""
    salida, giradas, fuera = [], 0, 0
    for a in cands:
        pdf = resolutor.pdf(a["calibre_id"])
        g = giros(pdf) if pdf else []
        if a["rects"] and a["hoja"] and 0 < a["hoja"] <= len(g) and g[a["hoja"] - 1]:
            giradas += 1
            continue
        if any(r[1] < -0.01 or r[2] < -0.01 or r[1] + r[3] > 1.01 or r[2] + r[4] > 1.01 for r in a["rects"]):
            fuera += 1
            continue
        salida.append(a)
    avisos = []
    if giradas:
        avisos.append(f"{giradas} anotaciones en hojas giradas quedan solo en la base (cada herramienta las mide a su modo)")
    if fuera:
        avisos.append(f"{fuera} anotaciones con rectángulos fuera de la hoja quedan solo en la base")
    return salida, avisos


def _sys_lib():
    lib = str(base.REPO / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)


# --------------------------------------------------------------------------------------------------------------- Zotero
def plan_zotero(cands: list[dict], ruta_zotero: Path, resolutor: Resolutor) -> tuple[list[dict], list[str]]:
    from lectura_base.lib.adaptadores import zotero as z
    plan, avisos = [], []
    if not ruta_zotero.is_file():
        return [], ["Zotero: no está zotero.sqlite"]
    with z.copia(ruta_zotero) as c:
        adjuntos = z.adjuntos_pdf(c, resolutor.biblioteca)
    for a in cands:
        adj = adjuntos.get(a["calibre_id"])
        if adj is None:
            continue
        hojas = medidas(adj["archivo"]) if adj["archivo"] else []
        fila = z.anotacion_de_zotero(a, hojas)
        if fila is None:
            avisos.append(f"Zotero: la anotación {a['uid']} (libro {a['calibre_id']}, hoja {a['hoja']}) no se ubica en su PDF")
            continue
        plan.append({"uid": a["uid"], "calibre_id": a["calibre_id"], "hoja": a["hoja"], "texto": a["texto"][:80],
                     "adjunto": adj["item_id"], "libreria": adj["library_id"], "fila": fila})
    return plan, avisos


def aplicar_zotero(plan: list[dict], ruta_zotero: Path, ruta: Path | None = None) -> list[dict]:
    """Escribe el plan en Zotero por la puerta y apunta las presencias. Devuelve [{uid, origen_id}]."""
    if not plan:
        return []
    _sys_lib()
    import escribir           # noqa: E402  (lib/escribir.py: la puerta)
    import escribir_zotero    # noqa: E402  (lib/escribir_zotero.py: las primitivas z_*)
    hechas = []
    with escribir.puerta("lectura_base", zotero=ruta_zotero):
        con = escribir_zotero.conexion_zotero(ruta_zotero)
        try:
            cur = con.cursor()
            for p in plan:
                clave = escribir_zotero.z_anadir_anotacion(cur, p["adjunto"], p["libreria"], p["fila"])
                hechas.append({"uid": p["uid"], "origen_id": clave})
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()
        if not escribir.integridad(ruta_zotero):
            raise RuntimeError("zotero.sqlite no pasó integrity_check tras escribir: restaurar el respaldo de la puerta")
    base.registrar_presencias(hechas, "zotero", aplicar=True, ruta=ruta)
    return hechas


# ------------------------------------------------------------------------------------------------------------- KOReader
def plan_koreader(cands: list[dict], resolutor: Resolutor, ruta: Path | None = None) -> tuple[list[dict], list[str]]:
    from lectura_base.lib.adaptadores import koreader as k
    carpeta = k.carpeta_koreader()
    if carpeta is None:
        return [], ["KOReader: no está su carpeta"]
    md5s = {}
    with base.lector(ruta) as c:
        if c is not None:
            md5s = {r["calibre_id"]: r["md5"] for r in c.execute("SELECT calibre_id, md5 FROM libros WHERE md5 != ''")}
    plan, avisos = [], []
    for a in cands:
        md5 = md5s.get(a["calibre_id"]) or (resolutor.ficha(a["calibre_id"]) or {}).get("md5", "")
        sidecar = k.sidecar_de(carpeta, md5)
        pdf = resolutor.pdf(a["calibre_id"])
        if sidecar is None or pdf is None:
            continue                                  # KOReader no ha abierto ese PDF: no hay dónde escribir
        e = k.entrada(a, medidas(pdf))
        if e is None:
            continue
        plan.append({"uid": a["uid"], "calibre_id": a["calibre_id"], "hoja": a["hoja"], "texto": a["texto"][:80],
                     "sidecar": str(sidecar), "entrada": e})
    return plan, avisos


def aplicar_koreader(plan: list[dict], ruta: Path | None = None, respaldos: Path | None = None) -> list[dict]:
    from lectura_base.lib.adaptadores import koreader as k
    _sys_lib()
    import escribir  # noqa: E402
    respaldos = respaldos or escribir.raiz_respaldos() / "lectura" / "koreader"
    hechas = []
    por_sidecar: dict[str, list[dict]] = {}
    for p in plan:
        por_sidecar.setdefault(p["sidecar"], []).append(p)
    for sidecar, ps in por_sidecar.items():
        ids = k.anadir(Path(sidecar), [p["entrada"] for p in ps], respaldos)
        hechas += [{"uid": p["uid"], "origen_id": i} for p, i in zip(ps, ids)]
    base.registrar_presencias(hechas, "koreader", aplicar=True, ruta=ruta)
    return hechas


# --------------------------------------------------------------------------------------------------------------- Okular
def plan_okular(cands: list[dict], resolutor: Resolutor) -> tuple[list[dict], list[str]]:
    from lectura_base.lib.adaptadores import okular as o
    plan = []
    for a in cands:
        pdf = resolutor.pdf(a["calibre_id"])
        if pdf is None:
            continue
        nodo = o.elemento(a)
        if nodo is None:
            continue
        plan.append({"uid": a["uid"], "calibre_id": a["calibre_id"], "hoja": a["hoja"], "texto": a["texto"][:80],
                     "pdf": str(pdf), "nodo": nodo})
    return plan, []


def aplicar_okular(plan: list[dict], ruta: Path | None = None, respaldos: Path | None = None) -> list[dict]:
    from lectura_base.lib.adaptadores import okular as o
    _sys_lib()
    import escribir  # noqa: E402
    respaldos = respaldos or escribir.raiz_respaldos() / "lectura" / "okular"
    por_pdf: dict[str, list[dict]] = {}
    for p in plan:
        por_pdf.setdefault(p["pdf"], []).append(p)
    hechas = []
    for pdf, ps in por_pdf.items():
        ids = o.anadir(Path(pdf), [p["nodo"] for p in ps], o.carpeta_docdata(), respaldos)
        hechas += [{"uid": p["uid"], "origen_id": i} for p, i in zip(ps, ids)]
    base.registrar_presencias(hechas, "okular", aplicar=True, ruta=ruta)
    return hechas


# --------------------------------------------------------------------------------------------------------------- Yachay
def plan_yachay(cands: list[dict]) -> tuple[list[dict], list[str]]:
    from lectura_base.lib.adaptadores import yachay as y
    plan = []
    for a in cands:
        cuerpo = y.a_resaltado(a)
        if cuerpo is not None:
            plan.append({"uid": a["uid"], "calibre_id": a["calibre_id"], "hoja": a["hoja"], "texto": a["texto"][:80], "cuerpo": cuerpo})
    return plan, []


def aplicar_yachay(plan: list[dict], cliente, ruta: Path | None = None) -> list[dict]:
    hechas = []
    for p in plan:
        r = cliente.resaltar(**p["cuerpo"])
        hechas.append({"uid": p["uid"], "origen_id": str((r or {}).get("id"))})
    base.registrar_presencias(hechas, "yachay", aplicar=True, ruta=ruta)
    return hechas


# ---------------------------------------------------------------------------------------------------------- orquestar
def exportar(destino: str, aplicar: bool = False, ids: set[int] | None = None, limite: int | None = None,
             ruta: Path | None = None, resolutor: Resolutor | None = None, cliente=None) -> dict:
    """{destino, plan, avisos, hechas, escribe}: lo que se llevaría (o se llevó) al destino."""
    if destino not in DESTINOS:
        raise ValueError(f"destino desconocido: {destino} (uno de {', '.join(DESTINOS)})")
    resolutor = resolutor or Resolutor()
    cands = candidatas(destino, ruta, ids)
    previos: list[str] = []
    cands, previos = ubicables(cands, resolutor)      # Yachay también: ahí la hoja girada caería en otro lugar
    if destino == "zotero":
        ruta_z = Path(os.environ.get("ZOTERO_DB") or Path(os.environ.get("ZOTERO_DIR") or Path.home() / "Zotero") / "zotero.sqlite")
        plan, avisos = plan_zotero(cands, ruta_z, resolutor)
    elif destino == "koreader":
        plan, avisos = plan_koreader(cands, resolutor, ruta)
    elif destino == "okular":
        plan, avisos = plan_okular(cands, resolutor)
    else:
        plan, avisos = plan_yachay(cands)
    avisos = previos + avisos
    if limite is not None:
        plan = plan[:limite]
    salida = {"destino": destino, "plan": plan, "avisos": avisos, "hechas": [], "escribe": destino in ESCRIBE}
    if not aplicar or not plan:
        return salida
    if destino not in ESCRIBE:
        raise PermissionError(PENDIENTES[destino])
    if destino == "zotero":
        salida["hechas"] = aplicar_zotero(plan, ruta_z, ruta)
    elif destino == "koreader":
        salida["hechas"] = aplicar_koreader(plan, ruta)
    elif destino == "okular":
        salida["hechas"] = aplicar_okular(plan, ruta)
    else:
        if cliente is None:
            raise RuntimeError("Yachay: sin cliente (la fase 3b) o sin token en el llavero")
        salida["hechas"] = aplicar_yachay(plan, cliente, ruta)
    return salida
