// TarjetaLibro — un libro en la cuadrícula del catálogo (reingeniería B3–B4): la portada en miniatura (la de Calibre por
// `image://portadas/<id>`; sin portada, un sustituto con el título y el autor en los colores del tema), la barra de
// lectura de KOReader sobre su borde inferior, el título, el autor y el año, y las marcas de Zotero y de la clave.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.ItemDelegate {
    id: tarjeta

    required property int index
    required property var model
    property bool actual: false
    signal elegida(int indice)
    signal abierta(int indice)

    padding: Kirigami.Units.smallSpacing
    bottomPadding: Kirigami.Units.largeSpacing
    highlighted: actual
    onClicked: elegida(index)
    onDoubleClicked: abierta(index)
    Accessible.name: model.titulo + ", " + model.autores + (model.año ? ", " + model.año : "")

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: width * 1.45
            Rectangle {                               // el sustituto: los colores del tema, el título y el autor
                anchors.fill: parent
                visible: !tarjeta.model.portada || portada.status !== Image.Ready
                radius: Kirigami.Units.cornerRadius
                color: Kirigami.Theme.alternateBackgroundColor
                border.color: Kirigami.Theme.disabledTextColor
                border.width: 1
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.largeSpacing
                    Kirigami.Icon { source: "x-office-document"; Layout.alignment: Qt.AlignHCenter; implicitWidth: Kirigami.Units.iconSizes.large; implicitHeight: implicitWidth; opacity: 0.5 }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: tarjeta.model.titulo
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                        maximumLineCount: 5
                        elide: Text.ElideRight
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillHeight: true }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: tarjeta.model.autores
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
            }
            Image {
                id: portada
                anchors.fill: parent
                source: tarjeta.model.fuente
                visible: tarjeta.model.portada
                asynchronous: true
                cache: true
                fillMode: Image.PreserveAspectFit
                verticalAlignment: Image.AlignBottom
                sourceSize.width: 220
                smooth: true
            }
        }
        QQC2.ProgressBar {                            // la lectura en KOReader (el hueco se guarda aunque no la haya)
            Layout.fillWidth: true
            opacity: tarjeta.model.koProgreso >= 0 ? 1 : 0
            from: 0; to: 1
            value: Math.max(0, tarjeta.model.koProgreso)
            Accessible.name: tarjeta.model.koProgreso >= 0 ? "Leído en KOReader: " + Math.round(tarjeta.model.koProgreso * 100) + " %" : "Sin abrir en KOReader"
            QQC2.ToolTip.text: "KOReader: " + Math.round(tarjeta.model.koProgreso * 100) + " %"
            QQC2.ToolTip.visible: hovered && tarjeta.model.koProgreso >= 0
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: tarjeta.model.titulo
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.weight: Font.DemiBold
            color: tarjeta.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label {
                Layout.fillWidth: true
                text: tarjeta.model.autores + (tarjeta.model.año ? " · " + tarjeta.model.año : "")
                elide: Text.ElideRight
                font: Kirigami.Theme.smallFont
                color: tarjeta.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
            }
            Kirigami.Icon {
                visible: tarjeta.model.clave !== ""
                source: "tag"
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
                Accessible.name: "Con clave para citar"
                QQC2.ToolTip.text: tarjeta.model.clave
                QQC2.ToolTip.visible: zonaClave.hovered
                HoverHandler { id: zonaClave }
            }
            Kirigami.Icon {
                source: tarjeta.model.zotero ? "data-success" : "emblem-unavailable"
                opacity: tarjeta.model.zotero ? 1 : 0.5
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
                Accessible.name: tarjeta.model.zotero ? "En Zotero" : "Sin Zotero"
                QQC2.ToolTip.text: tarjeta.model.zotero ? "Enlazado con Zotero" : "Sin Zotero"
                QQC2.ToolTip.visible: zonaZotero.hovered
                HoverHandler { id: zonaZotero }
            }
        }
    }
}
