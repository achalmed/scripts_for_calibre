// TarjetaLibro — un libro en la cuadrícula del catálogo (reingeniería B3–B4): la portada en miniatura (la de Calibre por
// `image://portadas/<id>`; sin portada, un sustituto con el título y el autor en los colores del tema), la barra de
// lectura de KOReader bajo la portada, del color de KOReader (BarraLectura, §9.9), el título, el autor y el año, y las
// marcas de Zotero y de la clave.
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
    highlighted: false                              // la elegida lleva un anillo, no el relleno (decisiones §9.2)
    hoverEnabled: true
    onClicked: elegida(index)
    background: Rectangle {
        radius: Kirigami.Units.cornerRadius * 2
        color: tarjeta.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.05) : "transparent"
        border.width: tarjeta.actual ? 2 : 0
        border.color: Kirigami.Theme.highlightColor
    }
    onDoubleClicked: abierta(index)
    Accessible.name: model.titulo + ", " + model.autores + (model.año ? ", " + model.año : "")

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: width * 1.45
            // el sustituto: los colores del tema, el título y el autor; anclado abajo y con la proporción de una portada
            // común (no la caja entera, que lo hacía más alto que las portadas vecinas), sin borde gris
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.width * 1.33
                visible: !tarjeta.model.portada || portada.status !== Image.Ready
                radius: Kirigami.Units.cornerRadius
                color: Kirigami.Theme.alternateBackgroundColor
                border.color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.12)
                border.width: 1
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.largeSpacing
                    Kirigami.Icon { source: "x-office-document-symbolic"; isMask: true; color: Kirigami.Theme.disabledTextColor; Layout.alignment: Qt.AlignHCenter
                                    implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth; opacity: 0.7 }
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
        BarraLectura {                                // la lectura en KOReader, de su color (el hueco se guarda aunque no la haya)
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing / 2
            opacity: tarjeta.model.koProgreso >= 0 ? 1 : 0
            fraccion: Math.max(0, tarjeta.model.koProgreso)
            tono: studio.lectura.colores.koreader || ""
            Accessible.name: tarjeta.model.koProgreso >= 0 ? "Leído en KOReader: " + Math.round(tarjeta.model.koProgreso * 100) + " %" : "Sin abrir en KOReader"
            QQC2.ToolTip.text: "KOReader: " + Math.round(tarjeta.model.koProgreso * 100) + " %"
            QQC2.ToolTip.visible: zonaLectura.hovered && tarjeta.model.koProgreso >= 0
            HoverHandler { id: zonaLectura }
        }
        FontMetrics { id: metricas; font: Kirigami.Theme.defaultFont }
        QQC2.Label {
            Layout.fillWidth: true
            // siempre el alto de dos líneas: los títulos de una línea ya no bajan la fila de autor y año de su tarjeta
            Layout.preferredHeight: Math.ceil(metricas.lineSpacing * 2)
            verticalAlignment: Text.AlignTop
            text: tarjeta.model.titulo
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.weight: Font.DemiBold
            color: Kirigami.Theme.textColor
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label {
                Layout.fillWidth: true
                text: tarjeta.model.autores + (tarjeta.model.año ? " · " + tarjeta.model.año : "")
                elide: Text.ElideRight
                font: Kirigami.Theme.smallFont
                color: Kirigami.Theme.disabledTextColor
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
                // en Zotero, una palomita verde; sin él, una interrogación tenue (antes, un círculo con aspa que parecía
                // un botón de quitar, y una «data-success» que en Colloid parece una casilla de verificación)
                source: tarjeta.model.zotero ? "checkmark" : "dialog-question-symbolic"
                color: tarjeta.model.zotero ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
                opacity: tarjeta.model.zotero ? 1 : 0.6
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
