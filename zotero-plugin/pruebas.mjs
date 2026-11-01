// pruebas.mjs — prueba con Node las funciones puras de «Ecosistema» (content/puras.js) y lee el índice real.
//
// Objetivo: que el calibre_id, la URL de Calibre, el plan de series y el resumen de un libro salgan bien fuera de Zotero.
// Método: node:test y node:assert; el índice real (`$XDG_STATE_HOME/biblioteca/indice.json`) solo se LEE: si no está,
//   esas pruebas se saltan. Ninguna prueba escribe nada.
// Uso:    node pruebas.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const P = require("./content/puras.js");

test("calibre_id de la ruta de un adjunto enlazado", () => {
	assert.equal(P.calibreIdDeRuta("attachments:Max, Weber/El politico y el cientifico (2)/El politico - Max, Weber.epub"), 2);
	assert.equal(P.calibreIdDeRuta("attachments:A, B/Informe (2004) (48)/x.pdf"), 48);   // el año del título no cuenta
	assert.equal(P.calibreIdDeRuta("attachments:A\\Título (7)\\x.pdf"), 7);              // barras de Windows
	assert.equal(P.calibreIdDeRuta("attachments:A/Sin id/x.pdf"), null);
	assert.equal(P.calibreIdDeRuta("attachments:A/Título (9)/sub/x.pdf"), null);         // el id va en la carpeta del archivo
	assert.equal(P.calibreIdDeRuta("storage:x.pdf"), null);
	assert.equal(P.calibreIdDeRuta(""), null);
	assert.equal(P.calibreIdDeRuta(undefined), null);
	assert.equal(P.calibreIdDeRutas(["storage:a.pdf", "attachments:A/T (5)/a.pdf", "attachments:A/T (6)/b.pdf"]), 5);
	assert.equal(P.calibreIdDeRutas([]), null);
});

test("hex UTF-8 en minúsculas y URL de Calibre", () => {
	assert.equal(P.hexUtf8("biblioteca"), "6269626c696f74656361");
	assert.equal(P.hexUtf8("Bibliotéca"), "4269626c696f74c3a96361");   // é = c3 a9
	assert.equal(P.hexUtf8(""), "");
	assert.equal(P.nombreBase("/x/y/biblioteca/"), "biblioteca");
	assert.equal(P.nombreBase("C:\\x\\Calibre Library"), "Calibre Library");
	assert.equal(P.urlCalibre("/x/biblioteca", 48), "calibre://show-book/_hex_-6269626c696f74656361/48");
	assert.equal(P.urlCalibre("/x/Calibre Library", 3), `calibre://show-book/_hex_-${Buffer.from("Calibre Library").toString("hex")}/3`);
	assert.equal(P.urlStudio(48), "biblioteca-studio://libro/48");
});

test("ruta del índice con y sin XDG_STATE_HOME", () => {
	assert.equal(P.rutaIndice("/e", "/c"), "/e/biblioteca/indice.json");
	assert.equal(P.rutaIndice("", "/c"), "/c/.local/state/biblioteca/indice.json");
	assert.equal(P.rutaIndice("", "/c/", (...p) => join(...p)), "/c/.local/state/biblioteca/indice.json");
});

test("validar el índice", () => {
	assert.equal(P.validarIndice({ esquema: 1, libros: {} }).ok, true);
	assert.match(P.validarIndice({ esquema: 2, libros: {} }).motivo, /esquema 2/);
	assert.equal(P.validarIndice({ esquema: 1 }).ok, false);
	assert.equal(P.validarIndice(null).ok, false);
});

test("resumen de un libro del índice", () => {
	const indice = {
		esquema: 1, biblioteca: "/x/biblioteca",
		libros: { 48: { titulo: "T", autores: ["A, B"], fichas: ["catalogacion/fichas/48_x.md"], nota: "/n/t.md", clave: "k", zotero_key: "Z" } },
	};
	const r = P.resumenLibro(indice, 48);
	assert.equal(r.enBiblioteca, true);
	assert.equal(r.fichas.length, 1);
	assert.equal(r.nota, "/n/t.md");
	assert.equal(r.urlCalibre, "calibre://show-book/_hex_-6269626c696f74656361/48");
	const fuera = P.resumenLibro(indice, 49);
	assert.equal(fuera.enBiblioteca, false);
	assert.equal(fuera.urlStudio, "biblioteca-studio://libro/49");
	assert.equal(P.resumenLibro(indice, null).urlStudio, "");
	assert.equal(P.resumenLibro(null, 48).enBiblioteca, false);   // sin índice: solo el id y Biblioteca Studio
});

