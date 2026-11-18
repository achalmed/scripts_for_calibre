// EspacioEtapas — el Método Documental (Adquirir → Entrada → Catalogar → Fichas → Manifiestos) o la Coherencia
// (Sincronizar, Puerta, Tareas automáticas) (reingeniería B10; rediseño del 2026-11-18, decisiones §9.9). Arriba, en
// Coherencia, tres tarjetas (Calibre ⇄ Zotero, Calibre ⇄ KOReader y Tareas automáticas: un punto de estado, una línea tenue
// y su botón). Después, las etapas: en el Método, un recorrido de pasos numerados con su contador y la elegida resaltada;
// en la Coherencia, chips. Debajo, la descripción de la etapa, «Simular (F5)» y «Aplicar (Ctrl+Intro)» (la acción rellena de
// la vista) con la línea tenue «respaldo verificado · se puede deshacer» cuando la operación escribe en una base. Y lo de
// siempre: la tabla de lo que maneja la etapa y, a la derecha, el elemento elegido, la operación con los pasos de la
// puerta, el plan, el registro y la salida de la CLI.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

ColumnLayout {
    id: raiz
    required property var filas                  // etapas.filasMetodo o etapas.filasCoherencia
    property bool recorrido: true                 // un camino de pasos numerados (el Método); si no, chips (la Coherencia)
    property bool tarjetas: false                 // las tres tarjetas de arriba de Coherencia
    readonly property var etapas: studio.etapas
    readonly property var ops: studio.operaciones
    readonly property string vista: studio.espacio.vista
    property alias pestana: lado.currentIndex
    spacing: 0

    function tabla() { return tablas.children[tablas.currentIndex] }
    function accion(n) { return studio.acciones.accion(n) }

    // las tres tarjetas de Coherencia
    GridLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        Layout.bottomMargin: 0
        visible: raiz.tarjetas
        columns: width >= Kirigami.Units.gridUnit * 48 ? 3 : 1
        columnSpacing: Kirigami.Units.largeSpacing
        rowSpacing: Kirigami.Units.smallSpacing
        Repeater {
            model: raiz.tarjetas ? raiz.etapas.tarjetasCoherencia : []
            delegate: Tarjeta {
                id: tarjeta
                required property var modelData
                Layout.preferredWidth: 1
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Rectangle {
                        implicitWidth: Kirigami.Units.smallSpacing * 2; implicitHeight: implicitWidth; radius: width / 2
                        color: tarjeta.modelData.estado === "positivo" ? Kirigami.Theme.positiveTextColor
                             : (tarjeta.modelData.estado === "negativo" ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor)
                        Accessible.name: tarjeta.modelData.estado === "positivo" ? "en orden" : "requiere atención"
                    }
                    QQC2.Label { Layout.fillWidth: true; text: tarjeta.modelData.titulo; font.weight: Font.DemiBold; elide: Text.ElideRight }
                    Chip {
                        text: tarjeta.modelData.boton
                        ayuda: tarjeta.modelData.operacion !== "" ? "Elige la operación: se simula con F5 y se aplica con Ctrl+Intro" : "Ver la etapa"
                        onClicked: {
                            studio.espacio.fijarVista(tarjeta.modelData.vista)
                            if (tarjeta.modelData.operacion !== "") { studio.operaciones.fijar(tarjeta.modelData.operacion); lado.currentIndex = 1 }
                        }
                    }
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: tarjeta.modelData.linea
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.disabledTextColor
                    elide: Text.ElideRight
                }
            }
        }
    }

    // las etapas
    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: raiz.filas
            delegate: RowLayout {
                id: etapa
                required property var modelData
                required property int index
                readonly property bool elegida: raiz.vista === modelData.nombre
                readonly property string cuenta: modelData.contador !== "" && modelData.contador !== undefined ? String(modelData.contador) : ""
                Layout.fillWidth: raiz.recorrido && index > 0
                spacing: Kirigami.Units.smallSpacing
                Rectangle {                              // la línea que une un paso con el anterior
                    visible: raiz.recorrido && etapa.index > 0
                    Layout.fillWidth: true
                    Layout.minimumWidth: Kirigami.Units.gridUnit
                    implicitHeight: 1
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.2)
                }
                QQC2.AbstractButton {
                    id: boton
                    visible: raiz.recorrido
                    hoverEnabled: true
                    padding: Kirigami.Units.smallSpacing
                    onClicked: studio.espacio.fijarVista(etapa.modelData.nombre)
                    Accessible.name: etapa.modelData.texto + (etapa.cuenta !== "" ? ", " + etapa.cuenta : "")
                    contentItem: RowLayout {
                        spacing: Kirigami.Units.smallSpacing
                        Rectangle {
                            implicitWidth: Kirigami.Units.gridUnit * 1.5; implicitHeight: implicitWidth; radius: width / 2
                            color: etapa.elegida ? Kirigami.Theme.highlightColor : "transparent"
                            border.width: etapa.elegida ? 0 : 1
                            border.color: Qt.alpha(Kirigami.Theme.textColor, boton.hovered ? 0.5 : 0.25)
                            QQC2.Label {
                                anchors.centerIn: parent
                                text: etapa.index + 1
                                font: Kirigami.Theme.smallFont
                                color: etapa.elegida ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            }
                        }
                        ColumnLayout {
                            spacing: 0
                            QQC2.Label { text: etapa.modelData.texto; font.weight: etapa.elegida ? Font.DemiBold : Font.Normal }
                            QQC2.Label { text: etapa.cuenta !== "" ? etapa.cuenta : "—"; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                        }
                    }
                    background: Rectangle {
                        radius: Kirigami.Units.cornerRadius
                        color: boton.hovered && !etapa.elegida ? Qt.alpha(Kirigami.Theme.textColor, 0.06) : "transparent"
                    }
                }
                Chip {
                    visible: !raiz.recorrido
                    text: etapa.modelData.texto + (etapa.cuenta !== "" ? "  " + etapa.cuenta : "")
                    icono: etapa.modelData.icono
                    destacado: etapa.elegida
                    onClicked: studio.espacio.fijarVista(etapa.modelData.nombre)
                }
            }
        }
        Item { Layout.fillWidth: !raiz.recorrido }
    }

    // la etapa elegida: qué es, y simular o aplicar su operación
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.largeSpacing
        Layout.rightMargin: Kirigami.Units.largeSpacing
        Layout.bottomMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            QQC2.Label {
                Layout.fillWidth: true
                text: studio.espacio.paraQue
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: raiz.ops.hayOperacion
                text: raiz.ops.titulo + (raiz.ops.escribe && raiz.ops.bases !== "" ? " · respaldo verificado · se puede deshacer"
                                                                                   : (raiz.ops.escribe ? "" : " · solo lee"))
                font: Kirigami.Theme.smallFont
                color: Kirigami.Theme.disabledTextColor
                elide: Text.ElideRight
            }
        }
        BotonAccion { accion: raiz.accion("op.cancelar"); conTexto: false; visible: raiz.ops.enCurso }
        BotonAccion { accion: raiz.accion("op.simular"); visible: raiz.ops.hayOperacion }
        QQC2.Button {
            readonly property var a: raiz.accion("op.aplicar")
            visible: raiz.ops.hayOperacion && raiz.ops.escribe
            highlighted: true
            text: a.textoPlano; icon.name: a.icono; enabled: a.habilitada
            onClicked: a.disparar()
            QQC2.ToolTip.text: a.descripcion + " (" + a.atajoTexto + ")"; QQC2.ToolTip.visible: hovered
        }
    }
    Kirigami.Separator { Layout.fillWidth: true }

    QQC2.SplitView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        orientation: Qt.Horizontal

        StackLayout {
            id: tablas
            QQC2.SplitView.fillWidth: true
            QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 20
            currentIndex: Math.max(0, raiz.filas.findIndex(f => f.nombre === raiz.vista))

            Repeater {
                model: raiz.filas
                delegate: TablaDatos {
                    required property var modelData
                    readonly property string nombre: modelData.nombre
                    modelo: raiz.etapas.modeloDe(nombre)
                    claveAjustes: nombre
                    umbralEstrecho: Kirigami.Units.gridUnit * 36
                    mensajeVacio: ({
                        adquirir: "Ninguna descarga en fuentes_descargadas.tsv: «Descargar» (desde una fuente abierta) deja aquí su fila",
                        entrada: "La zona de entrada está vacía y no hay filas pendientes: deja aquí lo que haya que ingerir (Archivo › Abrir la zona de entrada)",
                        catalogar: "No hay filas en catalogacion/resumen_catalogacion.tsv: las escribe «Catalogar en Calibre» (Entrada)",
                        fichas: "No hay fichas canónicas en catalogacion/fichas/: las escribe «Catalogar en Calibre» al aplicar",
                        manifiestos: "Ningún fuentes.yml en las raíces vigiladas: «Generar el de un proyecto» crea uno",
                        sincronizar: "Sin comprobaciones: hace falta el índice de libros (Ctrl+R)",
                        puerta: "Sin respaldos todavía: cada escritura por la puerta deja aquí el suyo",
                        tareas: "systemd no responde"
                    })[nombre] || ""
                    iconoVacio: modelData.icono
                    columnas: ({
                        adquirir: [{ ancho: 9, secundaria: true }, { ancho: 7 }, { ancho: 12, mono: true }, { ancho: 0, minimo: 12 }, { ancho: 12, secundaria: true, estrecho: true }, { ancho: 7, semantica: true }],
                        entrada: [{ ancho: 0, minimo: 14, conIcono: true }, { ancho: 7, semantica: true }, { ancho: 16, secundaria: true, estrecho: true }, { ancho: 6, secundaria: true, estrecho: true }, { ancho: 5, alinear: "derecha", mono: true }, { ancho: 14, secundaria: true, estrecho: true, visible: false }],
                        catalogar: [{ ancho: 5, alinear: "derecha", mono: true }, { ancho: 12, secundaria: true, estrecho: true }, { ancho: 0, minimo: 14, conIcono: true }, { ancho: 7, secundaria: true, estrecho: true }, { ancho: 5, secundaria: true, estrecho: true }, { ancho: 6, secundaria: true, estrecho: true }, { ancho: 4, semantica: true }],
                        fichas: [{ ancho: 16, mono: true, conIcono: true, estrecho: true }, { ancho: 5, alinear: "derecha", mono: true }, { ancho: 0, minimo: 14 }, { ancho: 7, secundaria: true, estrecho: true }, { ancho: 7, semantica: true }],
                        manifiestos: [{ ancho: 0, minimo: 10, conIcono: true }, { ancho: 16, secundaria: true, estrecho: true }, { ancho: 5, alinear: "derecha" }, { ancho: 5, alinear: "derecha", semantica: true }, { ancho: 7, secundaria: true, estrecho: true }],
                        sincronizar: [{ ancho: 0, minimo: 14, conIcono: true }, { ancho: 14, semantica: true }, { ancho: 14, secundaria: true, estrecho: true }],
                        puerta: [{ ancho: 0, minimo: 10, conIcono: true }, { ancho: 6, alinear: "derecha" }, { ancho: 9, secundaria: true }, { ancho: 18, secundaria: true, estrecho: true }],
                        tareas: [{ ancho: 0, minimo: 12, conIcono: true }, { ancho: 7, secundaria: true }, { ancho: 9, secundaria: true, estrecho: true }, { ancho: 9, secundaria: true, estrecho: true }, { ancho: 14, semantica: true }]
                    })[nombre] || []
                    onOrdenar: (columna, descendente) => modelo.ordenar(columna, descendente)
                    onFilaActualCambiada: fila => { raiz.etapas.fijarFila(nombre, fila); if (fila >= 0 && lado.currentIndex > 1) lado.currentIndex = 0 }
                    onActivada: fila => { raiz.etapas.fijarFila(nombre, fila); raiz.etapas.abrirElemento() }
                }
            }
        }
        ColumnLayout {
            QQC2.SplitView.preferredWidth: Kirigami.Units.gridUnit * 28
            QQC2.SplitView.minimumWidth: Kirigami.Units.gridUnit * 18
            spacing: 0
            QQC2.TabBar {
                id: lado
                Layout.fillWidth: true
                currentIndex: 1
                QQC2.TabButton { text: "Elemento"; width: implicitWidth }
                QQC2.TabButton { text: "Operación"; width: implicitWidth }
                QQC2.TabButton { text: "Plan"; width: implicitWidth }
                QQC2.TabButton { text: "Registro"; width: implicitWidth }
                QQC2.TabButton { text: "Salida"; width: implicitWidth }
            }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: lado.currentIndex
                Elemento {}
                Operacion { conBotones: false }      // Simular y Aplicar, arriba (§9.9)
                Plan {}
                Registro {}
                PanelInferior { consola: studio.consola }
            }
        }
    }
}
