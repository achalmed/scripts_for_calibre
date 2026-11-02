// Registro — la salida íntegra de la última aplicación (--aplicar) de la operación elegida, con su fecha y su orden.
import QtQuick
import GuiComun

VistaTexto {
    readonly property var o: studio.operaciones
    texto: o.registro
    definicion: "Bash"
    mensajeVacio: !o.hayOperacion ? "Esta vista no tiene operaciones" : (o.escribe ? "Sin registro todavía: Aplicar (Ctrl+Intro) corre «" + o.titulo + "» con --aplicar por la puerta y deja aquí su salida" : "Esta operación no tiene modo «aplicar»")
    iconoVacio: "dialog-ok-apply"
    nombreAccesible: "Registro de " + o.titulo
}
