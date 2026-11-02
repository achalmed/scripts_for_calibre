"""biblioteca_app/servicios/catalogo.py — el catálogo bibliográfico de Biblioteca Studio, sin Qt (reingeniería B2, B5,
B6 y B8; `docs/reingenieria.md`).

- `leer(calibre_db, indice)`: cada libro de Calibre con sus metadatos editoriales (año, serie y número, etiquetas,
  editorial, idiomas, identificadores, tipo, páginas, descripción) y su lectura en KOReader (`#ko_progfloat`,
  `#ko_status`, `#ko_tiempo`, `#ko_lastmod`), que `lib/indice.editorial` lee de `metadata.db` en SOLO LECTURA (la
  ventana no abre las bases), unidos al índice (clave de Zotero, clave para citar, fichas, nota). El JSON del índice y
  su orden no cambian: son contrato de los complementos.
- `consulta(texto)` y `cumple(libro, terminos)`: la búsqueda avanzada (`titulo:`, `autor:`, `año:` o un rango,
  `serie:`, `etiqueta:`, `id:`, `clave:`; palabras sueltas en todo; comillas para agrupar), sin tildes ni mayúsculas.
- `facetas(libros)`: los valores de los filtros (colección = la serie, autor, década, tipo) con su cuenta.
- `bandejas(libros, entrada, fichas)`: las bandejas de trabajo y lo que hay en cada una.
"""
from __future__ import annotations

import re
import shlex
import unicodedata
from html import unescape
from pathlib import Path

CAMPOS = {"titulo": "titulo", "título": "titulo", "autor": "autor", "autores": "autor", "año": "año", "ano": "año", "anio": "año",
          "serie": "serie", "coleccion": "serie", "colección": "serie", "etiqueta": "etiqueta", "etiquetas": "etiqueta", "tag": "etiqueta",
          "id": "id", "isbn": "id", "doi": "id", "clave": "clave", "tipo": "tipo"}
ORDENES = (("titulo", "Título"), ("autor", "Autor"), ("año", "Año"), ("añadido", "Recién añadidos"))
BANDEJAS = (
    ("clasificar", "Pendientes de clasificar", "view-catalog",
     "Lo que entró y aún no está catalogado en Calibre, y los libros sin tipo", "entrada", "catalogar"),
    ("fichas", "Fichas incompletas", "document-edit-verify",
     "Fichas canónicas sin verificar y fichas que no encuentran su libro", "fichas", "fichas_estado"),
    ("sin_clave", "Sin clave para citar", "tag",
     "Enlazados con Zotero pero sin clave (la pone Better BibTeX en Zotero)", "sincronizar", "zotero_calibre"),
    ("sin_zotero", "Sin Zotero", "zotero",
     "Libros de Calibre que Zotero todavía no tiene enlazados", "sincronizar", "enlazar_zotero"),
    ("sin_portada", "Sin portada", "image-missing",
     "Libros sin cover.jpg en su carpeta de Calibre", "catalogar", "catalogacion"),
)


