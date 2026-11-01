"""La acción del complemento: un botón con su menú para los libros elegidos (solo lectura de la base)."""
import json
import os
import time
from functools import partial

from qt.core import QApplication, QDialog, QDialogButtonBox, QLabel, QMenu, Qt, QUrl, QVBoxLayout

from calibre.gui2 import error_dialog, info_dialog, open_url
from calibre.gui2.actions import InterfaceAction


def _estado():
    return os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")


def ruta_indice():
    return os.path.join(_estado(), "biblioteca", "indice.json")


def leer_indice():
    try:
        with open(ruta_indice(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class AccionEcosistema(InterfaceAction):
    name = "Ecosistema"
    action_spec = ("Ecosistema", None, "El libro en Zotero, su clave para citar, sus fichas y su nota", None)
    action_type = "current"
    dont_add_to = frozenset()

    def genesis(self):
        self.menu = QMenu(self.gui)
        for texto, funcion in (("Qué es este libro…", self.ficha), ("Abrir en Zotero", self.abrir_zotero),
                               ("Abrir en Biblioteca Studio", self.abrir_studio),
                               ("Abrir la nota de lectura", self.abrir_nota),
                               ("Copiar la clave para citar", self.copiar_clave), (None, None),
                               ("Marcar para verificar", self.marcar)):
            if texto is None:
                self.menu.addSeparator()
                continue
            accion = self.menu.addAction(texto)
            accion.triggered.connect(partial(self._con_libro, funcion))
        self.qaction.setMenu(self.menu)
        self.qaction.triggered.connect(partial(self._con_libro, self.ficha))

    # ---------------------------------------------------------------------------------------------------------
    def _elegidos(self):
        filas = self.gui.library_view.selectionModel().selectedRows()
        return [self.gui.library_view.model().id(r) for r in filas]

    def _con_libro(self, funcion, *_):
        ids = self._elegidos()
        if not ids:
            return error_dialog(self.gui, "Ecosistema", "Elige un libro.", show=True)
        funcion(ids)

    def _datos(self, libro_id):
        """Lo que el índice sabe del libro, completado con la base de Calibre (solo lectura)."""
        db = self.gui.current_db.new_api
        indice = leer_indice()
        d = dict(indice.get("libros", {}).get(str(libro_id), {}))
        d.setdefault("titulo", db.field_for("title", libro_id))
        if not d.get("zotero_key"):
            try:
                d["zotero_key"] = db.field_for("#zotero_key", libro_id) or ""
            except Exception:  # noqa: BLE001  la columna puede no existir en otra biblioteca
                d["zotero_key"] = ""
        d["en_indice"] = str(libro_id) in indice.get("libros", {})
        d["generado"] = indice.get("generado", "")
        return d

    # --------------------------------------------------------------------------------------------- acciones
    def ficha(self, ids):
        d = self._datos(ids[0])
        nota = d.get("nota") or ""
        filas = [f"<h3>{d.get('titulo', '')}</h3>",
                 f"<p><b>Calibre</b> {ids[0]} · <b>Zotero</b> {d.get('zotero_key') or '—'} · "
                 f"<b>clave para citar</b> {d.get('clave') or '—'}</p>",
                 f"<p><b>Nota de lectura</b>: {'sí' if nota and os.path.isfile(nota) else 'todavía no'}</p>",
                 f"<p><b>Fichas que lo citan</b>: {len(d.get('fichas', []))}</p>"]
        filas += [f"<p style='margin-left:12px'>{f}</p>" for f in d.get("fichas", [])[:8]]
        if not d["en_indice"]:
            filas.append("<p><i>Este libro no está en el índice: actualízalo desde Biblioteca Studio "
                         "(Sincronizar → Actualizar el índice).</i></p>")
        elif d["generado"]:
            filas.append(f"<p style='color:gray'>Índice del {d['generado'][:16].replace('T', ' ')}</p>")
        dialogo = QDialog(self.gui)
        dialogo.setWindowTitle("Ecosistema")
        caja = QVBoxLayout(dialogo)
        etiqueta = QLabel("".join(filas))
        etiqueta.setWordWrap(True)
        etiqueta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        caja.addWidget(etiqueta)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botones.rejected.connect(dialogo.reject)
        caja.addWidget(botones)
        dialogo.resize(520, 300)
        dialogo.exec()

    def abrir_zotero(self, ids):
        clave = self._datos(ids[0]).get("zotero_key")
        if not clave:
            return error_dialog(self.gui, "Ecosistema", "Este libro todavía no está enlazado con Zotero.", show=True)
        open_url(QUrl(f"zotero://select/library/items/{clave}"))

    def abrir_studio(self, ids):
        open_url(QUrl(f"biblioteca-studio://libro/{ids[0]}"))

    def abrir_nota(self, ids):
        nota = self._datos(ids[0]).get("nota") or ""
        if not os.path.isfile(nota):
            return info_dialog(self.gui, "Ecosistema", "Todavía no hay nota de lectura: la crean el complemento de "
                               "KOReader o Zotero Integration (Obsidian).", show=True)
        open_url(QUrl.fromLocalFile(nota))

    def copiar_clave(self, ids):
        claves = [c for c in (self._datos(i).get("clave") for i in ids) if c]
        if not claves:
            return error_dialog(self.gui, "Ecosistema", "Ninguno de los libros elegidos tiene clave para citar.",
                                show=True)
        QApplication.clipboard().setText(", ".join(claves))
        self.gui.status_bar.show_message(f"Copiado: {', '.join(claves)}", 4000)

    def marcar(self, ids):
        """Anota los libros en una cola de texto que Biblioteca Studio y la verificación leen; no toca la base."""
        cola = os.path.join(_estado(), "biblioteca", "por-verificar.tsv")
        os.makedirs(os.path.dirname(cola), exist_ok=True)
        db = self.gui.current_db.new_api
        with open(cola, "a", encoding="utf-8") as f:
            for i in ids:
                f.write(f"{i}\t{db.field_for('title', i)}\t{time.strftime('%Y-%m-%d %H:%M')}\n")
        self.gui.status_bar.show_message(f"{len(ids)} libro(s) marcado(s) para verificar", 4000)
