// Main.qml — Biblioteca Studio (reingeniería del 2026-11-02, docs/reingenieria.md): un gestor bibliográfico sobre la
// biblioteca de Calibre, en GuiComun.VentanaBase. Arriba, las cuatro áreas (Catálogo · Bandejas · Método Documental ·
// Coherencia, Ctrl+1–4), la búsqueda y el estado de la puerta de escritura. En el centro, el área: el catálogo con
// portadas, filtros y la ficha editorial; las bandejas de trabajo; o las etapas con su tabla, su operación y los seis
// pasos de la puerta. Abajo, la barra de estado. Ninguna llamada al disco ni a una suite aquí: todo lo hacen los
// controladores de Python (studio.*); la ventana no escribe en ninguna base.
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

    title: (area === "catalogo" && libros.hayActual ? libros.titulo : (enLibros ? espacio.textoArea : espacio.textoVista)) + " — Biblioteca Studio"
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
    Connections { target: espacio; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onAreaCambiada() { busqueda.text = ventana.enLibros ? libros.busqueda : "" } }
    Connections { target: libros; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onFiltroCambiado() { if (ventana.enLibros && !busqueda.activeFocus) busqueda.text = libros.busqueda } }
    Connections { target: etapas; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections {
        target: ops
        function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) }
        function onTerminada(id, aplicar, codigo) { const e = espacioActual(); if (e) e.pestana = aplicar ? 1 : 2 }
    }

    // ------------------------------------------------------------------ la cabecera: áreas, búsqueda y puerta
    header: QQC2.ToolBar {
        position: QQC2.ToolBar.Header
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing
            QQC2.TabBar {
                id: areas
                currentIndex: espacio.indiceArea
                onCurrentIndexChanged: espacio.fijarAreaPorIndice(currentIndex)
                Repeater {
                    model: 4                       // fijas: el TabBar del estilo de KDE no admite crearse vacío
                    delegate: QQC2.TabButton {
                        required property int index
                        readonly property var a: espacio.areas[index]
                        text: a.texto + (a.nombre === "bandejas" ? "  " + (libros.contadores.sin_zotero + libros.contadores.sin_clave + libros.contadores.clasificar + libros.contadores.fichas) : "")
                        icon.name: a.icono
                        width: implicitWidth
                        QQC2.ToolTip.text: "Ctrl+" + (index + 1)
                        QQC2.ToolTip.visible: hovered
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Kirigami.SearchField {
                id: busqueda
                Layout.preferredWidth: Kirigami.Units.gridUnit * 22
                placeholderText: ventana.enLibros ? "Título, autor, año:, serie:, etiqueta:, id:, clave: (Ctrl+F)" : "Filtrar la tabla (Ctrl+F)"
                Accessible.name: "Buscar"
                onTextChanged: espera.restart()
                Keys.onEscapePressed: text = ""
                Timer {
                    id: espera
                    interval: 250
                    onTriggered: {
                        if (ventana.enLibros) { espacio.fijarArea("catalogo"); libros.buscar(busqueda.text) }
                        else { const e = ventana.espacioActual(); const t = e ? e.tabla() : null; if (t && t.modelo && t.modelo.filtrar) t.modelo.filtrar(busqueda.text) }
                    }
                }
            }
            // la puerta: Calibre y Zotero abiertos o cerrados, el candado
            QQC2.Control {
                id: chipPuerta
                readonly property bool libre: !puerta.calibreAbierto && !puerta.candadoCalibre
                padding: Kirigami.Units.smallSpacing
                leftPadding: Kirigami.Units.largeSpacing
                rightPadding: Kirigami.Units.largeSpacing
                background: Rectangle { radius: height / 2; color: chipPuerta.libre ? Kirigami.Theme.positiveBackgroundColor : Kirigami.Theme.neutralBackgroundColor }
                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon { source: chipPuerta.libre ? "object-unlocked" : "object-locked"; implicitWidth: Kirigami.Units.iconSizes.small; implicitHeight: implicitWidth }
                    QQC2.Label { text: puerta.calibreAbierto ? "Calibre abierto" : (puerta.candadoCalibre ? "Candado ocupado" : "Puerta lista"); font.weight: Font.DemiBold }
                }
                QQC2.ToolTip.text: puerta.contexto + (chipPuerta.libre ? "" : "\nAplicar espera a que Calibre se cierre y el candado quede libre.")
                QQC2.ToolTip.visible: zonaPuerta.hovered
                HoverHandler { id: zonaPuerta }
                TapHandler { onTapped: { espacio.fijarVista("puerta"); espacio.fijarArea("coherencia") } }
                Accessible.name: "Puerta de escritura: " + puerta.contexto
            }
            BotonAccion { accion: ventana.accion("ver.indice"); conTexto: false }
            BotonAccion { accion: ventana.accion("ventana.paleta"); conTexto: false }
        }
    }

    // ------------------------------------------------------------------ las áreas
    StackLayout {
        anchors.fill: parent
        currentIndex: espacio.indiceArea
        Catalogo { id: catalogo }
        Bandejas { id: bandejas }
        EspacioEtapas { id: metodo; filas: etapas.filasMetodo }
        EspacioEtapas { id: coherencia; filas: etapas.filasCoherencia; recorrido: false }
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
