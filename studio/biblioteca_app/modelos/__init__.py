"""biblioteca_app/modelos — las filas de las tablas de Biblioteca Studio (libros, descargas, entrada, catalogación, fichas,
manifiestos, coherencia, respaldos, tareas automáticas), sin Qt (se prueban solas); los modelos de Qt son los
genéricos de `gui_comun.modelos` (`ModeloTabla`, `ModeloFiltrado`)."""
from __future__ import annotations

from pathlib import Path

COLUMNAS = {
    "libros": [("Título", "titulo"), ("Autores", "autores"), ("Calibre", "id"), ("Zotero", "zotero_key"), ("Clave para citar", "clave"),
               ("Fichas", "fichas"), ("Nota", "nota")],
    "adquirir": [("Fecha", "fecha"), ("Fuente", "fuente"), ("Referencia", "referencia"), ("Título", "titulo"), ("Archivo", "archivo"),
                 ("Estado", "estado")],
    "entrada": [("Archivo", "archivo"), ("Paso", "paso"), ("Título", "titulo"), ("Confianza", "confianza"), ("Calibre", "calibre_id"),
                ("Origen", "origen")],
    "catalogar": [("Calibre", "id"), ("Autores", "autores"), ("Título", "titulo"), ("Tipo", "tipo_zotero"), ("Fecha", "fecha"),
                  ("Confianza", "confianza"), ("Ficha", "ficha")],
    "fichas": [("Ficha", "ficha"), ("Calibre", "calibre_id"), ("Título", "titulo"), ("Proyecto", "proyecto"), ("Verificación", "verificacion")],
    "manifiestos": [("Proyecto", "proyecto"), ("Carpeta", "carpeta"), ("Entradas", "entradas"), ("Sin libro", "sin_libro"), ("Generado", "generado")],
    "sincronizar": [("Comprobación", "comprobacion"), ("Resultado", "resultado"), ("Lo resuelve", "resuelve")],
    "puerta": [("Suite", "suite"), ("Respaldos", "n"), ("Último", "ultimo"), ("Carpeta", "carpeta")],
    "tareas": [("Unidad", "unidad"), ("Estado", "activo"), ("Próxima", "proxima"), ("Última", "ultima"), ("Resultado", "resultado")],
}
COLUMNAS_FICHAS_LIBRO = [("Ficha", "ficha")]
ICONO_LIBRO = "folder-book"
FILTROS_LIBROS = (("todos", "Todos"), ("sin_zotero", "Sin Zotero"), ("sin_clave", "Sin clave para citar"), ("sin_ficha", "Sin ficha"),
                  ("sin_nota", "Sin nota enlazada"))


def cumple_filtro(libro: dict, filtro: str) -> bool:
    if filtro == "sin_zotero":
        return not libro.get("zotero_key")
    if filtro == "sin_clave":
        return bool(libro.get("zotero_key")) and not libro.get("clave")
    if filtro == "sin_ficha":
        return not libro.get("fichas")
    if filtro == "sin_nota":
        return not libro.get("apuntes")
    return True


def fila_libro(d: dict) -> dict:
    """Una fila de la tabla Libros desde una entrada del índice (`datos.libros`)."""
    nota = d.get("apuntes") or ""
    existe = bool(nota and Path(nota).is_file()) or bool(d.get("nota") and Path(d["nota"]).is_file())
    fichas = d.get("fichas") or []
    return {"titulo": d.get("titulo", ""), "autores": " · ".join(d.get("autores") or []), "id": str(d.get("id", "")),
            "zotero_key": d.get("zotero_key") or "—", "clave": d.get("clave") or "—", "fichas": str(len(fichas)) if fichas else "—",
            "nota": "enlazada" if nota else ("existe" if existe else "—"),
            "nivel": "positivo" if d.get("zotero_key") and d.get("clave") else ("neutro" if d.get("zotero_key") else "inactivo"),
            "icono": ICONO_LIBRO, "habilitado": True, "datos": d,
            "crudo": {"id": int(d["id"]) if str(d.get("id", "")).isdigit() else 0, "fichas": len(fichas)}}


