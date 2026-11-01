/*
 * content/ecosistema.js — la capa de la extensión «Ecosistema» que toca Zotero: la sección del panel del ítem y la
 * orden «Organizar por series».
 *
 * Objetivo: ver desde Zotero el libro en Calibre (su calibre_id, si sigue en la biblioteca, sus fichas, su nota de
 *   lectura) y organizar una colección por series con vista previa y confirmación.
 * Método: lee en solo lectura el índice de `lib/indice.py` (`$XDG_STATE_HOME/biblioteca/indice.json`); las
 *   decisiones están en `puras.js` (EcosistemaPuras), cargado antes en el mismo ámbito por bootstrap.js.
 * Límite: la sección no escribe nada. «Organizar por series» sí escribe en Zotero (colecciones), con su API y solo
 *   después de confirmar: es la excepción declarada a la puerta única de escritura (README §Límite honesto).
 */
"use strict";

var Ecosistema = {
	id: null,
	rootURI: null,
	idSeccion: null,
	idsMenus: [],
	enCurso: false,
	cacheIndice: { ruta: "", fecha: 0, datos: null, error: "" },

	PREF: "extensions.ecosistema.",
	FTL: "ecosistema.ftl",
	CLASE_DOM: "ecosistema-dom",
	ICONO_16: "chrome://ecosistema/content/icono-16.svg",
	ICONO_20: "chrome://ecosistema/content/icono-20.svg",
	XHTML: "http://www.w3.org/1999/xhtml",

	// ─── ciclo de vida ──────────────────────────────────────────────────────────────────────────────────────────

	iniciar({ id, rootURI }) {
		this.id = id;
		this.rootURI = rootURI;
		this.registrarSeccion();
		this.registrarMenus();
	},

	terminar() {
		if (this.idSeccion) {
			Zotero.ItemPaneManager.unregisterSection(this.idSeccion);
			this.idSeccion = null;
		}
		if (Zotero.MenuManager) {
			for (const idMenu of this.idsMenus) {
				Zotero.MenuManager.unregisterMenu(idMenu);
			}
		}
		this.idsMenus = [];
		for (const ventana of Zotero.getMainWindows()) {
			this.alDescargarVentana(ventana);
		}
		this.cacheIndice = { ruta: "", fecha: 0, datos: null, error: "" };
	},

	/** Cada ventana principal: el archivo de textos (Fluent) y, en Zotero 7, los menús por DOM. */
	alCargarVentana(ventana) {
		ventana.MozXULElement.insertFTLIfNeeded(this.FTL);
		if (!Zotero.MenuManager) {
			this.menusPorDom(ventana);
		}
	},

	/** Lo que se puso en la ventana se quita: los menús por DOM y el enlace al archivo de textos. */
	alDescargarVentana(ventana) {
		const doc = ventana.document;
		for (const el of doc.querySelectorAll(`.${this.CLASE_DOM}`)) {
			el.remove();
		}
		doc.querySelector(`[href="${this.FTL}"]`)?.remove();
	},

	pref(nombre, porDefecto) {
		const valor = Zotero.Prefs.get(this.PREF + nombre, true);
		return valor === undefined ? porDefecto : valor;
	},

	// ─── el índice (solo lectura) ───────────────────────────────────────────────────────────────────────────────

	rutaIndice() {
		let xdg = "";
		try {
			xdg = Services.env.get("XDG_STATE_HOME") || "";
		}
		catch (e) {
			xdg = "";
		}
		let casa = "";
		try {
			casa = PathUtils.homeDir;
		}
		catch (e) {
			casa = Services.dirsvc.get("Home", Components.interfaces.nsIFile).path;
		}
		return EcosistemaPuras.rutaIndice(xdg, casa, (...p) => PathUtils.join(...p));
	},

	/** El índice leído y validado; se relee solo si cambió su fecha en el disco. */
	async indice() {
		const ruta = this.rutaIndice();
		const c = this.cacheIndice;
		let fecha = 0;
		try {
			fecha = (await IOUtils.stat(ruta)).lastModified || 0;
		}
		catch (e) {
			this.cacheIndice = { ruta, fecha: 0, datos: null, error: `no hay índice en ${ruta}` };
			return this.cacheIndice;
		}
		if (c.ruta === ruta && c.fecha === fecha && (c.datos || c.error)) {
			return c;
		}
		try {
			const datos = JSON.parse(await IOUtils.readUTF8(ruta));
			const v = EcosistemaPuras.validarIndice(datos);
			this.cacheIndice = v.ok ? { ruta, fecha, datos, error: "" } : { ruta, fecha, datos: null, error: v.motivo };
		}
		catch (e) {
			this.cacheIndice = { ruta, fecha, datos: null, error: `no se pudo leer el índice: ${e.message || e}` };
		}
		return this.cacheIndice;
	},

	// ─── el ítem y su calibre_id ────────────────────────────────────────────────────────────────────────────────

	/** El ítem del que habla la sección: el normal; con un adjunto o una nota hija, su padre. */
	itemObjetivo(item) {
		if (!item) {
			return null;
		}
		if (item.isRegularItem()) {
			return item;
		}
		return item.parentItem || item;
	},

	/** Las rutas de los adjuntos enlazados del ítem (o del propio adjunto suelto), en su orden. */
	rutasEnlazadas(item) {
		const adjuntos = item.isAttachment() ? [item] : Zotero.Items.get(item.getAttachments());
		return adjuntos
			.filter((a) => a && a.isAttachment() && a.attachmentLinkMode === Zotero.Attachments.LINK_MODE_LINKED_FILE)
			.map((a) => a.attachmentPath || "");
	},

	calibreId(item) {
		return EcosistemaPuras.calibreIdDeRutas(this.rutasEnlazadas(item));
	},

	// ─── la sección del panel ───────────────────────────────────────────────────────────────────────────────────

	registrarSeccion() {
		this.idSeccion = Zotero.ItemPaneManager.registerSection({
			paneID: "ecosistema-libro",
			pluginID: this.id,
			header: { l10nID: "ecosistema-seccion-cabecera", icon: this.ICONO_16 },
			sidenav: { l10nID: "ecosistema-seccion-lateral", icon: this.ICONO_20 },
			onItemChange: ({ item, setEnabled }) => {
				setEnabled(!!item && (item.isRegularItem() || item.isAttachment()));
				return true;
			},
			onRender: ({ doc, body }) => {
				body.replaceChildren(this.parrafo(doc, "Buscando el libro en el índice…", "ecosistema-tenue"));
			},
			onAsyncRender: async (props) => this.pintarSeccion(props),
		});
	},

	async pintarSeccion({ doc, body, item, setSectionSummary }) {
		const objetivo = this.itemObjetivo(item);
		const marca = String(objetivo ? objetivo.id : "");
		body.dataset.ecosistemaItem = marca;
		const calibreId = objetivo ? this.calibreId(objetivo) : null;
		const { datos, error } = await this.indice();
		const resumen = EcosistemaPuras.resumenLibro(datos, calibreId);
		let notaExiste = false;
		if (resumen.nota) {
			try {
				notaExiste = await IOUtils.exists(resumen.nota);
			}
			catch (e) {
				notaExiste = false;
			}
		}
		if (body.dataset.ecosistemaItem !== marca) {
			return;   // el panel ya muestra otro ítem: este dibujo llegó tarde
		}
		const caja = doc.createElementNS(this.XHTML, "div");
		caja.className = "ecosistema-seccion";
		caja.style.cssText = "display:flex;flex-direction:column;gap:4px;padding:2px 0;";
		if (calibreId === null) {
			caja.append(this.parrafo(doc, "Sin calibre_id: ningún adjunto enlazado tiene la forma "
				+ "«attachments:<Autor>/<Título> (<id>)/<archivo>».", "ecosistema-tenue"));
			setSectionSummary?.("sin calibre_id");
			body.replaceChildren(caja);
			return;
		}
		caja.append(this.fila(doc, "calibre_id", String(calibreId)));
		if (error) {
			caja.append(this.fila(doc, "Índice", error));
		}
		else {
			caja.append(this.fila(doc, "En la biblioteca", resumen.enBiblioteca ? "sí" : "no (el índice no lo tiene)"));
			if (resumen.enBiblioteca) {
				caja.append(this.fila(doc, "Fichas que lo citan", String(resumen.fichas.length)));
				caja.append(this.fila(doc, "Nota de lectura", notaExiste ? "sí" : "no"));
			}
		}
		const botones = doc.createElementNS(this.XHTML, "div");
		botones.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;";
		if (resumen.urlCalibre && resumen.enBiblioteca) {
			botones.append(this.boton(doc, "Abrir en Calibre", () => this.abrirURL(resumen.urlCalibre)));
		}
		botones.append(this.boton(doc, "Abrir en Biblioteca Studio", () => this.abrirURL(resumen.urlStudio)));
		if (notaExiste) {
			botones.append(this.boton(doc, "Abrir la nota de lectura", () => this.abrirArchivo(resumen.nota)));
		}
		caja.append(botones);
		setSectionSummary?.(`calibre_id ${calibreId}` + (resumen.enBiblioteca
			? ` · ${EcosistemaPuras.plural(resumen.fichas.length, "ficha")}` : " · fuera del índice"));
		body.replaceChildren(caja);
	},

	parrafo(doc, texto, clase) {
		const p = doc.createElementNS(this.XHTML, "div");
		p.textContent = texto;
		if (clase) {
			p.className = clase;
			p.style.opacity = "0.75";
		}
		return p;
	},

	fila(doc, etiqueta, valor) {
		const div = doc.createElementNS(this.XHTML, "div");
		const b = doc.createElementNS(this.XHTML, "span");
		b.textContent = `${etiqueta}: `;
		b.style.fontWeight = "600";
		const v = doc.createElementNS(this.XHTML, "span");
		v.textContent = valor;
		div.append(b, v);
		return div;
	},

	boton(doc, texto, accion) {
		const b = doc.createElementNS(this.XHTML, "button");
		b.textContent = texto;
		b.addEventListener("click", (ev) => {
			ev.preventDefault();
			accion();
		});
		return b;
	},

	abrirURL(url) {
		try {
			Zotero.launchURL(url);
		}
		catch (e) {
			this.aviso("Ecosistema", `No se pudo abrir ${url}: ${e.message || e}.\n`
				+ "¿Está registrado el manejador de ese esquema en el sistema?");
		}
	},

	abrirArchivo(ruta) {
		try {
			Zotero.launchFile(ruta);
		}
		catch (e) {
			this.aviso("Ecosistema", `No se pudo abrir ${ruta}: ${e.message || e}`);
		}
	},

	aviso(titulo, texto) {
		Services.prompt.alert(Zotero.getMainWindow(), titulo, texto);
	},

	// ─── los menús ──────────────────────────────────────────────────────────────────────────────────────────────

	/** Zotero 8 o posterior: MenuManager (Herramientas y el contextual de una colección). */
	registrarMenus() {
		if (!Zotero.MenuManager) {
			return;   // Zotero 7: los pone menusPorDom() en cada ventana
		}
		const herramientas = Zotero.MenuManager.registerMenu({
			menuID: "ecosistema-series-herramientas",
			pluginID: this.id,
			target: "main/menubar/tools",
			menus: [{
				menuType: "menuitem",
				l10nID: "ecosistema-menu-series",
				enableForTabTypes: ["library"],
				onCommand: () => this.organizarPorSeries(this.coleccionSeleccionada()),
			}],
		});
		const contextual = Zotero.MenuManager.registerMenu({
			menuID: "ecosistema-series-coleccion",
			pluginID: this.id,
			target: "main/library/collection",
			menus: [{
				menuType: "menuitem",
				l10nID: "ecosistema-menu-series",
				onShowing: (ev, ctx) => ctx.setVisible(!!this.coleccionDeContexto(ctx)),
				onCommand: (ev, ctx) => this.organizarPorSeries(this.coleccionDeContexto(ctx)),
			}],
		});
		this.idsMenus = [herramientas, contextual].filter(Boolean);
	},

	coleccionDeContexto(ctx) {
		try {
			const fila = ctx && ctx.collectionTreeRows ? ctx.collectionTreeRows[0] : null;
			if (fila && fila.isCollection && fila.isCollection()) {
				return fila.ref;
			}
		}
		catch (e) {
			// sin filas en el contexto: se usa la selección del panel
		}
		return this.coleccionSeleccionada();
	},

	coleccionSeleccionada() {
		const panel = Zotero.getActiveZoteroPane();
		return panel ? panel.getSelectedCollection() : null;
	},

	/** Zotero 7 (sin MenuManager): menús por DOM, que alDescargarVentana quita por su clase. */
	menusPorDom(ventana) {
		const doc = ventana.document;
		const lugares = [["menu_ToolsPopup", "ecosistema-series-herramientas"], ["zotero-collectionmenu", "ecosistema-series-coleccion"]];
		for (const [idPadre, idItem] of lugares) {
			const padre = doc.getElementById(idPadre);
			if (!padre || doc.getElementById(idItem)) {
				continue;
			}
			const item = doc.createXULElement("menuitem");
			item.id = idItem;
			item.classList.add(this.CLASE_DOM);
			item.setAttribute("label", "Organizar por series…");
			item.addEventListener("command", () => this.organizarPorSeries(this.coleccionSeleccionada()));
			padre.append(item);
		}
	},

	// ─── «Organizar por series» ─────────────────────────────────────────────────────────────────────────────────

	/**
	 * Simula siempre primero: arma el plan, lo muestra y solo escribe si se confirma. Cancelar = simulación.
	 * La lógica de series_organizer.js: mueve (o copia, según la preferencia) los ítems padre de la colección a una
	 * subcolección por su campo Series; no toca hijos, metadatos ni etiquetas.
	 */
	async organizarPorSeries(coleccion) {
		const ventana = Zotero.getMainWindow();
		if (!coleccion) {
			this.aviso("Organizar por series", "Selecciona primero una colección (no una biblioteca ni una búsqueda).");
			return;
		}
		if (this.enCurso) {
			this.aviso("Organizar por series", "Ya hay una organización en curso; espera a que termine.");
			return;
		}
		this.enCurso = true;
		try {
			const mantener = !!this.pref("mantenerEnColeccionPrincipal", false);
			const elementos = coleccion.getChildItems(false).filter((it) => it.isRegularItem()).map((it) => ({
				id: it.id, titulo: it.getField("title"), serie: it.getField("series"),
			}));
			const plan = EcosistemaPuras.planPorSeries(elementos, {
				prefijo: String(this.pref("prefijoSeries", "") || ""),
				existentes: coleccion.getChildCollections(false).map((c) => c.name),
				limite: Number(this.pref("limite", 0)) || 0,
			});
			const texto = EcosistemaPuras.textoVistaPrevia(plan, { coleccion: coleccion.name, mantener });
			Zotero.debug(`[Ecosistema] vista previa de «Organizar por series»:\n${texto}\n`
				+ plan.series.map((g) => `${g.existe ? "=" : "+"} ${g.nombre}: ${g.titulos.join(" | ")}`).join("\n"));
			if (plan.aMover === 0) {
				this.aviso("Organizar por series", texto.replace("Nada se ha escrito todavía.", "No hay nada que organizar."));
				return;
			}
			const aplicar = Services.prompt.confirm(ventana, "Organizar por series — vista previa",
				`${texto}\n\n¿Aplicar? (Cancelar = solo simulación; haz antes una copia de seguridad de Zotero)`);
			if (!aplicar) {
				this.aviso("Organizar por series", "Simulación: no se escribió nada.");
				return;
			}
			const r = await this.aplicarPlan(coleccion, plan, mantener);
			this.aviso("Organizar por series", `Hecho: ${EcosistemaPuras.plural(r.creadas, "subcolección creada", "subcolecciones creadas")}, `
				+ `${EcosistemaPuras.plural(r.movidos, "ítem")} ${mantener ? "copiados" : "movidos"}, `
				+ `${EcosistemaPuras.plural(r.errores.length, "error", "errores")}.`
				+ (r.errores.length ? `\n\n${r.errores.slice(0, 10).join("\n")}` : ""));
		}
		catch (e) {
			Zotero.logError(e);
			this.aviso("Organizar por series", `Error: ${e.message || e}`);
		}
		finally {
			this.enCurso = false;
		}
	},

	/** Escribe el plan: una transacción por serie (crear la subcolección si falta, añadir, quitar de la principal). */
	async aplicarPlan(coleccion, plan, mantener) {
		const resultado = { creadas: 0, movidos: 0, errores: [] };
		for (const grupo of plan.series) {
			try {
				await Zotero.DB.executeTransaction(async () => {
					let sub = coleccion.getChildCollections(false).find((c) => c.name === grupo.nombre);
					if (!sub) {
						sub = new Zotero.Collection();
						sub.libraryID = coleccion.libraryID;
						sub.name = grupo.nombre;
						sub.parentID = coleccion.id;
						await sub.save();
						resultado.creadas++;
					}
					await sub.addItems(grupo.ids);
					if (!mantener) {
						await coleccion.removeItems(grupo.ids);
					}
				});
				resultado.movidos += grupo.ids.length;
			}
			catch (e) {
				Zotero.logError(e);
				resultado.errores.push(`«${grupo.nombre}»: ${e.message || e}`);
			}
		}
		return resultado;
	},
};
