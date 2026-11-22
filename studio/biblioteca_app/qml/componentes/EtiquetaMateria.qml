// EtiquetaMateria — una etiqueta (materia) de Calibre como las que se pegan en los libros (2026-11-22, pedido del autor):
// una pestaña con la punta triangular a la izquierda y un ojal, en un tono neutro del texto (el acento de Lliphi Oscuro
// es rojo y las etiquetas parecerían errores); al pasar se marca y un clic
// busca los libros con esa etiqueta. Sin colores propios: todo sale de Kirigami.Theme.
import QtQuick
import QtQuick.Shapes
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: raiz
    readonly property real punta: height * 0.42
    readonly property color tinta: Kirigami.Theme.textColor
    hoverEnabled: true
    focusPolicy: Qt.TabFocus
    font: Kirigami.Theme.smallFont
    leftPadding: punta + Kirigami.Units.smallSpacing * 1.5
    rightPadding: Kirigami.Units.smallSpacing * 2.5
    topPadding: Kirigami.Units.smallSpacing
    bottomPadding: Kirigami.Units.smallSpacing
    Accessible.role: Accessible.Button
    Accessible.name: "Etiqueta " + text

    HoverHandler { cursorShape: Qt.PointingHandCursor }

    contentItem: QQC2.Label {
        text: raiz.text
        font: raiz.font
        color: Kirigami.Theme.textColor
        opacity: raiz.hovered || raiz.visualFocus ? 1 : 0.85
        verticalAlignment: Text.AlignVCenter
    }

    background: Item {
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeWidth: raiz.visualFocus ? 2 : 1
                strokeColor: Qt.alpha(raiz.tinta, raiz.hovered || raiz.visualFocus ? 0.6 : 0.28)
                fillColor: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, raiz.tinta,
                                                                   raiz.pressed ? 0.24 : raiz.hovered ? 0.16 : 0.08)
                joinStyle: ShapePath.RoundJoin
                startX: raiz.punta; startY: 0.5
                PathLine { x: raiz.width - 3.5; y: 0.5 }
                PathArc { x: raiz.width - 0.5; y: 3.5; radiusX: 3; radiusY: 3 }
                PathLine { x: raiz.width - 0.5; y: raiz.height - 3.5 }
                PathArc { x: raiz.width - 3.5; y: raiz.height - 0.5; radiusX: 3; radiusY: 3 }
                PathLine { x: raiz.punta; y: raiz.height - 0.5 }
                PathLine { x: 0.5; y: raiz.height / 2 }
                PathLine { x: raiz.punta; y: 0.5 }
            }
        }
        Rectangle {                     // el ojal
            width: Math.max(3, raiz.height * 0.16)
            height: width
            radius: width / 2
            x: raiz.punta * 0.72 - width / 2
            y: (raiz.height - height) / 2
            color: Kirigami.Theme.backgroundColor
            border.width: 1
            border.color: Qt.alpha(raiz.tinta, 0.4)
        }
    }
}
