// Bandejas — el trabajo pendiente de la biblioteca, aparte del catálogo (reingeniería B8): pendientes de clasificar,
// fichas incompletas, sin clave para citar, sin Zotero y sin portada; cada bandeja con lo que tiene (libros con su
// portada, documentos de la zona de entrada, fichas sin libro) y la operación que la vacía, que se simula y se aplica
// por la puerta con sus seis pasos a la vista. A la derecha, la ficha del libro elegido o la operación.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

RowLayout {
    id: raiz
    readonly property var l: studio.libros
    readonly property var b: l.bandejaInfo
    spacing: 0

    // la operación que vacía la bandeja queda elegida mientras se está en Bandejas (sin salir del área)
    function sincronizar() {
        if (studio.espacio.area !== "bandejas" || !raiz.b.operacion) return
        if (studio.operaciones.actual !== raiz.b.operacion) studio.operaciones.fijar(raiz.b.operacion)
    }
    function preparar() { sincronizar(); lado.currentIndex = 1 }
    Connections { target: studio.espacio; function onAreaCambiada() { raiz.sincronizar() } }
    Connections { target: raiz.l; function onBandejaCambiada() { raiz.sincronizar() } }
    Component.onCompleted: { if (raiz.l.bandeja === "" && raiz.l.bandejas.length) raiz.l.fijarBandeja(raiz.l.bandejas[0].clave); raiz.sincronizar() }

    // las bandejas
    QQC2.ScrollView {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 15
        Layout.fillHeight: true
        ListView {
            id: listaBandejas
            model: raiz.l.bandejas
            clip: true
            delegate: QQC2.ItemDelegate {
                required property var modelData
                width: ListView.view.width
                highlighted: modelData.clave === raiz.l.bandeja
                onClicked: raiz.l.fijarBandeja(modelData.clave)
                Accessible.name: modelData.titulo + ", " + modelData.n
                contentItem: RowLayout {
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon { source: modelData.icono; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { Layout.fillWidth: true; text: modelData.titulo; elide: Text.ElideRight; font.weight: Font.DemiBold; color: parent.parent.parent.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                        QQC2.Label { Layout.fillWidth: true; text: modelData.descripcion; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; font: Kirigami.Theme.smallFont; color: parent.parent.parent.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor }
                    }
                    QQC2.Label {
                        text: modelData.n
                        font.weight: Font.DemiBold
                        color: modelData.n > 0 ? (parent.parent.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.neutralTextColor) : Kirigami.Theme.disabledTextColor
                    }
                }
            }
        }
    }
    Kirigami.Separator { Layout.fillHeight: true }

    // lo que hay en la bandeja
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon { source: raiz.b.icono || "mail-folder-inbox"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Kirigami.Heading { level: 3; text: (raiz.b.titulo || "") + (raiz.b.n !== undefined ? " · " + raiz.b.n : ""); Layout.fillWidth: true; elide: Text.ElideRight }
                QQC2.Label { text: raiz.b.descripcion || ""; color: Kirigami.Theme.disabledTextColor; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
            QQC2.Button {
                visible: (raiz.b.operacion || "") !== ""
                text: "Preparar la operación"
                icon.name: "system-run"
                onClicked: raiz.preparar()
                QQC2.ToolTip.text: "Elige la operación que vacía esta bandeja: se simula con F5 y se aplica con Ctrl+Intro por la puerta"
                QQC2.ToolTip.visible: hovered
            }
        }
        Kirigami.Separator { Layout.fillWidth: true }
        QQC2.ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: contenido
                model: raiz.l.bandejaModelo
                clip: true
                section.property: "seccion"
                section.delegate: Kirigami.ListSectionHeader { required property string section; width: ListView.view.width; text: section }
                delegate: FilaLibro {
                    width: contenido.width
                    actual: !model.otro && model.id === raiz.l.id
                    onElegida: i => { if (!model.otro) { raiz.l.fijarId(model.id); lado.currentIndex = 0 } }
                    onAbierta: i => { if (!model.otro) { raiz.l.fijarId(model.id); studio.acciones.accion("libro.archivo").disparar() } }
                }
                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.gridUnit * 4
                    visible: contenido.count === 0
                    icon.name: "checkmark"
                    text: "Nada pendiente en esta bandeja"
                }
            }
        }
    }
    Kirigami.Separator { Layout.fillHeight: true }

    // a la derecha: el libro o la operación
    ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.fillHeight: true
        spacing: 0
        QQC2.TabBar {
            id: lado
            Layout.fillWidth: true
            currentIndex: 1                          // la operación que vacía la bandeja; un libro elegido pasa a «Libro»
            QQC2.TabButton { text: "Libro"; width: implicitWidth }
            QQC2.TabButton { text: "Operación"; width: implicitWidth }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: lado.currentIndex
            FichaEditorial { onCerrar: lado.currentIndex = 1 }
            Operacion {}
        }
    }
}
