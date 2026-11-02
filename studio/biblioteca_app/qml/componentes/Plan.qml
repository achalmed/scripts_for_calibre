// Plan — la salida íntegra de la última simulación (o ejecución) de la operación elegida, con su fecha y su orden.
import QtQuick
import GuiComun

VistaTexto {
    readonly property var o: studio.operaciones
    texto: o.plan
    definicion: "Bash"
    mensajeVacio: !o.hayOperacion ? "Esta vista no tiene operaciones" : "Sin plan todavía: " + o.verbo + " (F5) corre «" + o.titulo + "» sin escribir y deja aquí su salida"
    iconoVacio: "system-run"
    nombreAccesible: "Plan de " + o.titulo
}
