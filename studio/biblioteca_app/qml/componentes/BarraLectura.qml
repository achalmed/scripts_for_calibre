// BarraLectura — la barra fina del avance de lectura (decisiones §9.9), del color de la herramienta donde se lee (lo da
// Python: studio.lectura.colores, KOReader, Zotero, Okular o Yachay); sin color, el de acento. La usan las portadas del
// catálogo, la lista, la ficha del libro y «Seguir leyendo».
import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: raiz
    property real fraccion: 0
    property string tono: ""
    implicitWidth: Kirigami.Units.gridUnit * 4
    implicitHeight: Math.max(3, Math.round(Kirigami.Units.smallSpacing * 0.75))
    radius: height / 2
    color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
    Accessible.role: Accessible.ProgressBar
    Accessible.name: "Leído: " + Math.round(Math.max(0, fraccion) * 100) + " %"
    Rectangle {
        width: parent.width * Math.max(0, Math.min(1, raiz.fraccion))
        height: parent.height
        radius: parent.radius
        color: raiz.tono !== "" ? raiz.tono : Kirigami.Theme.highlightColor
    }
}
