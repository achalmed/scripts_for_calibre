// Lectura — el área «Lectura» (Ctrl+3, decisiones §9.6): la base de lectura de Biblioteca Studio, donde se juntan los
// subrayados, resaltados y notas de KOReader, Zotero, Okular y Yachay, y las horas, sesiones y progreso de cada libro.
// A la izquierda, el resumen de toda la base (con las horas de las últimas doce semanas) y los libros con lectura; a la
// derecha, el libro elegido: su tiempo y su progreso en cada herramienta, sus subrayados (filtrados por origen con los
// chips; cada uno se copia como cita) y sus últimas sesiones. Solo lee (studio.lectura): la base la escribe la operación
// «Base de lectura» de Coherencia › Sincronizar. Sin colores propios: el de cada subrayado es el que le dio su herramienta.
// Arriba a la izquierda (§9.8), «Sincronizar ahora» (una vuelta, la misma del timer) y el interruptor de la
// sincronización automática de cada hora, con la última vuelta y la próxima. El rediseño del 2026-11-18 (§9.9) suma cuatro
// cifras arriba (subrayados, horas en doce semanas, libros con lectura y racha), el mapa de calor de horas por día de las
// doce semanas (7 filas por 12 columnas, más oscuro con más horas, con su ayuda) y, en cada subrayado, una raya a la
// izquierda del color de la herramienta donde nació (los colores los da Python: studio.lectura.colores).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.Control {
    id: raiz
    readonly property var lec: studio.lectura
    readonly property var r: lec.resumen
    readonly property var b: lec.libro
    padding: 0
    Accessible.name: "Lectura"

    component Tenue: QQC2.Label {
        Layout.fillWidth: true
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }

    contentItem: Item {
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: Math.min(parent.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 30)
            visible: !raiz.lec.hayBase
            icon.name: "view-readermode"
            text: "La base de lectura aún está vacía"
            explanation: "«Sincronizar ahora» junta aquí los subrayados y las horas de KOReader, Zotero, Okular y Yachay, y lleva a cada uno lo que le falta."
            helpfulAction: Kirigami.Action {
                text: "Sincronizar ahora"
                icon.name: "view-refresh"
                enabled: !raiz.lec.sincronizando
                onTriggered: raiz.lec.sincronizarAhora()
            }
        }

        ColumnLayout {
            anchors.fill: parent
            visible: raiz.lec.hayBase
            spacing: 0

            // las cuatro cifras de arriba (§9.9)
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: raiz.lec.cifras
                    delegate: Tarjeta {
                        required property var modelData
                        Layout.preferredWidth: 1
                        Cifra { Layout.fillWidth: true; valor: modelData.valor; rotulo: modelData.rotulo }
                    }
                }
            }
            Kirigami.Separator { Layout.fillWidth: true }

            QQC2.SplitView {
                Layout.fillWidth: true
                Layout.fillHeight: true
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

                        // la sincronización (§9.8): el botón, el interruptor de cada hora y en qué va
                        Tarjeta {
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.smallSpacing
                                Kirigami.Icon { source: "view-refresh"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth }
                                QQC2.Label { text: "Sincronización"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                                QQC2.Switch {
                                    id: interruptor
                                    text: "Cada hora"
                                    checked: raiz.lec.timerActivo
                                    onToggled: raiz.lec.fijarTimer(checked)
                                    QQC2.ToolTip.text: "Encendido, la base se sincroniza sola cada hora; apagado, solo con el botón"
                                    QQC2.ToolTip.visible: hovered
                                    Accessible.name: "Sincronización automática cada hora"
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.smallSpacing
                                Tenue { Layout.fillWidth: true; text: raiz.lec.estadoSincronia }
                                QQC2.BusyIndicator { running: raiz.lec.sincronizando; visible: running; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth }
                                GrupoOpciones {
                                OpcionColor {
                                    text: "Sincronizar ahora"
                                    icon.name: "view-refresh"
                                    enabled: !raiz.lec.sincronizando
                                    onClicked: raiz.lec.sincronizarAhora()
                                    descripcion: "Trae lo nuevo de KOReader, Zotero, Okular y Yachay y lleva a cada uno lo que le falta; lo que esté abierto queda para la próxima vuelta"
                                }
                                }
                            }
                        }

                        Tarjeta {
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.largeSpacing * 2
                                Cifra { valor: raiz.r.tiempo || "—"; rotulo: "en total" }
                                Cifra { valor: raiz.r.mes || "—"; rotulo: "este mes" }
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
                                                // el color de KOReader (un dato: sus horas son las que se cuentan), no el acento del tema,
                                                // que en Lliphi Oscuro es el rojo de los errores
                                                color: modelData.horas > 0 ? (raiz.lec.colores.koreader || Kirigami.Theme.positiveTextColor) : Qt.alpha(Kirigami.Theme.textColor, 0.1)
                                            }
                                            QQC2.ToolTip.text: "Semana del " + modelData.etiqueta + ": " + modelData.horas + " h en " + modelData.sesiones + " sesiones"
                                            QQC2.ToolTip.visible: zona.containsMouse
                                            MouseArea { id: zona; anchors.fill: parent; hoverEnabled: true }
                                            Accessible.name: QQC2.ToolTip.text
                                        }
                                    }
                                }
                            }
                            // el mapa de calor: una casilla por día (7 filas, lunes arriba; 12 columnas, la semana actual a la derecha)
                            Grid {
                                id: calor
                                Layout.fillWidth: true
                                Layout.topMargin: Kirigami.Units.smallSpacing
                                rows: 7
                                flow: Grid.TopToBottom
                                spacing: 2
                                readonly property real ancho: Math.max(6, (width - spacing * 11) / 12)      // las columnas, a la par de las barras
                                readonly property real alto: Math.min(ancho, Kirigami.Units.gridUnit * 0.8)
                                Repeater {
                                    model: raiz.lec.dias
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: calor.ancho
                                        height: calor.alto
                                        radius: 2
                                        opacity: modelData.futuro ? 0 : 1
                                        color: modelData.nivel > 0 ? Qt.alpha(raiz.lec.colores.koreader || Kirigami.Theme.positiveTextColor, 0.2 + 0.2 * modelData.nivel)
                                                                   : Qt.alpha(Kirigami.Theme.textColor, 0.07)
                                        QQC2.ToolTip.text: modelData.texto
                                        QQC2.ToolTip.visible: casilla.containsMouse
                                        MouseArea { id: casilla; anchors.fill: parent; hoverEnabled: true }
                                        Accessible.name: modelData.texto
                                    }
                                }
                            }
                            Tenue { text: "Últimas doce semanas, por semana y por día, de KOReader (la única herramienta que guarda la hora de cada página)" }
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
                            // la elegida teñida con su marca (FondoSeleccion de la base), no el bloque lleno del acento (en Lliphi Oscuro, el rojo de los errores)
                            background: FondoSeleccion { elegida: fila.highlighted; sobre: fila.hovered; pulsada: fila.pressed; foco: fila.visualFocus }
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
                                    color: Kirigami.Theme.textColor
                                }
                                QQC2.Label {
                                    Layout.fillWidth: true
                                    text: [fila.modelData.detalle, fila.modelData.origenes].filter(x => x).join(" · ")
                                    elide: Text.ElideRight
                                    font: Kirigami.Theme.smallFont
                                    color: Kirigami.Theme.disabledTextColor
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
                                Kirigami.Heading { type: Kirigami.Heading.Type.Primary; Layout.fillWidth: true; level: 2; text: raiz.b.titulo || ""; wrapMode: Text.WordWrap }
                                GrupoOpciones { OpcionColor { text: "Ver en el catálogo"; icon.name: "folder-book"; onClicked: raiz.lec.verEnCatalogo() } }
                            }
                            Tenue { text: [raiz.b.autores, raiz.b.tiempo !== "—" ? raiz.b.tiempo + " de lectura" : "", raiz.b.datos].filter(x => x).join(" · ") }
                        }

                        // el progreso en cada herramienta
                        Tarjeta {
                            visible: raiz.b.hay && (raiz.b.progreso || []).length > 0
                            espacio: Kirigami.Units.largeSpacing
                            Repeater {
                                model: raiz.b.progreso || []
                                delegate: RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.largeSpacing
                                    QQC2.Label { text: modelData.origen; Layout.preferredWidth: Kirigami.Units.gridUnit * 5 }
                                    BarraLectura {                 // del color de la herramienta (§9.9); sin avance, guarda su hueco
                                        Layout.preferredWidth: Kirigami.Units.gridUnit * 6
                                        opacity: modelData.fraccion >= 0 ? 1 : 0
                                        fraccion: Math.max(0, modelData.fraccion)
                                        tono: modelData.color
                                        Accessible.name: modelData.origen + ": " + modelData.texto
                                    }
                                    QQC2.Label { Layout.fillWidth: true; text: modelData.texto; color: Kirigami.Theme.disabledTextColor; elide: Text.ElideRight }
                                }
                            }
                        }

                        // los subrayados: un selector por origen, cada herramienta con su punto de color (un dato, COLORES)
                        SelectorSegmentado {
                            visible: raiz.b.hay && raiz.lec.origenes.length > 0
                            titulo: "Origen de los subrayados"
                            opciones: raiz.lec.origenes.map(o => ({ clave: o.nombre, texto: o.texto, color: raiz.lec.colores[o.nombre] || "transparent" }))
                            actual: raiz.lec.origen
                            onElegida: clave => raiz.lec.fijarOrigen(clave)
                        }
                        Tenue { visible: raiz.b.hay && raiz.b.total === 0; text: "Este libro no tiene subrayados en ninguna herramienta." }

                        Repeater {
                            model: raiz.lec.anotaciones
                            delegate: Tarjeta {
                                id: tarjeta
                                required property var modelData
                                HoverHandler { id: sobreSubrayado }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.largeSpacing
                                    Rectangle {                    // la raya: el color de la herramienta donde nació (§9.9)
                                        Layout.fillHeight: true
                                        implicitWidth: 3
                                        radius: 1.5
                                        color: tarjeta.modelData.colorOrigen || Kirigami.Theme.disabledTextColor
                                        Accessible.name: "De " + tarjeta.modelData.origen
                                    }
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
                                    // copiar, discreto: solo el icono, en su pozo, al pasar el ratón por el subrayado
                                    GrupoOpciones {
                                        Layout.alignment: Qt.AlignTop
                                        opacity: sobreSubrayado.hovered ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                                        OpcionColor {
                                            text: "Copiar el subrayado"
                                            icon.name: "edit-copy"
                                            display: QQC2.AbstractButton.IconOnly
                                            descripcion: "Copiar: " + tarjeta.modelData.cita
                                            onClicked: raiz.lec.copiar(tarjeta.modelData.cita)
                                        }
                                    }
                                }
                            }
                        }

                        // las últimas sesiones
                        Kirigami.Heading {
                            type: Kirigami.Heading.Type.Primary
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
}
