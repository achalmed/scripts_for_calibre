// Tarjeta — una tarjeta sutil (decisiones §9.2 y §9.9): el fondo de la vista, una línea fina y esquinas suaves, con su
// contenido en columna. La de Lectura, Inicio, Fichas y Coherencia (antes vivía dentro de Lectura.qml). Colores y radios
// salen de Kirigami.Theme y Units.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: raiz
    default property alias contenido: columna.data
    property alias espacio: columna.spacing
    property bool resaltada: false                    // la elegida: un anillo del color de acento, no el relleno (§9.2)
    Layout.fillWidth: true
    implicitWidth: columna.implicitWidth + Kirigami.Units.largeSpacing * 2
    implicitHeight: columna.implicitHeight + Kirigami.Units.largeSpacing * 2
    radius: Kirigami.Units.cornerRadius * 2
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false
    color: Kirigami.Theme.backgroundColor
    border.width: resaltada ? 2 : 1
    border.color: resaltada ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, 0.1)
    ColumnLayout {
        id: columna
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
    }
}