def _plano(texto) -> str:
    """Sin tildes ni mayúsculas (para buscar «economia» y hallar «Economía»)."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return t.casefold()


_CAMPOS_PLANOS = {_plano(k): v for k, v in CAMPOS.items()}


def _año(pubdate) -> int | None:
    """Calibre guarda «sin fecha» como el año 101."""
    m = re.match(r"(\d{4})", str(pubdate or ""))
    if not m:
        return None
    a = int(m.group(1))
    return a if a > 1000 else None


def _texto_html(html: str) -> str:
    """La descripción de Calibre es HTML: texto plano con sus párrafos."""
    t = re.sub(r"(?i)<\s*(br|/p|/div|/li)\s*/?>", "\n", html or "")
    t = unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _fecha(valor) -> str:
    return str(valor or "")[:10]


def _indice_lib():
    """`lib/indice.py` del repo (la lectura de las bases en solo lectura vive en `lib/`, nunca en la ventana)."""
    import importlib.util
    ruta = Path(__file__).resolve().parents[3] / "lib" / "indice.py"
    spec = importlib.util.spec_from_file_location("biblioteca_indice", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _numero(v, tipo=float):
    try:
        return tipo(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def leer(calibre_db: Path, indice: dict | None = None, biblioteca: Path | None = None) -> dict:
    """{libros: [ … ], inmutable: bool}: cada libro con lo que la ficha editorial y los filtros necesitan
    (`lib/indice.editorial`, en solo lectura) unido al índice."""
    indice = indice or {"libros": {}}
    biblioteca = Path(biblioteca) if biblioteca else Path(calibre_db).parent
    crudo = _indice_lib().editorial(Path(calibre_db))
    del_indice = indice.get("libros", {})
    libros = []
    for b, d in crudo["libros"].items():
        i = del_indice.get(str(b), {})
        portada = (biblioteca / d["carpeta"] / "cover.jpg") if d["carpeta"] else None
        hay_portada = bool(d["has_cover"]) if d["has_cover"] is not None else bool(portada and portada.is_file())
        prog = _numero(d.get("ko_progfloat"))
        minutos = _numero(d.get("ko_tiempo"), int)
        paginas = _numero(d.get("pages"), int)
        libros.append({
            "id": str(b), "titulo": d["titulo"], "autores": d["autores"], "carpeta": d["carpeta"],
            "año": _año(d["pubdate"]), "serie": d["serie"], "serie_indice": _numero(d["serie_indice"]) if d["serie"] else None,
            "etiquetas": d["etiquetas"], "editorial": d["editorial"], "idiomas": d["idiomas"], "identificadores": d["identificadores"],
            "descripcion": _texto_html(d["descripcion"]), "tipo": str(d.get("item_type") or d.get("clasificador") or ""),
            "clasificador": str(d.get("clasificador") or ""), "paginas": paginas or None,
            "formatos": d["formatos"], "portada": hay_portada, "ruta_portada": str(portada) if portada else "",
            "orden_titulo": d["orden_titulo"] or d["titulo"], "orden_autor": d["orden_autor"] or " & ".join(d["autores"]),
            "añadido": _fecha(d["añadido"]),
            "ko_progreso": max(0.0, min(1.0, prog)) if prog is not None else None, "ko_estado": str(d.get("ko_status") or ""),
            "ko_minutos": minutos or 0, "ko_ultima": _fecha(d.get("ko_lastmod")),
            "zotero_key": i.get("zotero_key", ""), "clave": i.get("clave", ""), "fichas": list(i.get("fichas") or []),
            "nota": i.get("apuntes") or i.get("nota") or "", "nota_enlazada": bool(i.get("apuntes")),
            "en_indice": bool(i),
        })
    return {"libros": libros, "inmutable": crudo["inmutable"]}


# ---------------------------------------------------------------------------- la búsqueda avanzada
def consulta(texto: str) -> list[tuple[str, str]]:
    """[(campo o "", valor)] de «autor:quispe año:2019-2021 "ciudades pequeñas"»; un campo desconocido busca en todo."""
    try:
        partes = shlex.split(texto or "")
    except ValueError:                       # comillas sin cerrar: se buscan las palabras tal cual
        partes = (texto or "").split()
    terminos = []
    for p in partes:
        campo, sep, valor = p.partition(":")
        if sep and _plano(campo) in _CAMPOS_PLANOS and valor:
            terminos.append((_CAMPOS_PLANOS[_plano(campo)], _plano(valor)))
        elif p.strip():
            terminos.append(("", _plano(p)))
    return terminos


def _en_año(año: int | None, valor: str) -> bool:
    if año is None:
        return False
    m = re.fullmatch(r"(\d{4})?\s*-\s*(\d{4})?", valor)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) <= año <= int(m.group(2) or 9999)
    return str(año).startswith(valor)


def cumple(libro: dict, terminos: list[tuple[str, str]]) -> bool:
    """¿El libro cumple todos los términos? (y lógico)."""
    for campo, valor in terminos:
        if campo == "titulo":
            ok = valor in _plano(libro["titulo"])
        elif campo == "autor":
            ok = any(valor in _plano(a) for a in libro["autores"])
        elif campo == "año":
            ok = _en_año(libro["año"], valor)
        elif campo == "serie":
            ok = valor in _plano(libro["serie"])
        elif campo == "etiqueta":
            ok = any(valor in _plano(t) for t in libro["etiquetas"])
        elif campo == "id":
            ok = (valor == libro["id"] or valor == _plano(libro["zotero_key"])
                  or any(valor in _plano(v) for v in libro["identificadores"].values()))
        elif campo == "clave":
            ok = valor in _plano(libro["clave"])
        elif campo == "tipo":
            ok = valor in _plano(libro["tipo"])
        else:
            ok = (valor in _plano(libro["titulo"]) or any(valor in _plano(a) for a in libro["autores"]) or valor in _plano(libro["serie"])
                  or any(valor in _plano(t) for t in libro["etiquetas"]) or valor in _plano(libro["clave"]) or valor == libro["id"]
                  or any(valor == _plano(v) for v in libro["identificadores"].values()))
        if not ok:
            return False
    return True


# ------------------------------------------------------------------------------- facetas y orden
def decada(año: int | None) -> str:
    return f"{año // 10 * 10}–{año // 10 * 10 + 9}" if año else "sin año"


def facetas(libros: list[dict], tope: int = 400) -> dict[str, list[dict]]:
    """{coleccion, autor, decada, tipo: [{valor, n}]}: por cuenta descendente (las décadas, en orden); a lo sumo `tope`."""
    cuentas: dict[str, dict[str, int]] = {"coleccion": {}, "autor": {}, "decada": {}, "tipo": {}}
    for l in libros:
        if l["serie"]:
            cuentas["coleccion"][l["serie"]] = cuentas["coleccion"].get(l["serie"], 0) + 1
        for a in l["autores"]:
            cuentas["autor"][a] = cuentas["autor"].get(a, 0) + 1
        d = decada(l["año"])
        cuentas["decada"][d] = cuentas["decada"].get(d, 0) + 1
        t = l["tipo"] or "sin tipo"
        cuentas["tipo"][t] = cuentas["tipo"].get(t, 0) + 1
    salida = {}
    for k, v in cuentas.items():
        if k == "decada":                    # de la más reciente a la más antigua; «sin año» al final
            orden = sorted((x for x in v.items() if x[0] != "sin año"), reverse=True) + [x for x in v.items() if x[0] == "sin año"]
        else:
            orden = sorted(v.items(), key=lambda kv: (-kv[1], _plano(kv[0])))
        salida[k] = [{"valor": a, "n": n} for a, n in orden[:tope]]
    return salida


def cumple_filtros(libro: dict, filtros: dict[str, str]) -> bool:
    """Los filtros de la izquierda: colección (serie), autor, década y tipo; vacío = todos."""
    if filtros.get("coleccion") and libro["serie"] != filtros["coleccion"]:
        return False
    if filtros.get("autor") and filtros["autor"] not in libro["autores"]:
        return False
    if filtros.get("decada") and decada(libro["año"]) != filtros["decada"]:
        return False
    if filtros.get("tipo") and (libro["tipo"] or "sin tipo") != filtros["tipo"]:
        return False
    return True


def clave_orden(orden: str):
    """La función de orden de `sorted` para cada criterio de `ORDENES`."""
    if orden == "autor":
        return lambda l: (_plano(l["orden_autor"]) or "~", _plano(l["orden_titulo"]))
    if orden == "año":
        return lambda l: (-(l["año"] or 0), _plano(l["orden_titulo"]))
    if orden == "añadido":
        return lambda l: (l["añadido"] == "", "".join(chr(0x10FFFF - ord(ch)) for ch in l["añadido"]), _plano(l["orden_titulo"]))
    return lambda l: _plano(l["orden_titulo"])


# ------------------------------------------------------------------------------------- bandejas
def ficha_completa(libro: dict, estados: dict[str, str]) -> bool:
    """Una ficha canónica y verificada (por script o a mano)."""
    return bool(libro["fichas"]) and all(estados.get(Path(f).name, "pendiente").startswith("verificada") for f in libro["fichas"])


def bandejas(libros: list[dict], entrada: list[dict], fichas: list[dict]) -> dict[str, dict]:
    """{bandeja: {libros: [ids], otros: [filas de la entrada], n}}: lo que hay que trabajar en cada una."""
    estados = {f["ficha"]: f.get("verificacion", "pendiente") for f in fichas}
    ids = {l["id"] for l in libros}
    sin_catalogar = [dict(e, seccion="En la zona de entrada") for e in entrada if e.get("paso") in ("recibido", "identificado")]
    salida = {
        "clasificar": {"libros": [l["id"] for l in libros if not l["tipo"]], "otros": sin_catalogar},
        "fichas": {"libros": [l["id"] for l in libros if l["fichas"] and not ficha_completa(l, estados)],
                   "otros": [dict(f, paso=f.get("verificacion", ""), archivo=f["ficha"], origen=f"catalogacion/fichas/{f['ficha']}",
                                  seccion="Fichas sin su libro en Calibre")
                             for f in fichas if not str(f.get("calibre_id", "")).strip() or str(f["calibre_id"]) not in ids]},
        "sin_clave": {"libros": [l["id"] for l in libros if l["zotero_key"] and not l["clave"]], "otros": []},
        "sin_zotero": {"libros": [l["id"] for l in libros if not l["zotero_key"]], "otros": []},
        "sin_portada": {"libros": [l["id"] for l in libros if not l["portada"]], "otros": []},
    }
    for v in salida.values():
        v["n"] = len(v["libros"]) + len(v["otros"])
    return salida
