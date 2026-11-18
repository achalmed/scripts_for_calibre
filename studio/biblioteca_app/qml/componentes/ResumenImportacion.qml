// ResumenImportacion — el plan de «Fusionar e importar a Zotero» (decisiones §2.15), leído del informe que la CLI deja al
// simular (`studio.operaciones.informe`, el de la operación elegida): tres cifras (nuevas, ya estaban, dudosas), de qué archivos y en qué colección, y
// las obras de cada grupo con su título y, en una línea tenue, su fuente o su porqué. Las dudosas van primero: no se crean.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: raiz
    property var informe: studio.operaciones.informe
    property int filas: 8
    readonly property var c: informe && informe.cuentas ? informe.cuentas : ({})
    visible: informe && informe.cuentas !== undefined
    spacing: Kirigami.Units.smallSpacing

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.largeSpacing * 2
        Cifra { valor: String(raiz.c.nuevo || 0); rotulo: "Nuevas" }
        Cifra { valor: String(raiz.c.ya || 0); rotulo: "Ya estaban" }
        Cifra { valor: String(raiz.c.dudoso || 0); rotulo: "Dudosas" }
        Item { Layout.fillWidth: true }
    }
    QQC2.Label {
        Layout.fillWidth: true
        text: raiz.visible ? ((raiz.informe.aplicado ? "Aplicado " : "Simulado ") + raiz.informe.fecha + " · " + raiz.informe.archivos.join(", ")
                              + " · «" + raiz.informe.coleccion + "»" + (raiz.c.repetidos ? " · " + raiz.c.repetidos + " repetidos, fundidos" : "")) : ""
        font: Kirigami.Theme.smallFont
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }

    Repeater {
        model: [{ clave: "dudoso", titulo: "Dudosas: no se crean" }, { clave: "nuevo", titulo: "Nuevas" }, { clave: "ya", titulo: "Ya estaban: no se tocan" }]
        delegate: ColumnLayout {
            id: grupo
            required property var modelData
            readonly property var g: raiz.visible ? raiz.informe[modelData.clave] : null
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            visible: !!g && g.total > 0
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label { text: grupo.modelData.titulo + " · " + (grupo.g ? grupo.g.total : 0); font.weight: Font.DemiBold }
            Repeater {
                model: grupo.g ? grupo.g.obras.slice(0, raiz.filas) : []
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label { Layout.fillWidth: true; text: modelData.titulo; elide: Text.ElideRight }
                    QQC2.Label { Layout.fillWidth: true; text: modelData.linea; font: Kirigami.Theme.smallFont; color: Kirigami.Theme.disabledTextColor; elide: Text.ElideRight }
                }
            }
            QQC2.Label {
                visible: !!grupo.g && grupo.g.total > raiz.filas
                text: grupo.g ? (grupo.g.total - raiz.filas) + " más en la pestaña Plan" : ""
                font: Kirigami.Theme.smallFont
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
}
