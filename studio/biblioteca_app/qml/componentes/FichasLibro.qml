// FichasLibro — las fichas canónicas (catalogacion/fichas/) que citan el libro actual; Intro o doble clic abre la ficha.
import QtQuick
import org.kde.kirigami as Kirigami
import GuiComun

TablaDatos {
    readonly property var l: studio.libros
    modelo: l.fichasModelo
    mensajeVacio: l.hayActual ? "Ninguna ficha cita este libro: las escribe «Catalogar en Calibre» al aplicar" : "Ningún libro"
    iconoVacio: "document-edit-verify"
    columnas: [{ ancho: 0, minimo: 10, conIcono: true }]
    onActivada: fila => l.abrirFicha(fila)
}
