// Main.qml — Biblioteca Studio: la biblioteca, el Método Documental y la coherencia Calibre ⇄ KOReader ⇄ Zotero en un
// espacio de trabajo al estilo Dolphin/Kate sobre GuiComun.VentanaStudio. Navegación (Biblioteca · Método Documental ·
// Coherencia) · centro (la tabla de lo que cada vista maneja) · detalles (el libro: Resumen y Fichas; el elemento; la
// operación actual con su Plan y su Registro) · panel inferior (la salida de la CLI; Registro) · barra de estado.
// Ninguna llamada al disco ni a una suite aquí: todo lo hacen los controladores de Python (studio.*).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun
import "componentes"

VentanaStudio {
    id: ventana

    readonly property var espacio: studio.espacio
    readonly property var registro: studio.acciones
    readonly property var libros: studio.libros
    readonly property var etapas: studio.etapas
    readonly property var ops: studio.operaciones
    readonly property string vista: espacio.vista
    readonly property int indice: espacio.indiceVista
    readonly property bool enLibros: vista === "libros"
    readonly property bool elementoDeAqui: etapas.hayElemento && etapas.vistaElemento === vista

    title: espacio.textoVista + " — Biblioteca Studio"
    acciones: registro
    tareas: studio.tareas
    consola: studio.consola
    descripcion: descripcionStudio
    autor: "Edison Achalma (@achalmed)"
    resumen: espacio.resumen
    contexto: espacio.contexto
    claveAjustes: "ventana"
    abrirInferiorAlEmpezarTarea: studio.ajustes.abrirInferior

    function accion(nombre) { return registro.accion(nombre) }
    function tablaActual() { return centro.children[ventana.indice] }
    function irAPestana(i) { ventana.mostrarDetalles = true; detalles.pestanaActual = i }
    function pestanaInicial() {
        if (ventana.enLibros) return 0
        if (ventana.vista === "puerta") return 2
        return ventana.elementoDeAqui ? 2 : 3
    }
    function religarNavegacion() {
        navegacion.actual = Qt.binding(() => ventana.enLibros ? (libros.filtro === "todos" ? "libros" : "libros." + libros.filtro) : ventana.vista)
    }

    // ------------------------------------------------------------------ lo que Python pide a la interfaz
    Connections {
        target: studio.interfaz
        function onPedir(nombre, datos) {
            switch (nombre) {
            case "filtrar": filtro.forceActiveFocus(); filtro.selectAll(); break
            case "seleccionar_todo": { const t = tablaActual(); if (t && t.seleccionarTodo) t.seleccionarTodo(); break }
            case "seleccionar_fila": { const t = tablaActual(); if (t && datos.fila >= 0) t.seleccionarFila(datos.fila, true); break }
            case "aplicar": dialogoAplicar.abrir(); break
            case "pestana": irAPestana(datos.indice); break
            case "paleta": ventana.paleta.abrir(datos.texto || ""); break
            }
        }
    }
    Connections { target: espacio; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections { target: libros; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onSeleccionar(fila) { if (fila >= 0) tablaLibros.seleccionarFila(fila, true); irAPestana(0) } }
    Connections { target: etapas; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } }
    Connections { target: ops; function onAviso(texto, tipo) { ventana.mensajes.mostrar(texto, tipo) } function onTerminada(id, aplicar, codigo) { irAPestana(aplicar ? 5 : 4) } }
    Connections { target: espacio; function onVistaCambiada() { filtro.text = ""; religarNavegacion(); irAPestana(pestanaInicial()) } }
    Connections { target: libros; function onFiltroCambiado() { religarNavegacion() } }

    // ------------------------------------------------------------------ barra: la operación de la vista y el filtro
    herramientasExtra: [
        QQC2.ComboBox {
            id: selectorOperacion
            visible: ops.lista.length > 0
            Layout.preferredWidth: Kirigami.Units.gridUnit * 18
            model: ops.lista
            textRole: "titulo"
            currentIndex: ops.indiceActual
            onActivated: index => ops.fijarPorIndice(index)
            Accessible.name: "Operación de la vista"
            QQC2.ToolTip.text: ops.descripcion
            QQC2.ToolTip.visible: hovered && ops.descripcion !== ""
            Connections { target: ops; function onListaCambiada() { selectorOperacion.currentIndex = ops.indiceActual } }
        },
        Kirigami.SearchField {
            id: filtro
            Layout.preferredWidth: Kirigami.Units.gridUnit * 11
            placeholderText: ventana.enLibros ? "Título, autor, clave o número (Ctrl+F)" : "Filtrar (Ctrl+F)"
            onTextChanged: { const t = tablaActual(); if (t && t.modelo && t.modelo.filtrar) t.modelo.filtrar(text) }
            Keys.onEscapePressed: { text = ""; const t = tablaActual(); if (t) t.forceActiveFocus() }
            Accessible.name: "Filtrar"
        }
    ]

    // ------------------------------------------------------------------ navegación
    navegacion: PanelNavegacion {
        id: navegacion
        secciones: [
            { titulo: "Biblioteca", filas: libros.filasNavegacion },
            { titulo: "Método Documental", filas: etapas.filasMetodo },
            { titulo: "Coherencia", filas: etapas.filasCoherencia }
        ]
        onElegida: nombre => {
            if (nombre.startsWith("libros")) { espacio.fijarVista("libros"); libros.fijarFiltro(nombre.length > 6 ? nombre.substring(7) : "todos") }
            else espacio.fijarVista(nombre)
            religarNavegacion()
        }
        Component.onCompleted: religarNavegacion()
    }

    // ------------------------------------------------------------------ centro: una tabla por vista
    centro: StackLayout {
        id: centro
        currentIndex: ventana.indice

        component MenuLibro: MenuAcciones {
            acciones: ventana.registro
            conAtajos: false
            elementos: [
                { tipo: "accion", nombre: "libro.calibre" }, { tipo: "accion", nombre: "libro.zotero" }, { tipo: "accion", nombre: "libro.archivo" }, { tipo: "accion", nombre: "libro.nota" },
                { tipo: "separador" },
                { tipo: "accion", nombre: "libro.copiar_clave" }, { tipo: "accion", nombre: "libro.fichas" },
                { tipo: "separador" },
                { tipo: "accion", nombre: "archivo.carpeta" }, { tipo: "accion", nombre: "archivo.copiar" }
            ]
        }
        component MenuElemento: MenuAcciones {
            acciones: ventana.registro
            conAtajos: false
            elementos: [
                { tipo: "accion", nombre: "archivo.abrir" }, { tipo: "accion", nombre: "archivo.carpeta" }, { tipo: "accion", nombre: "archivo.copiar" },
                { tipo: "separador" },
                { tipo: "accion", nombre: "op.simular" }, { tipo: "accion", nombre: "op.aplicar" },
                { tipo: "separador" },
                { tipo: "accion", nombre: "ver.releer" }
            ]
        }
        // una tabla de etapa: el modelo y la fila seleccionada van por el nombre de la vista
        component TablaEtapa: TablaDatos {
            required property string vista
            modelo: etapas.modeloDe(vista)
            claveAjustes: vista
            umbralEstrecho: Kirigami.Units.gridUnit * 36
            onOrdenar: (columna, descendente) => modelo.ordenar(columna, descendente)
            onFilaActualCambiada: fila => etapas.fijarFila(vista, fila)
            onActivada: fila => { etapas.fijarFila(vista, fila); etapas.abrirElemento() }
            menuContextual: MenuElemento {}
        }

        TablaDatos {                                              // 0 · Libros
            id: tablaLibros
            modelo: libros.modelo
            claveAjustes: "libros"
            umbralEstrecho: Kirigami.Units.gridUnit * 40
            mensajeVacio: !libros.hayIndice ? "No hay índice de libros: Actualizar el índice (Ctrl+R) lo genera leyendo Calibre y Zotero en solo lectura"
                                            : (libros.modelo.filas === 0 && filtro.text === "" ? "Ningún libro cumple el filtro «" + libros.textoFiltro + "»" : "Ningún libro coincide")
            iconoVacio: "folder-book"
            columnas: [
                { ancho: 0, minimo: 14, conIcono: true },
                { ancho: 11, secundaria: true },
                { ancho: 5, alinear: "derecha", mono: true },
                { ancho: 7, mono: true, secundaria: true, estrecho: true },
                { ancho: 11, mono: true, semantica: true, estrecho: true },
                { ancho: 4, alinear: "derecha", secundaria: true, estrecho: true },
                { ancho: 6, secundaria: true, estrecho: true }
            ]
            onOrdenar: (columna, descendente) => libros.modelo.ordenar(columna, descendente)
            onFilaActualCambiada: fila => libros.fijarFila(fila)
            onActivada: fila => { libros.fijarFila(fila); libros.abrirArchivo() }
            menuContextual: MenuLibro {}
        }
        TablaEtapa {                                              // 1 · Adquirir
            vista: "adquirir"
            mensajeVacio: "Ninguna descarga en fuentes_descargadas.tsv: «Descargar» (desde una fuente abierta) deja aquí su fila"
            iconoVacio: "download"
            columnas: [{ ancho: 9, secundaria: true }, { ancho: 7 }, { ancho: 12, mono: true }, { ancho: 0, minimo: 12 }, { ancho: 12, secundaria: true, estrecho: true }, { ancho: 7, semantica: true }]
        }
        TablaEtapa {                                              // 2 · Entrada
            vista: "entrada"
            mensajeVacio: "La zona de entrada está vacía y no hay filas pendientes: deja aquí lo que haya que ingerir (Archivo › Abrir la zona de entrada)"
            iconoVacio: "document-import"
            columnas: [{ ancho: 0, minimo: 14, conIcono: true }, { ancho: 7, semantica: true }, { ancho: 16, secundaria: true, estrecho: true }, { ancho: 6, secundaria: true, estrecho: true }, { ancho: 5, alinear: "derecha", mono: true }, { ancho: 14, secundaria: true, estrecho: true, visible: false }]
        }
        TablaEtapa {                                              // 3 · Catalogar
            vista: "catalogar"
            mensajeVacio: "No hay filas en catalogacion/resumen_catalogacion.tsv: las escribe «Catalogar en Calibre» (Entrada)"
            iconoVacio: "view-catalog"
            columnas: [{ ancho: 5, alinear: "derecha", mono: true }, { ancho: 12, secundaria: true, estrecho: true }, { ancho: 0, minimo: 14, conIcono: true }, { ancho: 7, secundaria: true, estrecho: true }, { ancho: 5, secundaria: true, estrecho: true }, { ancho: 6, secundaria: true, estrecho: true }, { ancho: 4, semantica: true }]
        }
        TablaEtapa {                                              // 4 · Fichas
            vista: "fichas"
            mensajeVacio: "No hay fichas canónicas en catalogacion/fichas/: las escribe «Catalogar en Calibre» al aplicar"
            iconoVacio: "document-edit-verify"
            columnas: [{ ancho: 16, mono: true, conIcono: true, estrecho: true }, { ancho: 5, alinear: "derecha", mono: true }, { ancho: 0, minimo: 14 }, { ancho: 7, secundaria: true, estrecho: true }, { ancho: 7, semantica: true }]
        }
        TablaEtapa {                                              // 5 · Manifiestos
            vista: "manifiestos"
            mensajeVacio: "Ningún fuentes.yml en las raíces vigiladas (la zona de entrada, los datos crudos de datafw y escritura): «Generar el de un proyecto» crea uno"
            iconoVacio: "view-list-text"
            columnas: [{ ancho: 0, minimo: 10, conIcono: true }, { ancho: 16, secundaria: true, estrecho: true }, { ancho: 5, alinear: "derecha" }, { ancho: 5, alinear: "derecha", semantica: true }, { ancho: 7, secundaria: true, estrecho: true }]
        }
        TablaEtapa {                                              // 6 · Sincronizar
            vista: "sincronizar"
            mensajeVacio: "Sin comprobaciones: hace falta el índice de libros (Ctrl+R)"
            iconoVacio: "folder-sync"
            columnas: [{ ancho: 0, minimo: 14, conIcono: true }, { ancho: 14, semantica: true }, { ancho: 14, secundaria: true, estrecho: true }]
        }
        TablaEtapa {                                              // 7 · Puerta
            vista: "puerta"
            mensajeVacio: "Sin respaldos todavía: cada escritura por la puerta deja aquí el suyo (con el SSD montado, en su carpeta de respaldos; si no, en el estado de usuario)"
            iconoVacio: "object-locked"
            columnas: [{ ancho: 0, minimo: 10, conIcono: true }, { ancho: 6, alinear: "derecha" }, { ancho: 9, secundaria: true }, { ancho: 18, secundaria: true, estrecho: true }]
        }
        TablaEtapa {                                              // 8 · Tareas automáticas
            vista: "tareas"
            mensajeVacio: "systemd no responde"
            iconoVacio: "chronometer"
            columnas: [{ ancho: 0, minimo: 12, conIcono: true }, { ancho: 7, secundaria: true }, { ancho: 9, secundaria: true, estrecho: true }, { ancho: 9, secundaria: true, estrecho: true }, { ancho: 14, semantica: true }]
        }
    }

    // ------------------------------------------------------------------ detalles: el libro, el elemento o la operación
    detalles: PanelDetalles {
        id: detalles
        anchoPreferido: Kirigami.Units.gridUnit * 26
        anchoMinimo: Kirigami.Units.gridUnit * 18
        titulo: ventana.enLibros ? (libros.hayActual ? libros.titulo : (libros.hayIndice ? "" : "Sin índice"))
                                 : (ventana.elementoDeAqui ? etapas.elementoTitulo : (ops.hayOperacion ? ops.titulo : espacio.textoVista))
        subtitulo: ventana.enLibros ? (libros.hayActual ? libros.autores + " · Calibre " + libros.id : "")
                                    : (ventana.elementoDeAqui ? etapas.elementoSubtitulo : espacio.paraQue)
        icono: ventana.enLibros ? "folder-book" : (ventana.elementoDeAqui ? "" : "")
        mensajeVacio: "Elige un libro en la tabla, búscalo con Ctrl+F o ábrelo desde Calibre, KOReader o Zotero"
        iconoVacio: "folder-book"
        accionesCabecera: ventana.enLibros ? [ventana.accion("libro.calibre"), ventana.accion("libro.zotero"), ventana.accion("libro.archivo")]
                                           : [ventana.accion("archivo.abrir"), ventana.accion("archivo.carpeta")]
        pestanas: [
            { titulo: "Resumen", visible: ventana.enLibros },
            { titulo: "Fichas", contador: libros.nFichas, visible: ventana.enLibros },
            { titulo: "Elemento", visible: !ventana.enLibros },
            { titulo: "Operación", visible: ops.lista.length > 0 },
            { titulo: "Plan", visible: ops.lista.length > 0 },
            { titulo: "Registro", visible: ops.lista.length > 0 && ops.escribe }
        ]
        ResumenLibro {}
        FichasLibro {}
        Elemento {}
        Operacion { id: paginaOperacion }
        Plan {}
        Registro {}
        Component.onCompleted: ventana.irAPestana(ventana.pestanaInicial())
    }

    // ------------------------------------------------------------------ panel inferior
    inferior: PanelInferior { consola: studio.consola }

    // ------------------------------------------------------------------ diálogos
    Kirigami.PromptDialog {
        id: dialogoAplicar
        title: "Aplicar: " + ops.titulo
        subtitle: ops.textoConfirmacion
        standardButtons: Kirigami.Dialog.Cancel
        customFooterActions: [Kirigami.Action { text: "Aplicar"; icon.name: "dialog-ok-apply"; enabled: ops.puedeAplicar; onTriggered: { ops.aplicar(); dialogoAplicar.close() } }]
        function abrir() {
            if (!ops.puedeAplicar) { ventana.mensajes.mostrar(ops.motivoNoAplicar, "aviso"); irAPestana(3); return }
            open()
        }
    }
    dialogoAjustes: DialogoAjustesStudio {}
}
