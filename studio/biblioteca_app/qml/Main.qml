// Main.qml — Biblioteca Studio (reingeniería del 2026-11-02, docs/reingenieria.md; rediseño del 2026-11-18, decisiones
// §9.9): un gestor bibliográfico sobre la biblioteca de Calibre, en GuiComun.VentanaBase. Arriba, sin el nombre del studio
// (la regla de la familia, gui-comun: el título lo pone KWin), las áreas como chips (Inicio · Catálogo · Lectura · Fichas ·
// Método · Coherencia, Ctrl+1–6), la búsqueda y el punto de la puerta de escritura. Bandejas (Ctrl+7) no es chip: se llega
// desde Inicio, el menú Ver y la paleta. En el centro, el área: lo de hoy; el catálogo con portadas, filtros y la ficha
// editorial; la base de lectura; las fichas y su repaso; las etapas con su tabla, su operación y los seis pasos de la
// puerta; o las bandejas de trabajo. Abajo, la barra de estado. Ninguna llamada al disco ni a una suite aquí: todo lo
// hacen los controladores de Python (studio.*); la ventana no escribe en ninguna base.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun
import "componentes"

VentanaBase {
    id: ventana

    readonly property var espacio: studio.espacio
    readonly property var registro: studio.acciones
    readonly property var libros: studio.libros
    readonly property var etapas: studio.etapas
    readonly property var ops: studio.operaciones
    readonly property var puerta: studio.puerta
    readonly property string area: espacio.area
    readonly property bool enLibros: area === "catalogo" || area === "bandejas"
    readonly property bool buscaLibros: enLibros || area === "inicio" || area === "lectura"     // la búsqueda lleva al catálogo

    title: (area === "catalogo" && libros.hayActual ? libros.titulo : (area === "metodo" || area === "coherencia" ? espacio.textoVista : espacio.textoArea)) + " — Biblioteca Studio"
    acciones: registro
    tareas: studio.tareas
    consola: studio.consola
    descripcion: descripcionStudio
    autor: "Edison Achalma (@achalmed)"
    claveAjustes: "ventana-3"
    width: 1440
    height: 900

    function accion(nombre) { return registro.accion(nombre) }
    function espacioActual() { return area === "metodo" ? metodo : (area === "coherencia" ? coherencia : null) }
    function textoBusqueda() { return ventana.enLibros ? libros.busqueda : (area === "fichas" ? studio.fichas.busqueda : "") }

    // ------------------------------------------------------------------ lo que Python pide a la interfaz
    Connections {
        target: studio.interfaz
        function onPedir(nombre, datos) {
            switch (nombre) {
            case "buscar": busqueda.forceActiveFocus(); busqueda.selectAll(); break
            case "filtros": espacio.fijarArea("catalogo"); catalogo.mostrarFiltros = !catalogo.mostrarFiltros; break
            case "seleccionar_todo": { const e = espacioActual(); const t = e ? e.tabla() : null; if (t && t.seleccionarTodo) t.seleccionarTodo(); break }
            case "seleccionar_fila": { const e = espacioActual(); const t = e ? e.tabla() : null; if (t && datos.fila >= 0) t.seleccionarFila(datos.fila, true); break }
            case "aplicar": dialogoAplicar.abrir(); break
            case "pestana": { const e = espacioActual(); if (e) e.pestana = datos.indice; break }
            case "paleta": ventana.paleta.abrir(datos.texto || ""); break
            case "aviso": ventana.mensajes.mostrar(datos.texto, datos.tipo || "informacion"); break
            }
        }
    }
    Connections { target: espacio; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onAreaCambiada() { busqueda.text = ventana.textoBusqueda() } }
    Connections { target: libros; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onFiltroCambiado() { if (ventana.enLibros && !busqueda.activeFocus) busqueda.text = libros.busqueda } }
    Connections { target: etapas; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections { target: studio.lectura; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections { target: studio.fichas; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections {
        target: ops
        function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) }
        function onTerminada(id, aplicar, codigo) { const e = espacioActual(); if (e) e.pestana = aplicar ? 1 : 2 }
    }

    // ------------------------------------------------------------------ la cabecera: áreas, búsqueda y puerta
    // la barra de arriba (decisiones §9.2 y §9.9): ligera, como la de Datafw Studio y LaTeX Studio. Las seis áreas
    // como chips (la elegida, rellena), la búsqueda, el estado de la puerta como un punto y una línea, y lo de siempre en ⋮ y Ctrl+K
    header: ColumnLayout {
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.smallSpacing
            Layout.leftMargin: Kirigami.Units.largeSpacing
            Layout.rightMargin: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            Repeater {
                model: espacio.areas.length
                delegate: Chip {
                    required property int index
                    readonly property var a: espacio.areas[index]
                    visible: a.chip
                    text: a.texto
                    icono: a.icono
                    destacado: espacio.indiceArea === index
                    ayuda: a.atajo
                    onClicked: espacio.fijarAreaPorIndice(index)
                }
            }
            Item { Layout.fillWidth: true }
            Kirigami.SearchField {
                id: busqueda
                Layout.preferredWidth: Kirigami.Units.gridUnit * 20
                placeholderText: ventana.buscaLibros ? "Título, autor, año:, serie:, etiqueta:, id:, clave: (Ctrl+F)"
                                                     : (ventana.area === "fichas" ? "Buscar en las fichas (Ctrl+F)" : "Filtrar la tabla (Ctrl+F)")
                Accessible.name: "Buscar"
                onTextChanged: espera.restart()
                Keys.onEscapePressed: text = ""
                Timer {
                    id: espera
                    interval: 250
                    onTriggered: {
                        if (ventana.area === "fichas") studio.fichas.buscar(busqueda.text)
                        else if (ventana.buscaLibros) { if (busqueda.text !== libros.busqueda) { espacio.fijarArea("catalogo"); libros.buscar(busqueda.text) } }
                        else { const e = ventana.espacioActual(); const t = e ? e.tabla() : null; if (t && t.modelo && t.modelo.filtrar) t.modelo.filtrar(busqueda.text) }
                    }
                }
            }
            // la puerta: Calibre y Zotero abiertos o cerrados, el candado (un clic lleva a su etapa)
            QQC2.AbstractButton {
                id: chipPuerta
                readonly property bool libre: !puerta.calibreAbierto && !puerta.candadoCalibre
                hoverEnabled: true
                padding: Kirigami.Units.smallSpacing
                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Rectangle { implicitWidth: Kirigami.Units.smallSpacing * 2; implicitHeight: implicitWidth; radius: width / 2
                                color: chipPuerta.libre ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
                    QQC2.Label { text: puerta.calibreAbierto ? "Calibre abierto" : (puerta.candadoCalibre ? "Candado ocupado" : "Puerta lista")
                                 font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor }
                }
                onClicked: { espacio.fijarVista("puerta"); espacio.fijarArea("coherencia") }
                QQC2.ToolTip.text: puerta.contexto + (chipPuerta.libre ? "" : "\nAplicar espera a que Calibre se cierre y el candado quede libre.")
                QQC2.ToolTip.visible: hovered
                Accessible.name: "Puerta de escritura: " + puerta.contexto
            }
            BotonAccion { accion: ventana.accion("ver.indice"); conTexto: false; flat: true }
            BotonAccion { accion: ventana.accion("ventana.paleta"); conTexto: false; flat: true }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.alpha(Kirigami.Theme.textColor, 0.1) }
    }

    // ------------------------------------------------------------------ las áreas
    StackLayout {
        anchors.fill: parent
        currentIndex: espacio.indiceArea           // el orden de espacio.AREAS
        Inicio { id: inicio }
        Catalogo { id: catalogo }
        Lectura { id: lectura }
        Fichas { id: fichas }
        EspacioEtapas { id: metodo; filas: etapas.filasMetodo }
        EspacioEtapas { id: coherencia; filas: etapas.filasCoherencia; recorrido: false; tarjetas: true }
        Bandejas { id: bandejas }
    }

    footer: BarraEstado {
        resumen: espacio.resumen
        contexto: espacio.contexto
        tareas: studio.tareas
        onProgresoPulsado: { const e = ventana.espacioActual(); if (e) e.pestana = 4 }
    }

    // ------------------------------------------------------------------ Aplicar: la orden, las bases y los pasos de la puerta
    Kirigami.Dialog {
        id: dialogoAplicar
        title: "Aplicar: " + ops.titulo
        standardButtons: Kirigami.Dialog.Cancel
        preferredWidth: Kirigami.Units.gridUnit * 34
        padding: Kirigami.Units.largeSpacing * 2
        customFooterActions: [Kirigami.Action { text: "Aplicar"; icon.name: "dialog-ok-apply"; enabled: ops.puedeAplicar; onTriggered: { ops.aplicar(); dialogoAplicar.close() } }]
        function abrir() {
            if (!ops.puedeAplicar) { ventana.mensajes.mostrar(ops.motivoNoAplicar, "aviso"); return }
            open()
        }
        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            QQC2.Label { Layout.fillWidth: true; Layout.maximumWidth: Kirigami.Units.gridUnit * 30; text: ops.textoConfirmacion; wrapMode: Text.WordWrap }
            LineaPasos { Layout.fillWidth: true; Layout.maximumWidth: Kirigami.Units.gridUnit * 30; pasos: studio.operaciones.pasos; titulo: "La puerta de escritura"; resumen: studio.operaciones.resumenPasos }
        }
    }
    dialogoAjustes: DialogoAjustesStudio {}
}
