// Inicio — el área «Inicio» (Ctrl+1, rediseño del 2026-11-18, decisiones §9.9): «Esto es lo de hoy». Arriba, el saludo y,
// a la derecha, el estado breve de la sincronización; debajo, cuatro cifras (leído esta semana, subrayados nuevos, fichas
// por revisar y pendientes de las bandejas: un clic lleva a su lugar) y dos tarjetas: «Seguir leyendo» (hasta tres libros
// en curso con su portada, la barra del color de la herramienta donde se leen y «Abrir») y «Siguiente paso» (hasta cuatro
// filas con el botón que lleva a Nueva ficha, a una bandeja, a LaTeX Studio o al repaso). Lo que no tiene datos no se
// muestra. Solo lee (studio.inicio); la única acción rellena es el «Abrir» del primer libro.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

Item {
    id: raiz
    readonly property var ini: studio.inicio
    readonly property bool ancho: vista.availableWidth >= Kirigami.Units.gridUnit * 46
    Accessible.name: "Inicio"

    component Tenue: QQC2.Label {
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        elide: Text.ElideRight
    }

    // «Fichar N subrayados»: el libro pasa a ser el de la ficha y el diálogo abre con el primero ya puesto
    function ficharObra(d) {
        studio.libros.fijarId(d.id)
        dialogoFicha.abrir({ tipo: "obra" })
    }
    function fichar(d) {
        studio.libros.fijarId(d.id)
        dialogoFicha.abrir({ tipo: "textual", pagina: d.pagina || "", hoja: d.hoja || 0, textos: { "Cita exacta": d.texto || "" } })
    }

    QQC2.ScrollView {
        id: vista
        anchors.fill: parent
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: Math.min(vista.availableWidth - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 64)
            x: (vista.availableWidth - width) / 2
            spacing: Kirigami.Units.largeSpacing * 2

            // el saludo y la sincronización
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.gridUnit * 1.5
                spacing: Kirigami.Units.largeSpacing
                ColumnLayout {
                    spacing: 0
                    Kirigami.Heading { level: 1; type: Kirigami.Heading.Type.Primary; text: "Esto es lo de hoy" }
                    Tenue { text: raiz.ini.fecha.charAt(0).toUpperCase() + raiz.ini.fecha.slice(1) }
                }
                Item { Layout.fillWidth: true }
                // al borde derecho de las tarjetas, alineado con ellas (antes flotaba a media fila)
                RowLayout {
                    visible: studio.lectura.hayBase
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: Kirigami.Units.smallSpacing
                    Rectangle {
                        implicitWidth: Kirigami.Units.smallSpacing * 2; implicitHeight: implicitWidth; radius: width / 2
                        color: studio.lectura.sincronizando ? Kirigami.Theme.neutralTextColor
                             : (studio.lectura.timerActivo ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor)
                    }
                    Tenue { text: studio.lectura.estadoSincronia }
                }
            }

            // las cuatro cifras
            GridLayout {
                Layout.fillWidth: true
                visible: raiz.ini.cifras.length > 0
                columns: raiz.ancho ? 4 : 2
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.largeSpacing
                Repeater {
                    model: raiz.ini.cifras
                    delegate: Tarjeta {
                        required property var modelData
                        Layout.preferredWidth: 1
                        Cifra {
                            Layout.fillWidth: true
                            valor: modelData.valor
                            rotulo: modelData.rotulo
                            interactiva: true
                            ayuda: modelData.accion === "bandeja" ? "Ir a las bandejas (Ctrl+8)"
                                 : (modelData.accion === "revisar" ? "Ver las fichas por revisar" : "Ir a Lectura")
                            onPulsada: raiz.ini.ir(modelData.accion, modelData.datos)
                        }
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: raiz.ancho && seguir.visible && pasos.visible ? 2 : 1
                columnSpacing: Kirigami.Units.largeSpacing * 2
                rowSpacing: Kirigami.Units.largeSpacing * 2

                // seguir leyendo
                Tarjeta {
                    id: seguir
                    visible: raiz.ini.seguir.length > 0
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    espacio: Kirigami.Units.largeSpacing
                    Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary; text: "Seguir leyendo" }
                    Repeater {
                        model: raiz.ini.seguir
                        delegate: RowLayout {
                            id: fila
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            Item {
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 2.4
                                Layout.preferredHeight: Kirigami.Units.gridUnit * 3.4
                                Rectangle {
                                    anchors.fill: parent
                                    visible: !fila.modelData.portada || portada.status !== Image.Ready
                                    radius: Kirigami.Units.cornerRadius
                                    color: Kirigami.Theme.alternateBackgroundColor
                                    Kirigami.Icon { anchors.centerIn: parent; source: "x-office-document-symbolic"; isMask: true; color: Kirigami.Theme.disabledTextColor; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth }
                                }
                                Image {
                                    id: portada
                                    anchors.fill: parent
                                    source: fila.modelData.fuente
                                    visible: fila.modelData.portada
                                    asynchronous: true
                                    fillMode: Image.PreserveAspectFit
                                    sourceSize.width: 220
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Kirigami.Units.smallSpacing / 2
                                QQC2.Label { Layout.fillWidth: true; text: fila.modelData.titulo; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Tenue { Layout.fillWidth: true; text: fila.modelData.autores; visible: text !== "" }
                                BarraLectura { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.smallSpacing / 2; fraccion: fila.modelData.fraccion; tono: fila.modelData.color }
                                Tenue { Layout.fillWidth: true; text: fila.modelData.texto }
                            }
                            // el primero, la acción principal de Inicio; los demás, una opción en su pozo
                            BotonPrincipal {
                                visible: fila.index === 0
                                text: "Abrir"
                                icon.name: "document-open"
                                enabled: fila.modelData.enCatalogo
                                onClicked: raiz.ini.abrir(fila.modelData.id)
                                QQC2.ToolTip.text: "El documento con su aplicación"; QQC2.ToolTip.visible: hovered
                            }
                            GrupoOpciones {
                                visible: fila.index > 0
                                OpcionColor { text: "Abrir"; icon.name: "document-open"; enabled: fila.modelData.enCatalogo
                                              descripcion: "El documento con su aplicación"; onClicked: raiz.ini.abrir(fila.modelData.id) }
                            }
                        }
                    }
                }

                // el siguiente paso
                Tarjeta {
                    id: pasos
                    visible: raiz.ini.pasos.length > 0
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    espacio: Kirigami.Units.largeSpacing
                    Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary; text: "Siguiente paso" }
                    Repeater {
                        model: raiz.ini.pasos
                        delegate: RowLayout {
                            id: paso
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing
                            Kirigami.Icon { source: paso.modelData.icono; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: implicitWidth }
                            QQC2.Label { Layout.fillWidth: true; text: paso.modelData.texto; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                            GrupoOpciones {
                                OpcionColor {
                                    text: paso.modelData.boton
                                    onClicked: paso.modelData.accion === "obra" ? raiz.ficharObra(paso.modelData.datos) : paso.modelData.accion === "ficha" ? raiz.fichar(paso.modelData.datos)
                                                                                  : raiz.ini.ir(paso.modelData.accion, paso.modelData.datos)
                                }
                            }
                        }
                    }
                }
            }

            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.gridUnit * 4
                visible: raiz.ini.cifras.length === 0 && !seguir.visible && !pasos.visible
                icon.name: "go-home"
                text: "Nada pendiente hoy"
                explanation: "Aquí aparecen lo que estás leyendo, lo que falta fichar y lo que espera en las bandejas"
            }
            Item { implicitHeight: Kirigami.Units.gridUnit }
        }
    }

    DialogoFicha { id: dialogoFicha }
}
