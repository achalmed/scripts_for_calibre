"""fichas/lib/grafia.py — fase M2 de meta/NORMATIVA_ARCHIVOS.md: claves y valores en snake_case.

Objetivo: que toda ficha, lectura y plantilla use `calibre_id`, `zotero_key`,
  `clave_bibtex`, `tipo: ficha_*`, `verificacion.estado: verificada_*` y
  `proyecto: <id>` (nombre de la carpeta del proyecto, no una ruta: `escritura/<tipo>/<id>/…`, una ruta absoluta o
  con `~` pasan a su id con `lib/rutas.id_proyecto`).
Método: reescritura del bloque frontmatter, línea a línea, sin tocar el cuerpo;
  simulación por defecto; respaldo tar.gz y UNDO.sh en $RESPALDOS_DIR/biblioteca/fuentes/fichas/ (ola 2, F5; P240).
Fundamento: meta/diagnosticos/DIAGNOSTICO_METADATOS_2026-09.md §2.1 (cinco grafías del mismo
  identificador). decision_de_diseno.
Límite: no rellena claves vacías ni valida el cuerpo (eso es `validar`).
"""
import importlib.util
import re
import tarfile
from datetime import datetime
from pathlib import Path

CLAVES = {"calibre-id": "calibre_id", "zotero-key": "zotero_key", "clave-bibtex": "clave_bibtex",
          "citekey": "clave_bibtex", "fecha-busqueda": "fecha_busqueda", "verificacion-global": "verificacion_global",
          "verificada-script": "verificada_script", "verificada-autor": "verificada_autor",
          "revista-o-editorial": "revista_o_editorial", "volumen-numero-paginas": "volumen_numero_paginas",
          "doi-o-url": "doi_o_url"}
VALORES = {"verificada-script": "verificada_script", "verificada-autor": "verificada_autor",
           "ficha-catalogacion": "ficha_catalogacion", "ficha-fuente": "ficha_fuente", "ficha-textual": "ficha_textual",
           "ficha-parafrasis": "ficha_parafrasis", "ficha-sintesis": "ficha_sintesis",
           "ficha-parafraseo-complejo": "ficha_sintesis", "ficha-replicacion": "ficha_replicacion",
           "indice-fichas": "indice_fichas"}
RUTA_PROYECTO = re.compile(r"^(\s*proyecto:\s*)escritura/[a-z]+/([^/\n]+)(?:/[^\n]*)?\s*$")
PROYECTO_CON_RUTA = re.compile(r"^(\s*proyecto:\s*)(\S*/\S*)\s*$")   # una ruta (absoluta o con ~), no un id

_R = Path(__file__).resolve().parents[2] / "lib" / "rutas.py"   # id_proyecto: la carpeta del proyecto, sin la ruta
_s = importlib.util.spec_from_file_location("rutas", _R); _rutas = importlib.util.module_from_spec(_s); _s.loader.exec_module(_rutas)


def migrar_texto(txt):
    """Frontmatter con claves y valores en snake_case; el cuerpo intacto."""
    if not txt.startswith("---"):
        return txt
    partes = txt.split("\n---", 1)
    if len(partes) < 2:
        return txt
    fm, resto = partes
    out = []
    for l in fm.split("\n"):
        m = re.match(r"^(\s*)([A-Za-z_][\w-]*)(:\s*)(.*)$", l)
        if m:
            k = CLAVES.get(m.group(2), m.group(2))
            v = m.group(4)
            for a, b in VALORES.items():
                if v.strip() == a:
                    v = v.replace(a, b)
            l = f"{m.group(1)}{k}{m.group(3)}{v}"
            mp = RUTA_PROYECTO.match(l)
            if mp:
                l = f"{mp.group(1)}{mp.group(2)}"
            mr = PROYECTO_CON_RUTA.match(l)
            if mr:                                   # `proyecto: /…/datafw` (ingesta bib --proyecto RUTA, 2026-10-26) → datafw
                l = f"{mr.group(1)}{_rutas.id_proyecto(mr.group(2))}"
        out.append(l)
    return "\n".join(out) + "\n---" + resto


def rutas_del_cuerpo(txt, docs):
    """Las rutas de la máquina del cuerpo de una ficha, sin la carpeta de inicio (RQ-SEC-01): lo que cae bajo DOCS_ROOT
    queda relativo a ella (`biblioteca-studio/entrada/x.pdf`, como `identificar.py` y los ledgers desde F5) y «del
    proyecto `<ruta>`» pasa al id. El frontmatter no se toca (eso es `migrar_texto`)."""
    if not txt.startswith("---"):
        return txt
    partes = txt.split("\n---", 1)
    if len(partes) < 2:
        return txt
    fm, cuerpo = partes
    base = str(Path(docs)).rstrip("/") + "/"
    cuerpo = re.sub(r"del proyecto `([/~][^`\n]*)`", lambda m: f"del proyecto `{_rutas.id_proyecto(m.group(1), docs)}`", cuerpo)
    cuerpo = cuerpo.replace(base, "")
    return fm + "\n---" + cuerpo


def migrar_rutas(carpetas, docs, aplicar=False, raiz_respaldos=None):
    """`fichas rutas`: como `migrar`, pero para el cuerpo (simulación por omisión; respaldo y UNDO antes de escribir)."""
    cambios = []
    for c in carpetas:
        for f in sorted(Path(c).rglob("*.md")):
            txt = f.read_text(encoding="utf-8", errors="replace")
            nuevo = rutas_del_cuerpo(txt, docs)
            if nuevo != txt:
                cambios.append((f, nuevo))
    d = None
    if aplicar and cambios:
        d = respaldar([f for f, _ in cambios], raiz_respaldos, "rutas_fichas")
        for f, nuevo in cambios:
            f.write_text(nuevo, encoding="utf-8")
    return cambios, d


def respaldar(archivos, raiz_respaldos, etiqueta):
    """tar.gz de `archivos` y su UNDO.sh en `raiz_respaldos/<etiqueta>_<sello>/`, fuera del repo; devuelve la carpeta.

    Se comprueba que el tar se lee entero antes de devolver: sin respaldo legible, nadie escribe.
    """
    sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    d = Path(raiz_respaldos) / f"{etiqueta}_{sello}"
    d.mkdir(parents=True, exist_ok=True)
    tar = d / "respaldo.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        for f in archivos:
            t.add(f, arcname=str(Path(f).resolve()).lstrip("/"))
    with tarfile.open(tar) as t:
        if len(t.getnames()) != len(archivos):
            raise OSError(f"respaldo incompleto en {tar}")
    (d / "UNDO.sh").write_text("#!/usr/bin/env bash\n# UNDO.sh — restaura las fichas desde el respaldo (rutas absolutas).\n"
                               f"set -euo pipefail\ntar -xzf \"{tar}\" -C /\necho revertido\n", encoding="utf-8")
    (d / "UNDO.sh").chmod(0o755)
    return d


def migrar(carpetas, aplicar=False, raiz_respaldos=None):
    cambios = []
    for c in carpetas:
        for f in sorted(Path(c).rglob("*.md")):
            txt = f.read_text(encoding="utf-8", errors="replace")
            nuevo = migrar_texto(txt)
            if nuevo != txt:
                cambios.append((f, nuevo))
    if not aplicar or not cambios:
        return cambios, None
    d = respaldar([f for f, _ in cambios], raiz_respaldos, "M2_grafia_fichas")
    for f, nuevo in cambios:
        f.write_text(nuevo, encoding="utf-8")
    return cambios, d
