// PanelFiltros — los filtros del catálogo (reingeniería B6): colección (la serie de Calibre), autor, año (por décadas) y
// tipo, cada uno con sus valores y cuántos libros da cada uno dentro de la búsqueda actual; un clic filtra, otro lo
// quita. Arriba, la ayuda de la búsqueda por campo.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.Control {
    id: raiz
    readonly property var l: studio.libros
    readonly property var claves: ({ coleccion: "coleccion", autor: "autor", decada: "decada", tipo: "tipo" })

    padding: 0
    Accessible.name: "Filtros del catálogo"

    contentItem: QQC2.ScrollView {
        id: desplazable
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: desplazable.availableWidth
            spacing: 0
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                Kirigami.Heading { level: 4; text: "Filtros"; Layout.fillWidth: true }
                QQC2.ToolButton {
                    text: "Quitar"
                    icon.name: "edit-clear-all"
                    visible: raiz.l.hayFiltros
                    onClicked: raiz.l.limpiarFiltros()
                }
            }
            Repeater {
                model: raiz.l.nombresFiltros
                delegate: ColumnLayout {
                    id: grupo
                    required property var modelData
                    readonly property var valores: raiz.l.facetas[modelData.clave] || []
                    readonly property string elegido: raiz.l.filtros[modelData.clave] || ""
                    property bool todos: false
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.ListSectionHeader { Layout.fillWidth: true; text: grupo.modelData.titulo + (grupo.elegido ? " · " + grupo.elegido : "") }
                    Repeater {
                        model: grupo.todos ? grupo.valores : grupo.valores.slice(0, 7)
                        delegate: QQC2.ItemDelegate {
                            required property var modelData
                            Layout.fillWidth: true
                            highlighted: grupo.elegido === modelData.valor
                            onClicked: raiz.l.fijarFiltro(grupo.modelData.clave, highlighted ? "" : modelData.valor)
                            Accessible.name: grupo.modelData.titulo + " " + modelData.valor + ", " + modelData.n + " libros"
                            contentItem: RowLayout {
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: modelData.valor
                                    elide: Text.ElideRight
                                    color: parent.parent.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                                }
                                QQC2.Label {
                                    text: modelData.n
                                    font: Kirigami.Theme.smallFont
                                    color: parent.parent.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
                                }
                            }
                        }
                    }
                    QQC2.ToolButton {
                        Layout.leftMargin: Kirigami.Units.smallSpacing
                        visible: grupo.valores.length > 7
                        text: grupo.todos ? "Menos" : "Ver los " + grupo.valores.length
                        flat: true
                        font: Kirigami.Theme.smallFont
                        onClicked: grupo.todos = !grupo.todos
                    }
                }
            }
            Kirigami.Separator { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing }
            QQC2.Label {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
                text: "Búsqueda por campo: <tt>titulo:</tt> <tt>autor:</tt> <tt>año:2010</tt> o <tt>año:1990-2000</tt> "
                      + "<tt>serie:</tt> <tt>etiqueta:</tt> <tt>id:</tt> (ISBN, DOI o el número de Calibre) <tt>clave:</tt>; "
                      + "comillas para varias palabras."
                textFormat: Text.StyledText
                wrapMode: Text.WordWrap
                font: Kirigami.Theme.smallFont
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
}
