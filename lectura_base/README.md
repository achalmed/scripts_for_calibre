---
tipo: readme
estado: activo
---
# lectura_base/ — una sola base de lectura: subrayados, notas, horas y progreso de todas las herramientas

<!-- suite:inicio -->
**Suite `lectura_base`** · objetivo *biblioteca* · estado *activo* · python · interfaz cli

Una sola base de lectura (fuera de Calibre y de Zotero) con los subrayados, notas, sesiones, horas y progreso de KOReader, Zotero, Okular y Yachay, sin duplicados entre ellos, con su cola de cambios y la vuelta a Zotero por la puerta.

- Escribe en: archivos, zotero · simula por defecto: sí
- Entrada: KOReader (metadata.*.lua, statistics.sqlite3), zotero.sqlite (copia), Okular (docdata), Yachay (su API)
- Depende de: python3, pdfinfo y pdftotext (poppler-utils), lib/escribir.py y lib/escribir_zotero.py (la puerta, para Zotero)
- Nota: La base vive en $XDG_DATA_HOME/biblioteca/lectura.sqlite (LECTURA_DB): datos del usuario, fuera de todo repo y de toda base de Calibre o Zotero; `lib/base.py` es su único escritor y se niega a abrir esas. La vuelta escribe en Zotero (por la puerta), KOReader (su .lua) y Okular (su docdata), con cada aplicación cerrada (§9.7), y Yachay (por su API con el token).

Comandos:

```bash
main.py estado                       # qué hay en la base (solo lee)
main.py sincronizar                  # simula: cada herramienta → la base
main.py sincronizar --aplicar
main.py exportar zotero [--aplicar]  # la vuelta: la base → Zotero, por la puerta
main.py libro 48 --json              # subrayados, tiempo y sesiones de un libro
main.py cambios --consumidor X       # la cola de cambios para otros programas
```

<sub>Bloque generado desde `suite.yml` por `core/suites.py generar` (2026-11-17); no se edita a mano.</sub>
<!-- suite:fin -->

Edison lee en KOReader, en Zotero, en Okular y en el lector de Yachay. Esta suite junta lo que cada uno guarda en **una
sola base, de Biblioteca Studio**: los subrayados, resaltados y notas (con su origen) y las sesiones, el tiempo y el
progreso de cada libro. Los studios la leen (el área «Lectura» de Biblioteca Studio) y otros programas siguen su cola
de cambios. El porqué, en `../docs/decisiones.md` §9.6 y §9.7.

```
KOReader  metadata.*.lua · statistics.sqlite3 ─┐
Zotero    itemAnnotations · readingTime (copia) ─┤  sincronizar   ┌──────────────────────────────┐
Okular    docdata/*.xml ─────────────────────────┼──────────────▶ │ lectura.sqlite               │ ──▶ área Lectura
Yachay    su API con token (fase 3b) ────────────┘  (solo lee)    │ anotaciones · presencias     │ ──▶ cola de cambios
                                                                   │ sesiones · progreso · cambios│
Zotero · KOReader · Okular ◀── exportar ───────────────────────────┘──────────────────────────────┘
```

## Dónde vive

`$XDG_DATA_HOME/biblioteca/lectura.sqlite` (o `LECTURA_DB`): son datos del usuario (lo subrayado solo en Yachay no está en
otra parte), fuera de todo repo y de toda base de Calibre o Zotero. `lib/base.py` es su único escritor y se niega a abrir
`CALIBRE_DB`, `ZOTERO_DB` o algo dentro de la biblioteca o de la carpeta de Zotero. Antes de cada escritura, un respaldo
verificado en `<respaldos de la puerta>/lectura/` (los cinco más recientes).

## Uso

```bash
python3 main.py                                  # = estado: qué hay en la base (solo lee)
python3 main.py sincronizar                      # SIMULA: lee cada herramienta y dice qué entraría, qué se uniría, qué cambió
python3 main.py sincronizar --aplicar            # concilia en la base (tras su respaldo)
python3 main.py sincronizar --origen koreader    # solo un origen
python3 main.py exportar zotero                  # SIMULA la vuelta: los subrayados que Zotero no tiene
python3 main.py exportar zotero --aplicar        # los escribe por la puerta (Zotero cerrado, candado, respaldo)
python3 main.py exportar koreader --aplicar      # en el .lua de cada PDF que KOReader abrió (KOReader cerrado)
python3 main.py exportar okular --aplicar        # en el docdata de cada PDF, nunca en el PDF (Okular cerrado)
python3 main.py libro 48                         # un libro: progreso por herramienta, subrayados, sesiones
python3 main.py cambios --consumidor mi-studio --avanzar --aplicar   # la cola desde su cursor, y lo guarda
```