test("plan por series: la regla de series_organizer.js", () => {
	const elementos = [
		{ id: 1, titulo: "a", serie: "Smith - Macro" },
		{ id: 2, titulo: "b", serie: "  Smith - Macro  " },   // espacios a los lados: la misma serie
		{ id: 3, titulo: "c", serie: "Otra" },
		{ id: 4, titulo: "d", serie: "" },
		{ id: 5, titulo: "e", serie: "   " },
		{ id: 6, titulo: "", serie: "Nueva" },
	];
	const plan = P.planPorSeries(elementos, { existentes: ["Otra", "Ajena"] });
	assert.deepEqual(plan.series.map((g) => [g.nombre, g.existe, g.ids]), [
		["Smith - Macro", false, [1, 2]], ["Otra", true, [3]], ["Nueva", false, [6]],
	]);
	assert.equal(plan.series[2].titulos[0], "(sin título)");
	assert.deepEqual([plan.total, plan.procesados, plan.conSerie, plan.sinSerie, plan.aCrear, plan.aReutilizar, plan.aMover],
		[6, 6, 4, 2, 2, 1, 4]);
	const conPrefijo = P.planPorSeries(elementos, { prefijo: "Serie: ", existentes: ["Otra"] });
	assert.equal(conPrefijo.series[1].nombre, "Serie: Otra");
	assert.equal(conPrefijo.series[1].existe, false);          // el prefijo forma parte del nombre exacto
	const limitado = P.planPorSeries(elementos, { limite: 3 });
	assert.deepEqual([limitado.total, limitado.procesados, limitado.aMover], [6, 3, 3]);
	assert.equal(P.planPorSeries([], {}).aMover, 0);
});

test("texto de la vista previa", () => {
	const plan = P.planPorSeries([{ id: 1, titulo: "a", serie: "S1" }, { id: 2, titulo: "b", serie: "S2" },
		{ id: 3, titulo: "c", serie: "S2" }, { id: 4, titulo: "d", serie: "" }], { existentes: ["S1"] });
	const t = P.textoVistaPrevia(plan, { coleccion: "Calibre", maxLineas: 1 });
	assert.match(t, /Colección: «Calibre»/);
	assert.match(t, /Subcolecciones nuevas: 1 · ya existentes que se reutilizan: 1/);
	assert.match(t, /Ítems que se mueven \(salen de la colección\): 3/);
	assert.match(t, /\+ «S2»: 2 ítems/);                      // la serie mayor primero
	assert.match(t, /… y 1 serie más/);
	assert.match(t, /Nada se ha escrito todavía/);
	assert.match(P.textoVistaPrevia(plan, { coleccion: "C", mantener: true }), /se copian/);
});

const RUTA_REAL = P.rutaIndice(process.env.XDG_STATE_HOME || "", homedir(), (...p) => join(...p));

test("el índice real: se lee, es válido y su calibre_id sale de la ruta de cada formato", { skip: !existsSync(RUTA_REAL) && `no hay índice en ${RUTA_REAL}` }, () => {
	const indice = JSON.parse(readFileSync(RUTA_REAL, "utf8"));   // solo lectura
	assert.deepEqual(P.validarIndice(indice), { ok: true, motivo: "" });
	const ids = Object.keys(indice.libros);
	assert.ok(ids.length > 0, "el índice no tiene libros");
	let conFormato = 0;
	let discrepan = [];
	for (const id of ids) {
		const libro = indice.libros[id];
		if (!libro.formatos || !libro.formatos.length) {
			continue;
		}
		conFormato++;
		// la ruta que Zotero guarda en el adjunto enlazado es `attachments:` + la ruta relativa a la biblioteca
		const visto = P.calibreIdDeRuta("attachments:" + libro.formatos[0]);
		if (visto !== Number(id)) {
			discrepan.push(`${id} → ${visto} (${libro.formatos[0]})`);
		}
	}
	assert.deepEqual(discrepan, [], "formatos cuyo calibre_id no coincide con su clave");
	const conFichas = ids.filter((id) => (indice.libros[id].fichas || []).length > 0);
	const ejemplo = conFichas[0] || ids[0];
	const r = P.resumenLibro(indice, Number(ejemplo));
	assert.equal(r.enBiblioteca, true);
	assert.match(r.urlCalibre, /^calibre:\/\/show-book\/_hex_-[0-9a-f]+\/\d+$/);
	console.log(`# índice real: ${ids.length} libros, ${conFormato} con formato (todos con su calibre_id en la ruta), `
		+ `${conFichas.length} con fichas; ejemplo ${ejemplo}: ${r.fichas.length} ficha(s), ${r.urlCalibre}`);
});
