// Operacion — la operación elegida de la vista: qué hace, en qué base escribe, la orden exacta (simular y aplicar), lo
// que pide (texto, carpeta o archivo) y el estado de la puerta; Simular (F5) y Aplicar (Ctrl+Intro) al pie.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

QQC2.ScrollView {
    id: pagina
    readonly property var o: studio.operaciones
    contentWidth: availableWidth
    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
    ColumnLayout {
        width: pagina.availableWidth - Kirigami.Units.largeSpacing * 2
        x: Kirigami.Units.largeSpacing
        y: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: !pagina.o.hayOperacion
            text: "Esta vista no tiene operaciones"
            icon.name: "system-run"
        }
        Kirigami.FormLayout {
            Layout.fillWidth: true
            visible: pagina.o.hayOperacion
            Kirigami.Heading { Kirigami.FormData.label: "Operación:"; level: 4; text: pagina.o.titulo; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            QQC2.Label { Kirigami.FormData.label: "Etapa:"; text: pagina.o.etapaTexto; color: Kirigami.Theme.disabledTextColor }
            QQC2.Label { Kirigami.FormData.label: "Qué hace:"; text: pagina.o.descripcion; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            QQC2.Label { Kirigami.FormData.label: "Escribe:"; text: pagina.o.basesTexto; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: pagina.o.escribe ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.positiveTextColor }
            Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "Lo que pide"; visible: pagina.o.entradaTipo !== "" }
            QQC2.TextField {
                id: campoTexto
                Kirigami.FormData.label: pagina.o.entradaEtiqueta + ":"
                visible: pagina.o.entradaTipo === "texto"
                Layout.fillWidth: true
                text: pagina.o.valor
                placeholderText: pagina.o.entradaEtiqueta
                onEditingFinished: pagina.o.fijarValor(text)
                Accessible.name: pagina.o.entradaEtiqueta
                Connections { target: pagina.o; function onCambiado() { if (!campoTexto.activeFocus) campoTexto.text = pagina.o.valor } }
            }
            CampoRuta {
                id: campoRuta
                Kirigami.FormData.label: pagina.o.entradaEtiqueta + ":"
                visible: pagina.o.entradaTipo === "carpeta" || pagina.o.entradaTipo === "archivo"
                Layout.fillWidth: true
                carpeta: pagina.o.entradaTipo === "carpeta"
                texto: pagina.o.valor
                titulo: pagina.o.entradaEtiqueta
                nombreAccesible: pagina.o.entradaEtiqueta
                onAceptada: t => pagina.o.fijarValor(t)
                Connections { target: pagina.o; function onCambiado() { if (!campoRuta.campoTexto.activeFocus) campoRuta.texto = pagina.o.valor } }
            }
            Kirigami.Separator { Kirigami.FormData.isSection: true; Kirigami.FormData.label: "La orden" }
            QQC2.Label { Kirigami.FormData.label: pagina.o.verbo + " (F5):"; text: pagina.o.ordenSimular; font: Kirigami.Theme.fixedWidthFont; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
            QQC2.Label { Kirigami.FormData.label: "Aplicar (Ctrl+Intro):"; visible: pagina.o.escribe; text: pagina.o.ordenAplicar; font: Kirigami.Theme.fixedWidthFont; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
            QQC2.Label { Kirigami.FormData.label: "Puerta:"; visible: pagina.o.escribe && pagina.o.bases !== ""; text: studio.puerta.estadoDe(pagina.o.bases); wrapMode: Text.WordWrap; Layout.fillWidth: true; color: pagina.o.puedeAplicar ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
            QQC2.Label { Kirigami.FormData.label: "Ahora:"; visible: pagina.o.escribe && !pagina.o.puedeAplicar; text: pagina.o.motivoNoAplicar; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Kirigami.Theme.neutralTextColor }
            QQC2.Label { Kirigami.FormData.label: "Ahora:"; visible: !pagina.o.escribe && !pagina.o.puedeSimular; text: pagina.o.motivoNoSimular; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: Kirigami.Theme.neutralTextColor }
        }
        RowLayout {
            visible: pagina.o.hayOperacion
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            Item { Layout.fillWidth: true }
            BotonAccion { accion: studio.acciones.accion("op.cancelar"); conTexto: false; visible: pagina.o.enCurso }
            BotonAccion { accion: studio.acciones.accion("op.simular") }
            QQC2.Button {
                readonly property var a: studio.acciones.accion("op.aplicar")
                visible: pagina.o.escribe
                highlighted: true
                text: a.textoPlano; icon.name: a.icono; enabled: a.habilitada
                onClicked: a.disparar()
                QQC2.ToolTip.text: a.descripcion + " (" + a.atajoTexto + ")"; QQC2.ToolTip.visible: hovered
            }
        }
        Item { Layout.preferredHeight: Kirigami.Units.largeSpacing }
    }
}
