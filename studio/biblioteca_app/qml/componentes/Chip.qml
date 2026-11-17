// Chip — un botón ligero de contorno fino y esquinas suaves (el de Datafw Studio y LaTeX Studio, decisiones §9.2): las
// áreas y acciones de la barra de arriba y de la ficha. Colores, radio y letra salen de Kirigami.Theme y Units.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: raiz

    property string icono: ""
    property bool destacado: false
    property string ayuda: ""

    hoverEnabled: true
    padding: Kirigami.Units.smallSpacing
    leftPadding: Kirigami.Units.largeSpacing
    rightPadding: Kirigami.Units.largeSpacing
    font: Kirigami.Theme.defaultFont
    Accessible.name: text

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing
        Kirigami.Icon {
            visible: raiz.icono !== ""
            source: raiz.icono
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
            color: raiz.destacado ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
        }
        QQC2.Label {
            text: raiz.text
            font: raiz.font
            color: raiz.destacado ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            visible: text !== ""
        }
    }
    background: Rectangle {
        radius: Kirigami.Units.cornerRadius
        color: raiz.destacado ? Kirigami.Theme.highlightColor
             : (raiz.down ? Qt.alpha(Kirigami.Theme.textColor, 0.12) : (raiz.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent"))
        border.width: raiz.destacado ? 0 : 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, raiz.hovered ? 0.35 : 0.2)
    }
    QQC2.ToolTip.text: ayuda
    QQC2.ToolTip.visible: hovered && ayuda !== ""
    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
}
