// DialogoFicha — «Nueva ficha» desde la ficha de un libro, con su PDF al lado (decisiones §9.4). Se elige el escrito
// destino (primero los que ya usan el libro), el tipo y la página; la cita se copia del PDF de la izquierda. El formulario
// lo describe `lib/consulta.py formulario` (la norma de fichas); «Revisar» simula (el nombre, el cotejo contra el PDF, lo
// que la norma objeta) y «Guardar la ficha» escribe lo revisado en fuentes/fichas/ del escrito (y, si el libro aún no es
// su fuente, en su fuentes.yml y su references.bib). Nunca toca Calibre ni Zotero.
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
        tipo = v.tipo || "textual"; textos = v.textos || ({}); revision = null; hoja = v.hoja || 0; version++
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
    function campos() {
        const s = {}
        for (const k of def.secciones) s[k] = textos[k] || ""
        const c = { tipo: tipo, secciones: s, uso: uso.text, tema: tema.text }
        if (def.pagina) c.pagina = pagina.text
        if (def.categoria) c.categoria = categoria.currentText
        return c
    }
    function revisar(aplicar) {
        if (!escrito) { ventana.mensajes.mostrar("Elige el escrito de la ficha.", "aviso"); return }
        esperando = true
        fi.revisar(escrito.carpeta, campos(), aplicar)
    }

    Connections {
        target: dialogo.fi
        function onCambiado() { if (!dialogo.fi.ocupado && dialogo.pendiente && dialogo.visible) dialogo.listo() }
        function onRevisada(r) {
            dialogo.esperando = false
            if (!dialogo.visible) return
            if (r.aplicar && r.escrito) {
                ventana.mensajes.mostrar("Ficha guardada en «" + dialogo.escrito.titulo + "»: " + r.archivo, "positivo")
                dialogo.close()
                return
            }
            dialogo.revision = r
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
                RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: dialogo.tipos
                        Chip {
                            required property var modelData
                            text: modelData.nombre
                            destacado: dialogo.tipo === modelData.clave
                            onClicked: { dialogo.tipo = modelData.clave; dialogo.revision = null; dialogo.version++ }
                        }
                    }
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
}