def contar_libros(lista: list[dict]) -> dict:
    """Cuántos libros hay por filtro (los contadores de la navegación y la barra de estado)."""
    return {f: sum(1 for d in lista if cumple_filtro(d, f)) for f, _t in FILTROS_LIBROS}


def resumen_libros(c: dict) -> str:
    n = c.get("todos", 0)
    if n == 0:
        return "Sin índice de libros: Actualizar el índice (Ctrl+R)"
    partes = [f"{n} libro" + ("" if n == 1 else "s")]
    for clave, texto in (("sin_zotero", "sin Zotero"), ("sin_clave", "sin clave para citar"), ("sin_ficha", "sin ficha"), ("sin_nota", "sin nota")):
        if c.get(clave):
            partes.append(f"{c[clave]} {texto}")
    return " · ".join(partes)


def fila_descarga(f: dict) -> dict:
    return {**f, "nivel": {"descargado": "positivo", "error": "negativo"}.get(f.get("estado", ""), "neutro"), "icono": "download",
            "habilitado": True}


def fila_entrada(f: dict) -> dict:
    return {**f, "icono": "application-pdf" if f.get("archivo", "").lower().endswith(".pdf") else "text-x-generic",
            "habilitado": f.get("existe", True), "crudo": {"bytes": f.get("bytes", 0)}}


def fila_catalogacion(f: dict) -> dict:
    return {**f, "icono": ICONO_LIBRO, "habilitado": True, "crudo": {"id": int(f["id"]) if str(f.get("id", "")).isdigit() else 0}}


def fila_ficha(f: dict) -> dict:
    return {**f, "icono": "document-edit-verify", "habilitado": True,
            "crudo": {"calibre_id": int(f["calibre_id"]) if str(f.get("calibre_id", "")).isdigit() else 0}}


def fila_manifiesto(f: dict) -> dict:
    return {**f, "entradas": str(f.get("entradas", 0)), "sin_libro": str(f.get("sin_libro", 0)) if f.get("sin_libro") else "—",
            "icono": "view-list-text", "habilitado": True, "crudo": {"entradas": f.get("entradas", 0), "sin_libro": f.get("sin_libro", 0)}}


def fila_coherencia(c: dict, titulo_operacion: str) -> dict:
    return {**c, "resuelve": titulo_operacion, "icono": {"positivo": "dialog-ok-apply", "negativo": "dialog-cancel"}.get(c.get("nivel", ""), "dialog-information"),
            "habilitado": True, "crudo": {"resultado": c.get("cuantos", 0)}}


def fila_respaldo(r: dict) -> dict:
    return {**r, "n": str(r.get("n", 0)), "icono": "backup", "habilitado": True, "crudo": {"n": r.get("n", 0), "ultimo": r.get("ultimo_ts", 0)}}


def fila_tarea(t: dict) -> dict:
    return {**t, "icono": "chronometer", "habilitado": t.get("activo") != "no instalado"}


def campos_elemento(fila: dict, columnas: list[tuple[str, str]]) -> list[dict]:
    """[{etiqueta, valor}] con las columnas de la tabla y, después, lo demás que la fila trae (para la pestaña Elemento)."""
    ocultas = {"nivel", "icono", "habilitado", "crudo", "datos", "afectados", "existe", "ultimo_ts", "bytes", "cuantos"}
    vistos = set()
    salida = []
    for etiqueta, clave in columnas:
        vistos.add(clave)
        salida.append({"etiqueta": etiqueta, "valor": str(fila.get(clave, "") or "—")})
    for clave, valor in fila.items():
        if clave in vistos or clave in ocultas or valor in ("", None):
            continue
        salida.append({"etiqueta": clave.replace("_", " ").capitalize(), "valor": str(valor)})
    return salida
