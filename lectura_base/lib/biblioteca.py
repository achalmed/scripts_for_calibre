"""lectura_base/lib/biblioteca.py — lo que los adaptadores necesitan saber de la biblioteca, en SOLO LECTURA.

- `Resolutor`: de Calibre (`metadata.db` con `mode=ro`, nunca escrita) el título, los autores y los archivos de cada libro,
  y el MD5 parcial de KOReader (`#ko_md5`, por su etiqueta), para reconocer un libro por su `calibre_id`, por la carpeta
  `(<id>)/` de una ruta o por su MD5.
- `medidas` y `giros`: el tamaño en puntos y el giro de cada hoja de un PDF (`pdfinfo`), para pasar los rectángulos de
  cada herramienta a fracciones de la hoja y de vuelta (y no llevar los de una hoja girada).
- `md5_parcial`: el MD5 de KOReader (bloques de 1 KB en 0 y 1024·4^i), el mismo de `koreader/lib/sync_koreader.py`.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
from functools import lru_cache
from pathlib import Path

ID_EN_RUTA = re.compile(r"\((\d+)\)/[^/]*$")


def id_de_ruta(ruta: str) -> int | None:
    m = ID_EN_RUTA.search(str(ruta or ""))
    return int(m.group(1)) if m else None


def md5_parcial(ruta) -> str:
    m = hashlib.md5()
    try:
        with open(ruta, "rb") as f:
            for off in [0] + [1024 * (4 ** i) for i in range(0, 11)]:
                f.seek(off)
                bloque = f.read(1024)
                if not bloque:
                    break
                m.update(bloque)
    except OSError:
        return ""
    return m.hexdigest()


class Resolutor:
    """La biblioteca de Calibre vista por la base de lectura (solo lee; si no hay `metadata.db`, no sabe nada)."""

    def __init__(self, calibre_db: str | os.PathLike | None = None, biblioteca: str | os.PathLike | None = None):
        self.biblioteca = Path(biblioteca or os.environ.get("BIBLIOTECA_DIR") or "")
        self.calibre_db = Path(calibre_db or os.environ.get("CALIBRE_DB") or (self.biblioteca / "metadata.db"))
        self.libros: dict[int, dict] = {}
        self.por_md5: dict[str, int] = {}
        if self.calibre_db.is_file():
            self._leer()

    def _leer(self) -> None:
        c = sqlite3.connect(self.calibre_db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            for b, titulo, carpeta in c.execute("select id, title, path from books"):
                self.libros[b] = {"titulo": titulo or "", "carpeta": carpeta or "", "autores": [], "formatos": {}, "md5": ""}
            for b, nombre in c.execute("select l.book, a.name from books_authors_link l join authors a on a.id = l.author order by l.id"):
                if b in self.libros:
                    self.libros[b]["autores"].append((nombre or "").replace("|", ","))
            for b, fmt, nombre in c.execute("select book, format, name from data"):
                if b in self.libros:
                    self.libros[b]["formatos"][fmt.upper()] = self.biblioteca / self.libros[b]["carpeta"] / f"{nombre}.{fmt.lower()}"
            fila = c.execute("select id from custom_columns where label = 'ko_md5'").fetchone()
            if fila:
                for b, v in c.execute(f"select book, value from custom_column_{int(fila[0])}"):
                    if b in self.libros and v:
                        self.libros[b]["md5"] = str(v)
                        self.por_md5[str(v)] = b
        except sqlite3.DatabaseError:
            pass
        finally:
            c.close()

    def id_de(self, ruta: str = "", md5: str = "") -> int | None:
        """El libro de una ruta (`(<id>)/`) o de un MD5 parcial (`#ko_md5`)."""
        b = id_de_ruta(ruta)
        if b is not None:
            return b
        return self.por_md5.get(md5 or "")

    def ficha(self, calibre_id) -> dict:
        d = self.libros.get(int(calibre_id)) if calibre_id is not None else None
        if not d:
            return {}
        return {"titulo": d["titulo"], "autores": " & ".join(d["autores"]), "md5": d["md5"]}

    def pdf(self, calibre_id) -> Path | None:
        d = self.libros.get(int(calibre_id)) if calibre_id is not None else None
        p = (d or {}).get("formatos", {}).get("PDF")
        return p if p and Path(p).is_file() else None


_MEDIDA = re.compile(r"^Page\s+(\d+)\s+size:\s+([\d.]+)\s+x\s+([\d.]+)")
_GIRO = re.compile(r"^Page\s+(\d+)\s+rot:\s+(\d+)")


@lru_cache(maxsize=256)
def _paginas(ruta: str, mtime: float) -> tuple:
    """((ancho, alto, giro), …) de cada hoja, de una sola llamada a pdfinfo."""
    try:
        r = subprocess.run(["pdfinfo", "-f", "1", "-l", "100000", ruta], capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    hojas, giros = {}, {}
    for linea in r.stdout.decode("utf-8", "replace").splitlines():
        m = _MEDIDA.match(linea)
        if m:
            hojas[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
            continue
        g = _GIRO.match(linea)
        if g:
            giros[int(g.group(1))] = int(g.group(2)) % 360
    return tuple((*hojas[n], giros.get(n, 0)) for n in sorted(hojas))


def _de_pdf(ruta) -> tuple:
    try:
        p = Path(ruta)
        return _paginas(str(p), p.stat().st_mtime)
    except (OSError, TypeError):
        return ()


def medidas(ruta) -> list[tuple[float, float]]:
    """[(ancho, alto)] en puntos de cada hoja de un PDF, sin girar; [] si no se puede leer."""
    return [(w, h) for w, h, _ in _de_pdf(ruta)]


def giros(ruta) -> list[int]:
    """El giro de cada hoja (0, 90, 180, 270): en una hoja girada cada herramienta mide sus rectángulos a su modo."""
    return [g for _, _, g in _de_pdf(ruta)]
