// DialogoFicha — «Nueva ficha» desde la ficha de un libro, con su PDF al lado (decisiones §9.4). Se elige el escrito
// destino (primero los que ya usan el libro), el tipo y la página; la cita se copia del PDF de la izquierda. El formulario
// lo describe `lib/consulta.py formulario` (la norma de fichas); «Revisar» simula (el nombre, el cotejo contra el PDF, lo
// que la norma objeta) y «Guardar la ficha» escribe lo revisado en fuentes/fichas/ del escrito (y, si el libro aún no es
// su fuente, en su fuentes.yml y su references.bib). Nunca toca Calibre ni Zotero.
// La ficha de obra (§9.13): si la persona tiene la suya en Yachay (la trae la base de lectura), la de obra nace rellena con
// ella; al revisar se simula también qué iría a Yachay y sobre qué versión, y al guardar se ofrece llevarla de vuelta, tras
// confirmar. Un 409 no pisa: se muestra lo que hay en Yachay y se elige llevar la tuya sobre esa versión o quedarte con la de
// Yachay. Todo pasa por `studio.fichado` (la CLI de la base de lectura, con el token del llavero) y por VueltaYachay.
// Corregir (§9.13, nota del 2026-11-19): `corregir(f)` abre una ficha que ya existe en un escrito (desde el área Fichas) con
// su huella; «Revisar» simula la corrección (`guardar_ficha`) y «Guardar la corrección» la escribe sin pisar lo que cambió en
// disco. La de obra corregida ofrece la misma vuelta a Yachay.
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
    property var corrigiendo: null               // {carpeta, archivo, huella, escrito}: la ficha que ya existe y se corrige
    readonly property var obraYachay: studio.lectura.fichaObra.hay === true
                                      && Number(studio.lectura.fichaObra.calibreId) === Number(studio.libros.ficha.id) ? studio.lectura.fichaObra : null
    readonly property var def: tipos.find(t => t.clave === tipo) || ({ secciones: [], pagina: false, categoria: false })
    readonly property var escrito: escritos.currentIndex >= 0 ? fi.escritos[escritos.currentIndex] : null
    readonly property bool revisada: !!revision && !revision.error && !revision.aplicar

    title: (corrigiendo ? "Corregir la ficha de «" : "Nueva ficha de «") + (studio.libros.ficha.titulo || "") + "»"
    preferredWidth: Kirigami.Units.gridUnit * 72
    preferredHeight: Kirigami.Units.gridUnit * 44
    standardButtons: Kirigami.Dialog.Cancel
    showCloseButton: false     // los botones ya están al pie (la × de la cabecera es roja en algunos temas de iconos)

    // `v` (opcional): una ficha ya pensada {tipo, pagina, hoja, categoria, tema, textos, revisar} (del estudio de obra)
    function abrir(v) {
        v = v || {}
        tipo = v.tipo || "textual"; textos = v.textos || ({}); revision = null; hoja = v.hoja || 0; origen = v.origen || null
        deYachay = !!v.textos && tipo === "obra" && !!obraYachay; corrigiendo = null; vuelta.olvidar()
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
    // `f`: una ficha de la lista del área Fichas {tipo, carpeta, archivo, calibreId, escrito}; se lee con su huella
    function corregir(f) {
        tipo = f.tipo; textos = ({}); revision = null; hoja = 0; origen = null; deYachay = false; vuelta.olvidar()
        corrigiendo = { carpeta: f.carpeta, archivo: f.archivo, huella: "", escrito: f.escrito || "" }
        pagina.text = ""; tema.text = ""; uso.text = ""
        version++
        pendiente = { leer: true }
        open()
        if (Number(fi.calibreId) !== Number(f.calibreId)) fi.preparar(Number(f.calibreId))
        else listo()
    }
    // lo leído de la ficha que se corrige (o la de ahora, si cambió en disco)
    function poner(r) {
        const s = {}
        for (const x of (r.secciones || [])) s[x.titulo] = x.texto || ""
        tipo = r.tipo || tipo; textos = s; revision = null
        pagina.text = r.pagina || ""; uso.text = r.uso || ""
        categoriaPedida = r.categoria || "Cita clave"
        categoria.currentIndex = Math.max(0, categoria.model.indexOf(categoriaPedida))
        corrigiendo = Object.assign({}, corrigiendo, { archivo: r.archivo || corrigiendo.archivo, huella: r.huella || "" })
        version++
    }
    // el libro está listo: la hoja del PDF y, si se pidió, la revisión (o, al corregir, el escrito y la ficha)
    function listo() {
        const v = pendiente
        pendiente = null
        if (!v) return
        if (v.leer && corrigiendo) {
            escritos.currentIndex = fi.escritos.findIndex(e => e.carpeta === corrigiendo.carpeta)
            fi.leerFicha(corrigiendo.carpeta, corrigiendo.archivo)
            return
        }
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
        if (corrigiendo && !corrigiendo.huella) { ventana.mensajes.mostrar("La ficha aún se está leyendo.", "aviso"); return }
        if (!corrigiendo && !escrito) { ventana.mensajes.mostrar("Elige el escrito de la ficha.", "aviso"); return }
        esperando = true
        if (!aplicar && tipo === "obra") vuelta.simular(seccionesObra())
        if (corrigiendo) fi.corregir(corrigiendo.carpeta, corrigiendo.archivo, corrigiendo.huella, campos(), aplicar)
        else fi.revisar(escrito.carpeta, campos(), aplicar)
    }
    // hay algo que llevar a Yachay: la simulación salió bien y cambia alguna respuesta
    readonly property bool llevable: tipo === "obra" && vuelta.llevable
    readonly property string tituloEscrito: corrigiendo ? corrigiendo.escrito : (escrito ? escrito.titulo : "")

    Connections {
        target: dialogo.fi
        function onCambiado() { if (!dialogo.fi.ocupado && dialogo.pendiente && dialogo.visible) dialogo.listo() }
        function onRevisada(r) {
            dialogo.esperando = false
            if (!dialogo.visible) return
            if (r.codigo === "ficha_cambiada") {                       // otro la cambió en disco: no se pisa, se relee
                ventana.mensajes.mostrar("La ficha cambió en disco desde que la abriste: está la de ahora; revísala de nuevo.", "aviso")
                if (r.actual) dialogo.poner(r.actual)
                vuelta.olvidar()
                return
            }
            if (r.aplicar && r.escrito) {
                ventana.mensajes.mostrar((r.correccion ? "Ficha corregida en «" : "Ficha guardada en «") + dialogo.tituloEscrito + "»: " + r.archivo, "positivo")
                if (dialogo.llevable) { vuelta.ofrecer(); return }      // ofrecer la vuelta a Yachay (§9.13)
                dialogo.close()
                return
            }
            dialogo.revision = r
        }
        function onCorregible(r) {
            if (!dialogo.visible || !dialogo.corrigiendo) return
            if (r.error) { ventana.mensajes.mostrar(r.error, "error"); return }
            dialogo.poner(r)
        }
    }

    customFooterActions: [
        Kirigami.Action {
            text: "Revisar"; icon.name: "document-preview"
            enabled: !dialogo.esperando && !!dialogo.escrito
            onTriggered: dialogo.revisar(false)
        },
        Kirigami.Action {
            text: dialogo.corrigiendo ? "Guardar la corrección" : "Guardar la ficha"; icon.name: "document-save"
            enabled: dialogo.revisada && !dialogo.esperando
            onTriggered: dialogo.revisar(true)
        }
    ]

    Item {
      implicitWidth: Kirigami.Units.gridUnit * 70
      implicitHeight: Kirigami.Units.gridUnit * 36
      VueltaYachay {
          id: vuelta
          activo: dialogo.visible
          calibreId: dialogo.fi.calibreId
          titulo: studio.libros.ficha.titulo || ""
          onTerminada: dialogo.close()                 // la ficha del escrito ya está guardada
      }
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
                    enabled: !dialogo.corrigiendo              // una corrección no cambia de escrito
                    displayText: dialogo.corrigiendo ? dialogo.corrigiendo.escrito : currentText
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
                // el tipo de ficha, en un selector segmentado (gui-comun 4.2); una corrección no cambia de tipo
                SelectorSegmentado {
                    visible: !dialogo.corrigiendo
                    titulo: "Tipo de ficha"
                    opciones: dialogo.tipos.map(t => ({ clave: t.clave, texto: t.nombre }))
                    actual: dialogo.tipo
                    onElegida: clave => {
                        dialogo.tipo = clave; dialogo.revision = null; vuelta.olvidar()
                        if (clave === "obra") dialogo.rellenarObra()
                        dialogo.version++
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
                        text: !dialogo.revisada ? ""
                              : dialogo.corrigiendo ? "Al guardar se corrige fuentes/fichas/" + dialogo.revision.archivo + " en «" + dialogo.tituloEscrito + "»"
                                + (dialogo.revision.renombra ? " (antes " + dialogo.revision.antes + "; los enlaces de las otras fichas se corrigen)" : "")
                                + ". Calibre y Zotero no se tocan."
                              : "Al guardar se escribe fuentes/fichas/" + dialogo.revision.archivo + " en «" + dialogo.tituloEscrito + "»"
                              + (dialogo.revision.nueva_fuente ? "; el libro aún no es su fuente: se añade a su fuentes.yml y a su references.bib" : "")
                              + ". Calibre y Zotero no se tocan."
                    }
                    // lo que iría a la ficha de obra de Yachay (§9.13): se ofrece al guardar, tras confirmar
                    QQC2.Label {
                        objectName: "planYachay"
                        Layout.fillWidth: true
                        visible: dialogo.tipo === "obra" && !!vuelta.plan
                        wrapMode: Text.WordWrap
                        color: vuelta.plan && vuelta.plan.error ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.textColor
                        text: vuelta.resumen + (dialogo.llevable ? " Al guardar se te ofrece llevarla." : "")
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
