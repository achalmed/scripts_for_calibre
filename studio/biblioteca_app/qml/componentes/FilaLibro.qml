// FilaLibro — un libro (o un documento de la zona de entrada, en una bandeja) en la lista compacta: la portada pequeña,
// el título, autor · año · serie · tipo, la lectura de KOReader (su barra, de su color: §9.9) y las marcas de Zotero
// y de la clave.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.ItemDelegate {
    id: fila

    required property int index
    required property var model
    property bool actual: false
    signal elegida(int indice)
    signal abierta(int indice)

    highlighted: actual
    // la elegida teñida con su marca (FondoSeleccion de la base), no el bloque lleno del acento (en Lliphi Oscuro, el rojo de los errores)
    background: FondoSeleccion { elegida: fila.highlighted; sobre: fila.hovered; pulsada: fila.pressed; foco: fila.visualFocus }
    onClicked: elegida(index)
    onDoubleClicked: abierta(index)
    Accessible.name: model.titulo + ", " + model.autores

    readonly property color secundario: Kirigami.Theme.disabledTextColor

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
                source: fila.model.otro ? "document-import" : "x-office-document-symbolic"
                isMask: true                                  // simbólico y tenue: el azul del tipo de archivo desentonaba con las portadas
                color: Kirigami.Theme.disabledTextColor
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
                color: Kirigami.Theme.textColor
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
        BarraLectura {                                // del color de KOReader (§9.9)
            visible: fila.model.koProgreso >= 0
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4
            fraccion: Math.max(0, fila.model.koProgreso)
            tono: studio.lectura.colores.koreader || ""
            Accessible.name: "Leído en KOReader: " + Math.round(fila.model.koProgreso * 100) + " %"
        }
        Kirigami.Icon {
            visible: !fila.model.otro
            // en Zotero, una palomita verde; sin él, una interrogación tenue (antes, un círculo con aspa que parecía
            // un botón de quitar, y una «data-success» que en Colloid parece una casilla de verificación)
            source: fila.model.zotero ? "checkmark" : "dialog-question-symbolic"
            color: fila.model.zotero ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
            opacity: fila.model.zotero ? 1 : 0.6
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
            Accessible.name: fila.model.zotero ? "En Zotero" : "Sin Zotero"
        }
    }
}
