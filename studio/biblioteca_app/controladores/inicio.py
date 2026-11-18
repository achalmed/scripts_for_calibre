"""biblioteca_app/controladores/inicio.py — el área «Inicio» (rediseño del 2026-11-18, decisiones §9.9): «Esto es lo de hoy».

Objetivo: abrir la ventana y saber qué hacer: cuatro cifras (leído esta semana, subrayados nuevos de los últimos siete
  días, fichas por revisar y pendientes de las bandejas), «Seguir leyendo» (hasta tres libros en curso con su avance en
  la herramienta donde se leyeron por última vez) y «Siguiente paso» (hasta cuatro filas, cada una con el botón que lleva
  a su lugar).
Método: todo se lee de lo que ya leen las otras áreas: la base de lectura (`lectura_base/lib/consulta.py`: `semanas`,
  `nuevas`, `en_curso`, `subrayados`), las bandejas (`libros.contadores`), las fichas de los escritos y el repaso
  (`controladores/fichas.py`). Un subrayado está «por fichar» si ninguna ficha de su libro contiene su texto.
Límite: lo que no tiene datos no se muestra (sin base de lectura no hay «Seguir leyendo» ni horas); nada se inventa. Solo
  lee: los botones llevan a otra área, a una bandeja, al diálogo «Nueva ficha» o a LaTeX Studio.
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

from gui_comun.qt import QObject, Property, Signal, Slot

from biblioteca_app.controladores.lectura import COLORES, NOMBRES, consulta

SUMAN_PENDIENTES = ("clasificar", "fichas", "sin_clave", "sin_zotero")   # las bandejas que se cuentan como pendientes
SEMANA = 7 * 86400


def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def por_fichar(subrayados: list[dict], fichas: list[dict]) -> dict[int, list[dict]]:
    """{calibre_id: [subrayados sin ficha]}: los que ninguna ficha de su libro contiene (ni ellos a la ficha)."""
    citas: dict[str, list[str]] = {}
    for f in fichas:
        for texto in {f.get("literal") or "", f.get("cita") or ""} - {""}:      # el literal y, de una paráfrasis, la paráfrasis
            if f.get("calibreId"):
                citas.setdefault(str(f["calibreId"]), []).append(_normal(texto))
    salida: dict[int, list[dict]] = {}
    for s in subrayados:
        texto = _normal(s["texto"])
        if len(texto) < 12:
            continue
        cabeza = texto[:60]
        if any(cabeza in c or c[:60] in texto for c in citas.get(str(s["calibre_id"]), [])):
            continue
        salida.setdefault(int(s["calibre_id"]), []).append(s)
    return salida


def fuentes_nuevas(escritos: list[dict], ahora: float | None = None) -> dict | None:
    """El escrito cuyo `fuentes/fuentes.yml` cambió en la última semana (el más reciente), con su documento principal."""
    ahora = ahora or time.time()
    mejor, cuando = None, 0.0
    for e in escritos:
        y = Path(e.get("carpeta") or "") / "fuentes" / "fuentes.yml"
        try:
            m = y.stat().st_mtime
        except OSError:
            continue
        if ahora - m <= SEMANA and m > cuando and e.get("principal"):
            mejor, cuando = e, m
    return mejor


class Inicio(QObject):
    cambiado = Signal()

    def __init__(self, espacio, libros, lectura, fichas, parent=None):
        super().__init__(parent)
        self.espacio, self.libros, self.lectura, self.fichas = espacio, libros, lectura, fichas
        self._cifras: list = []
        self._seguir: list = []
        self._pasos: list = []
        for senal in (libros.cambiado, lectura.cambiado, fichas.cambiado, fichas.repasoCambiado):
            senal.connect(self.recargar)
        self.recargar()

    # ------------------------------------------------------------------ leer
    @Slot()
    def recargar(self) -> None:
        ruta = self.lectura.ruta()
        hay_base = self.lectura.hayBase
        cifras = []
        if hay_base:
            try:
                semana = consulta.semanas(1, ruta)[-1]
                nuevas = consulta.nuevas(7, ruta)
            except Exception:  # noqa: BLE001 — una base a medio escribir: la próxima señal lo vuelve a leer
                semana, nuevas = None, None
            if semana is not None:
                cifras.append({"valor": consulta.texto_duracion(semana["segundos"]) if semana["segundos"] else "0 h",
                               "rotulo": "Leído esta semana", "accion": "area", "datos": {"area": "lectura"}})
                cifras.append({"valor": str(nuevas), "rotulo": "Subrayados nuevos", "accion": "area", "datos": {"area": "lectura"}})
        if self.fichas.leidas:
            cifras.append({"valor": str(self.fichas.porRevisar), "rotulo": "Fichas por revisar", "accion": "revisar", "datos": {}})
        c = self.libros.contadores
        if self.libros.total:
            cifras.append({"valor": str(sum(int(c.get(k, 0) or 0) for k in SUMAN_PENDIENTES)), "rotulo": "Pendientes",
                           "accion": "bandeja", "datos": {"bandeja": self._primera_bandeja()}})
        self._cifras = cifras
        self._seguir = self._leer_seguir(ruta) if hay_base else []
        self._pasos = self._leer_pasos(ruta if hay_base else None)
        self.cambiado.emit()

    def _primera_bandeja(self) -> str:
        """La primera bandeja con algo (por la que se entra a Bandejas desde la cifra «Pendientes»)."""
        return next((b["clave"] for b in self.libros.bandejas if b["n"] and b["clave"] in SUMAN_PENDIENTES), "")

    def _leer_seguir(self, ruta) -> list:
        try:
            en_curso = consulta.en_curso(3, ruta)
        except Exception:  # noqa: BLE001
            return []
        salida = []
        for l in en_curso:
            cat = self.libros._por_id.get(str(l["calibre_id"]), {})
            salida.append({"id": str(l["calibre_id"]), "titulo": cat.get("titulo") or l["titulo"],
                           "autores": " · ".join(cat.get("autores") or []) or l["autores"],
                           "fuente": f"image://portadas/{l['calibre_id']}" if cat.get("portada") else "", "portada": bool(cat.get("portada")),
                           "fraccion": l["fraccion"], "color": COLORES.get(l["origen"], ""),
                           "texto": f"{l['porcentaje']} % · en {NOMBRES.get(l['origen'], l['origen'])}",
                           "enCatalogo": bool(cat)})
        return salida

    def _leer_pasos(self, ruta) -> list:
        pasos = []
        fichas = self.fichas.todas() if self.fichas.leidas else []
        if ruta is not None and self.fichas.leidas:
            try:
                pendientes = por_fichar(consulta.subrayados(ruta), fichas)
            except Exception:  # noqa: BLE001
                pendientes = {}
            if pendientes:
                cid, lista = max(pendientes.items(), key=lambda kv: len(kv[1]))
                cat = self.libros._por_id.get(str(cid), {})
                if cat:
                    s = lista[0]
                    n = len(lista)
                    pasos.append({"icono": "document-new", "texto": f"Fichar {n} subrayado{'s' if n != 1 else ''} de «{cat['titulo']}»",
                                  "boton": "Nueva ficha", "accion": "ficha",
                                  "datos": {"id": str(cid), "texto": s["texto"], "pagina": s["pagina"], "hoja": s["hoja"] or 0}})
        if self.fichas.paraHoy:
            n = self.fichas.paraHoy
            pasos.append({"icono": "view-task", "texto": f"Repaso: {n} ficha{'s' if n != 1 else ''} para hoy", "boton": "Repasar",
                          "accion": "repaso", "datos": {}})
        e = fuentes_nuevas(self.fichas.escritos()) if self.fichas.leidas else None
        if e is not None:
            pasos.append({"icono": "document-edit", "texto": f"Fuentes nuevas en «{e['titulo']}»", "boton": "Abrir en LaTeX Studio",
                          "accion": "latex", "datos": {"principal": e["principal"]}})
        c = self.libros.contadores
        titulos = {b["clave"]: b["titulo"] for b in self.libros.bandejas}
        for clave, texto in (("sin_clave", "{n} libro{s} sin clave para citar"), ("clasificar", "{n} pendiente{s} de clasificar"),
                             ("sin_zotero", "{n} libro{s} sin Zotero"), ("fichas", "{n} ficha{s} canónica{s} incompleta{s}")):
            n = int(c.get(clave, 0) or 0)
            if n:
                pasos.append({"icono": "mail-folder-inbox", "texto": texto.format(n=n, s="" if n == 1 else "s"),
                              "boton": titulos.get(clave, "Ver la bandeja"), "accion": "bandeja", "datos": {"bandeja": clave}})
        return pasos[:4]

    # ------------------------------------------------------------------ lo que la ventana pinta
    @Property("QVariantList", notify=cambiado)
    def cifras(self) -> list:
        return self._cifras

    @Property("QVariantList", notify=cambiado)
    def seguir(self) -> list:
        return self._seguir

    @Property("QVariantList", notify=cambiado)
    def pasos(self) -> list:
        return self._pasos

    @Property(str, notify=cambiado)
    def fecha(self) -> str:
        """«martes 18 de noviembre», sin depender del idioma de la máquina."""
        from datetime import date
        d = date.today()
        dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
        meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        return f"{dias[d.weekday()]} {d.day} de {meses[d.month - 1]}"

    # ------------------------------------------------------------------ a dónde llevan los botones
    @Slot(str, "QVariantMap")
    def ir(self, accion: str, datos: dict) -> None:
        """Lleva al lugar de una cifra o de un paso: un área, una bandeja, el repaso, las fichas por revisar o LaTeX Studio.
        («Nueva ficha» abre su diálogo en la ventana.)"""
        datos = dict(datos or {})
        if accion == "area":
            self.espacio.fijarArea(datos.get("area", "catalogo"))
        elif accion == "bandeja":
            if datos.get("bandeja"):
                self.libros.fijarBandeja(datos["bandeja"])
            self.espacio.fijarArea("bandejas")
        elif accion == "repaso":
            self.fichas.fijarModo("repaso")
            self.espacio.fijarArea("fichas")
        elif accion == "revisar":
            self.fichas.fijarFiltro("revisar")
            self.espacio.fijarArea("fichas")
        elif accion == "latex":
            self.libros.abrirEnLatex(datos.get("principal", ""))
        elif accion == "libro":
            self.libros.fijarId(str(datos.get("id", "")))
            self.espacio.fijarArea("catalogo")

    @Slot(str)
    def abrir(self, libro_id: str) -> None:
        """«Abrir» de «Seguir leyendo»: el documento del libro con su aplicación."""
        self.libros.fijarId(str(libro_id))
        self.libros.abrirArchivo()
