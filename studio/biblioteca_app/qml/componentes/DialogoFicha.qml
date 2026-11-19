// DialogoFicha — «Nueva ficha» desde la ficha de un libro, con su PDF al lado (decisiones §9.4). Se elige el escrito
// destino (primero los que ya usan el libro), el tipo y la página; la cita se copia del PDF de la izquierda. El formulario
// lo describe `lib/consulta.py formulario` (la norma de fichas); «Revisar» simula (el nombre, el cotejo contra el PDF, lo
// que la norma objeta) y «Guardar la ficha» escribe lo revisado en fuentes/fichas/ del escrito (y, si el libro aún no es
// su fuente, en su fuentes.yml y su references.bib). Nunca toca Calibre ni Zotero.
// La ficha de obra (§9.13): si la persona tiene la suya en Yachay (la trae la base de lectura), la de obra nace rellena con
// ella; al revisar se simula también qué iría a Yachay y sobre qué versión, y al guardar se ofrece llevarla de vuelta, tras
// confirmar. Un 409 no pisa: se muestra lo que hay en Yachay y se elige llevar la tuya sobre esa versión o quedarte con la de
// Yachay. Todo pasa por `studio.fichado` (la CLI de la base de lectura, con el token del llavero).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

Kirigami.Dialog {
    id: dialogo
    readonly property var fi: studio.fichado
    readonly property var tipos: ((fi.formulario && fi.formulario.tipos) || []).filter(t => t.libro)
    property string tipo: "textual"
    property var textos: ({})
    property var revision: null
    property bool esperando: false
    property int version: 0
    property int hoja: 0
    property string categoriaPedida: "Cita clave"
    property var pendiente: null                 // lo que espera a que el libro esté listo (escritos, formulario, PDF)
    property var origen: null                    // {autor: "llm", herramienta} si la propuso la IA (estudio de obra; C3.3)
    property bool deYachay: false                // la ficha de obra nació rellena con la de Yachay (§9.13)
    property var planYachay: null                // lo que iría a Yachay (simulación) o {error}
    property var conflicto: null                 // el 409: lo que hay en Yachay ahora
    readonly property var obraYachay: studio.lectura.fichaObra.hay === true
                                      && Number(studio.lectura.fichaObra.calibreId) === Number(studio.libros.ficha.id) ? studio.lectura.fichaObra : null
    readonly property var def: tipos.find(t => t.clave === tipo) || ({ secciones: [], pagina: false, categoria: false })
    readonly property var escrito: escritos.currentIndex >= 0 ? fi.escritos[escritos.currentIndex] : null
    readonly property bool revisada: !!revision && !revision.error && !revision.aplicar

    title: "Nueva ficha de «" + (studio.libros.ficha.titulo || "") + "»"
    preferredWidth: Kirigami.Units.gridUnit * 72
    preferredHeight: Kirigami.Units.gridUnit * 44
    standardButtons: Kirigami.Dialog.Cancel

    // `v` (opcional): una ficha ya pensada {tipo, pagina, hoja, categoria, tema, textos, revisar} (del estudio de obra)
    function abrir(v) {
        v = v || {}
        tipo = v.tipo || "textual"; textos = v.textos || ({}); revision = null; hoja = v.hoja || 0; origen = v.origen || null
        deYachay = !!v.textos && tipo === "obra" && !!obraYachay; planYachay = null; conflicto = null
        if (tipo === "obra" && !v.textos) rellenarObra()
        version++
        pagina.text = v.pagina || ""; tema.text = v.tema || ""; uso.text = v.uso || ""
        categoriaPedida = v.categoria || "Cita clave"
        categoria.currentIndex = Math.max(0, categoria.model.indexOf(categoriaPedida))
        pendiente = v
        open()
        if (Number(fi.calibreId) !== Number(studio.libros.ficha.id)) fi.preparar(studio.libros.ficha.id)
        else listo()
    }
    // el libro está listo: la hoja del PDF y, si se pidió, la revisión
    function listo() {
        const v = pendiente
        pendiente = null
        if (!v) return
        if (hoja > 0) irAHoja.restart()
        if (v.revisar) Qt.callLater(revisar, false)
    }
    Timer { id: irAHoja; interval: 400; onTriggered: pdf.irA(dialogo.hoja, 0) }
    // la de obra, con la de Yachay si existe y aún no se escribió nada en sus seis preguntas
    function rellenarObra() {
        if (!obraYachay) return
        const guias = Object.keys(obraYachay.secciones)
        if (guias.some(k => (textos[k] || "") !== "")) return
        textos = Object.assign({}, obraYachay.secciones)
        deYachay = true
    }
    function seccionesObra() {
        const s = {}
        for (const k of Object.keys((def.guias || {}))) s[k] = textos[k] || ""
        return s
    }
    function campos() {
        const s = {}
        for (const k of def.secciones) s[k] = textos[k] || ""
        const c = { tipo: tipo, secciones: s, uso: uso.text, tema: tema.text }
        if (def.pagina) c.pagina = pagina.text
        if (def.categoria) c.categoria = categoria.currentText
        if (origen) c.origen = origen
        return c
    }
    function revisar(aplicar) {
        if (!escrito) { ventana.mensajes.mostrar("Elige el escrito de la ficha.", "aviso"); return }
        esperando = true
        if (!aplicar && tipo === "obra") { planYachay = null; fi.simularYachay(seccionesObra()) }
        fi.revisar(escrito.carpeta, campos(), aplicar)
    }
    // hay algo que llevar a Yachay: la simulación salió bien y cambia alguna respuesta
    readonly property bool llevable: tipo === "obra" && !!planYachay && !planYachay.error && (planYachay.cambian || []).length > 0

    Connections {
        target: dialogo.fi
        function onCambiado() { if (!dialogo.fi.ocupado && dialogo.pendiente && dialogo.visible) dialogo.listo() }
        function onRevisada(r) {
            dialogo.esperando = false
            if (!dialogo.visible) return
            if (r.aplicar && r.escrito) {
                ventana.mensajes.mostrar("Ficha guardada en «" + dialogo.escrito.titulo + "»: " + r.archivo, "positivo")
                if (dialogo.llevable) { confirmarYachay.open(); return }      // ofrecer la vuelta a Yachay (§9.13)
                dialogo.close()
                return
            }
            dialogo.revision = r
        }
        function onYachay(r) {
            if (!dialogo.visible) return
            if (r.accion === "simular") { dialogo.planYachay = r; return }
            if (r.codigo === "lectura_modificada") { dialogo.conflicto = r; conflictoYachay.open(); return }
            if (r.error) {
                ventana.mensajes.mostrar(r.sinCanal ? "Yachay: no hay token en el llavero; la ficha quedó solo en el escrito."
                                                    : "Yachay: " + r.error, "aviso")
                return
            }
            if (r.accion === "quedarse") {
                ventana.mensajes.mostrar(r.ok ? "Te quedaste con la ficha de obra de Yachay: la base ya la tiene." : "Yachay: " + r.error,
                                         r.ok ? "positivo" : "aviso")
            } else if (r.escrita) {
                ventana.mensajes.mostrar("Ficha de obra llevada a Yachay (versión " + r.version + ")" + (r.aviso ? ". " + r.aviso : "."), r.aviso ? "aviso" : "positivo")
            }
            studio.lectura.recargar()
            dialogo.close()
        }
    }

    customFooterActions: [
        Kirigami.Action {
            text: "Revisar"; icon.name: "document-preview"
            enabled: !dialogo.esperando && !!dialogo.escrito
            onTriggered: dialogo.revisar(false)
        },
        Kirigami.Action {
            text: "Guardar la ficha"; icon.name: "document-save"
            enabled: dialogo.revisada && !dialogo.esperando
            onTriggered: dialogo.revisar(true)
        }
    ]

    Item {
      implicitWidth: Kirigami.Units.gridUnit * 70
      implicitHeight: Kirigami.Units.gridUnit * 36
      RowLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        // el PDF del libro: la cita se copia de aquí
        VistaPdf {
            id: pdf
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 34
            visor: dialogo.fi.visor
            mensajeVacio: "El libro no tiene PDF"
            explicacionVacia: "Escribe la cita tal cual está en la fuente: se coteja al revisar."
        }

        QQC2.ScrollView {
            id: vista
            Layout.fillHeight: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 34
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            ColumnLayout {
                width: vista.availableWidth - Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                QQC2.Label { text: "Escrito"; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                QQC2.ComboBox {
                    id: escritos
                    Layout.fillWidth: true
                    model: dialogo.fi.escritos.map(e => e.titulo + (e.usa ? " · ya usa el libro" : ""))
                    Accessible.name: "Escrito de la ficha"
                    onActivated: dialogo.revision = null
                }
                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: !!dialogo.origen
                    type: Kirigami.MessageType.Information
                    text: "La propuso la IA: se guarda marcada y queda en el registro de uso de IA del escrito. No se podrá citar hasta que cotejes su página en el PDF."
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !!dialogo.origen && !!dialogo.fi.formulario.origen
                    text: dialogo.fi.formulario.origen ? dialogo.fi.formulario.origen.porque + " · " + dialogo.fi.formulario.origen.fuente : ""
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: dialogo.tipos
                        Chip {
                            required property var modelData
                            text: modelData.nombre
                            destacado: dialogo.tipo === modelData.clave
                            onClicked: {
                                dialogo.tipo = modelData.clave; dialogo.revision = null; dialogo.planYachay = null
                                if (modelData.clave === "obra") dialogo.rellenarObra()
                                dialogo.version++
                            }
                        }
                    }
                }
                // la línea «por qué · fuente» del tipo (la ficha de obra, C3.1)
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: !!dialogo.def.porque
                    text: (dialogo.def.porque || "") + " · " + (dialogo.def.fuente || "")
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                    wrapMode: Text.WordWrap
                }
                Kirigami.InlineMessage {
                    objectName: "rellenaDeYachay"
                    Layout.fillWidth: true
                    visible: dialogo.tipo === "obra" && dialogo.deYachay && !!dialogo.obraYachay
                    type: Kirigami.MessageType.Information
                    text: "Rellena con tu ficha de obra de Yachay (" + (dialogo.obraYachay ? dialogo.obraYachay.detalle : "") + "). "
                          + "Esta es su copia para el escrito: ajusta «Uso que le daré» a él."
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Kirigami.Units.largeSpacing
                    QQC2.Label { text: "Página o lugar"; visible: dialogo.def.pagina }
                    RowLayout {
                        visible: dialogo.def.pagina
                        Layout.fillWidth: true
                        QQC2.TextField { id: pagina; Layout.fillWidth: true; placeholderText: "la impresa: 12 · art. 5 · 3.2"; onTextChanged: dialogo.revision = null }
                        QQC2.Label { text: "hoja " + pdf.paginaActual + " del PDF"; color: Kirigami.Theme.disabledTextColor; font: Kirigami.Theme.smallFont }
                    }
                    QQC2.Label { text: "Categoría"; visible: dialogo.def.categoria }
                    QQC2.ComboBox {
                        id: categoria
                        Layout.fillWidth: true
                        visible: dialogo.def.categoria
                        model: (dialogo.fi.formulario && dialogo.fi.formulario.categorias) || []
                        onModelChanged: currentIndex = Math.max(0, model.indexOf(dialogo.categoriaPedida))
                        onActivated: { dialogo.categoriaPedida = currentText; dialogo.revision = null }
                    }
                    QQC2.Label { text: "Tema" }
                    QQC2.TextField { id: tema; Layout.fillWidth: true; placeholderText: "dos a cuatro palabras (si no, sale de la cita)" }
                    QQC2.Label { text: "Uso" }
                    QQC2.TextField { id: uso; Layout.fillWidth: true; placeholderText: "la parte del escrito que respalda" }
                }
                Repeater {
                    model: dialogo.version >= 0 ? dialogo.def.secciones.slice() : []
                    ColumnLayout {
                        required property string modelData
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label {
                            text: modelData + (modelData === dialogo.def.literal ? " (tal cual en la fuente, sin comillas)" : "")
                            font: Kirigami.Theme.smallFont
                            color: Kirigami.Theme.disabledTextColor
                        }
                        QQC2.TextArea {
                            Layout.fillWidth: true
                            Layout.minimumHeight: Kirigami.Units.gridUnit * (modelData === dialogo.def.literal ? 4 : 3)
                            wrapMode: TextEdit.Wrap
                            placeholderText: (dialogo.def.guias || {})[modelData] || ""
                            text: dialogo.textos[modelData] || ""
                            Accessible.name: modelData
                            onTextChanged: { if (activeFocus) { dialogo.textos[modelData] = text; dialogo.revision = null } }
                        }
                    }
                }

                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    visible: !!dialogo.revision && !!dialogo.revision.error
                    type: Kirigami.MessageType.Error
                    text: dialogo.revision && dialogo.revision.error ? dialogo.revision.error : ""
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: dialogo.revisada
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Separator { Layout.fillWidth: true }
                    RowLayout {
                        Layout.fillWidth: true
                        readonly property string estado: dialogo.revisada ? dialogo.revision.verificacion.estado || "pendiente" : ""
                        Kirigami.Icon {
                            source: parent.estado.startsWith("verificada") ? "checkmark" : parent.estado === "observada" ? "data-warning" : "question"
                            implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                            color: parent.estado.startsWith("verificada") ? Kirigami.Theme.positiveTextColor
                                 : parent.estado === "observada" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
                        }
                        QQC2.Label {
                            text: ({ verificada_script: "Cotejada en el PDF", verificada_autor: "Verificada por el autor",
                                     observada: "Observada", pendiente: "Sin cotejar" })[parent.estado] || ""
                            font.weight: Font.Medium
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: dialogo.revisada ? dialogo.revision.archivo : ""
                            font.family: Kirigami.Theme.fixedWidthFont.family
                            elide: Text.ElideMiddle
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        wrapMode: Text.WordWrap
                        color: Kirigami.Theme.disabledTextColor
                        text: dialogo.revisada ? (dialogo.revision.detalle || "") : ""
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: !dialogo.revisada ? "" : "Al guardar se escribe fuentes/fichas/" + dialogo.revision.archivo + " en «" + (dialogo.escrito ? dialogo.escrito.titulo : "") + "»"
                              + (dialogo.revision.nueva_fuente ? "; el libro aún no es su fuente: se añade a su fuentes.yml y a su references.bib" : "")
                              + ". Calibre y Zotero no se tocan."
                    }
                    // lo que iría a la ficha de obra de Yachay (§9.13): se ofrece al guardar, tras confirmar
                    QQC2.Label {
                        objectName: "planYachay"
                        Layout.fillWidth: true
                        visible: dialogo.tipo === "obra" && !!dialogo.planYachay
                        wrapMode: Text.WordWrap
                        color: dialogo.planYachay && dialogo.planYachay.error ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
                        text: !dialogo.planYachay ? ""
                              : dialogo.planYachay.error ? "Yachay: " + (dialogo.planYachay.sinCanal ? "sin token en el llavero; la ficha queda solo en el escrito." : dialogo.planYachay.error)
                              : !dialogo.llevable ? "Tu ficha de obra en Yachay ya dice esto."
                              : "En Yachay: " + (dialogo.planYachay.nueva && !dialogo.planYachay.version_base ? "sería tu primera ficha de obra de este libro"
                                                 : "tu ficha de obra va en la versión " + dialogo.planYachay.version_base)
                                + "; cambiarían " + dialogo.planYachay.cambian.join(", ") + ". Al guardar se te ofrece llevarla."
                    }
                    Repeater {
                        model: dialogo.revisada ? dialogo.revision.problemas : []
                        QQC2.Label {
                            required property string modelData
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: "· " + modelData
                            color: modelData.startsWith("aviso") ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.negativeTextColor
                        }
                    }
                }
            }
        }
    }
    }

    // la vuelta a Yachay, tras confirmar (§9.13)
    Kirigami.PromptDialog {
        id: confirmarYachay
        objectName: "confirmarYachay"
        title: "¿Llevarla también a Yachay?"
        subtitle: !dialogo.planYachay ? "" : "Tu ficha de obra de «" + (studio.libros.ficha.titulo || "") + "» en Yachay "
                  + (dialogo.planYachay.nueva && !dialogo.planYachay.version_base ? "aún no existe: nacería con estas respuestas."
                                                                                  : "va en la versión " + dialogo.planYachay.version_base + ".")
                  + " Cambiarían: " + (dialogo.planYachay.cambian || []).join(", ") + ". Yachay mide que sean palabras propias; "
                  + "si otro la cambió allí después, no se pisa."
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action { text: "Llevar a Yachay"; icon.name: "go-up"
                              onTriggered: { confirmarYachay.close(); dialogo.fi.llevarAYachay(dialogo.seccionesObra(), -1) } },
            Kirigami.Action { text: "Ahora no"; icon.name: "dialog-cancel"; onTriggered: { confirmarYachay.close(); dialogo.close() } }
        ]
    }
    // un 409: otro guardó en Yachay después; nada se envió
    Kirigami.PromptDialog {
        id: conflictoYachay
        objectName: "conflictoYachay"
        readonly property var actual: dialogo.conflicto && dialogo.conflicto.actual ? dialogo.conflicto.actual.ficha || ({}) : ({})
        readonly property var mia: dialogo.conflicto ? dialogo.conflicto.ficha || ({}) : ({})
        readonly property var claves: ({ pregunta: "Pregunta", metodo: "Método", datos: "Datos", hallazgo: "Hallazgo", limites: "Límites", uso: "Uso que le daré" })
        title: "Tu ficha de obra cambió en Yachay"
        subtitle: !dialogo.conflicto ? "" : "Va en la versión " + dialogo.conflicto.version + " desde la última sincronía y no se envió nada. "
                  + Object.keys(claves).filter(k => (actual[k] || "") !== (mia[k] || ""))
                          .map(k => claves[k] + ": en Yachay «" + (actual[k] || "") + "»; la tuya «" + (mia[k] || "") + "»").join(" · ")
        standardButtons: Kirigami.Dialog.Cancel
        customFooterActions: [
            Kirigami.Action { text: "Llevar la mía sobre la versión " + (dialogo.conflicto ? dialogo.conflicto.version : ""); icon.name: "go-up"
                              onTriggered: { conflictoYachay.close(); dialogo.fi.llevarAYachay(dialogo.seccionesObra(), Number(dialogo.conflicto.version)) } },
            Kirigami.Action { text: "Quedarme con la de Yachay"; icon.name: "go-down"
                              onTriggered: { conflictoYachay.close(); dialogo.fi.quedarseConYachay() } }
        ]
    }
}
