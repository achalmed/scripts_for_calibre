// FilaLibro — un libro (o un documento de la zona de entrada, en una bandeja) en la lista compacta: la portada pequeña,
// el título, autor · año · serie · tipo, la lectura de KOReader y las marcas de Zotero y de la clave.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.ItemDelegate {
    id: fila

    required property int index
    required property var model
    property bool actual: false
    signal elegida(int indice)
    signal abierta(int indice)

    highlighted: actual
    onClicked: elegida(index)
    onDoubleClicked: abierta(index)
    Accessible.name: model.titulo + ", " + model.autores

    readonly property color secundario: highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing
        Item {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 1.6
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2.3
            Image {
                anchors.fill: parent
                source: fila.model.fuente
                visible: fila.model.portada
                asynchronous: true
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 220
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                visible: !fila.model.portada
                source: fila.model.otro ? "document-import" : "x-office-document"
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: implicitWidth
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            QQC2.Label {
                Layout.fillWidth: true
                text: fila.model.titulo
                elide: Text.ElideRight
                font.weight: Font.DemiBold
                color: fila.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            }
            QQC2.Label {
                Layout.fillWidth: true
                text: fila.model.otro ? fila.model.detalle
                                      : [fila.model.autores, fila.model.año, fila.model.serie, fila.model.tipo].filter(x => x).join(" · ")
                elide: Text.ElideRight
                font: Kirigami.Theme.smallFont
                color: fila.secundario
            }
        }
        QQC2.Label {
            visible: fila.model.clave !== ""
            text: fila.model.clave
            font.family: Kirigami.Theme.fixedWidthFont.family
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: fila.secundario
            elide: Text.ElideRight
            Layout.maximumWidth: Kirigami.Units.gridUnit * 12
        }
        QQC2.ProgressBar {
            visible: fila.model.koProgreso >= 0
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4
            from: 0; to: 1
            value: Math.max(0, fila.model.koProgreso)
            Accessible.name: "Leído en KOReader: " + Math.round(fila.model.koProgreso * 100) + " %"
        }
        Kirigami.Icon {
            visible: !fila.model.otro
            source: fila.model.zotero ? "data-success" : "emblem-unavailable"
            opacity: fila.model.zotero ? 1 : 0.5
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
            Accessible.name: fila.model.zotero ? "En Zotero" : "Sin Zotero"
        }
    }
}
