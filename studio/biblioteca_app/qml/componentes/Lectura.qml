// Lectura — el área «Lectura» (Ctrl+5, decisiones §9.6): la base de lectura de Biblioteca Studio, donde se juntan los
// subrayados, resaltados y notas de KOReader, Zotero, Okular y Yachay, y las horas, sesiones y progreso de cada libro.
// A la izquierda, el resumen de toda la base (con las horas de las últimas doce semanas) y los libros con lectura; a la
// derecha, el libro elegido: su tiempo y su progreso en cada herramienta, sus subrayados (filtrados por origen con los
// chips; cada uno se copia como cita) y sus últimas sesiones. Solo lee (studio.lectura): la base la escribe la operación
// «Base de lectura» de Coherencia › Sincronizar. Sin colores propios: el de cada subrayado es el que le dio su herramienta.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

QQC2.Control {
    id: raiz
    readonly property var lec: studio.lectura
    readonly property var r: lec.resumen
    readonly property var b: lec.libro
    padding: 0
    Accessible.name: "Lectura"

    // una tarjeta sutil: el fondo de la vista, una línea fina, esquinas suaves
    component Tarjeta: Rectangle {
        default property alias contenido: columna.data
        property alias espacio: columna.spacing
        Layout.fillWidth: true
        implicitHeight: columna.implicitHeight + Kirigami.Units.largeSpacing * 2
        radius: Kirigami.Units.cornerRadius * 2
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.1)
        ColumnLayout {
            id: columna
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
        }
    }
    component Tenue: QQC2.Label {
        Layout.fillWidth: true
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }
    component Cifra: ColumnLayout {
        property string valor: ""
        property string rotulo: ""
        spacing: 0
        QQC2.Label { text: parent.valor; font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.35; font.weight: Font.DemiBold }
        QQC2.Label { text: parent.rotulo; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
    }

    contentItem: Item {
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: Math.min(parent.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 30)
            visible: !raiz.lec.hayBase
            icon.name: "view-readermode"
            text: "La base de lectura aún está vacía"
            explanation: "Coherencia › Sincronizar › «Base de lectura» junta aquí los subrayados y las horas de KOReader, Zotero, Okular y Yachay (F5 simula, Ctrl+Intro aplica)."
            helpfulAction: Kirigami.Action {
                text: "Ir a Sincronizar"
                icon.name: "folder-sync"
                onTriggered: { studio.operaciones.fijar("base_lectura"); studio.espacio.fijarVista("sincronizar"); studio.espacio.fijarArea("coherencia") }
            }
        }

        QQC2.SplitView {
            anchors.fill: parent
            visible: raiz.lec.hayBase
            orientation: Qt.Horizontal

            // ---------------------------------------------------------------- la base entera y los libros con lectura
            ColumnLayout {
                QQC2.SplitView.preferredWidth: Kirigami.Units.gridUnit * 24
                QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 16
                spacing: 0

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing

                    Tarjeta {
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing * 2
                            Cifra { valor: raiz.r.tiempo || "—"; rotulo: "en total" }
                            Cifra { valor: raiz.r.mes || "—"; rotulo: "este mes" }
                            Cifra { valor: String(raiz.r.racha || 0); rotulo: raiz.r.racha === 1 ? "día seguido" : "días seguidos" }
                            Item { Layout.fillWidth: true }
                        }
                        // las horas de las últimas doce semanas: una barra por semana, del color de acento
                        Item {
                            Layout.fillWidth: true
                            Layout.topMargin: Kirigami.Units.smallSpacing
                            implicitHeight: Kirigami.Units.gridUnit * 3
                            Row {
                                id: barras
                                anchors.fill: parent
                                spacing: Kirigami.Units.smallSpacing / 2
                                Repeater {
                                    model: raiz.lec.semanas
                                    delegate: Item {
                                        required property var modelData
                                        width: (barras.width - barras.spacing * 11) / 12
                                        height: barras.height
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            width: parent.width
                                            height: Math.max(2, parent.height * modelData.proporcion)
                                            radius: Kirigami.Units.cornerRadius / 2
                                            color: modelData.horas > 0 ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, 0.1)
                                        }
                                        QQC2.ToolTip.text: "Semana del " + modelData.etiqueta + ": " + modelData.horas + " h en " + modelData.sesiones + " sesiones"
                                        QQC2.ToolTip.visible: zona.containsMouse
                                        MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true }
                                        Accessible.name: QQC2.ToolTip.text
                                    }
                                }
                            }
                        }
                        Tenue { text: "Últimas doce semanas, de KOReader (la única herramienta que guarda la hora de cada página)" }
                        Tenue {
                            Layout.topMargin: Kirigami.Units.smallSpacing
                            text: raiz.r.anotaciones + " subrayados (" + raiz.r.origenes + "; " + raiz.r.compartidas + " en más de una herramienta) · "
                                  + raiz.r.sesiones + " sesiones · " + raiz.r.libros + " libros · sincronizado: " + raiz.r.ultima
                        }
                    }
                }

                ListView {
                    id: lista
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: raiz.lec.libros
                    QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                    delegate: QQC2.ItemDelegate {
                        id: fila
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        highlighted: modelData.id === raiz.lec.actualId
                        enabled: modelData.id >= 0
                        onClicked: raiz.lec.elegir(modelData.id)
                        Accessible.name: modelData.titulo + ", " + modelData.detalle
                        contentItem: ColumnLayout {
                            spacing: 0
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: fila.modelData.titulo
                                elide: Text.ElideRight
                                font.weight: Font.DemiBold
                                color: fila.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            }
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: [fila.modelData.detalle, fila.modelData.origenes].filter(x => x).join(" · ")
                                elide: Text.ElideRight
                                font: Kirigami.Theme.smallFont
                                color: fila.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
                            }
                        }
                    }
                }
            }

            // ---------------------------------------------------------------- el libro elegido
            QQC2.ScrollView {
                id: derecha
                QQC2.SplitView.fillWidth: true
                contentWidth: availableWidth
                QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
                Kirigami.Theme.colorSet: Kirigami.Theme.View
                Kirigami.Theme.inherit: false
                background: Rectangle { color: Kirigami.Theme.backgroundColor }

                ColumnLayout {
                    width: derecha.availableWidth - Kirigami.Units.largeSpacing * 4
                    x: Kirigami.Units.largeSpacing * 2
                    spacing: Kirigami.Units.largeSpacing

                    Kirigami.PlaceholderMessage {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.gridUnit * 4
                        visible: !raiz.b.hay
                        icon.name: "view-readermode"
                        text: "Elige un libro"
                        explanation: "Sus subrayados, su tiempo y su progreso en cada herramienta aparecen aquí"
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        visible: raiz.b.hay
                        spacing: Kirigami.Units.smallSpacing
                        RowLayout {
                            Layout.fillWidth: true
                            Kirigami.Heading { Layout.fillWidth: true; level: 2; text: raiz.b.titulo || ""; wrapMode: Text.WordWrap }
                            Chip { text: "Ver en el catálogo"; icono: "folder-book"; onClicked: raiz.lec.verEnCatalogo() }
                        }
                        Tenue { text: [raiz.b.autores, raiz.b.tiempo !== "—" ? raiz.b.tiempo + " de lectura" : "", raiz.b.datos].filter(x => x).join(" · ") }
                    }

                    // el progreso en cada herramienta
                    Tarjeta {
                        visible: raiz.b.hay && (raiz.b.progreso || []).length > 0
                        Repeater {
                            model: raiz.b.progreso || []
                            delegate: RowLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing
                                QQC2.Label { text: modelData.origen; Layout.preferredWidth: Kirigami.Units.gridUnit * 5 }
                                QQC2.ProgressBar {
                                    Layout.preferredWidth: Kirigami.Units.gridUnit * 6
                                    visible: modelData.fraccion >= 0
                                    from: 0; to: 1; value: Math.max(0, modelData.fraccion)
                                    Accessible.name: modelData.origen + ": " + modelData.texto
                                }
                                QQC2.Label { Layout.fillWidth: true; text: modelData.texto; color: Kirigami.Theme.disabledTextColor; elide: Text.ElideRight }
                            }
                        }
                    }

                    // los subrayados: los chips filtran por origen
                    Flow {
                        Layout.fillWidth: true
                        visible: raiz.b.hay
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: raiz.lec.origenes
                            delegate: Chip {
                                required property var modelData
                                text: modelData.texto
                                destacado: raiz.lec.origen === modelData.nombre
                                onClicked: raiz.lec.fijarOrigen(modelData.nombre)
                            }
                        }
                    }
                    Tenue { visible: raiz.b.hay && raiz.b.total === 0; text: "Este libro no tiene subrayados en ninguna herramienta." }

                    Repeater {
                        model: raiz.lec.anotaciones
                        delegate: Tarjeta {
                            id: tarjeta
                            required property var modelData
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing
                                Rectangle {                    // el color que le dio su herramienta, como un punto
                                    Layout.alignment: Qt.AlignTop
                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                    implicitWidth: Kirigami.Units.smallSpacing * 2
                                    implicitHeight: implicitWidth
                                    radius: width / 2
                                    color: tarjeta.modelData.color || Kirigami.Theme.disabledTextColor
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        visible: tarjeta.modelData.texto !== ""
                                        text: "“" + tarjeta.modelData.texto + "”"
                                        wrapMode: Text.WordWrap
                                        textFormat: Text.PlainText
                                    }
                                    QQC2.Label {
                                        Layout.fillWidth: true
                                        visible: tarjeta.modelData.nota !== ""
                                        text: tarjeta.modelData.nota
                                        wrapMode: Text.WordWrap
                                        textFormat: Text.PlainText
                                        font.italic: true
                                        color: Kirigami.Theme.disabledTextColor
                                    }
                                    Tenue { text: tarjeta.modelData.detalle }
                                }
                                Chip {
                                    Layout.alignment: Qt.AlignTop
                                    text: "Copiar"
                                    icono: "edit-copy"
                                    ayuda: tarjeta.modelData.cita
                                    onClicked: raiz.lec.copiar(tarjeta.modelData.cita)
                                }
                            }
                        }
                    }

                    // las últimas sesiones
                    Kirigami.Heading {
                        visible: raiz.b.hay && (raiz.b.sesiones || []).length > 0
                        Layout.topMargin: Kirigami.Units.largeSpacing
                        level: 4
                        text: "Últimas sesiones"
                    }
                    Repeater {
                        model: raiz.b.hay ? raiz.b.sesiones : []
                        delegate: Tenue { required property var modelData; text: modelData.texto }
                    }
                    Item { implicitHeight: Kirigami.Units.gridUnit * 2 }
                }
            }
        }
    }
}
