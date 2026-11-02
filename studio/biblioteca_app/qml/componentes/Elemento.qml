// Elemento — la fila seleccionada de la vista de etapa: todos sus campos (etiqueta: valor) y, si es una ficha o un
// manifiesto, su texto; en Sincronizar, la comprobación con sus afectados y la operación que la resuelve; en Puerta,
// el estado de los candados y cómo deshacer.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

Item {
    id: pagina
    readonly property var e: studio.etapas
    readonly property var p: studio.puerta
    readonly property bool conTexto: e.hayElemento && e.elementoTexto !== ""

    VistaTexto {
        anchors.fill: parent
        visible: pagina.conTexto
        texto: pagina.e.elementoTexto
        markdown: pagina.e.elementoEsMarkdown
        definicion: pagina.e.elementoEsMarkdown ? "" : "YAML"
        nombreAccesible: "Texto de " + pagina.e.elementoTitulo
    }
    QQC2.ScrollView {
        anchors.fill: parent
        visible: !pagina.conTexto
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: parent.availableWidth - Kirigami.Units.largeSpacing * 2
            x: Kirigami.Units.largeSpacing
            y: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing
            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                visible: !pagina.e.hayElemento && studio.espacio.vista !== "puerta"
                text: "Nada seleccionado"
                explanation: "Elige una fila de la tabla: aquí se ven todos sus campos. La pestaña Operación tiene la operación elegida de esta vista."
                icon.name: "view-list-details"
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                visible: studio.espacio.vista === "puerta"
                Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "La puerta ahora" }
                QQC2.Label { Kirigami.FormData.label: "Calibre:"; text: pagina.p.calibreAbierto ? "abierto (no se aplica en él)" : "cerrado"; color: pagina.p.calibreAbierto ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.positiveTextColor }
                QQC2.Label { Kirigami.FormData.label: "Zotero:"; text: pagina.p.zoteroAbierto ? "abierto (no se aplica en él)" : "cerrado"; color: pagina.p.zoteroAbierto ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.positiveTextColor }
                QQC2.Label { Kirigami.FormData.label: "Candados:"; text: (pagina.p.candadoCalibre ? "Calibre ocupado" : "Calibre libre") + " · " + (pagina.p.candadoZotero ? "Zotero ocupado" : "Zotero libre"); color: (pagina.p.candadoCalibre || pagina.p.candadoZotero) ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.positiveTextColor }
                Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Deshacer una escritura" }
                QQC2.Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Cierra la aplicación y copia el respaldo de la suite (Intro en la tabla abre su carpeta) sobre la base (metadata.db o zotero.sqlite). Las suites respaldan por la puerta antes de tocar nada; la guía del repo lo detalla (CLAUDE.md, «Deshacer una escritura»)."; color: Kirigami.Theme.disabledTextColor }
            }
            Repeater {
                model: pagina.e.elementoCampos
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label { text: modelData.etiqueta; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                    QQC2.Label { Layout.fillWidth: true; text: modelData.valor; wrapMode: Text.Wrap; textFormat: Text.PlainText }
                }
            }
            RowLayout {
                visible: pagina.e.hayElemento && pagina.e.elementoOperacion !== ""
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                QQC2.Button {
                    text: "Elegir la operación que lo resuelve"
                    icon.name: "go-jump"
                    onClicked: { studio.operaciones.fijar(pagina.e.elementoOperacion); studio.interfaz.pedir("pestana", { indice: 1 }) }
                }
            }
            Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
        }
    }
}
