/*
 * content/puras.js — las funciones puras de la extensión «Ecosistema» (no tocan Zotero ni el disco).
 *
 * Objetivo: que lo que decide (el calibre_id de una ruta de adjunto, la URL de Calibre, el plan de series, el
 *   resumen de un libro del índice) se pueda probar con `node pruebas.mjs` fuera de Zotero.
 * Método: un guion clásico que define `EcosistemaPuras`. En Zotero lo carga `Services.scriptloader.loadSubScript`
 *   en el ámbito del complemento; en Node lo exporta `module.exports` (pruebas.mjs lo pide con `createRequire`).
 * Límite: nada aquí lee archivos ni la base de Zotero; quien llama le da los datos ya leídos.
 */
"use strict";

var EcosistemaPuras = (function () {
	/** El índice que entiende esta versión (lo escribe `lib/indice.py`, `ESQUEMA = 1`). */
	const ESQUEMA_INDICE = 1;

	/** El `calibre_id` es el número entre paréntesis de la carpeta que contiene el archivo: `…/Título (48)/x.pdf`.
	 * La misma expresión que `_ID_EN_RUTA` de `lib/indice.py`, para que las dos piezas lean igual. */
	const ID_EN_RUTA = /\((\d+)\)\/[^/]*$/;

	/**
	 * El `calibre_id` de la ruta de un adjunto enlazado (`attachments:<Autor>/<Título> (<id>)/<archivo>`).
	 * @param {string} ruta - la ruta tal como la guarda Zotero (relativa a la base o absoluta).
	 * @returns {number|null} el id, o null si la ruta no lleva `(<id>)/` en la carpeta del archivo.
	 */
	function calibreIdDeRuta(ruta) {
		if (typeof ruta !== "string" || !ruta) {
			return null;
		}
		const m = ruta.replace(/\\/g, "/").match(ID_EN_RUTA);
		return m ? Number(m[1]) : null;
	}

	/** El primer `calibre_id` de una lista de rutas (el orden de los adjuntos), o null. */
	function calibreIdDeRutas(rutas) {
		for (const ruta of rutas || []) {
			const id = calibreIdDeRuta(ruta);
			if (id !== null) {
				return id;
			}
		}
		return null;
	}

	/** El último componente de una ruta, sin barras finales (`/a/biblioteca/` → `biblioteca`). */
	function nombreBase(ruta) {
		const partes = String(ruta || "").replace(/\\/g, "/").replace(/\/+$/, "").split("/");
		return partes[partes.length - 1] || "";
	}

	/** El texto en UTF-8 escrito en hexadecimal en minúsculas (`biblioteca` → `6269626c696f74656361`). */
	function hexUtf8(texto) {
		const bytes = new TextEncoder().encode(String(texto));
		let salida = "";
		for (const b of bytes) {
			salida += b.toString(16).padStart(2, "0");
		}
		return salida;
	}

	/**
	 * La URL que abre un libro en Calibre: `calibre://show-book/_hex_-<hex del nombre de la biblioteca>/<id>`.
	 * Calibre identifica la biblioteca por el nombre de su carpeta; `_hex_-` le dice que viene en hexadecimal.
	 * @param {string} carpetaBiblioteca - la carpeta de la biblioteca (`biblioteca` del índice).
	 * @param {number|string} calibreId
	 */
	function urlCalibre(carpetaBiblioteca, calibreId) {
		return `calibre://show-book/_hex_-${hexUtf8(nombreBase(carpetaBiblioteca))}/${calibreId}`;
	}

	/** La URL que abre un libro en Biblioteca Studio. */
	function urlStudio(calibreId) {
		return `biblioteca-studio://libro/${calibreId}`;
	}

	/**
	 * Dónde vive el índice: `$XDG_STATE_HOME/biblioteca/indice.json` o, sin esa variable,
	 * `<carpeta personal>/.local/state/biblioteca/indice.json` (lo mismo que `ruta_indice()` de `lib/indice.py`).
	 * @param {string} xdgState - el valor de XDG_STATE_HOME ("" si no está definida).
	 * @param {string} carpetaPersonal
	 * @param {(...partes: string[]) => string} [unir] - cómo unir rutas (PathUtils.join en Zotero).
	 */
	function rutaIndice(xdgState, carpetaPersonal, unir) {
		const juntar = unir || ((...p) => p.join("/").replace(/\/{2,}/g, "/"));
		const estado = xdgState ? xdgState : juntar(carpetaPersonal, ".local", "state");
		return juntar(estado, "biblioteca", "indice.json");
	}

	/**
	 * ¿Es un índice que esta versión entiende?
	 * @returns {{ok: boolean, motivo: string}}
	 */
	function validarIndice(indice) {
		if (!indice || typeof indice !== "object") {
			return { ok: false, motivo: "el índice no es un objeto JSON" };
		}
		if (indice.esquema !== ESQUEMA_INDICE) {
			return { ok: false, motivo: `esquema ${indice.esquema} del índice; esta extensión entiende el ${ESQUEMA_INDICE}` };
		}
		if (!indice.libros || typeof indice.libros !== "object") {
			return { ok: false, motivo: "el índice no trae «libros»" };
		}
		return { ok: true, motivo: "" };
	}

	/**
	 * Lo que la sección del panel dice de un libro, sacado del índice (sin mirar el disco).
	 * @param {object|null} indice - el índice ya leído y validado (o null si no lo hay).
	 * @param {number|null} calibreId
	 * @returns {{calibreId: number|null, enBiblioteca: boolean, titulo: string, autores: string[], fichas: string[],
	 *            nota: string, clave: string, zoteroKey: string, urlCalibre: string, urlStudio: string}}
	 */
	function resumenLibro(indice, calibreId) {
		const vacio = {
			calibreId: calibreId, enBiblioteca: false, titulo: "", autores: [], fichas: [], nota: "", clave: "",
			zoteroKey: "", urlCalibre: "", urlStudio: "",
		};
		if (calibreId === null || calibreId === undefined) {
			return vacio;
		}
		vacio.urlStudio = urlStudio(calibreId);
		if (indice && indice.biblioteca) {
			vacio.urlCalibre = urlCalibre(indice.biblioteca, calibreId);
		}
		const libro = indice && indice.libros ? indice.libros[String(calibreId)] : null;
		if (!libro) {
			return vacio;
		}
		return Object.assign(vacio, {
			enBiblioteca: true,
			titulo: libro.titulo || "",
			autores: Array.isArray(libro.autores) ? libro.autores : [],
			fichas: Array.isArray(libro.fichas) ? libro.fichas : [],
			nota: libro.nota || "",
			clave: libro.clave || "",
			zoteroKey: libro.zotero_key || "",
		});
	}

	/** «1 ficha» / «3 fichas»: el plural en español para los mensajes. */
	function plural(n, singular, pluralTexto) {
		return `${n} ${n === 1 ? singular : (pluralTexto || singular + "s")}`;
	}

	/**
	 * El plan de «Organizar por series»: qué subcolecciones hacen falta y qué ítems van a cada una.
	 * La misma regla que `zotero-series/series_organizer.js`: el campo Series sin espacios a los lados, con el prefijo
	 * delante; una subcolección existente se reutiliza si su nombre coincide exactamente; los ítems sin serie se cuentan
	 * y se quedan donde están.
	 * @param {{id: number, titulo: string, serie: string}[]} elementos - los ítems regulares de la colección, en orden.
	 * @param {{prefijo?: string, existentes?: string[], limite?: number}} [opciones]
	 *   existentes: los nombres de las subcolecciones que ya cuelgan de la colección; limite: 0 = sin límite.
	 * @returns {{series: {nombre: string, existe: boolean, ids: number[], titulos: string[]}[], total: number,
	 *            procesados: number, conSerie: number, sinSerie: number, aCrear: number, aReutilizar: number,
	 *            aMover: number}}
	 */
	function planPorSeries(elementos, opciones) {
		const op = opciones || {};
		const prefijo = op.prefijo || "";
		const existentes = new Set(op.existentes || []);
		const limite = op.limite > 0 ? op.limite : 0;
		const todos = elementos || [];
		const lote = limite && todos.length > limite ? todos.slice(0, limite) : todos;
		const mapa = new Map();
		let sinSerie = 0;
		for (const el of lote) {
			const serie = typeof el.serie === "string" ? el.serie.trim() : "";
			if (!serie) {
				sinSerie++;
				continue;
			}
			const nombre = prefijo + serie;
			if (!mapa.has(nombre)) {
				mapa.set(nombre, { nombre, existe: existentes.has(nombre), ids: [], titulos: [] });
			}
			const grupo = mapa.get(nombre);
			grupo.ids.push(el.id);
			grupo.titulos.push(el.titulo || "(sin título)");
		}
		const series = [...mapa.values()];
		const aMover = series.reduce((s, g) => s + g.ids.length, 0);
		return {
			series, total: todos.length, procesados: lote.length, conSerie: aMover, sinSerie,
			aCrear: series.filter((g) => !g.existe).length, aReutilizar: series.filter((g) => g.existe).length, aMover,
		};
	}

	/**
	 * El texto de la vista previa que se muestra antes de escribir.
	 * @param {ReturnType<typeof planPorSeries>} plan
	 * @param {{coleccion: string, mantener?: boolean, maxLineas?: number}} contexto
	 */
	function textoVistaPrevia(plan, contexto) {
		const ctx = contexto || {};
		const maxLineas = ctx.maxLineas > 0 ? ctx.maxLineas : 25;
		const verbo = ctx.mantener ? "se copian (se quedan también en la colección)" : "se mueven (salen de la colección)";
		const lineas = [
			`Colección: «${ctx.coleccion || ""}»`,
			`Ítems regulares: ${plan.total}` + (plan.procesados < plan.total ? ` (se procesan ${plan.procesados} por el límite)` : ""),
			`Con serie: ${plan.conSerie} · sin serie (no se tocan): ${plan.sinSerie}`,
			`Subcolecciones nuevas: ${plan.aCrear} · ya existentes que se reutilizan: ${plan.aReutilizar}`,
			`Ítems que ${verbo}: ${plan.aMover}`,
			"",
		];
		const orden = [...plan.series].sort((a, b) => b.ids.length - a.ids.length || a.nombre.localeCompare(b.nombre, "es"));
		for (const g of orden.slice(0, maxLineas)) {
			lineas.push(`${g.existe ? "  =" : "  +"} «${g.nombre}»: ${plural(g.ids.length, "ítem")}`);
		}
		if (orden.length > maxLineas) {
			lineas.push(`  … y ${plural(orden.length - maxLineas, "serie")} más (el detalle completo, en la consola de depuración)`);
		}
		lineas.push("", "(+ se crea, = ya existe). Nada se ha escrito todavía.");
		return lineas.join("\n");
	}

	const api = {
		ESQUEMA_INDICE, ID_EN_RUTA, calibreIdDeRuta, calibreIdDeRutas, nombreBase, hexUtf8, urlCalibre, urlStudio,
		rutaIndice, validarIndice, resumenLibro, plural, planPorSeries, textoVistaPrevia,
	};
	return Object.freeze(api);
})();

if (typeof module === "object" && module && module.exports) {
	module.exports = EcosistemaPuras;
}
