// VueltaYachay — llevar la ficha de obra de un libro a Yachay, tras confirmar (decisiones §9.13). La usan «Nueva ficha» y
// «Corregir la ficha» de un escrito (DialogoFicha) y «Corregir…» de la ficha de obra en Yachay (DialogoObraYachay): una sola
// vuelta para los tres. `simular` pide a `studio.fichado` qué iría a Yachay y sobre qué versión (sin escribir); `ofrecer`
// abre «¿Llevarla…?» con la versión y lo que cambia; «Llevar a Yachay» la envía con `version_base`. Un 409 no pisa: abre
// «Tu ficha de obra cambió en Yachay» con las dos respuestas lado a lado y «Llevar la mía sobre la versión N» o «Quedarme con
// la de Yachay». Todo por la CLI de la base de lectura (`CanalYachay`); la ventana no escribe la base ni guarda el token.
// Solo atiende la señal `yachay` mientras su diálogo está `activo` (hay varios diálogos de ficha en la ventana).
import QtQuick
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: vuelta
    objectName: "vueltaYachay"
    visible: false
    readonly property var fi: studio.fichado
    property bool activo: false                  // el diálogo dueño está abierto
    property int calibreId: 0
    property string titulo: ""                   // el título del libro
    property string pregunta: "¿Llevarla también a Yachay?"
    property var plan: null                      // lo que iría a Yachay (simulación) o {error}
    property var conflicto: null                 // el 409: lo que hay en Yachay ahora
    property var secciones: ({})                 // las seis respuestas que se simularon (las que viajan)
    // hay algo que llevar: la simulación salió bien y cambia alguna respuesta
    readonly property bool llevable: !!plan && !plan.error && (plan.cambian || []).length > 0
    readonly property bool primera: !!plan && !!plan.nueva && !plan.version_base
    // lo que dice la simulación, en una línea (sin la acción, que pone cada diálogo)
    readonly property string resumen: !plan ? ""
        : plan.error ? "Yachay: " + (plan.sinCanal ? "sin token en el llavero; no se puede llevar." : plan.error)
        : !llevable ? "Tu ficha de obra en Yachay ya dice esto."
        : "En Yachay: " + (primera ? "sería tu primera ficha de obra de este libro" : "tu ficha de obra va en la versión " + plan.version_base)
          + "; cambiarían " + plan.cambian.join(", ") + "."
    signal terminada(bool hecha)                 // se llevó o se quedó con la de Yachay (true), o «Ahora no» (false)

    function simular(s) {
        plan = null; conflicto = null; secciones = Object.assign({}, s)
        fi.simularYachayDe(calibreId, secciones)
    }
    function ofrecer() { dialogoConfirmar.open() }
    // `sobre` ≥ 0 tras un 409: llevar la suya sobre esa versión; -1, sobre la de la base
    function llevar(sobre) { dialogoConfirmar.close(); dialogoConflicto.close(); fi.llevarAYachayDe(calibreId, secciones, sobre) }
    function olvidar() { plan = null; conflicto = null }

    Connections {
        target: vuelta.fi
        enabled: vuelta.activo
        function onYachay(r) {
            if (Number(r.calibre_id || vuelta.calibreId) !== Number(vuelta.calibreId)) return      // la de otro libro
            if (r.accion === "simular") { vuelta.plan = r; return }
            if (r.codigo === "lectura_modificada") { vuelta.conflicto = r; dialogoConflicto.open(); return }
            if (r.error) {
                ventana.mensajes.mostrar(r.sinCanal ? "Yachay: no hay token en el llavero; no se envió nada." : "Yachay: " + r.error, "aviso")
                return
            }
            if (r.accion === "quedarse") {
                ventana.mensajes.mostrar(r.ok ? "Te quedaste con la ficha de obra de Yachay: la base ya la tiene." : "Yachay: " + r.error,
                                         r.ok ? "positivo" : "aviso")
            } else if (r.escrita) {
                ventana.mensajes.mostrar("Ficha de obra llevada a Yachay (versión " + r.version + ")" + (r.aviso ? ". " + r.aviso : "."),
                                         r.aviso ? "aviso" : "positivo")
            }
            studio.lectura.recargar()
            studio.fichas.recargar()
            vuelta.terminada(true)
        }
    }

    Kirigami.PromptDialog {
        id: dialogoConfirmar
        objectName: "confirmarYachay"
        title: vuelta.pregunta
        subtitle: !vuelta.plan ? "" : "Tu ficha de obra de «" + vuelta.titulo + "» en Yachay "
                  + (vuelta.primera ? "aún no existe: nacería con estas respuestas." : "va en la versión " + vuelta.plan.version_base + ".")
                  + " Cambiarían: " + (vuelta.plan.cambian || []).join(", ") + ". Yachay mide que sean palabras propias; "
                  + "si otro la cambió allí después, no se pisa."
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action { text: "Llevar a Yachay"; icon.name: "go-up"
                              onTriggered: vuelta.llevar(-1) },
            Kirigami.Action { text: "Ahora no"; icon.name: "dialog-cancel"; onTriggered: { dialogoConfirmar.close(); vuelta.terminada(false) } }
        ]
    }
    // un 409: otro guardó en Yachay después; nada se envió
    Kirigami.PromptDialog {
        id: dialogoConflicto
        objectName: "conflictoYachay"
        readonly property var actual: vuelta.conflicto && vuelta.conflicto.actual ? vuelta.conflicto.actual.ficha || ({}) : ({})
        readonly property var mia: vuelta.conflicto ? vuelta.conflicto.ficha || ({}) : ({})
        readonly property var claves: ({ pregunta: "Pregunta", metodo: "Método", datos: "Datos", hallazgo: "Hallazgo", limites: "Límites", uso: "Uso que le daré" })
        title: "Tu ficha de obra cambió en Yachay"
        subtitle: !vuelta.conflicto ? "" : "Va en la versión " + vuelta.conflicto.version + " desde la última sincronía y no se envió nada. "
                  + Object.keys(claves).filter(k => (actual[k] || "") !== (mia[k] || ""))
                          .map(k => claves[k] + ": en Yachay «" + (actual[k] || "") + "»; la tuya «" + (mia[k] || "") + "»").join(" · ")
        standardButtons: Kirigami.Dialog.Cancel
        customFooterActions: [
            Kirigami.Action { text: "Llevar la mía sobre la versión " + (vuelta.conflicto ? vuelta.conflicto.version : ""); icon.name: "go-up"
                              onTriggered: vuelta.llevar(Number(vuelta.conflicto.version)) },
            Kirigami.Action { text: "Quedarme con la de Yachay"; icon.name: "go-down"
                              onTriggered: { dialogoConflicto.close(); vuelta.fi.quedarseConYachay() } }
        ]
    }
}
