// DialogoCatalogarIA — «Catalogar con un chat» (Ctrl+Shift+I) desde Método › Entrada o Método › Catalogar (decisiones §9.15):
// el paso 02 del Método Documental hecho con el chat que la persona prefiera, sin que el studio llame a ningún modelo. Tres
// pasos, como «Estudiar con la IA»: copiar el prompt (el del paso 02 con la portada del documento, la ficha que hay que
// corregir y los vocabularios cerrados de Calibre), pegar el bloque ```yaml que devolvió el chat, y ver los cambios
// comprobados sin IA (problemas que impiden guardar, avisos que conviene leer). «Guardar en el registro» reescribe solo esa
// fila de pendientes.tsv o de resumen_catalogacion.tsv y elige la operación que la aplica (F5 simula, Ctrl+Intro aplica).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialogo
    readonly property var ca: studio.catalogado
    property var prompt: null
    property var revision: null
    property var guardado: null

    title: "Catalogar con un chat: «" + (ca.titulo || ca.archivo || "") + "»"
    preferredWidth: Kirigami.Units.gridUnit * 48
    preferredHeight: Kirigami.Units.gridUnit * 42
    standardButtons: Kirigami.Dialog.Close
    showCloseButton: false     // los botones ya están al pie (la × de la cabecera es roja en algunos temas de iconos)
    // «Cerrar» sin el círculo rojo de «dialog-close» (Colloid, Papirus): solo su texto
    Component.onCompleted: { const c = standardButton(Kirigami.Dialog.Close); if (c) c.icon.name = "" }

    // `texto` (opcional): lo pegado, que se revisa en cuanto se abre
    function abrir(texto) {
        prompt = null; revision = null; guardado = null; respuesta.text = texto || ""
        open()
        if (texto) Qt.callLater(() => dialogo.ca.revisar(texto))
    }

    Connections {
        target: dialogo.ca
        function onPrompt(p) {
            dialogo.prompt = p
            if (p.prompt) ventana.mensajes.mostrar("Prompt del paso 02 copiado: pégalo en tu chat y trae su respuesta.", "positivo")
        }
        function onRevisado(r) { dialogo.revision = r }
        function onGuardado(r) {
            dialogo.guardado = r
            dialogo.revision = r
            if (r.escrito) ventana.mensajes.mostrar("Guardado en el registro: ahora «" + dialogo.ca.operacion + "» (F5 simula, Ctrl+Intro aplica).", "positivo")
        }
    }

    customFooterActions: [
        Kirigami.Action {
            text: "Copiar el prompt"; icon.name: "edit-copy"
            enabled: !dialogo.ca.ocupado
            onTriggered: dialogo.ca.copiarPrompt()
        },
        Kirigami.Action {
            text: "Revisar lo pegado"; icon.name: "dialog-ok"
            enabled: respuesta.text.trim() !== "" && !dialogo.ca.ocupado
            onTriggered: dialogo.ca.revisar(respuesta.text)
        },
        Kirigami.Action {
            text: "Guardar en el registro"; icon.name: "document-save"
            enabled: !!dialogo.revision && dialogo.revision.ok === true && (dialogo.revision.cambios || []).length > 0
                     && !dialogo.ca.ocupado && !(dialogo.guardado && dialogo.guardado.escrito)
            onTriggered: dialogo.ca.guardar(respuesta.text)
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

            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Kirigami.Theme.disabledTextColor
                text: (dialogo.ca.vista === "entrada" ? "Archivo de la zona de entrada: " + dialogo.ca.archivo + ". Lo guardado corrige su fila de pendientes.tsv."
                                                      : "Libro " + dialogo.ca.clave + " de Calibre. Lo guardado corrige su fila de resumen_catalogacion.tsv.")
                      + " Ni Calibre ni Zotero se tocan hasta «" + dialogo.ca.operacion + "»."
            }

            Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary;  text: "1. Copia el prompt y pégalo en tu chat" }
            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "El prompt «Catalogar en Calibre» del Método Documental, con el texto de las primeras hojas, la ficha que hay que "
                      + "corregir y los vocabularios cerrados de Calibre (clasificador, item_type y etiquetas). Sirve cualquier chat: "
                      + "Claude, ChatGPT, Gemini…; el studio no llama a ninguno."
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !!dialogo.prompt && (!!dialogo.prompt.error || !!dialogo.prompt.aviso)
                type: dialogo.prompt && dialogo.prompt.error ? Kirigami.MessageType.Error : Kirigami.MessageType.Warning
                text: dialogo.prompt ? (dialogo.prompt.error || dialogo.prompt.aviso || "") : ""
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: !!dialogo.prompt && !!dialogo.prompt.prompt
                wrapMode: Text.WordWrap
                color: Kirigami.Theme.positiveTextColor
                text: dialogo.prompt && dialogo.prompt.prompt ? "Copiado: «" + dialogo.prompt.fuente.titulo + "», versión " + (dialogo.prompt.fuente.version || "—")
                      + ", " + dialogo.prompt.prompt.length + " caracteres" + (dialogo.prompt.conTexto ? ", con el texto del documento." : ", sin texto del documento.") : ""
            }

            Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary;  text: "2. Pega aquí la respuesta del chat" }
            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 9
                QQC2.TextArea {
                    id: respuesta
                    wrapMode: TextEdit.Wrap
                    placeholderText: "La respuesta entera o solo el bloque ```yaml «tipo: catalogacion»"
                    font.family: Kirigami.Theme.fixedWidthFont.family
                    Accessible.name: "Respuesta del chat"
                    onTextChanged: { dialogo.revision = null; dialogo.guardado = null }
                }
            }

            // 3. lo comprobado
            Kirigami.Heading { level: 4; type: Kirigami.Heading.Type.Primary;  text: "3. Revisa los cambios"; visible: !!dialogo.revision && !dialogo.revision.error }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !!dialogo.revision && !!dialogo.revision.error
                type: Kirigami.MessageType.Error
                text: dialogo.revision ? (dialogo.revision.error || "") : ""
            }
            Repeater {
                model: dialogo.revision ? dialogo.revision.problemas || [] : []
                Kirigami.InlineMessage { required property string modelData; Layout.fillWidth: true; visible: true; type: Kirigami.MessageType.Error; text: modelData }
            }
            // los avisos juntos, en un solo mensaje con su lista (antes, una caja naranja por aviso, apiladas)
            Kirigami.InlineMessage {
                readonly property var avisos: dialogo.revision ? dialogo.revision.avisos || [] : []
                Layout.fillWidth: true
                visible: avisos.length > 0
                type: Kirigami.MessageType.Warning
                text: avisos.length === 1 ? avisos[0] : "• " + avisos.join("\n• ")
            }
            GridLayout {
                Layout.fillWidth: true
                visible: !!dialogo.revision && (dialogo.revision.cambios || []).length > 0
                columns: 3
                columnSpacing: Kirigami.Units.largeSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                QQC2.Label { text: "Campo"; font.weight: Font.DemiBold }
                QQC2.Label { text: "Ahora"; font.weight: Font.DemiBold; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                QQC2.Label { text: "Propuesto"; font.weight: Font.DemiBold; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                Repeater {
                    model: dialogo.revision ? (dialogo.revision.cambios || []).length * 3 : 0
                    delegate: QQC2.Label {
                        required property int index
                        readonly property var c: dialogo.revision.cambios[Math.floor(index / 3)]
                        readonly property int col: index % 3
                        Layout.fillWidth: col > 0
                        Layout.preferredWidth: col > 0 ? 1 : -1
                        Layout.alignment: Qt.AlignTop
                        text: col === 0 ? c.rotulo : (col === 1 ? (c.antes || "—") : (c.despues || "—"))
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                        color: col === 0 ? Kirigami.Theme.disabledTextColor : (col === 1 ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.textColor)
                        font.strikeout: col === 1 && c.antes !== ""
                    }
                }
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !!dialogo.guardado && dialogo.guardado.escrito === true
                type: Kirigami.MessageType.Positive
                text: "Guardado en " + (dialogo.guardado ? dialogo.guardado.ruta : "") + ". Queda elegida «" + dialogo.ca.operacion
                      + "»: simúlala (F5) y aplícala (Ctrl+Intro) con Calibre cerrado."
            }
        }
    }
}
