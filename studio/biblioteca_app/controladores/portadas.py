"""biblioteca_app/controladores/portadas.py — las portadas del catálogo en miniatura (reingeniería B3).

`image://portadas/<id>` (cuadrícula) y `image://portadas/<id>/grande` (ficha editorial): un proveedor de imágenes
asíncrono lee el `cover.jpg` del libro en SOLO LECTURA (`QImageReader`, escalado al leer: no se decodifica la imagen
entera), lo guarda como JPEG en la caché del studio (`$XDG_CACHE_HOME/biblioteca-studio/portadas/`, la clave lleva el
libro, el tamaño y la fecha del archivo: una portada nueva en Calibre invalida la vieja) y lo devuelve. La caché se
poda a un tope (`TOPE_MB`) quitando lo menos usado. Un libro sin portada devuelve una imagen vacía: QML pinta el
sustituto con el título. Nunca se escribe en la carpeta de la biblioteca.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from gui_comun.qt import QSize, QStandardPaths

try:                                    # gui_comun.qt no exporta QtQuick.QQuickImageProvider (candidato a la base)
    from PySide6.QtGui import QImage, QImageReader
    from PySide6.QtQml import QQmlImageProviderBase
    from PySide6.QtQuick import QQuickImageProvider
except ImportError:                     # pragma: no cover  (PyQt6)
    from PyQt6.QtGui import QImage, QImageReader
    from PyQt6.QtQml import QQmlImageProviderBase
    from PyQt6.QtQuick import QQuickImageProvider

ANCHO_MINIATURA = 220                   # px de ancho de la cuadrícula (a 2× para pantallas densas cabe en 440)
ANCHO_GRANDE = 520
TOPE_MB = 200
CALIDAD = 85


def cache_portadas() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation) or str(Path.home() / ".cache" / "biblioteca-studio")
    return Path(base) / "portadas"


def podar(carpeta: Path, tope_bytes: int) -> int:
    """Borra las miniaturas menos usadas (la fecha de modificación se renueva al usarlas) hasta quedar bajo el tope;
    devuelve cuántas borró. Solo toca su propia carpeta de caché."""
    try:
        archivos = [(p, p.stat()) for p in carpeta.glob("*.jpg")]
    except OSError:
        return 0
    total = sum(s.st_size for _p, s in archivos)
    borradas = 0
    for p, s in sorted(archivos, key=lambda x: x[1].st_mtime):
        if total <= tope_bytes:
            break
        try:
            p.unlink()
            total -= s.st_size
            borradas += 1
        except OSError:
            pass
    return borradas


def miniatura(origen: Path, destino_carpeta: Path, clave: str, ancho: int) -> QImage:
    """La miniatura de `origen` a `ancho` px (de la caché si ya está); una imagen vacía si no hay portada legible."""
    try:
        st = origen.stat()
    except OSError:
        return QImage()
    archivo = destino_carpeta / f"{clave}-{ancho}-{st.st_mtime_ns}.jpg"
    if archivo.is_file():
        try:
            os.utime(archivo)                      # usada ahora: la poda quita primero lo que nadie mira
        except OSError:
            pass
        img = QImage(str(archivo))
        if not img.isNull():
            return img
    lector = QImageReader(str(origen))
    lector.setAutoTransform(True)
    tam = lector.size()
    if tam.isValid() and tam.width() > ancho:
        lector.setScaledSize(QSize(ancho, max(1, round(tam.height() * ancho / tam.width()))))
    img = lector.read()
    if img.isNull():
        return QImage()
    try:
        destino_carpeta.mkdir(parents=True, exist_ok=True)
        for viejo in destino_carpeta.glob(f"{clave}-{ancho}-*.jpg"):     # la de una portada anterior del mismo libro
            viejo.unlink(missing_ok=True)
        img.save(str(archivo), "JPG", CALIDAD)
    except OSError:
        pass
    return img


class ProveedorPortadas(QQuickImageProvider):
    """`image://portadas/<id>[/grande]`; las rutas de `cover.jpg` las fija el catálogo (`fijar_rutas`)."""

    def __init__(self, carpeta: Path | None = None, tope_mb: int = TOPE_MB):
        super().__init__(QQuickImageProvider.ImageType.Image, QQmlImageProviderBase.Flag.ForceAsynchronousImageLoading)
        self.carpeta = Path(carpeta) if carpeta else cache_portadas()
        self.tope = tope_mb * 1024 * 1024
        self._rutas: dict[str, str] = {}
        self._cerrojo = threading.Lock()
        self._nuevas = 0

    def fijar_rutas(self, rutas: dict[str, str]) -> None:
        with self._cerrojo:
            self._rutas = dict(rutas)

    def ruta(self, libro: str) -> str:
        with self._cerrojo:
            return self._rutas.get(libro, "")

    def requestImage(self, ident, size=None, requested=None):   # noqa: N802  (la firma de Qt)
        partes = str(ident).split("?", 1)[0].split("/")
        libro, grande = partes[0], len(partes) > 1 and partes[1] == "grande"
        ruta = self.ruta(libro)
        ancho = ANCHO_GRANDE if grande else ANCHO_MINIATURA
        if requested is not None and requested.isValid() and requested.width() > 0:
            ancho = min(max(requested.width(), 64), 1200)
        img = miniatura(Path(ruta), self.carpeta, libro, ancho) if ruta else QImage()
        if not img.isNull():
            self._nuevas += 1
            if self._nuevas % 200 == 0:
                podar(self.carpeta, self.tope)
        if size is not None and hasattr(size, "setWidth"):
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img
