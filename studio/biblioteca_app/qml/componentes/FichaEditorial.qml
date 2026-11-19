// FichaEditorial — el libro leído como en un catálogo de biblioteca (reingeniería B7; reordenada el 2026-11-18, decisiones
// §9.9): arriba, la portada, el título, el autor y el año, la clave para citar en monoespaciada (Zotero manda en citas) y
// dos cifras (Leído y Subrayados, de la base de lectura); la fila «Abrir» (la acción rellena), «Nueva ficha», «Estudiar
// con la IA» y «Citar en LaTeX» (copia \parencite{clave}); «Usado en»; Dolphin, Calibre y Zotero; y debajo, el estado en
// Zotero, la lectura en KOReader, la nota, identificadores, materias, descripción, formatos y fichas canónicas. Solo lee: lo que cambia la biblioteca es una operación.
// Desde aquí se ficha el libro en un escrito y se estudia con la IA (DialogoFicha y DialogoEstudioObra, §9.4 y §9.5):
// eso escribe solo en las fichas del escrito, nunca en Calibre ni en Zotero. Debajo de «Usado en», la ficha de obra de la
// persona en Yachay (§9.13: las seis respuestas, temas, signo, si está leída), con «Llevar a un escrito» y «Corregir…»
// (DialogoObraYachay: las seis, a Yachay tras confirmar, sin pasar por un escrito).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.Control {
    id: raiz
    readonly property var l: studio.libros
    readonly property var f: l.ficha
    signal cerrar()

    padding: 0
    Kirigami.Theme.colorSet: Kirigami.Theme.View
    Kirigami.Theme.inherit: false
    background: Rectangle { color: Kirigami.Theme.backgroundColor }
    Accessible.name: "Ficha de " + (f.titulo || "ningún libro")

    function accion(n) { return studio.acciones.accion(n) }

    contentItem: Item {
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.gridUnit * 2
            visible: !raiz.l.hayActual
            icon.name: "folder-book"
            text: "Elige un libro"
            explanation: "Su ficha editorial, su clave para citar y su lectura aparecen aquí"
        }
        QQC2.ScrollView {
            id: desplazable
            anchors.fill: parent
            visible: raiz.l.hayActual
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

            ColumnLayout {
                width: desplazable.availableWidth - Kirigami.Units.largeSpacing * 4
                x: Kirigami.Units.largeSpacing * 2
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    QQC2.Label { text: "Calibre " + (raiz.f.id || ""); color: Kirigami.Theme.disabledTextColor; font: Kirigami.Theme.smallFont }
                    Item { Layout.fillWidth: true }
                    QQC2.ToolButton { icon.name: "window-close"; display: QQC2.AbstractButton.IconOnly; text: "Cerrar la ficha"; onClicked: raiz.cerrar(); Accessible.name: text }
                }
                // la portada, el título, el autor y el año, y la clave para citar (§9.9)
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.largeSpacing
                    Item {
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 7
                        Layout.preferredHeight: Layout.preferredWidth * 1.45
                        Image {
                            id: portada
                            anchors.fill: parent
                            source: raiz.f.fuente || ""
                            visible: raiz.f.portada === true
                            asynchronous: true
                            fillMode: Image.PreserveAspectFit
                            verticalAlignment: Image.AlignTop
                            sourceSize.width: 520
                        }
                        Rectangle {
                            anchors.fill: parent
                            visible: raiz.f.portada !== true || portada.status !== Image.Ready
                            radius: Kirigami.Units.cornerRadius
                            color: Kirigami.Theme.alternateBackgroundColor
                            border.color: Qt.alpha(Kirigami.Theme.textColor, 0.15)
                            Kirigami.Icon { anchors.centerIn: parent; source: "image-missing"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: implicitWidth; opacity: 0.5 }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        spacing: Kirigami.Units.smallSpacing
                        Kirigami.Heading {
                            Layout.fillWidth: true
                            level: 3
                            text: raiz.f.titulo || ""
                            wrapMode: Text.WordWrap
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: [(raiz.f.autores || []).join(" · ") || "sin autor", raiz.f.año || ""].filter(x => x).join(" · ")
                            wrapMode: Text.WordWrap
                            font.italic: true
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Kirigami.Units.smallSpacing
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: raiz.f.clave || "sin clave (la pone Better BibTeX en Zotero)"
                                font: raiz.f.clave ? Kirigami.Theme.fixedWidthFont : Kirigami.Theme.smallFont
                                color: raiz.f.clave ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
                                elide: Text.ElideRight
                                Accessible.name: "Clave para citar: " + text
                            }
                            BotonAccion { accion: raiz.accion("libro.copiar_clave"); conTexto: false; flat: true; visible: !!raiz.f.clave }
                        }
                        // dos cifras: lo leído y los subrayados (los de la base de lectura, que sigue al libro elegido)
                        RowLayout {
                            Layout.topMargin: Kirigami.Units.smallSpacing
                            spacing: Kirigami.Units.largeSpacing * 2
                            readonly property bool enBase: studio.lectura.libro.hay === true && String(studio.lectura.actualId) === String(raiz.f.id)
                            readonly property real leido: enBase && studio.lectura.libro.fraccion >= 0 ? studio.lectura.libro.fraccion : (raiz.f.koProgreso ?? -1)
                            Cifra { visible: parent.leido >= 0; valor: Math.round(Math.max(0, parent.leido) * 100) + " %"; rotulo: "Leído" }
                            Cifra { visible: parent.enBase; valor: String(studio.lectura.libro.total || 0); rotulo: "Subrayados" }
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: [raiz.f.imprenta || "", (raiz.f.serie || "") !== "" ? "Colección: " + raiz.f.serie : ""].filter(x => x).join(" · ")
                    wrapMode: Text.WordWrap
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                }

                // abrir (la acción rellena), fichar, estudiar con la IA (§9.4 y §9.5) y citar en LaTeX
                Flow {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Chip {
                        readonly property var a: raiz.accion("libro.archivo")
                        text: "Abrir"
                        icono: "document-open"
                        destacado: true
                        enabled: a ? a.habilitada : false
                        ayuda: "El documento con su aplicación"
                        onClicked: a.disparar()
                    }
                    Chip {
                        objectName: "nuevaFicha"
                        text: "Nueva ficha"
                        icono: "document-new"
                        ayuda: "Una ficha textual, de paráfrasis o de fuente en un escrito, con el PDF al lado y su cotejo"
                        onClicked: dialogoFicha.abrir()
                    }
                    Chip {
                        objectName: "estudiarIA"
                        text: "Estudiar con la IA"
                        icono: "tools-wizard"
                        ayuda: "Copia el prompt de una mirada sobre unas hojas del libro y lee de vuelta lo que respondió el chat"
                        onClicked: dialogoEstudio.abrir()
                    }
                    Chip {
                        text: "Citar en LaTeX"
                        icono: "edit-copy"
                        enabled: !!raiz.f.clave
                        ayuda: raiz.f.clave ? "Copia \\parencite{" + raiz.f.clave + "}: pégalo en LaTeX Studio" : "Sin clave para citar: enlázalo con Zotero"
                        onClicked: raiz.l.copiarCita()
                    }
                }

                // en qué escritos se usa (§9.1)
                Kirigami.Heading { level: 4; text: "Usado en"; visible: raiz.l.usos.length > 0 }
                Repeater {
                    model: raiz.l.usos
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        Layout.fillWidth: true
                        icon.name: "document-edit"
                        enabled: !!modelData.principal
                        contentItem: ColumnLayout {
                            spacing: 0
                            QQC2.Label { Layout.fillWidth: true; text: modelData.titulo; elide: Text.ElideRight }
                            QQC2.Label { Layout.fillWidth: true; text: modelData.proyecto + (modelData.fichas ? " · " + modelData.fichas + " ficha" + (modelData.fichas === 1 ? "" : "s") : "")
                                         elide: Text.ElideMiddle; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                        }
                        onClicked: raiz.l.abrirEnLatex(modelData.principal)
                        QQC2.ToolTip.text: "Abrir el escrito en LaTeX Studio"
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    }
                }

                // la ficha de obra de la persona en Yachay (§9.13), como la trajo la base de lectura
                ColumnLayout {
                    id: obraYachay
                    objectName: "fichaObraYachay"
                    readonly property var fo: studio.lectura.fichaObra
                    Layout.fillWidth: true
                    visible: fo.hay === true && String(fo.calibreId) === String(raiz.f.id)
                    spacing: Kirigami.Units.smallSpacing
                    RowLayout {
                        Layout.fillWidth: true
                        Kirigami.Heading { level: 4; text: obraYachay.fo.procedencia || "Ficha de obra en Yachay"; Layout.fillWidth: true }
                        Chip {
                            objectName: "fichaObraAlEscrito"
                            text: "Llevar a un escrito"
                            icono: "document-new"
                            ayuda: "Una ficha de obra en un escrito, rellena con esta: ajusta «Uso que le daré» a ese escrito"
                            onClicked: dialogoFicha.abrir({ tipo: "obra", textos: Object.assign({}, obraYachay.fo.secciones) })
                        }
                        Chip {
                            objectName: "fichaObraCorregir"
                            text: "Corregir…"
                            icono: "document-edit"
                            ayuda: "Corregir tus seis respuestas en Yachay sin pasar por un escrito: se revisa qué cambia y se lleva tras confirmar"
                            onClicked: dialogoObraYachay.abrir(obraYachay.fo, studio.libros.ficha.titulo || "")
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: obraYachay.fo.detalle || ""
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.WordWrap
                    }
                    Repeater {
                        model: obraYachay.visible ? obraYachay.fo.preguntas : []
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 0
                            QQC2.Label { text: modelData.titulo; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                            QQC2.Label {
                                Layout.fillWidth: true
                                text: modelData.texto || "Sin responder"
                                color: modelData.texto ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
                                wrapMode: Text.WordWrap
                                textFormat: Text.PlainText
                            }
                        }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: [obraYachay.fo.temas ? "Temas: " + obraYachay.fo.temas : "", obraYachay.fo.signo ? "Signo: " + obraYachay.fo.signo : ""].filter(x => x).join(" · ")
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.WordWrap
                    }
                }

                // lo demás del libro: su carpeta, Calibre y Zotero
                Flow {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: [{ n: "libro.dolphin", t: "Dolphin", i: "system-file-manager" }, { n: "libro.calibre", t: "Calibre", i: "calibre" },
                                { n: "libro.zotero", t: "Zotero", i: "zotero" }]
                        Chip {
                            required property var modelData
                            readonly property var a: raiz.accion(modelData.n)
                            text: modelData.t
                            icono: modelData.i
                            enabled: a ? a.habilitada : false
                            ayuda: a ? a.texto.replace("&", "") : ""
                            onClicked: a.disparar()
                        }
                    }
                }

                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    wideMode: false
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Citar" }
                    RowLayout {
                        Kirigami.FormData.label: "Zotero:"
                        Kirigami.Icon {
                            source: raiz.f.zotero ? "data-success" : "data-warning"
                            implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                        }
                        QQC2.Label { text: raiz.f.zotero ? "enlazado · " + raiz.f.zoteroKey : "sin enlazar (bandeja «Sin Zotero»)"; font.family: raiz.f.zotero ? Kirigami.Theme.fixedWidthFont.family : Kirigami.Theme.defaultFont.family }
                    }
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Lectura" }
                    ColumnLayout {
                        Kirigami.FormData.label: "KOReader:"
                        Layout.fillWidth: true
                        QQC2.Label { text: raiz.f.koreader || "sin abrir en KOReader"; color: raiz.f.koreader ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        BarraLectura { visible: (raiz.f.koProgreso ?? -1) >= 0; fraccion: Math.max(0, raiz.f.koProgreso ?? 0); tono: studio.lectura.colores.koreader || ""; Layout.fillWidth: true }
                    }
                    RowLayout {
                        Kirigami.FormData.label: "Nota de lectura:"
                        QQC2.Label { text: raiz.f.hayNota ? (raiz.f.notaEnlazada ? "enlazada en Calibre" : "en notas/") : "todavía no hay"; color: raiz.f.hayNota ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor }
                        BotonAccion { accion: raiz.accion("libro.nota"); conTexto: false; visible: raiz.f.hayNota === true }
                    }
                    Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Descripción bibliográfica"; visible: idsRep.count > 0 || (raiz.f.tipo || "") !== "" }
                    QQC2.Label { Kirigami.FormData.label: "Tipo:"; visible: (raiz.f.tipo || "") !== ""; text: raiz.f.tipo || "" }
                    Repeater {
                        id: idsRep
                        model: raiz.f.identificadores || []
                        delegate: QQC2.Label {
                            required property var modelData
                            Kirigami.FormData.label: modelData.tipo + ":"
                            text: modelData.valor
                            font.family: Kirigami.Theme.fixedWidthFont.family
                            textFormat: Text.PlainText
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                    }
                    // ¿existe? El DOI en Crossref y el ISBN en Open Library (C12.5, §9.10), con su por qué y su fuente
                    QQC2.Label {
                        Kirigami.FormData.label: "Existe:"
                        visible: (raiz.f.ids || "") !== ""
                        text: raiz.f.ids || ""
                        color: (raiz.f.ids || "").indexOf("no existe") >= 0 || (raiz.f.ids || "").indexOf("mal formado") >= 0
                               ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.disabledTextColor
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    QQC2.Label {
                        visible: (raiz.f.ids || "") !== ""
                        text: raiz.f.porqueIds || ""
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.disabledTextColor
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    QQC2.Label { Kirigami.FormData.label: "Añadido:"; visible: (raiz.f.añadido || "") !== ""; text: raiz.f.añadido || ""; color: Kirigami.Theme.disabledTextColor }
                }
                // materias (etiquetas)
                Flow {
                    Layout.fillWidth: true
                    visible: (raiz.f.etiquetas || []).length > 0
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: raiz.f.etiquetas || []
                        delegate: QQC2.Button {
                            required property string modelData
                            text: modelData
                            flat: true
                            font: Kirigami.Theme.smallFont
                            onClicked: raiz.l.buscar("etiqueta:\"" + modelData + "\"")
                            QQC2.ToolTip.text: "Buscar los libros con esta etiqueta"
                            QQC2.ToolTip.visible: hovered
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: raiz.f.descripcion || ""
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                }
                Kirigami.Heading { level: 4; text: "Formatos"; visible: (raiz.f.formatos || []).length > 0 }
                Repeater {
                    model: raiz.f.formatos || []
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        QQC2.Label { text: modelData.formato; font.weight: Font.DemiBold }
                        QQC2.Label { text: modelData.nombre; elide: Text.ElideMiddle; Layout.fillWidth: true; color: Kirigami.Theme.disabledTextColor }
                        QQC2.Label { text: modelData.tamano; color: Kirigami.Theme.disabledTextColor }
                    }
                }
                Kirigami.Heading { level: 4; text: "Fichas canónicas"; visible: (raiz.f.fichas || []).length > 0 }
                Repeater {
                    model: raiz.f.fichas || []
                    delegate: QQC2.ItemDelegate {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.nombre + " · " + modelData.verificacion
                        icon.name: modelData.verificacion.startsWith("verificada") ? "document-edit-verify" : "document-edit"
                        onClicked: raiz.l.abrirFicha(modelData.ruta)
                    }
                }
                Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
            }
        }
    }

    DialogoFicha { id: dialogoFicha; objectName: "dialogoFicha" }
    DialogoObraYachay { id: dialogoObraYachay; objectName: "dialogoObraYachay" }
    DialogoEstudioObra { id: dialogoEstudio; objectName: "dialogoEstudio"; dialogoFicha: dialogoFicha }
}
