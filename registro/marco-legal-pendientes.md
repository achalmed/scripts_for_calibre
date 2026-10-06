---
tipo: doc
titulo: "Pendientes y advertencias de la biblioteca normativa: descargas manuales, normas derogadas o sustituidas, PDF sin capa de texto"
estado: activo
origen: "01_inteligencia_legislativa/02_investigacion/marco_legal/PENDIENTES.md (CIL del despacho, M10 D6)"
---
# Pendientes y advertencias de la biblioteca normativa

Lo que **no** se pudo automatizar, lo que **no existe**, y lo que hay que
**vigilar** por vigencia. Revisar antes de citar cualquier norma en un dictamen,
proyecto de ley o informe.

Fecha de la descarga: **31 de julio de 2026**. Las rutas de carpeta que siguen (`03_congreso/…`,
`19_informes_permanentes/…`) son las de aquella descarga; hoy los PDF están en Calibre, en la serie
«Marco legal NN - …», y su carpeta de origen es el campo `carpeta` de
`manifiestos/marco_legal/manifiesto.tsv`.

---

## 1. Descarga manual obligatoria (2 archivos)

El portal del **BCRP está protegido por Imperva** y responde con un desafío
JavaScript (`Pardon Our Interruption`, HTTP 200, 6 183 bytes) en lugar del PDF.
No es una URL rota: es una barrera anti-bot deliberada. Se probó con `curl` y con
`wget`, con cabeceras de navegador completas. **Hay que bajarlos desde el navegador:**

| Archivo | Origen |
| ------- | ------ |
| `19_informes_permanentes/bcrp_reporte_estabilidad_financiera_2026_05.pdf` | https://www.bcrp.gob.pe/docs/Publicaciones/Reporte-Estabilidad-Financiera/2026/mayo/ref-mayo-2026.pdf |
| `19_informes_permanentes/bcrp_memoria_anual_2025.pdf` | https://www.bcrp.gob.pe/docs/Publicaciones/Memoria/2025/memoria-bcrp-2025.pdf |

> El *Reporte de Inflación junio 2026* sí se obtuvo (el bloqueo es intermitente,
> por tasa de peticiones). Si al re-correr el script fallan los tres, bájalos a mano.
> Índice de publicaciones: https://www.bcrp.gob.pe/publicaciones.html

**`www.sbs.gob.pe` tiene el mismo problema** (WAF Incapsula: devuelve un stub HTML
de 212 bytes). Ahí están las **mejores versiones concordadas de la Ley 27693 (UIF)
y del D.Leg. 1106**; las que hay en `11_seguridad/` vienen de fuentes alternas y
están menos consolidadas. Si necesitas las concordadas, bájalas desde el navegador.

---

## 1-bis. Archivos que requieren recorte

Tres normas solo estaban disponibles como **compendio SPIJ del día de publicación**
(el PDF trae todas las normas de esa fecha). Hay que extraer las páginas de la norma:

| Archivo en `11_seguridad/` | La norma empieza en |
| -------------------------- | ------------------- |
| D.Leg. 1106 (compendio del 19/04/2012, 146 pp) | pág. 20 |
| D.S. 015-2003-JUS — Reglamento del Cód. de Ejecución Penal (compendio del 11/09/2003) | pág. 27 |
| ROF del INPE, D.S. 009-2007-JUS (compendio del 10/10/2007) | pág. 29 |

Para recortar: `pdftk entrada.pdf cat 20-end output salida.pdf`
o `qpdf --pages entrada.pdf 20-z -- entrada.pdf salida.pdf`

---

## 2. Documentos que NO existen (no seguir buscándolos)

Se verificó exhaustivamente. Estas piezas del encargo original no tienen
publicación oficial; se anota el sustituto institucional ya descargado.

