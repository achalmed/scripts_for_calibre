// DialogoAjustesStudio — «Configurar Biblioteca Studio…» (Ctrl+Mayús+,): General (la terminal y el panel inferior).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard
import GuiComun

DialogoAjustes {
    id: dialogo
    title: "Configurar Biblioteca Studio"
    readonly property var a: studio.ajustes
    modulos: [{ titulo: "General", icono: "configure", pagina: paginaGeneral }]
    onGuardado: { dialogo.a.guardar(); ventana.mensajes.mostrar("Preferencias guardadas.", "positivo") }

    Component {
        id: paginaGeneral
        ColumnLayout {
            function guardar() { dialogo.a.terminal = terminal.text; dialogo.a.abrirInferior = abrir.checked }
            FormCard.FormHeader { title: "Sistema" }
            FormCard.FormCard {
                FormCard.FormTextFieldDelegate { id: terminal; label: "Terminal para «Abrir terminal en el repo»"; text: dialogo.a.terminal; placeholderText: "konsole" }
                FormCard.FormCheckDelegate { id: abrir; text: "Abrir el panel inferior al correr una operación"; description: "La salida de la CLI aparece sola (como la terminal de Dolphin); F4 lo pliega"; checked: dialogo.a.abrirInferior }
            }
            FormCard.FormHeader { title: "La puerta" }
            FormCard.FormCard {
                FormCard.FormTextDelegate { text: "La ventana no escribe en Calibre ni en Zotero: cada operación es la CLI de su suite, que simula con F5 y aplica con Ctrl+Intro por la única puerta (aplicación cerrada, candado y respaldo verificado). Los respaldos y los candados se ven en Coherencia › Puerta; el tema es el del escritorio." }
            }
        }
    }
}
