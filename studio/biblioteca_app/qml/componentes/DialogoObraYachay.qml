// DialogoObraYachay — «Corregir…» de la ficha de obra en Yachay (decisiones §9.13, nota del 2026-11-19): las seis respuestas
// de la ficha de la persona sobre la obra, corregidas sin pasar por un escrito. «Revisar» simula qué cambiaría y sobre qué
// versión; «Llevar a Yachay…» la envía tras confirmar (VueltaYachay: `version_base`; un 409 no pisa y deja elegir). No escribe
// en ningún escrito (la copia de cada escrito queda como está), ni en Calibre ni en Zotero; la base la actualiza la CLI.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialogo
    readonly property var fi: studio.fichado
    property int calibreId: 0
    property string libro: ""                    // el título del libro
    property string detalle: ""                  // versión, cuántas respondió, si la dio por leída
    property var preguntas: []                   // los seis títulos, en su orden
    property var textos: ({})
    property int version: 0
    readonly property var guias: (((fi.formulario && fi.formulario.tipos) || []).find(t => t.clave === "obra") || {}).guias || ({})

    title: "Corregir tu ficha de obra de «" + libro + "»"
    preferredWidth: Kirigami.Units.gridUnit * 36
    standardButtons: Kirigami.Dialog.Cancel
    showCloseButton: false     // los botones ya están al pie (la × de la cabecera es roja en algunos temas de iconos)

    // `fo`: la ficha de obra de Yachay como la da `studio.lectura.fichaObra` ({calibreId, preguntas, detalle})
    function abrir(fo, titulo) {
        calibreId = Number(fo.calibreId); libro = titulo || ""; detalle = fo.detalle || ""
        preguntas = (fo.preguntas || []).map(p => p.titulo)
        const t = {}
        for (const p of (fo.preguntas || [])) t[p.titulo] = p.texto || ""
        textos = t
        vuelta.olvidar()
        version++
        open()
    }
    function revisar() { vuelta.simular(secciones()) }
    function secciones() {
        const s = {}
        for (const k of preguntas) s[k] = textos[k] || ""
        return s
    }

    customFooterActions: [
        Kirigami.Action {
            text: "Revisar"; icon.name: "document-preview"
            enabled: !dialogo.fi.ocupado
            onTriggered: dialogo.revisar()
        },
        Kirigami.Action {
            text: "Llevar a Yachay…"; icon.name: "go-up"
            enabled: vuelta.llevable && !dialogo.fi.ocupado
            onTriggered: vuelta.ofrecer()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        QQC2.Label {
            Layout.fillWidth: true
            text: "Es tu ficha sobre la obra, la de todos tus escritos: las copias que ya están en un escrito no cambian. "
                  + "«Revisar» dice qué cambiaría en Yachay; nada se envía sin confirmar."
            wrapMode: Text.WordWrap
        }
        QQC2.Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: dialogo.detalle
            font: Kirigami.Theme.smallFont
            color: Kirigami.Theme.disabledTextColor
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: dialogo.version >= 0 ? dialogo.preguntas.slice() : []
            ColumnLayout {
                required property string modelData
                Layout.fillWidth: true
                spacing: 0
                QQC2.Label { text: modelData; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                QQC2.TextArea {
                    Layout.fillWidth: true
                    Layout.minimumHeight: Kirigami.Units.gridUnit * 3
                    wrapMode: TextEdit.Wrap
                    placeholderText: dialogo.guias[modelData] || ""
                    text: dialogo.textos[modelData] || ""
                    Accessible.name: modelData
                    onTextChanged: { if (activeFocus) { dialogo.textos[modelData] = text; vuelta.olvidar() } }
                }
            }
        }
        QQC2.Label {
            objectName: "planObraYachay"
            Layout.fillWidth: true
            visible: !!vuelta.plan
            wrapMode: Text.WordWrap
            color: vuelta.plan && vuelta.plan.error ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
            text: vuelta.resumen + (vuelta.llevable ? " «Llevar a Yachay…» la envía tras confirmar." : "")
        }
        VueltaYachay {
            id: vuelta
            activo: dialogo.visible
            calibreId: dialogo.calibreId
            titulo: dialogo.libro
            pregunta: "¿Llevarla a Yachay?"
            onTerminada: hecha => { if (hecha) dialogo.close() }      // «Ahora no» deja seguir corrigiendo
        }
    }
}
