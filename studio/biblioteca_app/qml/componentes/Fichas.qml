// Fichas — el área «Fichas» (Ctrl+4, rediseño del 2026-11-18, decisiones §9.9): todas las fichas de los escritos y las
// canónicas. A la izquierda, los filtros en lista (Todas, Textuales, Paráfrasis, Por revisar, con su cuenta) y el «Repaso
// para estudiantes». En el centro, cada ficha como una tarjeta sutil: la cita en letra de lectura y, debajo y tenue, la
// obra, la página, el tipo, si está cotejada con el PDF y el escrito; con «Abrir en LaTeX Studio», «Copiar la cita» y
// «Corregir…» (la ficha que ya existe en su escrito, en el diálogo de la ficha; la de obra ofrece después llevarla a Yachay).
// Arriba, «Nueva ficha» (la acción rellena) y «Estudiar con la IA», los diálogos de la ficha editorial, sobre el libro de
// la ficha elegida. El repaso es el sistema Leitner de cinco cajas (lib/repaso.py): la pregunta, «Mostrar la ficha», «La
// sabía» o «Repasar luego», y lo que queda hoy. Lee las fichas (studio.fichas) y escribe la base del repaso; corregir una
// ficha la escribe el diálogo (studio.fichado, con su huella).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

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
        Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary; text: "Fichas"; Layout.margins: Kirigami.Units.largeSpacing; Layout.bottomMargin: Kirigami.Units.smallSpacing }
        Repeater {
            model: raiz.fi.filtros
            delegate: QQC2.ItemDelegate {
                id: filtro
                required property var modelData
                Layout.fillWidth: true
                highlighted: !raiz.repaso && raiz.fi.filtro === modelData.clave
                // la elegida teñida con su marca (FondoSeleccion de la base), no el bloque lleno del acento (en Lliphi Oscuro, el rojo de los errores)
                background: FondoSeleccion { elegida: filtro.highlighted; sobre: filtro.hovered; pulsada: filtro.pressed; foco: filtro.visualFocus }
                onClicked: raiz.fi.fijarFiltro(modelData.clave)
                Accessible.name: modelData.texto + ", " + modelData.n
                contentItem: RowLayout {
                    QQC2.Label { Layout.fillWidth: true; text: filtro.modelData.texto; elide: Text.ElideRight
                                 color: Kirigami.Theme.textColor }
                    QQC2.Label { text: filtro.modelData.n; font: Kirigami.Theme.smallFont
                                 color: Kirigami.Theme.disabledTextColor }
                }
            }
        }
        Kirigami.ListSectionHeader { Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing; text: "Para estudiar" }
        QQC2.ItemDelegate {
            id: entradaRepaso
            Layout.fillWidth: true
            highlighted: raiz.repaso
            // la elegida teñida con su marca (FondoSeleccion de la base), no el bloque lleno del acento (en Lliphi Oscuro, el rojo de los errores)
            background: FondoSeleccion { elegida: entradaRepaso.highlighted; sobre: entradaRepaso.hovered; pulsada: entradaRepaso.pressed; foco: entradaRepaso.visualFocus }
            onClicked: raiz.fi.fijarModo("repaso")
            Accessible.name: "Repaso para estudiantes, " + raiz.fi.paraHoy + " para hoy"
            contentItem: RowLayout {
                Kirigami.Icon { source: "view-task"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                color: Kirigami.Theme.textColor }
                QQC2.Label { Layout.fillWidth: true; text: "Repaso para estudiantes"; elide: Text.ElideRight
                             color: Kirigami.Theme.textColor }
                QQC2.Label { text: raiz.fi.paraHoy; font: Kirigami.Theme.smallFont; visible: raiz.fi.paraHoy > 0
                             color: Kirigami.Theme.disabledTextColor }
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
                    type: Kirigami.Heading.Type.Primary
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
            GrupoOpciones {
                titulo: "Con el libro"
                OpcionColor {
                    text: "Estudiar con la IA"
                    icon.name: "tools-wizard"
                    enabled: studio.libros.hayActual
                    opacity: enabled ? 1 : 0.45
                    descripcion: studio.libros.hayActual ? "Una mirada sobre unas hojas de «" + studio.libros.titulo + "»: copia el prompt y lee lo que respondió el chat"
                                                         : "Elige una ficha o un libro del catálogo"
                    onClicked: dialogoEstudio.abrir()
                }
            }
            // la acción principal de la lista; en el repaso, la de la tarjeta
            BotonPrincipal {
                visible: !raiz.repaso
                text: "Nueva ficha"
                icon.name: "document-new"
                enabled: studio.libros.hayActual
                onClicked: dialogoFicha.abrir()
                QQC2.ToolTip.text: studio.libros.hayActual ? "Una ficha de «" + studio.libros.titulo + "» en un escrito, con el PDF al lado y su cotejo"
                                                           : "Elige una ficha o un libro del catálogo"
                QQC2.ToolTip.visible: hovered
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
                    HoverHandler { id: sobreFicha }
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
                        // las acciones en un pozo que aparece al pasar el ratón o en la elegida (antes, cuatro botones con borde en
                        // cada tarjeta: una pared de botones); «Cotejé la página», pendiente, siempre a la vista
                        GrupoOpciones {
                            titulo: "Con la ficha"
                            opacity: sobreFicha.hovered || ficha.resaltada || ficha.modelData.porCotejar ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                            OpcionColor {
                                visible: ficha.modelData.porCotejar
                                text: "Cotejé la página"
                                icon.name: "checkmark"
                                color: Kirigami.Theme.neutralTextColor
                                descripcion: "Comprobé en el PDF que la cita está en la página que dice: la ficha pasa a verificada por el autor y se puede citar"
                                onClicked: { confirmarCotejo.ficha = ficha.modelData; confirmarCotejo.open() }
                            }
                            OpcionColor {
                                // corregir una que ya existe en su escrito (§9.13): la de obra ofrece después llevarla a Yachay
                                objectName: "corregirFicha"
                                visible: ficha.modelData.carpeta !== "" && ["textual", "parafrasis", "fuente", "obra"].includes(ficha.modelData.tipo)
                                text: "Corregir…"
                                icon.name: "document-edit"
                                descripcion: ficha.modelData.tipo === "obra" ? "Corregir la ficha de obra de «" + ficha.modelData.escrito + "», con el PDF al lado; después se ofrece llevarla a Yachay"
                                                                             : "Corregir la ficha en «" + ficha.modelData.escrito + "», con el PDF al lado"
                                onClicked: { raiz.fi.elegir(ficha.modelData.clave); dialogoFicha.corregir(ficha.modelData) }
                            }
                            OpcionColor {
                                visible: ficha.modelData.principal !== ""
                                text: "Abrir en LaTeX Studio"
                                icon.name: "text-x-tex"
                                display: QQC2.AbstractButton.IconOnly
                                descripcion: "Abrir el escrito «" + ficha.modelData.escrito + "» en LaTeX Studio"
                                onClicked: raiz.fi.abrirEnLatex(ficha.modelData.principal)
                            }
                            OpcionColor {
                                visible: ficha.modelData.insertar !== ""
                                text: "Copiar la cita para LaTeX"
                                icon.name: "edit-copy"
                                display: QQC2.AbstractButton.IconOnly
                                descripcion: "Copiar para LaTeX: " + ficha.modelData.insertar
                                onClicked: raiz.fi.copiar(ficha.modelData.insertar)
                            }
                            OpcionColor {
                                visible: ficha.modelData.archivo !== ""      // la ficha de obra de Yachay no tiene archivo (§9.13)
                                text: "Abrir la ficha"
                                icon.name: "document-open"
                                display: QQC2.AbstractButton.IconOnly
                                descripcion: "Abrir el archivo de la ficha"
                                onClicked: raiz.fi.abrirArchivo(ficha.modelData.archivo)
                            }
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
                    Kirigami.Heading { Layout.fillWidth: true; level: 2; type: Kirigami.Heading.Type.Primary; text: raiz.t.pregunta || ""; wrapMode: Text.WordWrap }
                    Tenue { text: [raiz.t.tema, raiz.t.obra].filter(x => x).join(" · ") }
                    Kirigami.Separator { Layout.fillWidth: true; visible: raiz.fi.mostrada }
                    TextoLectura { visible: raiz.fi.mostrada; text: raiz.t.cita || "" }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        spacing: Kirigami.Units.smallSpacing
                        Item { Layout.fillWidth: true }
                        BotonPrincipal {
                            visible: !raiz.fi.mostrada
                            text: "Mostrar la ficha"
                            icon.name: "view-visible"
                            onClicked: raiz.fi.mostrar()
                        }
                        GrupoOpciones {
                            visible: raiz.fi.mostrada
                            OpcionColor {
                                text: "Repasar luego"
                                icon.name: "view-refresh"
                                descripcion: "Vuelve a la caja 1: mañana otra vez"
                                onClicked: raiz.fi.responder(false)
                            }
                        }
                        BotonPrincipal {
                            visible: raiz.fi.mostrada
                            text: "La sabía"
                            icon.name: "checkmark"
                            onClicked: raiz.fi.responder(true)
                            QQC2.ToolTip.text: "Sube una caja: vuelve más tarde"; QQC2.ToolTip.visible: hovered
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
                    GrupoOpciones {
                        OpcionColor {
                            text: "Descartar"
                            icon.name: "edit-undo"
                            descripcion: "Olvida estas respuestas: las fichas vuelven a la cola de hoy"
                            onClicked: raiz.fi.descartarRepaso()
                        }
                    }
                    BotonPrincipal {
                        text: "Guardar el repaso"
                        icon.name: "document-save"
                        onClicked: raiz.fi.guardarRepaso()
                        QQC2.ToolTip.text: "Escribe las respuestas en la base del repaso (con respaldo del día)"; QQC2.ToolTip.visible: hovered
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
        showCloseButton: false     // los botones ya están al pie (la × de la cabecera es roja en algunos temas de iconos)
        customFooterActions: [Kirigami.Action { text: "Sí, la cotejé"; icon.name: "checkmark"
                                                onTriggered: { raiz.fi.cotejar(confirmarCotejo.ficha.clave); confirmarCotejo.close() } }]
    }
    DialogoFicha { id: dialogoFicha; objectName: "dialogoFichaFichas" }
    DialogoEstudioObra { id: dialogoEstudio; dialogoFicha: dialogoFicha }
}
