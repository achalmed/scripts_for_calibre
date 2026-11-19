// Revision — el área «Revisión» (Ctrl+7; FLUJO_DE_CONOCIMIENTO C2.1, C2.2 y C2.3, decisiones §9.10): la revisión de literatura
// de un escrito. A la izquierda, los escritos. En el centro, de arriba abajo: el tipo de revisión (chips) con lo que exige
// cada uno, la pregunta y los criterios; los requisitos que faltan; la bitácora de búsqueda (cada búsqueda con su base, su
// cadena exacta, sus filtros, su fecha y sus resultados, y una nueva); el cribado en dos fases por registro; y el diagrama
// PRISMA 2020 que sale de todo eso. Cada parte lleva su línea tenue «por qué · fuente». La acción rellena es «Generar el
// diagrama». Cada botón simula (cambia una copia que se pinta y suma un cambio sin aplicar); la barra de arriba muestra la
// diferencia y «Aplicar» lo escribe studio.revision en fuentes/revision.yml del escrito; Calibre y Zotero no se tocan.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Dialogs as Dialogos
import org.kde.kirigami as Kirigami

RowLayout {
    id: raiz
    readonly property var rv: studio.revision
    readonly property var d: rv.datos || ({})
    readonly property var r: d.revision || ({})
    readonly property var c: d.cuentas || ({})
    readonly property var pq: d.porque || ({})
    spacing: 0
    Accessible.name: "Revisión"

    component Tenue: QQC2.Label {
        Layout.fillWidth: true
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }
    component PorQue: Tenue {
        property var de: null
        visible: !!de
        text: de ? de.texto + " · " + de.fuente : ""
    }
    component Titulo: Kirigami.Heading { level: 4; Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.largeSpacing }

    // ------------------------------------------------------------------ los escritos
    ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 14
        Layout.maximumWidth: Kirigami.Units.gridUnit * 14
        Layout.fillHeight: true
        spacing: 0
        Kirigami.Heading { level: 4; text: "Escritos"; Layout.margins: Kirigami.Units.largeSpacing; Layout.bottomMargin: Kirigami.Units.smallSpacing }
        QQC2.ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: listaEscritos
                model: raiz.rv.escritos
                clip: true
                delegate: QQC2.ItemDelegate {
                    id: fila
                    required property var modelData
                    width: ListView.view.width
                    highlighted: raiz.rv.escrito === modelData.carpeta
                    onClicked: raiz.rv.elegir(modelData.carpeta)
                    Accessible.name: modelData.titulo
                    contentItem: ColumnLayout {
                        spacing: 0
                        QQC2.Label { Layout.fillWidth: true; text: fila.modelData.titulo; elide: Text.ElideRight
                                     color: fila.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor }
                        QQC2.Label { Layout.fillWidth: true; text: fila.modelData.proyecto; elide: Text.ElideMiddle; font: Kirigami.Theme.smallFont
                                     color: fila.highlighted ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor }
                    }
                }
            }
        }
    }
    Kirigami.Separator { Layout.fillHeight: true }

    // ------------------------------------------------------------------ la revisión del escrito
    QQC2.ScrollView {
        id: vista
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false
        background: Rectangle { color: Kirigami.Theme.backgroundColor }

        ColumnLayout {
            width: Math.min(vista.availableWidth - Kirigami.Units.gridUnit * 2, Kirigami.Units.gridUnit * 56)
            x: Kirigami.Units.gridUnit
            spacing: Kirigami.Units.smallSpacing

            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.gridUnit * 4
                visible: !raiz.rv.escrito
                icon.name: "view-list-details"
                text: "Elige un escrito"
                explanation: "La revisión de literatura vive en fuentes/revision.yml de cada escrito"
            }

            // ---------------------------------------------------------- 1. el tipo de revisión (C2.3)
            RowLayout {
                visible: !!raiz.rv.escrito
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 3; text: raiz.rv.tituloEscrito; Layout.fillWidth: true; elide: Text.ElideRight }
                    Tenue { text: raiz.d.existe ? "fuentes/revision.yml" : "Aún sin bitácora: declara el tipo para empezar" }
                }
                Chip {
                    text: "Generar el diagrama"
                    icono: "office-chart-area-focus-peak-node"
                    destacado: raiz.rv.pendientes === 0
                    enabled: !raiz.rv.ocupado && raiz.rv.pendientes === 0 && (raiz.r.busquedas || []).length > 0
                    ayuda: "PRISMA 2020 desde la bitácora: fuentes/prisma.pdf, listo para \\includegraphics"
                    onClicked: raiz.rv.generarPrisma()
                }
            }
            // los cambios simulados: nada está en fuentes/revision.yml hasta «Aplicar»
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: !!raiz.rv.escrito && raiz.rv.pendientes > 0
                type: Kirigami.MessageType.Information
                text: raiz.rv.resumenPendientes + ". Lo que ves es la simulación; «Aplicar» lo escribe."
                actions: [
                    Kirigami.Action { text: "Ver la diferencia"; icon.name: "vcs-diff"; onTriggered: dialogoDiferencia.open() },
                    Kirigami.Action { text: "Descartar"; icon.name: "edit-undo"; onTriggered: raiz.rv.descartar() },
                    Kirigami.Action { text: "Aplicar"; icon.name: "dialog-ok-apply"; onTriggered: raiz.rv.aplicar() }
                ]
            }
            Titulo { visible: !!raiz.rv.escrito; text: "Tipo de revisión" }
            Flow {
                visible: !!raiz.rv.escrito
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: raiz.rv.tipos
                    Chip {
                        required property var modelData
                        text: modelData.nombre
                        destacado: false
                        checkable: false
                        icono: raiz.r.tipo === modelData.clave ? "checkmark" : ""
                        ayuda: "Búsqueda " + modelData.busqueda + "; síntesis " + modelData.sintesis
                        onClicked: raiz.rv.declarar(modelData.clave, pregunta.text, inclusion.text, exclusion.text)
                    }
                }
            }
            Tenue {
                visible: !!(raiz.d.tipo && raiz.d.tipo.nombre)
                color: Kirigami.Theme.textColor
                text: raiz.d.tipo && raiz.d.tipo.nombre ? "Búsqueda " + raiz.d.tipo.busqueda + " · evaluación: " + raiz.d.tipo.evaluacion
                                                          + " · síntesis " + raiz.d.tipo.sintesis + " · análisis " + raiz.d.tipo.analisis
                                                          + (raiz.r.declarada ? " · declarada el " + raiz.r.declarada : "") : ""
            }
            PorQue { de: raiz.rv.escrito ? raiz.pq.tipo : null }
            GridLayout {
                visible: !!raiz.rv.escrito
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Kirigami.Units.largeSpacing
                QQC2.Label { text: "Pregunta" }
                QQC2.TextField { id: pregunta; Layout.fillWidth: true; text: raiz.r.pregunta || ""; placeholderText: "¿Qué pregunta responde la revisión?" }
                QQC2.Label { text: "Se incluye"; Layout.alignment: Qt.AlignTop }
                QQC2.TextArea { id: inclusion; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; placeholderText: "Un criterio por línea"
                                text: (raiz.r.criterios && raiz.r.criterios.inclusion || []).join("\n") }
                QQC2.Label { text: "Se excluye"; Layout.alignment: Qt.AlignTop }
                QQC2.TextArea { id: exclusion; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; placeholderText: "Un criterio por línea"
                                text: (raiz.r.criterios && raiz.r.criterios.exclusion || []).join("\n") }
                Item { width: 1 }
                Chip { text: "Guardar la pregunta y los criterios"; icono: "document-save"; enabled: !!raiz.r.tipo
                       ayuda: raiz.r.tipo ? "" : "Primero elige el tipo de revisión"
                       onClicked: raiz.rv.declarar(raiz.r.tipo, pregunta.text, inclusion.text, exclusion.text) }
            }

            // ---------------------------------------------------------- lo que exige el tipo
            Titulo { visible: (raiz.d.requisitos || []).length > 0; text: "Lo que exige" }
            Repeater {
                model: raiz.d.requisitos || []
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon {
                        source: modelData.cumple ? "checkmark" : (modelData.exigencia === "obligatorio" ? "data-warning" : "data-information")
                        color: modelData.cumple ? Kirigami.Theme.positiveTextColor
                             : (modelData.exigencia === "obligatorio" ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.disabledTextColor)
                        implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth
                        Layout.alignment: Qt.AlignTop
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        QQC2.Label { Layout.fillWidth: true; text: modelData.texto + (modelData.exigencia === "recomendado" ? " (recomendado)" : ""); wrapMode: Text.WordWrap }
                        Tenue { visible: !modelData.cumple && modelData.detalle !== ""; text: modelData.detalle }
                    }
                }
            }

            // ---------------------------------------------------------- 2. la bitácora de búsqueda (C2.1)
            Titulo { visible: !!raiz.r.tipo; text: "Bitácora de búsqueda" }
            PorQue { de: raiz.r.tipo ? raiz.pq.bitacora : null }
            Repeater {
                model: raiz.r.busquedas || []
                Tarjeta {
                    id: busqueda
                    required property var modelData
                    RowLayout {
                        Layout.fillWidth: true
                        QQC2.Label { text: busqueda.modelData.id + " · " + busqueda.modelData.base; font.weight: Font.DemiBold }
                        Tenue { text: busqueda.modelData.fecha + " · " + busqueda.modelData.resultados + (busqueda.modelData.resultados === 1 ? " resultado" : " resultados")
                                      + (busqueda.modelData.clase !== "base" ? " · " + (raiz.rv.clases.find(x => x.clave === busqueda.modelData.clase) || {}).texto : "") }
                        Chip { visible: busqueda.modelData.cadena !== ""; icono: "edit-copy"; ayuda: "Copiar la cadena exacta para repetir la búsqueda"
                               Accessible.name: "Copiar la cadena"; onClicked: raiz.rv.copiar(busqueda.modelData.cadena) }
                        Chip { text: "Importar registros…"; icono: "document-import"; ayuda: "La exportación de la base, en RIS o BibTeX"
                               onClicked: { elegirArchivo.busqueda = busqueda.modelData.id; elegirArchivo.open() } }
                        Chip { text: "Añadir registro"; icono: "list-add"; onClicked: { dialogoRegistro.busqueda = busqueda.modelData.id; dialogoRegistro.open() } }
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: busqueda.modelData.cadena !== ""
                        text: busqueda.modelData.cadena
                        font.family: Kirigami.Theme.fixedWidthFont.family
                        wrapMode: Text.WrapAnywhere
                    }
                    Tenue { text: busqueda.modelData.filtros ? "Filtros: " + busqueda.modelData.filtros : "Sin filtros declarados" }
                }
            }
            // una búsqueda nueva
            Tarjeta {
                visible: !!raiz.r.tipo
                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: Kirigami.Units.largeSpacing
                    QQC2.Label { text: "Base o sitio" }
                    QQC2.TextField { id: nbBase; Layout.fillWidth: true; placeholderText: "Scopus, SciELO, Repositorio del BCRP…" }
                    QQC2.Label { text: "Clase" }
                    QQC2.ComboBox { id: nbClase; model: raiz.rv.clases.map(x => x.texto); Layout.fillWidth: true }
                    QQC2.Label { text: "Cadena exacta" }
                    QQC2.TextField { id: nbCadena; Layout.columnSpan: 3; Layout.fillWidth: true; font.family: Kirigami.Theme.fixedWidthFont.family
                                     placeholderText: "tal cual la escribiste en la base" }
                    QQC2.Label { text: "Filtros" }
                    QQC2.TextField { id: nbFiltros; Layout.columnSpan: 3; Layout.fillWidth: true; placeholderText: "años, idioma, tipo de documento (o «ninguno»)" }
                    QQC2.Label { text: "Fecha" }
                    QQC2.TextField { id: nbFecha; Layout.fillWidth: true; placeholderText: "AAAA-MM-DD (hoy, si la dejas vacía)" }
                    QQC2.Label { text: "Resultados" }
                    QQC2.SpinBox { id: nbResultados; from: 0; to: 1000000; editable: true; Layout.fillWidth: true }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    Chip {
                        text: "Añadir a la bitácora"
                        icono: "list-add"
                        enabled: nbBase.text.trim() !== ""
                        onClicked: {
                            raiz.rv.anadirBusqueda({ base: nbBase.text, clase: raiz.rv.clases[Math.max(0, nbClase.currentIndex)].clave, cadena: nbCadena.text,
                                                     filtros: nbFiltros.text, fecha: nbFecha.text, resultados: nbResultados.value })
                            nbBase.text = ""; nbCadena.text = ""; nbFiltros.text = ""; nbFecha.text = ""; nbResultados.value = 0
                        }
                    }
                }
            }

            // ---------------------------------------------------------- 3. el cribado en dos fases
            Titulo { visible: (raiz.r.registros || []).length > 0; text: "Cribado" }
            PorQue { de: (raiz.r.registros || []).length > 0 ? raiz.pq.cribado : null }
            Flow {
                visible: (raiz.r.registros || []).length > 0
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: raiz.rv.fases
                    Chip {
                        required property var modelData
                        text: modelData.texto + " · " + modelData.n
                        icono: raiz.rv.fase === modelData.clave ? "checkmark" : ""
                        onClicked: raiz.rv.fijarFase(modelData.clave)
                    }
                }
            }
            Repeater {
                model: raiz.rv.registros
                Tarjeta {
                    id: reg
                    required property var modelData
                    QQC2.Label { Layout.fillWidth: true; text: reg.modelData.titulo; wrapMode: Text.WordWrap; font.weight: Font.Medium }
                    Tenue { text: reg.modelData.id + " · " + reg.modelData.detalle }
                    Tenue { visible: !!reg.modelData.resumen && raiz.rv.fase === "fase1"; text: reg.modelData.resumen || ""; maximumLineCount: 4; elide: Text.ElideRight }
                    RowLayout {
                        Layout.fillWidth: true
                        visible: raiz.rv.fase === "fase1" || raiz.rv.fase === "fase2"
                        Item { Layout.fillWidth: true }
                        Chip { visible: raiz.rv.fase === "fase2" && reg.modelData.recuperado !== true; text: "No se consiguió"; icono: "dialog-cancel"
                               ayuda: "No hubo forma de leer el texto completo"; onClicked: raiz.rv.cribar(reg.modelData.id, 2, "no_recuperado", "") }
                        Chip { text: "Excluir"; icono: "list-remove"
                               onClicked: { dialogoMotivo.rid = reg.modelData.id; dialogoMotivo.fase = raiz.rv.fase === "fase1" ? 1 : 2; dialogoMotivo.open() } }
                        Chip { text: "Incluir"; icono: "list-add"; onClicked: raiz.rv.cribar(reg.modelData.id, raiz.rv.fase === "fase1" ? 1 : 2, "incluir", "") }
                    }
                }
            }
            Tenue {
                visible: (raiz.r.registros || []).length > 0 && raiz.rv.registros.length === 0
                text: "Nada en esta fase."
            }

            // ---------------------------------------------------------- 4. el diagrama PRISMA 2020 (C2.2)
            Titulo { visible: (raiz.r.busquedas || []).length > 0; text: "Diagrama PRISMA 2020" }
            PorQue { de: (raiz.r.busquedas || []).length > 0 ? raiz.pq.prisma : null }
            Tenue {
                visible: !!raiz.c.bases
                color: Kirigami.Theme.textColor
                text: raiz.c.bases ? raiz.c.bases.identificados + " identificados · " + raiz.c.bases.duplicados + " duplicados · "
                                     + raiz.c.bases.cribados + " cribados · " + raiz.c.bases.excluidos_titulo + " excluidos por título y resumen · "
                                     + raiz.c.bases.evaluados + " evaluados · " + raiz.c.incluidos + " incluidos" : ""
            }
            Repeater {
                model: raiz.c.avisos || []
                Tenue { required property string modelData; color: Kirigami.Theme.neutralTextColor; text: modelData }
            }
            Tenue {
                visible: !!raiz.d.prisma && raiz.d.prisma.al_dia === false
                color: Kirigami.Theme.neutralTextColor
                text: "El diagrama es de otras cifras: genéralo de nuevo."
            }
            QQC2.BusyIndicator { visible: raiz.rv.ocupado; running: visible }
            Image {
                Layout.fillWidth: true
                Layout.preferredHeight: visible ? width * (implicitHeight / Math.max(1, implicitWidth)) : 0
                visible: raiz.rv.vistaPrevia !== ""
                source: raiz.rv.vistaPrevia ? "file://" + raiz.rv.vistaPrevia : ""
                fillMode: Image.PreserveAspectFit
                cache: false
                Accessible.name: "Diagrama PRISMA 2020"
            }
            RowLayout {
                visible: !!raiz.d.prisma && raiz.d.prisma.pdf !== ""
                Item { Layout.fillWidth: true }
                Chip { text: "Abrir el PDF"; icono: "document-open"; onClicked: Qt.openUrlExternally("file://" + raiz.d.prisma.pdf) }
                Chip { text: "Copiar para LaTeX"; icono: "edit-copy"; ayuda: "\\includegraphics[width=\\textwidth]{fuentes/prisma}"
                       onClicked: raiz.rv.copiar("\\includegraphics[width=\\textwidth]{fuentes/prisma}") }
            }
            Item { implicitHeight: Kirigami.Units.gridUnit * 2 }
        }
    }

    Kirigami.Dialog {
        id: dialogoDiferencia
        title: "Lo que «Aplicar» escribirá en fuentes/revision.yml"
        standardButtons: Kirigami.Dialog.Close
        preferredWidth: Kirigami.Units.gridUnit * 44
        preferredHeight: Kirigami.Units.gridUnit * 28
        customFooterActions: [Kirigami.Action { text: "Aplicar"; icon.name: "dialog-ok-apply"
                                                onTriggered: { raiz.rv.aplicar(); dialogoDiferencia.close() } }]
        QQC2.ScrollView {
            QQC2.TextArea {
                readOnly: true
                text: raiz.rv.diferencia
                font: Kirigami.Theme.fixedWidthFont
                wrapMode: TextEdit.NoWrap
                Accessible.name: "La diferencia de la revisión"
            }
        }
    }
    Dialogos.FileDialog {
        id: elegirArchivo
        property string busqueda: ""
        title: "La exportación de la base (RIS o BibTeX)"
        nameFilters: ["Exportaciones (*.ris *.bib *.txt)", "Todos (*)"]
        onAccepted: raiz.rv.importar(busqueda, selectedFile.toString())
    }
    Kirigami.PromptDialog {
        id: dialogoMotivo
        property string rid: ""
        property int fase: 1
        title: fase === 1 ? "Excluir por título y resumen" : "Excluir por texto completo"
        subtitle: fase === 1 ? "El motivo es opcional en esta fase." : "Toda exclusión por texto completo lleva su motivo (PRISMA 2020)."
        standardButtons: Kirigami.Dialog.Cancel
        onOpened: { motivo.text = ""; motivo.forceActiveFocus() }
        QQC2.TextField { id: motivo; placeholderText: "Otra población, otro periodo, sin datos propios…" }
        customFooterActions: [Kirigami.Action { text: "Excluir"; icon.name: "list-remove"
                                                enabled: dialogoMotivo.fase === 1 || motivo.text.trim() !== ""
                                                onTriggered: { raiz.rv.cribar(dialogoMotivo.rid, dialogoMotivo.fase, "excluir", motivo.text); dialogoMotivo.close() } }]
    }
    Kirigami.Dialog {
        id: dialogoRegistro
        property string busqueda: ""
        title: "Añadir un registro a " + busqueda
        standardButtons: Kirigami.Dialog.Cancel
        preferredWidth: Kirigami.Units.gridUnit * 30
        onOpened: { rTitulo.text = ""; rAutores.text = ""; rAnio.text = ""; rDoi.text = ""; rTitulo.forceActiveFocus() }
        customFooterActions: [Kirigami.Action { text: "Añadir"; icon.name: "list-add"; enabled: rTitulo.text.trim() !== ""
                                                onTriggered: { raiz.rv.anadirRegistro(dialogoRegistro.busqueda, { titulo: rTitulo.text, autores: rAutores.text,
                                                                                                              anio: rAnio.text, doi: rDoi.text }); dialogoRegistro.close() } }]
        GridLayout {
            columns: 2
            QQC2.Label { text: "Título" }
            QQC2.TextField { id: rTitulo; Layout.fillWidth: true }
            QQC2.Label { text: "Autores" }
            QQC2.TextField { id: rAutores; Layout.fillWidth: true; placeholderText: "Apellido, Nombre; Apellido, Nombre" }
            QQC2.Label { text: "Año" }
            QQC2.TextField { id: rAnio; Layout.fillWidth: true }
            QQC2.Label { text: "DOI" }
            QQC2.TextField { id: rDoi; Layout.fillWidth: true }
        }
    }
}
