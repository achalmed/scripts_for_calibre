"""Complemento «Ecosistema» de Calibre: el libro elegido con su clave de Zotero, su clave para citar, sus fichas y su
nota de lectura, y abrirlo en Zotero o en Biblioteca Studio. Solo lee la base (la puerta de escritura de la biblioteca
es biblioteca-studio/lib/escribir*); lo único que escribe es una cola de texto «por verificar», fuera de la base.
"""
from calibre.customize import InterfaceActionBase


class Ecosistema(InterfaceActionBase):
    name = "Ecosistema"
    description = "El libro en Zotero, su clave para citar, sus fichas y su nota de lectura (solo lectura)"
    supported_platforms = ["linux", "osx", "windows"]
    author = "biblioteca-studio"
    version = (1, 0, 0)
    minimum_calibre_version = (6, 0, 0)
    actual_plugin = "calibre_plugins.ecosistema.ui:AccionEcosistema"
