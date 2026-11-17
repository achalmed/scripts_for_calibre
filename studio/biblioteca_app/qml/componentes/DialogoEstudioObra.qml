// DialogoEstudioObra — «Estudiar con la IA» desde la ficha de un libro (decisiones §9.5): la mirada del estudio de una
// obra por partes (el catálogo de Yachay: plan, conceptos, fichas textuales, síntesis…) sobre unas hojas del PDF. Dos
// pasos, como en Yachay: copiar el prompt (la mirada, con las hojas como unidades «uN») y pegar el bloque que devolvió el
// chat. Lo pegado se lee sin IA: el estudio en una línea y sus fichas propuestas, cada una cotejada en su hoja; «Llevar a
// un escrito» abre la ficha nueva ya rellena, que se revisa y se guarda allí. Ningún modelo se llama desde aquí.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialogo
    readonly property var fi: studio.fichado
    property var prompt: null
    property var pegado: null
    property bool esperando: false
    property var dialogoFicha: null              // el DialogoFicha de la ficha editorial (para llevar una propuesta)

    title: "Estudiar «" + (studio.libros.ficha.titulo || "") + "» con la IA"
    preferredWidth: Kirigami.Units.gridUnit * 46
    preferredHeight: Kirigami.Units.gridUnit * 42
    standardButtons: Kirigami.Dialog.Close

    // `texto` (opcional): lo pegado, que se lee en cuanto el libro esté listo
    function abrir(texto) {
        prompt = null; pegado = null; respuesta.text = texto || ""
        if (fi.calibreId !== studio.libros.ficha.id) fi.preparar(studio.libros.ficha.id)
        open()
        if (texto) Qt.callLater(() => { dialogo.esperando = true; dialogo.fi.leerPegado(texto) })
    }

    Connections {
        target: dialogo.fi
        function onPromptObra(p) {
            dialogo.esperando = false
            dialogo.prompt = p
            if (p.prompt) ventana.mensajes.mostrar("Prompt copiado (" + p.unidades + " hojas): pégalo en tu chat.", "positivo")
        }
        function onPegadoObra(r) { dialogo.esperando = false; dialogo.pegado = r }
    }

    customFooterActions: [
        Kirigami.Action {
            text: "Copiar el prompt"; icon.name: "edit-copy"
            enabled: mirada.currentIndex >= 0 && !dialogo.esperando
            onTriggered: { dialogo.esperando = true; dialogo.fi.copiarPrompt(dialogo.fi.miradas[mirada.currentIndex].clave, desde.value, hasta.value, proposito.text) }
        },
        Kirigami.Action {
            text: "Leer lo pegado"; icon.name: "dialog-ok"
            enabled: respuesta.text.trim() !== "" && !dialogo.esperando
            onTriggered: { dialogo.esperando = true; dialogo.fi.leerPegado(respuesta.text) }
        }
    ]

    QQC2.ScrollView {
        id: vista
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            x: Kirigami.Units.largeSpacing
            width: vista.availableWidth - Kirigami.Units.largeSpacing * 2
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Heading { level: 4; text: "1. Elige la mirada y las hojas, y copia el prompt" }
            QQC2.ComboBox {
                id: mirada
                Layout.fillWidth: true
                model: dialogo.fi.miradas.map(m => m.etapa + " · " + m.nombre)
                onModelChanged: currentIndex = Math.max(0, dialogo.fi.miradas.findIndex(m => m.clave === "obra_fichas"))
                Accessible.name: "Mirada"
            }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Kirigami.Theme.disabledTextColor
                text: mirada.currentIndex >= 0 && dialogo.fi.miradas.length ? dialogo.fi.miradas[mirada.currentIndex].pregunta
                      : dialogo.fi.ocupado ? "Preparando el libro…" : "Sin el catálogo de miradas (falta el código de Yachay)."
            }
            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                QQC2.Label { text: "Hojas del PDF" }
                QQC2.SpinBox { id: desde; from: 1; to: 9999; value: 1; editable: true; Accessible.name: "Desde la hoja" }
                QQC2.Label { text: "a" }
                QQC2.SpinBox { id: hasta; from: 1; to: 9999; value: 3; editable: true; Accessible.name: "Hasta la hoja" }
            }
            QQC2.TextField { id: proposito; Layout.fillWidth: true; placeholderText: "Para qué se estudia (comprender la parte, fichar para un escrito…)" }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !!dialogo.prompt && (!!dialogo.prompt.error || !!dialogo.prompt.aviso)
                type: dialogo.prompt && dialogo.prompt.error ? Kirigami.MessageType.Error : Kirigami.MessageType.Warning
                text: dialogo.prompt ? (dialogo.prompt.error || dialogo.prompt.aviso || "") : ""
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: !!dialogo.prompt && !!dialogo.prompt.fuente
                wrapMode: Text.WordWrap
                color: Kirigami.Theme.disabledTextColor
                text: dialogo.prompt && dialogo.prompt.fuente ? "Copiado: «" + dialogo.prompt.nombre + "», versión " + (dialogo.prompt.fuente.version || "—") + ", " + dialogo.prompt.unidades + " hojas." : ""
            }

            Kirigami.Heading { level: 4; text: "2. Pega aquí la respuesta del chat" }
            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 7
                QQC2.TextArea {
                    id: respuesta
                    wrapMode: TextEdit.Wrap
                    placeholderText: "El bloque yaml «tipo: estudio-de-obra» que devolvió el chat"
                    font.family: Kirigami.Theme.fixedWidthFont.family
                    Accessible.name: "Respuesta del chat"
                    onTextChanged: dialogo.pegado = null
                }
            }

            // 3. lo leído
            Repeater {
                model: dialogo.pegado ? (dialogo.pegado.errores || (dialogo.pegado.error ? [dialogo.pegado.error] : [])) : []
                Kirigami.InlineMessage { required property string modelData; Layout.fillWidth: true; visible: true; type: Kirigami.MessageType.Error; text: modelData }
            }
            Repeater {
                model: dialogo.pegado ? dialogo.pegado.avisos || [] : []
                Kirigami.InlineMessage { required property string modelData; Layout.fillWidth: true; visible: true; type: Kirigami.MessageType.Warning; text: modelData }
            }
            Kirigami.Heading { level: 4; text: "3. Las fichas propuestas"; visible: !!dialogo.pegado && dialogo.pegado.ok === true }
            QQC2.Label {
                Layout.fillWidth: true
                visible: text !== ""
                wrapMode: Text.WordWrap
                color: Kirigami.Theme.disabledTextColor
                text: dialogo.pegado && dialogo.pegado.estudio && dialogo.pegado.estudio.titulo
                      ? dialogo.pegado.estudio.titulo + (dialogo.pegado.estudio.unidad ? " · " + dialogo.pegado.estudio.unidad : "") + " · "
                        + dialogo.pegado.estudio.afirmaciones + " afirmaciones" : ""
            }
            Repeater {
                model: dialogo.pegado && dialogo.pegado.ok ? dialogo.pegado.fichas : []
                delegate: QQC2.Control {
                    id: tarjeta
                    required property var modelData
                    Layout.fillWidth: true
                    padding: Kirigami.Units.largeSpacing
                    background: Rectangle {
                        radius: Kirigami.Units.cornerRadius
                        color: "transparent"
                        border.width: 1
                        border.color: Qt.alpha(Kirigami.Theme.textColor, 0.15)
                    }
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        RowLayout {
                            Layout.fillWidth: true
                            Kirigami.Icon {
                                source: tarjeta.modelData.verificacion === "verificada_script" ? "checkmark" : tarjeta.modelData.verificacion === "observada" ? "data-warning" : "question"
                                implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                                color: tarjeta.modelData.verificacion === "verificada_script" ? Kirigami.Theme.positiveTextColor
                                     : tarjeta.modelData.verificacion === "observada" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                            }
                            QQC2.Label { text: (tarjeta.modelData.clase === "textual" ? "Textual" : "Paráfrasis") + " · " + tarjeta.modelData.tema; font.weight: Font.Medium }
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: "p. " + tarjeta.modelData.pagina + (tarjeta.modelData.hoja ? " · hoja " + tarjeta.modelData.hoja : "") + " · " + tarjeta.modelData.categoria
                                color: Kirigami.Theme.disabledTextColor
                                font: Kirigami.Theme.smallFont
                                elide: Text.ElideRight
                            }
                            Chip {
                                text: "Llevar a un escrito…"
                                icono: "document-new"
                                ayuda: "Abre la ficha nueva ya rellena: se elige el escrito, se revisa y se guarda"
                                onClicked: {
                                    const m = tarjeta.modelData
                                    const t = m.clase === "textual" ? { "Cita exacta": m.cita, "Análisis": m.analisis }
                                                                    : { "Paráfrasis": m.parafrasis, "Origen literal": m.cita, "Control de fidelidad": m.analisis }
                                    if (dialogo.dialogoFicha) dialogo.dialogoFicha.abrir({ tipo: m.clase, pagina: m.pagina, hoja: m.hoja, categoria: m.categoria,
                                                                                          tema: m.tema, textos: t })
                                }
                            }
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: tarjeta.modelData.cita ? "“" + tarjeta.modelData.cita + "”" : tarjeta.modelData.parafrasis
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            visible: tarjeta.modelData.verificacion !== "verificada_script"
                            text: tarjeta.modelData.detalle
                            wrapMode: Text.WordWrap
                            color: Kirigami.Theme.disabledTextColor
                            font: Kirigami.Theme.smallFont
                        }
                    }
                }
            }
        }
    }
}
