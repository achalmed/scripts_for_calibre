/*
 * bootstrap.js — arranque de la extensión «Ecosistema» (arquitectura de complementos de Zotero 7 y posteriores).
 *
 * Objetivo: registrar el espacio chrome://ecosistema/, cargar las funciones puras y la capa de Zotero, y dejar todo
 *   como estaba al apagar (sección, menús, archivos de textos y menús por DOM de cada ventana).
 * Método: Zotero llama a estas seis funciones con {id, version, rootURI} y una razón; el resto vive en content/.
 * Límite: aquí no hay lógica; la sección y la orden están en content/ecosistema.js.
 */
"use strict";

var registroChrome = null;

function install(datos, razon) {}

function uninstall(datos, razon) {}

async function startup({ id, version, rootURI }, razon) {
	await Zotero.initializationPromise;
	const inicio = Components.classes["@mozilla.org/addons/addon-manager-startup;1"]
		.getService(Components.interfaces.amIAddonManagerStartup);
	registroChrome = inicio.registerChrome(Services.io.newURI(rootURI + "manifest.json"),
		[["content", "ecosistema", rootURI + "content/"]]);
	Services.scriptloader.loadSubScript(rootURI + "content/puras.js");
	Services.scriptloader.loadSubScript(rootURI + "content/ecosistema.js");
	Ecosistema.iniciar({ id, version, rootURI });
	// las ventanas que ya estaban abiertas (instalación o activación con Zotero en marcha)
	for (const ventana of Zotero.getMainWindows()) {
		Ecosistema.alCargarVentana(ventana);
	}
	Zotero.debug(`[Ecosistema] ${version} en marcha`);
}

function onMainWindowLoad({ window }) {
	Ecosistema.alCargarVentana(window);
}

function onMainWindowUnload({ window }) {
	Ecosistema.alDescargarVentana(window);
}

function shutdown(datos, razon) {
	if (razon === APP_SHUTDOWN) {
		return;
	}
	if (typeof Ecosistema !== "undefined") {
		Ecosistema.terminar();
		Ecosistema = undefined;
	}
	if (registroChrome) {
		registroChrome.destruct();
		registroChrome = null;
	}
}
