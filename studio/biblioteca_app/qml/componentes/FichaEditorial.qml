// FichaEditorial — el libro leído como en un catálogo de biblioteca (reingeniería B7): la portada grande, el título, la
// mención de responsabilidad, el pie de imprenta y la serie; abrir el documento con su aplicación o mostrarlo en Dolphin;
// la clave para citar (Zotero manda en citas), el estado en Zotero y la lectura en KOReader; identificadores, materias,
// descripción, formatos, fichas canónicas y nota de lectura. Solo lee: lo que cambia la biblioteca es una operación.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.Control {
    id: raiz
    readonly property var l: studio.libros
    readonly property var f: l.ficha
    signal cerrar()

    padding: 0
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false
    background: Rectangle { color: Kirigami.Theme.backgroundColor }
    Accessible.name: "Ficha de " + (f.titulo || "ningún libro")

    function accion(n) { return studio.acciones.accion(n) }

    contentItem: Item {
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 2
            visible: !raiz.l.hayActual
            icon.name: "folder-book"
            text: "Elige un libro"
            explanation: "Su ficha editorial, su clave para citar y su lectura aparecen aquí"
        }
        QQC2.ScrollView {
            id: desplazable
            anchors.fill: parent
            visible: raiz.l.hayActual
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

            ColumnLayout {
                width: desplazable.availableWidth - Kirigami.Units.largeSpacing * 4
                x: Kirigami.Units.largeSpacing * 2
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    QQC2.Label { text: "Calibre " + (raiz.f.id || ""); color: Kirigami.Theme.disabledTextColor; font: Kirigami.Theme.smallFont }
                    Item { Layout.fillWidth: true }
                    QQC2.ToolButton { icon.name: "window-close"; display: QQC2.AbstractButton.IconOnly; text: "Cerrar la ficha"; onClicked: raiz.cerrar(); Accessible.name: text }
                }
                // la portada grande
                Item {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Math.min(parent.width, Kirigami.Units.gridUnit * 13)
                    Layout.preferredHeight: Layout.preferredWidth * 1.45
                    Image {
                        id: portada
                        anchors.fill: parent
                        source: raiz.f.fuente || ""
                        visible: raiz.f.portada === true
                        asynchronous: true
                        fillMode: Image.PreserveAspectFit
                        sourceSize.width: 520
                    }
                    Rectangle {
                        anchors.fill: parent
                        visible: raiz.f.portada !== true || portada.status !== Image.Ready
                        radius: Kirigami.Units.cornerRadius
                        color: Kirigami.Theme.alternateBackgroundColor
                        border.color: Kirigami.Theme.disabledTextColor
                        Kirigami.PlaceholderMessage { anchors.centerIn: parent; width: parent.width - Kirigami.Units.gridUnit; icon.name: "image-missing"; text: raiz.f.portada === true ? "" : "Sin portada" }
                    }
                }
                Kirigami.Heading {
                    Layout.fillWidth: true
                    level: 2
                    text: raiz.f.titulo || ""
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: (raiz.f.autores || []).join(" · ") || "sin autor"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    font.italic: true
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: raiz.f.imprenta || ""
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    color: Kirigami.Theme.disabledTextColor
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: (raiz.f.serie || "") !== ""
                    text: "Colección: " + (raiz.f.serie || "")
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    color: Kirigami.Theme.disabledTextColor
                }
                // abrir
                Flow {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    QQC2.Button {
                        readonly property var a: raiz.accion("libro.archivo")
                        text: "Abrir el documento"; icon.name: "document-open"; highlighted: true; enabled: a.habilitada
                        onClicked: a.disparar()
                    }
                    BotonAccion { accion: raiz.accion("libro.dolphin") }
                    BotonAccion { accion: raiz.accion("libro.calibre") }
                    BotonAccion { accion: raiz.accion("libro.zotero") }
                }

                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    wideMode: false
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Citar" }
                    RowLayout {
                        Kirigami.FormData.label: "Clave para citar:"
                        Layout.fillWidth: true
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: raiz.f.clave || "sin clave (la pone Better BibTeX en Zotero)"
                            font.family: raiz.f.clave ? Kirigami.Theme.fixedWidthFont.family : Kirigami.Theme.defaultFont.family
                            color: raiz.f.clave ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
                            elide: Text.ElideRight
                        }
                        BotonAccion { accion: raiz.accion("libro.copiar_clave"); conTexto: false }
                    }
                    RowLayout {
                        Kirigami.FormData.label: "Zotero:"
                        Kirigami.Icon {
                            source: raiz.f.zotero ? "data-success" : "data-warning"
                            implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                        }
                        QQC2.Label { text: raiz.f.zotero ? "enlazado · " + raiz.f.zoteroKey : "sin enlazar (bandeja «Sin Zotero»)"; font.family: raiz.f.zotero ? Kirigami.Theme.fixedWidthFont.family : Kirigami.Theme.defaultFont.family }
                    }
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Lectura" }
                    ColumnLayout {
                        Kirigami.FormData.label: "KOReader:"
                        Layout.fillWidth: true
                        QQC2.Label { text: raiz.f.koreader || "sin abrir en KOReader"; color: raiz.f.koreader ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        QQC2.ProgressBar { visible: (raiz.f.koProgreso ?? -1) >= 0; from: 0; to: 1; value: Math.max(0, raiz.f.koProgreso ?? 0); Layout.fillWidth: true; Accessible.name: "Progreso de lectura" }
                    }
                    RowLayout {
                        Kirigami.FormData.label: "Nota de lectura:"
                        QQC2.Label { text: raiz.f.hayNota ? (raiz.f.notaEnlazada ? "enlazada en Calibre" : "en notas/") : "todavía no hay"; color: raiz.f.hayNota ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor }
                        BotonAccion { accion: raiz.accion("libro.nota"); conTexto: false; visible: raiz.f.hayNota === true }
                    }
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Descripción bibliográfica"; visible: idsRep.count > 0 || (raiz.f.tipo || "") !== "" }
                    QQC2.Label { Kirigami.FormData.label: "Tipo:"; visible: (raiz.f.tipo || "") !== ""; text: raiz.f.tipo || "" }
                    Repeater {
                        id: idsRep
                        model: raiz.f.identificadores || []
                        delegate: QQC2.Label {
                            required property var modelData
                            Kirigami.FormData.label: modelData.tipo + ":"
                            text: modelData.valor
                            font.family: Kirigami.Theme.fixedWidthFont.family
                            textFormat: Text.PlainText
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                    }
                    QQC2.Label { Kirigami.FormData.label: "Añadido:"; visible: (raiz.f.añadido || "") !== ""; text: raiz.f.añadido || ""; color: Kirigami.Theme.disabledTextColor }
                }
                // materias (etiquetas)
                Flow {
                    Layout.fillWidth: true
                    visible: (raiz.f.etiquetas || []).length > 0
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: raiz.f.etiquetas || []
                        delegate: QQC2.Button {
                            required property string modelData
                            text: modelData
                            flat: true
                            font: Kirigami.Theme.smallFont
                            onClicked: raiz.l.buscar("etiqueta:\"" + modelData + "\"")
                            QQC2.ToolTip.text: "Buscar los libros con esta etiqueta"
                            QQC2.ToolTip.visible: hovered
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: raiz.f.descripcion || ""
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                }
                Kirigami.Heading { level: 4; text: "Formatos"; visible: (raiz.f.formatos || []).length > 0 }
                Repeater {
                    model: raiz.f.formatos || []
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        QQC2.Label { text: modelData.formato; font.weight: Font.DemiBold }
                        QQC2.Label { text: modelData.nombre; elide: Text.ElideMiddle; Layout.fillWidth: true; color: Kirigami.Theme.disabledTextColor }
                        QQC2.Label { text: modelData.tamano; color: Kirigami.Theme.disabledTextColor }
                    }
                }
                Kirigami.Heading { level: 4; text: "Fichas canónicas"; visible: (raiz.f.fichas || []).length > 0 }
                Repeater {
                    model: raiz.f.fichas || []
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.nombre + " · " + modelData.verificacion
                        icon.name: modelData.verificacion.startsWith("verificada") ? "document-edit-verify" : "document-edit"
                        onClicked: raiz.l.abrirFicha(modelData.ruta)
                    }
                }
                Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
            }
        }
    }
}
