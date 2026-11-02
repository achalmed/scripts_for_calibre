// Catalogo — la vista principal (reingeniería B3–B7): los filtros a la izquierda (F9), las portadas en cuadrícula o la
// lista compacta (Ctrl+G) en el centro, con su orden, y la ficha editorial del libro elegido a la derecha. Intro o doble
// clic abre el documento con su aplicación.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

RowLayout {
    id: raiz
    readonly property var l: studio.libros
    property bool mostrarFiltros: true
    property bool mostrarFicha: true
    spacing: 0

    function irA(i) {
        if (i < 0) return
        rejilla.currentIndex = i; lista.currentIndex = i
        if (raiz.l.enLista) lista.positionViewAtIndex(i, ListView.Contain); else rejilla.positionViewAtIndex(i, GridView.Contain)
        raiz.mostrarFicha = true
    }
    function elegir(i) { raiz.l.fijarFila(i); rejilla.currentIndex = i; lista.currentIndex = i; raiz.mostrarFicha = true }
    function abrir(i) { elegir(i); studio.acciones.accion("libro.archivo").disparar() }
    Connections { target: raiz.l; function onSeleccionar(i) { raiz.irA(i) } }

    PanelFiltros {
        visible: raiz.mostrarFiltros
        Layout.preferredWidth: Kirigami.Units.gridUnit * 14
        Layout.fillHeight: true
    }
    Kirigami.Separator { Layout.fillHeight: true; visible: raiz.mostrarFiltros }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            QQC2.Label {
                text: raiz.l.visibles === raiz.l.total ? raiz.l.total + " libros" : raiz.l.visibles + " de " + raiz.l.total + " libros"
                font.weight: Font.DemiBold
            }
            Repeater {                               // los filtros puestos, como fichas que se quitan
                model: raiz.l.nombresFiltros.filter(n => (raiz.l.filtros[n.clave] || "") !== "")
                delegate: QQC2.Button {
                    required property var modelData
                    text: modelData.titulo + ": " + raiz.l.filtros[modelData.clave]
                    icon.name: "edit-delete-remove"
                    flat: true
                    font: Kirigami.Theme.smallFont
                    onClicked: raiz.l.fijarFiltro(modelData.clave, "")
                }
            }
            Item { Layout.fillWidth: true }
            QQC2.Label { text: "Orden:"; color: Kirigami.Theme.disabledTextColor }
            QQC2.ComboBox {
                model: raiz.l.ordenes
                textRole: "titulo"
                currentIndex: raiz.l.ordenes.findIndex(o => o.clave === raiz.l.orden)
                onActivated: i => raiz.l.fijarOrden(raiz.l.ordenes[i].clave)
                Accessible.name: "Orden del catálogo"
            }
            QQC2.ToolButton {
                icon.name: raiz.l.enLista ? "view-list-icons" : "view-list-details"
                text: raiz.l.enLista ? "Cuadrícula" : "Lista"
                display: QQC2.AbstractButton.IconOnly
                onClicked: raiz.l.alternarForma()
                QQC2.ToolTip.text: (raiz.l.enLista ? "Ver las portadas" : "Ver la lista compacta") + " (Ctrl+G)"
                QQC2.ToolTip.visible: hovered
                Accessible.name: text
            }
        }
        Kirigami.Separator { Layout.fillWidth: true }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            GridView {
                id: rejilla
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                visible: !raiz.l.enLista
                clip: true
                model: raiz.l.modelo
                readonly property int columnas: Math.max(1, Math.floor(width / (Kirigami.Units.gridUnit * 9)))
                cellWidth: width / columnas
                cellHeight: cellWidth * 1.45 + Kirigami.Units.gridUnit * 6
                keyNavigationEnabled: true
                activeFocusOnTab: true
                currentIndex: -1
                cacheBuffer: cellHeight * 2
                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                delegate: TarjetaLibro {
                    width: rejilla.cellWidth
                    height: rejilla.cellHeight
                    actual: model.id === raiz.l.id
                    onElegida: i => raiz.elegir(i)
                    onAbierta: i => raiz.abrir(i)
                }
                Keys.onReturnPressed: raiz.abrir(currentIndex)
                onCurrentIndexChanged: if (activeFocus && currentIndex >= 0) raiz.l.fijarFila(currentIndex)
            }
            ListView {
                id: lista
                anchors.fill: parent
                visible: raiz.l.enLista
                clip: true
                model: raiz.l.modelo
                keyNavigationEnabled: true
                activeFocusOnTab: true
                currentIndex: -1
                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                delegate: FilaLibro {
                    width: lista.width
                    actual: model.id === raiz.l.id
                    onElegida: i => raiz.elegir(i)
                    onAbierta: i => raiz.abrir(i)
                }
                Keys.onReturnPressed: raiz.abrir(currentIndex)
                onCurrentIndexChanged: if (activeFocus && currentIndex >= 0) raiz.l.fijarFila(currentIndex)
            }
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.gridUnit * 4
                visible: raiz.l.visibles === 0
                icon.name: "folder-book"
                text: raiz.l.total === 0 ? "La biblioteca está vacía o no se pudo leer" : "Ningún libro cumple la búsqueda"
                explanation: raiz.l.total === 0 ? (raiz.l.error || "Comprueba la biblioteca de Calibre (BIBLIOTECA_DIR) y actualiza el índice (Ctrl+R)")
                                                : "Prueba con menos palabras o quita los filtros"
                helpfulAction: Kirigami.Action { text: "Quitar los filtros"; icon.name: "edit-clear-all"; enabled: raiz.l.hayFiltros; onTriggered: raiz.l.limpiarFiltros() }
            }
        }
    }
    Kirigami.Separator { Layout.fillHeight: true; visible: ficha.visible }
    FichaEditorial {
        id: ficha
        visible: raiz.mostrarFicha && raiz.l.hayActual
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.fillHeight: true
        onCerrar: raiz.mostrarFicha = false
    }
}
