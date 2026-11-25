// MapaBiblioteca — el área «Mapa» (decisiones §9.19, pedido del autor): el mapa de toda la biblioteca y, sobre todo,
// dónde estoy y qué me falta. Arriba, las cifras de la biblioteca (libros, leídos, en curso, sin abrir) y el grafo de
// los conceptos de todas las sesiones guiadas de Ñawinchay, con el mismo componente que el mapa de un libro
// (`MapaLectura`, §9.16). Abajo, los temas del vocabulario cerrado de Calibre, del que menos se ha leído al que más:
// cada uno con su barra (leído · en curso · sin abrir) y cuántos conceptos salieron de sus libros. Un tema con libros y
// sin conceptos es un tema que la biblioteca tiene y el lector todavía no. Solo lee (`studio.lectura`).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.Control {
    id: raiz
    readonly property var lec: studio.lectura
    readonly property var g: lec.mapaGlobal
    readonly property var c: lec.cobertura
    readonly property var temas: c.temas || []
    property bool todos: false
    readonly property int tope: todos ? temas.length : 40
    padding: 0
    Accessible.name: "Mapa"

    function cifra(n) { return Number(n || 0).toLocaleString(Qt.locale(), "f", 0) }

    contentItem: QQC2.ScrollView {
        contentWidth: availableWidth
        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            // las cifras de la biblioteca
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.gridUnit
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.libros); rotulo: "libros" }
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.leido); rotulo: "leídos" }
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.en_curso); rotulo: "en curso" }
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.sin_abrir); rotulo: "sin abrir" }
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.conceptos); rotulo: "conceptos" }
                Cifra { Layout.fillWidth: true; valor: raiz.cifra(raiz.c.con_materias); rotulo: "con materias" }
            }
            Kirigami.Separator { Layout.fillWidth: true }

            // el grafo de todo lo estudiado, con el componente del mapa de un libro
            MapaLectura {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                mapa: raiz.g
                titulo: "Lo que ya estudié"
                resumen: (raiz.g.conceptos || []).length + " conceptos · " + (raiz.g.relaciones || []).length
                         + " relaciones · de " + (raiz.g.libros || 0) + (raiz.g.libros === 1 ? " libro" : " libros")
                         + " con sesiones guiadas en Ñawinchay. Lo propuso la IA: cotéjelo con el texto."
                vacio: "Todavía no hay conceptos: los arman las sesiones guiadas de Ñawinchay. Los temas de abajo valen igual, salen de la biblioteca."
            }

            // dónde estoy: los temas, del que más falta al que menos
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                Layout.bottomMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Heading {
                    type: Kirigami.Heading.Type.Primary
                    level: 4
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    text: "Dónde estoy"
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                    text: raiz.temas.length + " temas del vocabulario de la biblioteca, del que menos he leído al que más."
                          + " Un tema con libros y sin conceptos es un tema que la biblioteca tiene y yo todavía no."
                }

                Repeater {
                    model: raiz.temas.slice(0, raiz.tope)
                    delegate: ColumnLayout {
                        id: fila
                        required property var modelData
                        readonly property int total: Math.max(1, modelData.libros)
                        Layout.fillWidth: true
                        Layout.bottomMargin: Kirigami.Units.smallSpacing
                        spacing: 0

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.largeSpacing

                            QQC2.Label {
                                id: nombreTema
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 11
                                elide: Text.ElideRight
                                text: fila.modelData.tema
                                HoverHandler { id: encimaDelTema }
                                QQC2.ToolTip.text: fila.modelData.tema
                                QQC2.ToolTip.visible: nombreTema.truncated && encimaDelTema.hovered
                            }
                            // la barra: leído · en curso · sin abrir
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: Kirigami.Units.gridUnit * 0.8
                                radius: height / 2
                                color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.08)
                                RowLayout {
                                    anchors.fill: parent
                                    spacing: 0
                                    Rectangle {
                                        Layout.fillHeight: true
                                        Layout.preferredWidth: parent.width * fila.modelData.leido / fila.total
                                        color: Kirigami.Theme.positiveTextColor
                                    }
                                    Rectangle {
                                        Layout.fillHeight: true
                                        Layout.preferredWidth: parent.width * fila.modelData.en_curso / fila.total
                                        color: Kirigami.Theme.neutralTextColor
                                    }
                                    Item { Layout.fillWidth: true; Layout.fillHeight: true }
                                }
                            }
                            QQC2.Label {
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 13
                                font: Kirigami.Theme.smallFont
                                color: Kirigami.Theme.disabledTextColor
                                elide: Text.ElideRight
                                text: raiz.cifra(fila.modelData.libros) + " · leídos " + fila.modelData.leido
                                      + " · sin abrir " + raiz.cifra(fila.modelData.sin_abrir)
                                      + (fila.modelData.conceptos > 0 ? " · " + fila.modelData.conceptos + " conceptos" : "")
                            }
                        }

                        // de qué trata el tema según OpenAlex (§9.20): lo que la biblioteca tiene aunque nadie lo haya leído
                        QQC2.Label {
                            visible: text !== ""
                            Layout.fillWidth: true
                            Layout.leftMargin: Kirigami.Units.gridUnit * 11 + Kirigami.Units.largeSpacing
                            elide: Text.ElideRight
                            font: Kirigami.Theme.smallFont
                            color: Kirigami.Theme.disabledTextColor
                            // con cuántos libros se sostiene: «según 1 de 236» avisa de que la materia es un indicio, no el tema
                            text: (fila.modelData.materias || []).length === 0 ? ""
                                  : "según " + fila.modelData.con_materias + " de " + raiz.cifra(fila.modelData.libros)
                                    + ": " + (fila.modelData.materias || []).join("  ·  ")
                        }
                    }
                }

                QQC2.Button {
                    visible: raiz.temas.length > 40
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    text: raiz.todos ? "Ver solo los 40 primeros" : "Ver los " + raiz.temas.length + " temas"
                    icon.name: raiz.todos ? "go-up" : "go-down"
                    onClicked: raiz.todos = !raiz.todos
                }
            }
        }
    }
}
