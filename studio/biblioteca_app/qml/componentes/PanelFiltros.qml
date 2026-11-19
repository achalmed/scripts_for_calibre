// PanelFiltros — los filtros del catálogo (reingeniería B6): colección (la serie de Calibre), autor, año (por décadas) y
// tipo, cada uno con sus valores y cuántos libros da cada uno dentro de la búsqueda actual; un clic filtra, otro lo
// quita. Arriba, la ayuda de la búsqueda por campo.
// Cada grupo se pliega con un clic en su título (y se recuerda); «Ver los N» muestra todos sus valores, y en un grupo largo
// (las colecciones son más de cien) un campo busca entre ellos (2026-11-19).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtCore
import org.kde.kirigami as Kirigami

QQC2.Control {
    id: raiz
    readonly property var l: studio.libros
    readonly property var claves: ({ coleccion: "coleccion", autor: "autor", decada: "decada", tipo: "tipo" })

    padding: 0
    Accessible.name: "Filtros del catálogo"

    Settings { id: recuerdo; category: "catalogo/filtros"; property var plegados: ({}) }
    function plegar(clave, si) { const p = Object.assign({}, recuerdo.plegados || {}); p[clave] = si; recuerdo.plegados = p }

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
                    readonly property bool plegado: !!(recuerdo.plegados || {})[modelData.clave]
                    readonly property var hallados: busca.text === "" ? grupo.valores
                                                    : grupo.valores.filter(v => String(v.valor).toLowerCase().indexOf(busca.text.toLowerCase()) >= 0)
                    property bool todos: false
                    Layout.fillWidth: true
                    spacing: 0
                    // el título del grupo: un clic lo pliega o lo despliega
                    QQC2.AbstractButton {
                        id: cabecera
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        hoverEnabled: true
                        padding: Kirigami.Units.smallSpacing
                        leftPadding: Kirigami.Units.largeSpacing
                        onClicked: raiz.plegar(grupo.modelData.clave, !grupo.plegado)
                        Accessible.name: grupo.modelData.titulo + (grupo.plegado ? ", plegado" : ", desplegado")
                        contentItem: RowLayout {
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: grupo.modelData.titulo + (grupo.elegido ? " · " + grupo.elegido : "")
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            QQC2.Label { text: grupo.valores.length; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                            Kirigami.Icon {
                                source: grupo.plegado ? "go-next-symbolic" : "go-down-symbolic"
                                implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                color: Kirigami.Theme.disabledTextColor
                            }
                        }
                        background: Rectangle { color: cabecera.hovered ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent" }
                    }
                    Kirigami.SearchField {
                        id: busca
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.smallSpacing
                        Layout.rightMargin: Kirigami.Units.smallSpacing
                        visible: !grupo.plegado && grupo.todos && grupo.valores.length > 15
                        placeholderText: "Buscar en " + grupo.modelData.titulo.toLowerCase()
                        font: Kirigami.Theme.smallFont
                    }
                    Repeater {
                        model: grupo.plegado ? [] : (grupo.todos ? grupo.hallados : grupo.valores.slice(0, 7))
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
                    // «Ver los N»: una fila entera, como las de los valores (el botón de antes se cortaba en «Ver los …»)
                    QQC2.ItemDelegate {
                        Layout.fillWidth: true
                        visible: !grupo.plegado && grupo.valores.length > 7
                        text: grupo.todos ? "Ver menos" : "Ver los " + grupo.valores.length
                        icon.name: grupo.todos ? "go-up-symbolic" : "go-down-symbolic"
                        font: Kirigami.Theme.smallFont
                        onClicked: { grupo.todos = !grupo.todos; if (!grupo.todos) busca.text = "" }
                        Accessible.name: grupo.todos ? "Ver menos " + grupo.modelData.titulo : "Ver todos los valores de " + grupo.modelData.titulo
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