En la ventana: Coherencia › Sincronizar › «Base de lectura» (F5 simula, Ctrl+Intro aplica) y «Subrayados de la base →
Zotero», «→ KOReader» y «→ Okular»; el área **Lectura** (Ctrl+5) muestra la base.

## El modelo

| tabla | qué guarda |
|---|---|
| `anotaciones` | un pasaje: libro (`calibre_id`, MD5 parcial de KOReader), hoja del PDF, página o capítulo que se cita, texto, rectángulos (fracciones de la hoja, origen arriba: `[[hoja, x, y, ancho, alto]]`, como Yachay), color, tipo, intención, nota, fechas, huella; `borrada` si ya no está en ninguna herramienta |
| `presencias` | dónde vive cada anotación: origen y su identificador allí (KOReader: `md5:fecha`; Zotero: la clave del ítem; Okular: `uniqueName`; Yachay: el id del resaltado); `ausente` si el origen ya no la tiene |
| `sesiones` | las de KOReader (cada página con su hora; una pausa de más de 10 min abre otra) |
| `progreso` | por libro y por origen: hoja, fracción, estado, segundos (cada origen es dueño de su reloj: las horas se suman, nunca se copian) |
| `cambios`, `cursores` | la cola: cada alta, cambio o baja (disparadores), y hasta dónde leyó cada consumidor |
| `libros`, `corridas` | título y MD5 de cada libro visto; el informe de cada conciliación |

## Sin duplicados al cruzar orígenes

Un registro nuevo de un origen se une a una anotación que ya vino de **otro** origen si es el mismo pasaje: la misma
huella (libro, hoja y comienzo del texto normalizado: sin tildes, sin signos, sin cortes de palabra), o el texto casi
igual (≥ 0,9) en la misma hoja o la vecina, o los rectángulos solapados (≥ 0,5) en la misma hoja (Okular no guarda texto),
o, sin hoja (un EPUB), el texto casi idéntico (≥ 0,95). Dos subrayados iguales de una misma herramienta siguen siendo dos.
Lo que la base escribió en una herramienta queda apuntado como presencia y vuelve como la misma anotación.

## Los adaptadores

| origen | lee | escribe |
|---|---|---|
| KOReader | `hashdocsettings/*/*.sdr/metadata.*.lua` (resaltados con `drawer`, progreso) y `statistics.sqlite3` (`mode=ro`) | sí (§9.7): en el `.lua` de los PDF que ya abrió, con KOReader cerrado, respaldo y escritura atómica (el `.lua` se reescribe idéntico byte a byte) |
| Zotero | `itemAnnotations` de los adjuntos PDF de la biblioteca, el readingTime de Ethereal Style y la última hoja, de una copia | sí, por la puerta: `z_anadir_anotacion` de `lib/escribir_zotero.py` |
| Okular | `docdata/*.xml` de los PDF de la biblioteca (el texto se recorta del PDF con `pdftotext`) | sí (§9.7): en el docdata (nunca en el PDF), con Okular cerrado y respaldo |
| Yachay | su API con token (`cliente.cambios`), cuando la fase 3b deje el cliente de Yachay (`cliente.py` de su repo) | **espera** el cliente y la aprobación del autor |

## Límite honesto

- Borrar en una herramienta no borra en las otras: la anotación queda `borrada` en la base solo si ya no está en ninguna.
- Un cambio de nota en una herramienta llega a la base (gana el más nuevo), pero aún no se lleva a las demás.
- Un EPUB no tiene hoja de PDF: sus subrayados de KOReader se unen a otros solo por el texto; no se exportan.
- Una hoja girada (90° o 270°) no se exporta a ninguna herramienta: cada una mide ahí sus rectángulos a su modo.
- Solo KOReader guarda la hora de cada página: las semanas, los días y la racha salen de él; el tiempo de Zotero cuenta en
  el total del libro.
- Okular 25 guarda las anotaciones en el propio PDF si se le pide («Guardar»): esas no están en docdata y no se leen
  (escribir en un PDF de Calibre cambiaría su MD5 de KOReader).
- No corre sola: no hay timer (systemd solo si el autor lo aprueba).
