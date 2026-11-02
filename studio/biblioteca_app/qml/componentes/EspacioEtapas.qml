// EspacioEtapas — el Método Documental (Adquirir → Entrada → Catalogar → Fichas → Manifiestos) o la Coherencia
// (Sincronizar, Puerta, Tareas automáticas) (reingeniería B10): las etapas como recorrido con su contador; la tabla de
// lo que maneja la etapa (los ledgers sí son tablas); a la derecha, el elemento elegido, la operación con los pasos de
// la puerta, el plan, el registro y la salida de la CLI.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

ColumnLayout {
    id: raiz
    required property var filas                  // etapas.filasMetodo o etapas.filasCoherencia
    property bool recorrido: true                 // con flechas entre etapas (el Método es un camino)
    readonly property var etapas: studio.etapas
    readonly property var ops: studio.operaciones
    readonly property string vista: studio.espacio.vista
    property alias pestana: lado.currentIndex
    spacing: 0

    function tabla() { return tablas.children[tablas.currentIndex] }

    // el recorrido de etapas
    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: raiz.filas
            delegate: RowLayout {
                required property var modelData
                required property int index
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Icon { visible: raiz.recorrido && index > 0; source: "go-next-symbolic"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth; opacity: 0.6 }
                QQC2.Button {
                    text: modelData.texto + (modelData.contador !== "" && modelData.contador !== undefined ? "  " + modelData.contador : "")
                    icon.name: modelData.icono
                    checkable: true
                    checked: raiz.vista === modelData.nombre
                    flat: !checked
                    onClicked: studio.espacio.fijarVista(modelData.nombre)
                }
            }
        }
        QQC2.Label {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.largeSpacing
            text: studio.espacio.paraQue
            horizontalAlignment: Text.AlignRight
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
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
                Operacion {}
                Plan {}
                Registro {}
                PanelInferior { consola: studio.consola }
            }
        }
    }
}
