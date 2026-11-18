// Cifra — un número grande con su rótulo tenue debajo (decisiones §9.9): las cifras de Inicio, de Lectura y de la ficha
// del libro. Si `interactiva`, es un botón que lleva a su lugar (`pulsada`). Letras y colores de Kirigami.Theme.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: raiz
    property string valor: ""
    property string rotulo: ""
    property bool interactiva: false
    property string ayuda: ""
    signal pulsada()

    hoverEnabled: interactiva
    focusPolicy: interactiva ? Qt.TabFocus : Qt.NoFocus
    padding: interactiva ? Kirigami.Units.smallSpacing : 0
    Accessible.name: rotulo + ": " + valor
    onClicked: if (interactiva) pulsada()
    contentItem: ColumnLayout {
        spacing: 0
        QQC2.Label {
            Layout.fillWidth: true
            text: raiz.valor
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.45
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        QQC2.Label {
            Layout.fillWidth: true
            text: raiz.rotulo
            font: Kirigami.Theme.smallFont
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
        }
    }
    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: raiz.interactiva && raiz.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent"
    }
    QQC2.ToolTip.text: ayuda
    QQC2.ToolTip.visible: hovered && ayuda !== ""
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
}
