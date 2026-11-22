// Catalogo — el área «Catálogo» (Ctrl+2; reingeniería B3–B7, rediseño del 2026-11-18, decisiones §9.9): los filtros a la
// izquierda (F9), las portadas en cuadrícula o la lista compacta (Ctrl+G) en el centro, con su orden, y la ficha editorial
// del libro elegido a la derecha. Arriba, la fila de los filtros puestos (y la búsqueda), que se quitan con un toque; bajo
// cada portada, la barra de lectura del color de KOReader. Intro o doble clic abre el documento con su aplicación.
// Los tres paneles van en un divisor (2026-11-19): el borde entre los filtros, el centro y la ficha se arrastra y el ancho
// se recuerda entre sesiones.
// 2026-11-22 (pedido del autor): «Agrupar» (colección, autor, tipo, década) con títulos de grupo en la lista, aparte del
// orden (que suma «Colección (índice)»); y «Sincronizar»: qué se sigue solo (Calibre al momento; de Zotero, las claves al
// momento y los metadatos con «Zotero ⇄ Calibre») y los dos botones para hacerlo ya.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtCore
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.SplitView {
    id: raiz
    readonly property var l: studio.libros
    property bool mostrarFiltros: true
    property bool mostrarFicha: true
    orientation: Qt.Horizontal

    Settings { id: recuerdo; category: "catalogo"; property var divisor }
    Component.onCompleted: if (recuerdo.divisor) raiz.restoreState(recuerdo.divisor)
    onResizingChanged: if (!resizing) recuerdo.divisor = raiz.saveState()

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
        QQC2.SplitView.preferredWidth: Kirigami.Units.gridUnit * 16
        QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 9
        QQC2.SplitView.maximumWidth: Kirigami.Units.gridUnit * 40
    }

    ColumnLayout {
        QQC2.SplitView.fillWidth: true
        QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 14
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            QQC2.Label {
                text: raiz.l.visibles === raiz.l.total ? raiz.l.total + " libros" : raiz.l.visibles + " de " + raiz.l.total + " libros"
                font.weight: Font.DemiBold
            }
            Item { Layout.fillWidth: true }
            QQC2.ToolButton {
                id: botonSincronia
                icon.name: "folder-sync"
                text: raiz.l.rehaciendoIndice ? "Sincronizando…" : "Sincronizar"
                display: QQC2.AbstractButton.TextBesideIcon
                onClicked: menuSincronia.popup(botonSincronia, 0, botonSincronia.height)
                QQC2.ToolTip.text: raiz.l.estadoSincronia
                QQC2.ToolTip.visible: hovered
                Accessible.name: "Sincronizar con Calibre y Zotero"
                Accessible.description: raiz.l.estadoSincronia
                QQC2.Menu {
                    id: menuSincronia
                    QQC2.MenuItem {
                        text: "Traer de Zotero las claves ahora (Ctrl+R)"
                        icon.name: "view-refresh"
                        enabled: !raiz.l.rehaciendoIndice
                        onTriggered: studio.acciones.accion("ver.indice").disparar()
                    }
                    QQC2.MenuItem {
                        text: "Zotero ⇄ Calibre: los metadatos…"
                        icon.name: "zotero"
                        onTriggered: { studio.acciones.accion("op.zotero_calibre").disparar(); studio.acciones.accion("ver.vista.sincronizar").disparar() }
                    }
                    QQC2.MenuSeparator {}
                    QQC2.MenuItem {
                        text: "Seguir los cambios de Calibre y Zotero"
                        checkable: true
                        checked: raiz.l.vigilar
                        onTriggered: { studio.acciones.accion("ver.vigilar").disparar(); checked = Qt.binding(() => raiz.l.vigilar) }
                    }
                    QQC2.MenuItem {
                        enabled: false
                        contentItem: QQC2.Label {
                            text: raiz.l.estadoSincronia.split(" · ").join("\n")
                            font: Kirigami.Theme.smallFont
                            color: Kirigami.Theme.disabledTextColor
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
            QQC2.Label { text: "Agrupar:"; color: Kirigami.Theme.disabledTextColor }
            QQC2.ComboBox {
                model: raiz.l.agrupaciones
                textRole: "titulo"
                currentIndex: raiz.l.agrupaciones.findIndex(o => o.clave === raiz.l.agrupar)
                onActivated: i => raiz.l.fijarAgrupar(raiz.l.agrupaciones[i].clave)
                Accessible.name: "Agrupar el catálogo por"
                QQC2.ToolTip.text: "Los grupos se ven con su título en la lista (Ctrl+G)"
                QQC2.ToolTip.visible: hovered
            }
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
        // los filtros puestos y la búsqueda: un toque los quita (§9.9)
        Flow {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            visible: raiz.l.hayFiltros || raiz.l.busqueda !== ""
            spacing: Kirigami.Units.smallSpacing
            OpcionColor {
                visible: raiz.l.busqueda !== ""
                elegida: true                         // la búsqueda puesta: teñida, y un toque la quita
                text: "Búsqueda: " + raiz.l.busqueda
                icon.name: "edit-delete-remove"
                descripcion: "Quitar la búsqueda"
                onClicked: raiz.l.buscar("")
            }
            Repeater {
                model: raiz.l.nombresFiltros.filter(n => (raiz.l.filtros[n.clave] || "") !== "")
                delegate: OpcionColor {
                    required property var modelData
                    elegida: true
                    text: modelData.titulo + ": " + raiz.l.filtros[modelData.clave]
                    icon.name: "edit-delete-remove"
                    descripcion: "Quitar este filtro"
                    onClicked: raiz.l.fijarFiltro(modelData.clave, "")
                }
            }
            QQC2.ToolButton {
                visible: (raiz.l.busqueda !== "" ? 1 : 0) + raiz.l.nombresFiltros.filter(n => (raiz.l.filtros[n.clave] || "") !== "").length > 1
                text: "Quitar todo"
                flat: true
                font: Kirigami.Theme.smallFont
                onClicked: { raiz.l.limpiarFiltros(); raiz.l.buscar("") }
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
                // el modelo, solo en la forma a la vista (cuadrícula o lista): la oculta rehacía sus filas en cada búsqueda o filtro (2026-11-19)
                model: raiz.l.enLista ? null : raiz.l.modelo
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
                model: raiz.l.enLista ? raiz.l.modelo : null
                keyNavigationEnabled: true
                activeFocusOnTab: true
                currentIndex: -1
                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                // agrupada: el título de cada grupo, fijo arriba mientras se recorre (las filas ya vienen por grupo)
                section.property: raiz.l.agrupar !== "" ? "grupo" : ""
                section.criteria: ViewSection.FullString
                section.labelPositioning: ViewSection.InlineLabels | ViewSection.CurrentLabelAtStart
                section.delegate: Kirigami.ListSectionHeader {
                    required property string section
                    width: ListView.view ? ListView.view.width : 0
                    text: section
                }
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
    FichaEditorial {
        id: ficha
        visible: raiz.mostrarFicha && raiz.l.hayActual
        QQC2.SplitView.preferredWidth: Kirigami.Units.gridUnit * 24
        QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 16
        onCerrar: raiz.mostrarFicha = false
    }
}