| Pedido | Realidad | Sustituto en la biblioteca |
| ------ | -------- | -------------------------- |
| Guía para elaborar proyectos de ley | No existe como publicación autónoma | `03_congreso/` → Manual de Técnica Legislativa 3.ª ed. 2021 + Manual del Proceso Legislativo (2012) |
| Manual del Congresista | No existe con ese título | `03_congreso/` → Manual del Parlamento (Delgado-Guembes, Oficialía Mayor 2012, 638 pp) + Guía de Gestión de la Representación Política |
| Manual de Redacción Legislativa | No se publica suelto | Va dentro del tomo MTL + MRP 2013, ya descargado |
| Directiva sobre trámite legislativo | No existe una directiva única: el trámite lo fija el propio Reglamento del Congreso | 9 directivas y PTA de gestión documental, mesa de partes digital y expediente virtual, en `03_congreso/` |
| Compendio de casaciones laborales y civiles | No hay PDF recopilatorio oficial; el PJ solo ofrece buscador dinámico | Los compendios MINJUS-SPIJ en `17_jurisprudencia/` cubren **solo materia penal**. Consultar el [buscador de jurisprudencia vinculante del PJ](https://www.pj.gob.pe/wps/wcm/connect/cij-juris/s_jurisprudencia_sistematizada/as_suprema/as_servicios/as_jurisprudencia_vinculante/inicio_jurisprudencia_vinculante) |
| RM 151-2021-PCM (norma que aprueba el Manual AIR) | La copia en `cdn.www.gob.pe` es una página suelta de El Peruano con contenido ajeno | El **Manual AIR Ex Ante** en sí (77 pp) sí está descargado en `18_manuales/` |

---

## 3. Cambios normativos recientes — VERIFICAR ANTES DE CITAR

Hallazgos de la descarga que contradicen lo que circula en buscadores:

### Régimen bicameral (crítico para este despacho)
El Congreso publicó en **julio de 2026** tres reglamentos nuevos: **Reglamento del
Congreso (Ed. Oficial mayo 2026)**, **Reglamento de la Cámara de Diputados** y
**Reglamento del Senado**. La edición de setiembre 2025 —que aparece primero en
Google— todavía dice *"Es unicameral"*. Los tres nuevos están en `03_congreso/`;
la de 2025 se conservó marcada como histórica.

> El **Manual de Técnica Legislativa** sigue siendo la 3.ª ed. **2021**: aún no se
> ha adaptado a la bicameralidad.

### Procedimiento administrativo
El **TUO de la Ley 27444 (D.S. 004-2019-JUS) fue DEROGADO** por el **D.S.
006-2026-JUS** (El Peruano, 30/04/2026), que aprueba un TUO nuevo. Ambos están en
`04_administracion_publica/`; usar el de 2026.

### Contrataciones
La **Ley 32069** y su reglamento **D.S. 009-2025-EF** rigen desde el **22/04/2025**
y sustituyen a la Ley 30225. El **OSCE ya no existe**: es la **OECE**, y las nuevas
directivas las emite la **Dirección General de Abastecimiento del MEF** (`EF/54.01`),
no la OECE. Las directivas OSCE anteriores rigieron solo hasta el 21/04/2025.

### Calidad regulatoria
El **D.S. 063-2021-PCM está derogado** por el **D.S. 023-2025-PCM** (25/02/2025),
reglamento del D.Leg. 1565 (Ley General de Mejora de la Calidad Regulatoria).
Ambos en `18_manuales/`, más dos instrumentos de 2026: Guía de Consulta Pública
(RSGP 002-2026) y Lineamientos de evaluación Ex Post (RSGP 010-2026).

### Reglamento de la PNP
El **D.S. 026-2017-IN fue sustituido** el 05/11/2025 por el **D.S. 012-2025-IN**
(nuevo reglamento del D.Leg. 1267, 312 artículos). Ambos están en `11_seguridad/`;
usar el de 2025. El de 2017 se conservó como histórico.

### Textos sin consolidar al día
Se descargó la mejor versión disponible, pero **no incorporan** las modificatorias
indicadas. Contrastar en SPIJ antes de citar:

| Norma | Falta incorporar |
| ----- | ---------------- |
| LOPE (Ley 29158) | Ley 31894 (2023) |
| D.Leg. 1267 (PNP) | D.Leg. 1318, Ley 31173, D.S. 012-2025-IN |
| D.Leg. 052 (Ministerio Público) | modificatorias posteriores a 2010 |
| Ley 27658 (Modernización) | D.Leg. 1694 (20/01/2026) — descargado aparte |
| D.S. 123-2018-PCM | D.S. 090-2026-PCM (10/06/2026) — descargado aparte |
| Ley 30220 (Universitaria) | D.U. 034-2019 |
| Ley 29783 (SST) | Ley 30222 y Ley 31246 |
| Ley 28044 (Educación) | D.Leg. 1375 |
| D.Leg. 1436 | D.Leg. 1630 (2024) |
| D.S. 284-2018-EF (Invierte.pe) | D.S. 179-2020-EF, 231-2022-EF, 074-2023-EF |
| Ley 29344 (AUS) | existe TUO por D.S. 020-2014-SA |
| Ley 30077 (Crimen Organizado) | Ley 32108 (2024) y D.Leg. 1731 (12/02/2026) |
| Ley 27693 (UIF) | D.Leg. 1249 |
| D.S. 015-2003-JUS (Regl. Ejec. Penal) | D.S. 022-2025-JUS (04/11/2025) |
| D.S. 011-2012-ED (Regl. Educación) | fuente subóptima: export SPIJ alojado en el Gob. Reg. de Lambayeque, única versión íntegra con capa de texto |

---

## 3-bis. Los reglamentos del Congreso tienen la capa de texto corrupta

No copiar y pegar de estos PDF a un proyecto de ley, dictamen u oficio: el hallazgo, el método
(`ocrmypdf -l spa`) y los libros de Calibre con el texto OCR están en `fuentes/congreso/README.md`. El
OCR es fiable pero no infalible: para citar un número de artículo en un documento oficial, contrástalo
visualmente contra el PDF original.

---

## 4. PDFs escaneados sin capa de texto (requieren OCR)

No se pueden buscar con `grep`/`pdftotext` ni citar textualmente. Si se van a
indexar, pasarles OCR (`ocrmypdf -l spa entrada.pdf salida.pdf`):

```
03_congreso/directiva_02_2023_dgp_cr_gestion_documental.pdf
03_congreso/directiva_07_2022_dgp_cr_mesa_de_partes_digital.pdf
03_congreso/directiva_07_2022_dgp_cr_modificacion_01.pdf
03_congreso/directiva_011_2023_dgp_cr_transferencia_documentos_archivisticos_comisiones.pdf
03_congreso/directiva_10_2022_om_cr_lineamientos_elaboracion_documentos.pdf
03_congreso/directiva_08_2022_dga_cr_apoyo_logistico_semana_de_representacion.pdf
03_congreso/pta_01_2013_recepcion_y_tramitacion_mociones_de_orden_del_dia.pdf
03_congreso/pta_01_2017_expediente_virtual_parlamentario_ley_resolucion_legislativa.pdf
03_congreso/pta_02_2017_tramitacion_pedidos_de_informacion_despacho_parlamentario.pdf
18_manuales/reglamento_dl_1565_ley_general_mejora_calidad_regulatoria_ds_023_2025_pcm.pdf
18_manuales/ds_023_2025_pcm_parte_resolutiva.pdf
```

El resto de la biblioteca (≈150 archivos) **sí tiene capa de texto** verificada.

---

## 5. Fuentes y trucos técnicos descubiertos

Útiles para futuras actualizaciones del manifiesto:

- **`https://diariooficial.elperuano.pe/Normas/obtenerDocumento?idNorma=<N>`** —
  textos **consolidados de forma continua** por Editora Perú, ligeros y con capa
  de texto. Sistemáticamente **más actuales que las ediciones oficiales del MINJUS**
  (que llevan años de retraso: Código Civil 16.ª ed. es de 2015).
  El catálogo completo (156 normas) se lista en:
  `https://diariooficial.elperuano.pe/Normas/consultarNormasActualizadas?Titulo=&NroNorma=&IdMateria=`
- **`https://www.gob.pe/busquedas.json?contenido[]=normas&term=<N>`** — devuelve
  JSON con `action_url` apuntando directo al PDF en `cdn.www.gob.pe`. Mucho más
  rápido que raspar HTML.
- **`www.gob.pe` responde HTTP 418 a peticiones tipo bot**, pero sirve normal a
  `curl`/`wget` con user-agent de navegador.
- **`www.congreso.gob.pe/Docs/...` devuelve 404**: la ruta viva es
  **`www3.congreso.gob.pe/Docs/...`**. Muchos enlaces que circulan están rotos por esto.
- **`spijweb.minjus.gob.pe/wp-content/uploads/YYYY/MM/<NORMA>.pdf`** — fuente SPIJ
  limpia, útil cuando la copia de `cdn.www.gob.pe` es un escaneo.
- **Evitar `leyes.congreso.gob.pe/Documentos/...`**: son escaneos de la edición
  completa de El Peruano (2–6 MB) **sin capa de texto**.
- **`www2.congreso.gob.pe/sicr/cendocbib/`** sí tiene capa de texto (a diferencia
  de `leyes.congreso.gob.pe/Documentos`). Son repositorios distintos.
- **Servidores caídos o bloqueados**: `sgp.pcm.gob.pe` (timeout),
  `contralaft.gob.pe` (timeout), `www.sbs.gob.pe` (WAF Incapsula),
  `www.bcrp.gob.pe` (Imperva). Para PCM, usar `cdn.www.gob.pe`.
- Algunas URLs del CENDOC contienen `$FILE` literal: **entrecomillarlas en Bash**.
- El MEF sigue un patrón predecible por año:
  `mef.gob.pe/contenidos/presu_publ/anexos/ppto<AAAA>/Ley_N_XXXXX-Leyde<Tipo><AAAA>.pdf`
