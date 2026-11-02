// PasosPuerta — los seis pasos de una escritura por la puerta (reingeniería B9): la aplicación cerrada, el candado, el
// respaldo verificado, aplicar, la integridad y liberar, cada uno con su estado (en espera, en curso, hecho, falló,
// omitido) y su detalle. Antes de aplicar dice cómo está la puerta ahora; durante y después, lo que la suite hizo. La
// ventana no abre la puerta: los pasos los da `lib/escribir.*` dentro de la suite (`servicios/pasos.py`).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: raiz
    readonly property var o: studio.operaciones
    visible: o.pasos.length > 0
    spacing: Kirigami.Units.smallSpacing
    Accessible.name: "Pasos de la puerta de escritura"

    function icono(estado) {
        switch (estado) {
        case "hecho": return "data-success"
        case "fallo": return "data-error"
        case "omitido": return "dialog-cancel"
        case "en_curso": return "view-refresh"
        default: return ""
        }
    }
    function color(estado) {
        switch (estado) {
        case "hecho": return Kirigami.Theme.positiveTextColor
        case "fallo": return Kirigami.Theme.negativeTextColor
        case "en_curso": return Kirigami.Theme.highlightColor
        default: return Kirigami.Theme.disabledTextColor
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Kirigami.Heading { level: 4; text: "La puerta de escritura" }
        Item { Layout.fillWidth: true }
        QQC2.Label {
            text: raiz.o.resumenPasos
            color: Kirigami.Theme.disabledTextColor
            font: Kirigami.Theme.smallFont
            elide: Text.ElideRight
            Layout.maximumWidth: raiz.width * 0.6
        }
    }
    Repeater {
        model: raiz.o.pasos
        delegate: RowLayout {
            id: paso
            required property var modelData
            required property int index
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Accessible.name: (index + 1) + ". " + modelData.titulo + ": " + modelData.estado + (modelData.detalle ? ", " + modelData.detalle : "")
            // el número sobre la línea que une los pasos
            Item {
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.fillHeight: true
                Layout.minimumHeight: Kirigami.Units.gridUnit * 2.2
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: parent.height / 2
                    width: 2
                    height: parent.height / 2 + Kirigami.Units.smallSpacing
                    visible: paso.index < raiz.o.pasos.length - 1
                    color: Kirigami.Theme.disabledTextColor
                    opacity: 0.4
                }
                Rectangle {                            // en espera: un círculo vacío
                    anchors.centerIn: parent
                    visible: paso.modelData.estado === "pendiente"
                    width: Kirigami.Units.iconSizes.small
                    height: width
                    radius: width / 2
                    color: Kirigami.Theme.backgroundColor
                    border.color: Kirigami.Theme.disabledTextColor
                    border.width: 2
                }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    visible: paso.modelData.estado !== "pendiente"
                    width: Kirigami.Units.iconSizes.smallMedium
                    height: width
                    source: raiz.icono(paso.modelData.estado)
                    color: raiz.color(paso.modelData.estado)
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                QQC2.Label {
                    Layout.fillWidth: true
                    text: (paso.index + 1) + ". " + paso.modelData.titulo
                    font.weight: paso.modelData.estado === "en_curso" || paso.modelData.estado === "fallo" ? Font.DemiBold : Font.Normal
                    color: paso.modelData.estado === "fallo" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                    elide: Text.ElideRight
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: paso.modelData.detalle || paso.modelData.explicacion
                    color: Kirigami.Theme.disabledTextColor
                    font: Kirigami.Theme.smallFont
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
