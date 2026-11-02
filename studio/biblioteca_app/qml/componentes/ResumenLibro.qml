// ResumenLibro — el libro actual de la vista Libros: portada, título, autores, claves (Calibre, Zotero, para citar),
// formatos, carpeta y nota de lectura; Abrir en Calibre, en Zotero, el archivo, la nota y Copiar la clave al pie.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.ScrollView {
    id: pagina
    readonly property var l: studio.libros
    contentWidth: availableWidth
    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
    ColumnLayout {
        width: pagina.availableWidth - Kirigami.Units.largeSpacing * 2
        x: Kirigami.Units.largeSpacing
        y: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: !pagina.l.hayActual
            text: pagina.l.hayIndice ? "Ningún libro" : "Sin índice de libros"
            explanation: pagina.l.hayIndice ? "Elige un libro en la tabla o búscalo con Ctrl+F; los complementos de Calibre, KOReader y Zotero abren aquí el suyo."
                                            : "Actualizar el índice (Ctrl+R) lee Calibre y Zotero en solo lectura y escribe el índice que leen la ventana y los complementos."
            icon.name: "folder-book"
        }
        RowLayout {
            visible: pagina.l.hayActual
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Image {
                visible: pagina.l.portada !== ""
                source: pagina.l.portada
                Layout.preferredWidth: Kirigami.Units.gridUnit * 6
                Layout.preferredHeight: Kirigami.Units.gridUnit * 8.5
                Layout.alignment: Qt.AlignTop
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                Accessible.name: "Portada de " + pagina.l.titulo
            }
            Kirigami.Icon {
                visible: pagina.l.portada === ""
                source: "folder-book"
                Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                Layout.alignment: Qt.AlignTop
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.Label { Kirigami.FormData.label: "Título:"; text: pagina.l.titulo; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                QQC2.Label { Kirigami.FormData.label: "Autores:"; text: pagina.l.autores; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                QQC2.Label { Kirigami.FormData.label: "Calibre:"; text: pagina.l.id; font: Kirigami.Theme.fixedWidthFont }
                QQC2.Label { Kirigami.FormData.label: "Zotero:"; text: pagina.l.zoteroKey || "sin enlazar"; font: pagina.l.zoteroKey ? Kirigami.Theme.fixedWidthFont : Kirigami.Theme.defaultFont; color: pagina.l.zoteroKey ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor }
                QQC2.Label { Kirigami.FormData.label: "Clave para citar:"; text: pagina.l.clave || "sin clave (Zotero manda)"; font: pagina.l.clave ? Kirigami.Theme.fixedWidthFont : Kirigami.Theme.defaultFont; color: pagina.l.clave ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
            }
        }
        Kirigami.FormLayout {
            visible: pagina.l.hayActual
            Layout.fillWidth: true
            Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Archivos" }
            QQC2.Label { Kirigami.FormData.label: "Formatos:"; text: pagina.l.formatos.length > 0 ? pagina.l.formatos.join("\n") : "ninguno"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: pagina.l.formatos.length > 0 ? Kirigami.Theme.textColor : Kirigami.Theme.negativeTextColor }
            QQC2.Label { Kirigami.FormData.label: "Carpeta:"; text: pagina.l.carpeta; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true; color: Kirigami.Theme.disabledTextColor }
            Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Lectura" }
            QQC2.Label { Kirigami.FormData.label: "Nota:"; text: pagina.l.hayNota ? (pagina.l.notaEnlazada ? "enlazada en «apuntes»" : "existe, sin enlazar («Enlazar las notas de lectura»)") : "todavía no (la crean KOReader o Zotero Integration)"; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: pagina.l.hayNota ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor }
            QQC2.Label { Kirigami.FormData.label: "Fichas:"; text: pagina.l.nFichas > 0 ? pagina.l.nFichas + " (pestaña Fichas)" : "ninguna ficha lo cita"; color: pagina.l.nFichas > 0 ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor }
        }
        RowLayout {
            visible: pagina.l.hayActual
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            Item { Layout.fillWidth: true }
            BotonAccion { accion: studio.acciones.accion("libro.nota"); conTexto: false }
            BotonAccion { accion: studio.acciones.accion("libro.copiar_clave"); conTexto: false }
            BotonAccion { accion: studio.acciones.accion("libro.archivo") }
            BotonAccion { accion: studio.acciones.accion("libro.zotero") }
            QQC2.Button {
                readonly property var a: studio.acciones.accion("libro.calibre")
                highlighted: true
                text: a.textoPlano; icon.name: a.icono; enabled: a.habilitada
                onClicked: a.disparar()
                QQC2.ToolTip.text: a.descripcion; QQC2.ToolTip.visible: hovered
            }
        }
        Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
    }
}
