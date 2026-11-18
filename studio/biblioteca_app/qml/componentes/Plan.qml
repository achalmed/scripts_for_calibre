// Plan — la salida íntegra de la última simulación (o ejecución) de la operación elegida, con su fecha y su orden; arriba,
// si la operación deja un informe (Fusionar e importar a Zotero, decisiones §2.15), su resumen: cuántas nuevas, cuántas ya
// estaban y cuántas dudosas, con cada obra.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import GuiComun

ColumnLayout {
    id: plan
    readonly property var o: studio.operaciones
    readonly property bool hayResumen: !!o.informe && o.informe.cuentas !== undefined   // no del `visible` del hijo: es circular
    spacing: 0
    QQC2.ScrollView {
        id: desplazar
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(resumen.implicitHeight + Kirigami.Units.largeSpacing * 2, plan.height * 0.55)
        visible: plan.hayResumen
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ResumenImportacion {
            id: resumen
            x: Kirigami.Units.largeSpacing
            y: Kirigami.Units.largeSpacing
            width: desplazar.availableWidth - Kirigami.Units.largeSpacing * 2
        }
    }
    Kirigami.Separator { Layout.fillWidth: true; visible: plan.hayResumen }
    VistaTexto {
        Layout.fillWidth: true
        Layout.fillHeight: true
        texto: o.plan
        definicion: "Bash"
        mensajeVacio: !o.hayOperacion ? "Esta vista no tiene operaciones" : "Sin plan todavía: " + o.verbo + " (F5) corre «" + o.titulo + "» sin escribir y deja aquí su salida"
        iconoVacio: "system-run"
        nombreAccesible: "Plan de " + o.titulo
    }
}
