// MapaLectura — el mapa de lo leído de un libro (2026-11-19, pedido del autor): los conceptos que la IA estructuró en
// las sesiones guiadas de Ñawinchay y sus relaciones, dibujados como un grafo (cada concepto un nodo, más grande cuanto
// más aparece; cada relación una flecha con su tipo); un clic en un nodo o en su píldora lo elige y muestra su tarjeta
// (definiciones, lugares, en cuántos otros libros aparece). Solo lee (`studio.lectura.mapa`); lo propuso la IA.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

ColumnLayout {
    id: raiz
    property var mapa: ({ conceptos: [], relaciones: [], etiquetas: [], sesiones: 0 })
    property string elegido: ""
    // el mismo grafo sirve para un libro y para toda la biblioteca (§9.19): sólo cambian los rótulos
    property string titulo: "Mapa de lo leído"
    property string resumen: ""
    property string vacio: "Aún no hay mapa: lo arman las sesiones guiadas de Ñawinchay cuyo prompt devolvió su bloque de conceptos y relaciones."
    readonly property var conceptos: mapa.conceptos || []
    readonly property var relaciones: mapa.relaciones || []
    readonly property bool hay: conceptos.length > 0
    readonly property var actual: conceptos.find(c => c.termino === elegido) || null
    readonly property var nombresTipo: ({ causa: "causa", contrasta: "contrasta con", ejemplifica: "ejemplifica", define: "define",
                                          parte_de: "es parte de", depende_de: "depende de", se_relaciona: "se relaciona con" })
    spacing: Kirigami.Units.smallSpacing
    onMapaChanged: { elegido = hay ? conceptos[0].termino : ""; lienzo.requestPaint() }
    onElegidoChanged: lienzo.requestPaint()

    Kirigami.Heading {
        type: Kirigami.Heading.Type.Primary
        level: 4
        Layout.topMargin: Kirigami.Units.largeSpacing
        text: raiz.titulo
    }
    QQC2.Label {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        text: !raiz.hay ? raiz.vacio : (raiz.resumen !== "" ? raiz.resumen
              : raiz.conceptos.length + " conceptos · " + raiz.relaciones.length + " relaciones · de " + raiz.mapa.sesiones
                + (raiz.mapa.sesiones === 1 ? " sesión guiada" : " sesiones guiadas") + " en Ñawinchay. Lo propuso la IA: cotéjelo con el texto.")
    }

    // el grafo
    Rectangle {
        visible: raiz.hay
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 18
        radius: Kirigami.Units.cornerRadius * 2
        readonly property bool oscuro: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.backgroundColor) === Kirigami.ColorUtils.Dark
        color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, oscuro ? 0.04 : 0.025)
        border.width: 1
        border.color: Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, oscuro ? 0.12 : 0.10)
        Canvas {
            id: lienzo
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            property var nodos: []
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            Connections { target: Kirigami.Theme; function onTextColorChanged() { lienzo.requestPaint() } }
            // en círculo; con uno solo, al centro
            function disponer() {
                const n = raiz.conceptos.length, cx = width / 2, cy = height / 2
                const r = Math.max(10, Math.min(width, height) / 2 - Kirigami.Units.gridUnit * 1.6)
                const maxVeces = Math.max(1, ...raiz.conceptos.map(c => c.veces || 1))
                return raiz.conceptos.map((c, i) => ({
                    termino: c.termino,
                    x: n === 1 ? cx : cx + r * Math.cos(-Math.PI / 2 + 2 * Math.PI * i / n),
                    y: n === 1 ? cy : cy + r * Math.sin(-Math.PI / 2 + 2 * Math.PI * i / n),
                    radio: Kirigami.Units.smallSpacing * (2 + 2 * (c.veces || 1) / maxVeces)
                }))
            }
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                if (!raiz.hay) return
                nodos = disponer()
                const por = {}
                for (const p of nodos) por[p.termino.toLowerCase()] = p
                const texto = Kirigami.Theme.textColor, tenue = Kirigami.Theme.disabledTextColor, acento = Kirigami.Theme.highlightColor
                ctx.font = (Kirigami.Theme.smallFont.pointSize * 1.33) + "px '" + Kirigami.Theme.defaultFont.family + "'"
                // las relaciones: flechas; las del elegido, del acento
                for (const rel of raiz.relaciones) {
                    const a = por[rel.de.toLowerCase()], b = por[rel.a.toLowerCase()]
                    if (!a || !b || a === b) continue
                    const delElegido = rel.de === raiz.elegido || rel.a === raiz.elegido
                    const ang = Math.atan2(b.y - a.y, b.x - a.x)
                    const x1 = a.x + Math.cos(ang) * a.radio, y1 = a.y + Math.sin(ang) * a.radio
                    const x2 = b.x - Math.cos(ang) * (b.radio + 3), y2 = b.y - Math.sin(ang) * (b.radio + 3)
                    ctx.strokeStyle = delElegido ? acento : tenue
                    ctx.fillStyle = ctx.strokeStyle
                    ctx.globalAlpha = delElegido ? 1 : 0.55
                    ctx.lineWidth = delElegido ? 2 : 1
                    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
                    ctx.beginPath(); ctx.moveTo(x2, y2)
                    ctx.lineTo(x2 - 8 * Math.cos(ang - 0.4), y2 - 8 * Math.sin(ang - 0.4))
                    ctx.lineTo(x2 - 8 * Math.cos(ang + 0.4), y2 - 8 * Math.sin(ang + 0.4))
                    ctx.closePath(); ctx.fill()
                    if (delElegido) {
                        ctx.globalAlpha = 1
                        ctx.fillStyle = texto
                        ctx.textAlign = "center"; ctx.textBaseline = "bottom"
                        ctx.fillText(raiz.nombresTipo[rel.tipo] || rel.tipo, (x1 + x2) / 2, (y1 + y2) / 2 - 3)
                    }
                }
                ctx.globalAlpha = 1
                // los conceptos
                for (const p of nodos) {
                    const elegido = p.termino === raiz.elegido
                    ctx.fillStyle = elegido ? acento : Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, acento, 0.35)
                    ctx.strokeStyle = acento
                    ctx.lineWidth = 1.5
                    ctx.beginPath(); ctx.arc(p.x, p.y, p.radio, 0, 2 * Math.PI); ctx.fill(); ctx.stroke()
                    ctx.fillStyle = texto
                    ctx.textAlign = p.x < width / 2 - 4 ? "right" : (p.x > width / 2 + 4 ? "left" : "center")
                    ctx.textBaseline = p.y < height / 2 ? "bottom" : "top"
                    const dx = ctx.textAlign === "right" ? -p.radio - 4 : ctx.textAlign === "left" ? p.radio + 4 : 0
                    const dy = ctx.textAlign === "center" ? (ctx.textBaseline === "bottom" ? -p.radio - 3 : p.radio + 3) : 0
                    ctx.font = (elegido ? "600 " : "") + (Kirigami.Theme.smallFont.pointSize * 1.33) + "px '" + Kirigami.Theme.defaultFont.family + "'"
                    ctx.fillText(p.termino, p.x + dx, p.y + dy)
                }
            }
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: lienzo.cerca(mouseX, mouseY) ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: mouse => { const p = lienzo.cerca(mouse.x, mouse.y); if (p) raiz.elegido = p.termino }
            }
            function cerca(x, y) {
                for (const p of nodos) if (Math.hypot(p.x - x, p.y - y) <= p.radio + Kirigami.Units.smallSpacing * 2) return p
                return null
            }
        }
    }

    // los conceptos como píldoras (y con el teclado)
    Flow {
        visible: raiz.hay
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: raiz.conceptos
            delegate: OpcionColor {
                required property var modelData
                text: modelData.termino + (modelData.veces > 1 ? "  " + modelData.veces : "")
                elegida: raiz.elegido === modelData.termino
                descripcion: modelData.otros > 0 ? "También en " + modelData.otros + (modelData.otros === 1 ? " libro más" : " libros más") : modelData.termino
                onClicked: raiz.elegido = modelData.termino
            }
        }
    }

    // la tarjeta del concepto elegido
    Rectangle {
        visible: raiz.actual !== null
        Layout.fillWidth: true
        implicitHeight: tarjeta.implicitHeight + Kirigami.Units.largeSpacing * 2
        radius: Kirigami.Units.cornerRadius * 2
        color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, Kirigami.Theme.highlightColor, 0.08)
        border.width: 1
        border.color: Kirigami.ColorUtils.tintWithAlpha(Kirigami.Theme.backgroundColor, Kirigami.Theme.highlightColor, 0.35)
        ColumnLayout {
            id: tarjeta
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            RowLayout {
                QQC2.Label { text: raiz.actual ? raiz.actual.termino : ""; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                EtiquetaNivel {
                    visible: raiz.actual !== null && raiz.actual.otros > 0
                    nivel: "activo"
                    text: raiz.actual ? "también en " + raiz.actual.otros + (raiz.actual.otros === 1 ? " libro más" : " libros más") : ""
                }
            }
            Repeater {
                model: raiz.actual ? raiz.actual.definiciones : []
                delegate: QQC2.Label { required property string modelData; Layout.fillWidth: true; wrapMode: Text.Wrap; text: modelData }
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: text !== ""
                wrapMode: Text.Wrap
                font: Kirigami.Theme.smallFont
                color: Kirigami.Theme.disabledTextColor
                text: raiz.actual && raiz.actual.lugares.length ? "Dónde: " + raiz.actual.lugares.join(" · ") : ""
            }
            Repeater {
                model: raiz.actual ? raiz.relaciones.filter(r => r.de === raiz.actual.termino || r.a === raiz.actual.termino) : []
                delegate: QQC2.Label {
                    required property var modelData
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    textFormat: Text.StyledText
                    text: "<b>" + modelData.de + "</b> " + (raiz.nombresTipo[modelData.tipo] || modelData.tipo) + " <b>" + modelData.a + "</b>"
                }
            }
        }
    }

    // los temas
    Flow {
        visible: (raiz.mapa.etiquetas || []).length > 0
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: raiz.mapa.etiquetas || []
            delegate: EtiquetaNivel { required property var modelData; nivel: "activo"; text: modelData[0] + (modelData[1] > 1 ? " · " + modelData[1] : "") }
        }
    }
}
