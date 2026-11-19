// Fichas — el área «Fichas» (Ctrl+4, rediseño del 2026-11-18, decisiones §9.9): todas las fichas de los escritos y las
// canónicas. A la izquierda, los filtros en lista (Todas, Textuales, Paráfrasis, Por revisar, con su cuenta) y el «Repaso
// para estudiantes». En el centro, cada ficha como una tarjeta sutil: la cita en letra de lectura y, debajo y tenue, la
// obra, la página, el tipo, si está cotejada con el PDF y el escrito; con «Abrir en LaTeX Studio» y «Copiar la cita».
// Arriba, «Nueva ficha» (la acción rellena) y «Estudiar con la IA», los diálogos de la ficha editorial, sobre el libro de
// la ficha elegida. El repaso es el sistema Leitner de cinco cajas (lib/repaso.py): la pregunta, «Mostrar la ficha», «La
// sabía» o «Repasar luego», y lo que queda hoy. Solo lee las fichas (studio.fichas); escribe solo la base del repaso.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

RowLayout {
    id: raiz
    readonly property var fi: studio.fichas
    readonly property bool repaso: fi.modo === "repaso"
    readonly property var t: fi.tarjeta
    spacing: 0
    Accessible.name: "Fichas"

    component Tenue: QQC2.Label {
        Layout.fillWidth: true
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }
    // la letra de lectura: la del tema, un poco más grande y con aire entre líneas
    component TextoLectura: QQC2.Label {
        Layout.fillWidth: true
        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.12
        lineHeight: 1.25
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
    }

    // ------------------------------------------------------------------ los filtros y el repaso
    ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 14
        Layout.maximumWidth: Kirigami.Units.gridUnit * 14
        Layout.fillWidth: false
        Layout.fillHeight: true
        spacing: 0
        Kirigami.Heading { level: 4; text: "Fichas"; Layout.margins: Kirigami.Units.largeSpacing; Layout.bottomMargin: Kirigami.Units.smallSpacing }
        Repeater {
            model: raiz.fi.filtros
            delegate: QQC2.ItemDelegate {
                id: filtro
                required property var modelData
                Layout.fillWidth: true
                highlighted: !raiz.repaso && raiz.fi.filtro === modelData.clave
                onClicked: raiz.fi.fijarFiltro(modelData.clave)
                Accessible.name: modelData.texto + ", " + modelData.n
                contentItem: RowLayout {
                    QQC2.Label { Layout.fillWidth: true; text: filtro.modelData.texto; elide: Text.ElideRight
                                 color: filtro.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                    QQC2.Label { text: filtro.modelData.n; font: Kirigami.Theme.smallFont
                                 color: filtro.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor }
                }
            }
        }
        Kirigami.ListSectionHeader { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing; text: "Para estudiar" }
        QQC2.ItemDelegate {
            id: entradaRepaso
            Layout.fillWidth: true
            highlighted: raiz.repaso
            onClicked: raiz.fi.fijarModo("repaso")
            Accessible.name: "Repaso para estudiantes, " + raiz.fi.paraHoy + " para hoy"
            contentItem: RowLayout {
                Kirigami.Icon { source: "view-task"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                color: entradaRepaso.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                QQC2.Label { Layout.fillWidth: true; text: "Repaso para estudiantes"; elide: Text.ElideRight
                             color: entradaRepaso.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                QQC2.Label { text: raiz.fi.paraHoy; font: Kirigami.Theme.smallFont; visible: raiz.fi.paraHoy > 0
                             color: entradaRepaso.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor }
            }
        }
        Tenue {
            Layout.margins: Kirigami.Units.largeSpacing
            Layout.topMargin: Kirigami.Units.smallSpacing
            visible: text !== ""
            text: raiz.fi.resumenRepaso
        }
        Item { Layout.fillHeight: true }
    }
    Kirigami.Separator { Layout.fillHeight: true }

    // ------------------------------------------------------------------ las fichas o el repaso
    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 0
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Kirigami.Heading {
                    level: 3
                    text: raiz.repaso ? "Repaso para estudiantes" : ((raiz.fi.filtros.find(f => f.clave === raiz.fi.filtro) || {}).texto || "Fichas")
                }
                Tenue {
                    elide: Text.ElideRight
                    wrapMode: Text.NoWrap
                    text: raiz.repaso ? "Leitner: la caja 1 cada día, la 2 cada 2, la 3 cada 4, la 4 cada 8 y la 5 cada 16"
                                      : (raiz.fi.cargando ? "Leyendo las fichas de los escritos…"
                                         : raiz.fi.lista.length + " fichas" + (studio.libros.hayActual ? " · libro: " + studio.libros.titulo : ""))
                }
            }
            Chip {
                text: "Estudiar con la IA"
                icono: "tools-wizard"
                enabled: studio.libros.hayActual
                ayuda: studio.libros.hayActual ? "Una mirada sobre unas hojas de «" + studio.libros.titulo + "»: copia el prompt y lee lo que respondió el chat"
                                               : "Elige una ficha o un libro del catálogo"
                onClicked: dialogoEstudio.abrir()
            }
            Chip {
                text: "Nueva ficha"
                icono: "document-new"
                destacado: !raiz.repaso                    // la acción rellena de la lista; en el repaso, la de la tarjeta
                enabled: studio.libros.hayActual
                onClicked: dialogoFicha.abrir()
                ayuda: studio.libros.hayActual ? "Una ficha de «" + studio.libros.titulo + "» en un escrito, con el PDF al lado y su cotejo"
                                               : "Elige una ficha o un libro del catálogo"
            }
        }
        Kirigami.Separator { Layout.fillWidth: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Kirigami.Theme.backgroundColor

            // la lista
            ListView {
                id: lista
                anchors.fill: parent
                anchors.margins: Kirigami.Units.largeSpacing
                visible: !raiz.repaso
                clip: true
                spacing: Kirigami.Units.largeSpacing
                model: raiz.fi.lista
                QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
                delegate: Tarjeta {
                    id: ficha
                    required property var modelData
                    width: ListView.view.width - Kirigami.Units.largeSpacing
                    resaltada: raiz.fi.actual === modelData.clave
                    TapHandler { onTapped: raiz.fi.elegir(ficha.modelData.clave) }
                    TextoLectura {
                        visible: ficha.modelData.cita !== ""
                        text: ficha.modelData.tipo === "textual" ? "“" + ficha.modelData.cita + "”" : ficha.modelData.cita
                        maximumLineCount: 6
                        elide: Text.ElideRight
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: ficha.modelData.cita === ""
                        text: ficha.modelData.obra
                        font.weight: Font.DemiBold
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Tenue { text: ficha.modelData.detalle }
                        Chip {
                            visible: ficha.modelData.principal !== ""
                            text: "Abrir en LaTeX Studio"
                            icono: "document-edit"
                            ayuda: "Abrir el escrito «" + ficha.modelData.escrito + "» en LaTeX Studio"
                            onClicked: raiz.fi.abrirEnLatex(ficha.modelData.principal)
                        }
                        Chip {
                            visible: ficha.modelData.insertar !== ""
                            icono: "edit-copy"
                            ayuda: "Copiar para LaTeX: " + ficha.modelData.insertar
                            Accessible.name: "Copiar la cita para LaTeX"
                            onClicked: raiz.fi.copiar(ficha.modelData.insertar)
                        }
                        Chip {
                            visible: ficha.modelData.porCotejar
                            text: "Cotejé la página"
                            icono: "checkmark"
                            ayuda: "Comprobé en el PDF que la cita está en la página que dice: la ficha pasa a verificada por el autor y se puede citar"
                            onClicked: { confirmarCotejo.ficha = ficha.modelData; confirmarCotejo.open() }
                        }
                        Chip {
                            icono: "document-open"
                            ayuda: "Abrir el archivo de la ficha"
                            Accessible.name: "Abrir la ficha"
                            onClicked: raiz.fi.abrirArchivo(ficha.modelData.archivo)
                        }
                    }
                    // por qué no se cita todavía (la de la IA sin cotejar o la que no casa con el PDF), con su fuente
                    Tenue {
                        visible: !ficha.modelData.citable && ficha.modelData.motivo !== ""
                        color: Kirigami.Theme.neutralTextColor
                        text: ficha.modelData.motivo
                    }
                    Tenue {
                        visible: ficha.modelData.porCotejar
                        text: raiz.fi.porqueOrigen
                    }
                }
                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.gridUnit * 4
                    visible: lista.count === 0 && !raiz.fi.cargando
                    icon.name: "document-edit-verify"
                    text: raiz.fi.filtro === "revisar" ? "Nada por revisar" : "Sin fichas todavía"
                    explanation: raiz.fi.filtro === "revisar" ? "Cada ficha está cotejada con su PDF"
                                                              : "Elige un libro en el catálogo y haz su primera ficha con «Nueva ficha»"
                }
                QQC2.BusyIndicator { anchors.centerIn: parent; running: raiz.fi.cargando; visible: running }
            }

            // el repaso
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 36)
                visible: raiz.repaso
                spacing: Kirigami.Units.largeSpacing
                Tarjeta {
                    visible: raiz.t.hay === true
                    espacio: Kirigami.Units.largeSpacing
                    Tenue { text: "Caja " + (raiz.t.caja || 1) + " de 5" + (raiz.t.nueva ? " · nueva" : "") + " · " + (raiz.t.tipo || "") }
                    Kirigami.Heading { Layout.fillWidth: true; level: 2; text: raiz.t.pregunta || ""; wrapMode: Text.WordWrap }
                    Tenue { text: [raiz.t.tema, raiz.t.obra].filter(x => x).join(" · ") }
                    Kirigami.Separator { Layout.fillWidth: true; visible: raiz.fi.mostrada }
                    TextoLectura { visible: raiz.fi.mostrada; text: raiz.t.cita || "" }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        spacing: Kirigami.Units.smallSpacing
                        Item { Layout.fillWidth: true }
                        Chip {
                            visible: !raiz.fi.mostrada
                            text: "Mostrar la ficha"
                            icono: "view-visible"
                            destacado: true
                            onClicked: raiz.fi.mostrar()
                        }
                        Chip {
                            visible: raiz.fi.mostrada
                            text: "Repasar luego"
                            icono: "view-refresh"
                            ayuda: "Vuelve a la caja 1: mañana otra vez"
                            onClicked: raiz.fi.responder(false)
                        }
                        Chip {
                            visible: raiz.fi.mostrada
                            text: "La sabía"
                            icono: "checkmark"
                            destacado: true
                            ayuda: "Sube una caja: vuelve más tarde"
                            onClicked: raiz.fi.responder(true)
                        }
                    }
                }
                Kirigami.PlaceholderMessage {
                    Layout.fillWidth: true
                    visible: raiz.t.hay !== true
                    icon.name: "checkmark"
                    text: "Nada por repasar hoy"
                    explanation: raiz.fi.resumenRepaso || "Las fichas textuales, de paráfrasis y de síntesis entran aquí solas"
                }
                Tenue { visible: raiz.t.hay === true; horizontalAlignment: Text.AlignHCenter; text: raiz.fi.resumenRepaso }
                // las respuestas se simulan: nada va a la base del repaso hasta «Guardar el repaso»
                RowLayout {
                    Layout.fillWidth: true
                    visible: raiz.fi.sinGuardar > 0
                    spacing: Kirigami.Units.smallSpacing
                    Tenue { Layout.fillWidth: true; text: raiz.fi.resumenSinGuardar }
                    Chip {
                        text: "Descartar"
                        icono: "edit-undo"
                        ayuda: "Olvida estas respuestas: las fichas vuelven a la cola de hoy"
                        onClicked: raiz.fi.descartarRepaso()
                    }
                    Chip {
                        text: "Guardar el repaso"
                        icono: "document-save"
                        destacado: true
                        ayuda: "Escribe las respuestas en la base del repaso (con respaldo del día)"
                        onClicked: raiz.fi.guardarRepaso()
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: confirmarCotejo
        property var ficha: ({})
        title: "Cotejé la página"
        subtitle: "¿Comprobaste en el PDF que la cita está en " + (ficha.pagina ? "la página " + ficha.pagina : "su lugar") + " de «" + (ficha.obra || "") + "»?"
                  + (ficha.deIa ? " La propuso la IA: desde ahora se podrá citar." : "")
        standardButtons: Kirigami.Dialog.Cancel
        customFooterActions: [Kirigami.Action { text: "Sí, la cotejé"; icon.name: "checkmark"
                                                onTriggered: { raiz.fi.cotejar(confirmarCotejo.ficha.clave); confirmarCotejo.close() } }]
    }
    DialogoFicha { id: dialogoFicha; objectName: "dialogoFichaFichas" }
    DialogoEstudioObra { id: dialogoEstudio; dialogoFicha: dialogoFicha }
}
