# articulo/config.py — artículos, tesis y documentos en acceso abierto: del DOI (o de la URL de la página
# del artículo) a su PDF. Segunda fuente del sistema documental (FD5, 2026-09-07).
#
# Orden de búsqueda: Unpaywall (best_oa_location.url_for_pdf) → Crossref (`link` con content-type PDF) →
# la página de destino del DOI o la URL dada, leyendo la etiqueta <meta name="citation_pdf_url"> que usan
# OJS, DSpace, SciELO y la mayoría de repositorios. Solo acceso abierto: nada de credenciales ni proxies.
import os

NOMBRE = "articulo"
DESCRIPCION = "Artículos, tesis y documentos en acceso abierto por DOI o URL (Unpaywall, Crossref, citation_pdf_url)"
TIPOS = ["doi", "url"]
UNPAYWALL = "https://api.unpaywall.org/v2/{doi}?email={email}"
CROSSREF = "https://api.crossref.org/works/{doi}"
DOI_ORG = "https://doi.org/{doi}"
# Unpaywall exige un correo de contacto en cada consulta. Sale del entorno (P248, ola 2 F5): el repo no guarda datos
# personales. Sin él, Unpaywall se omite y se sigue con Crossref y la página del DOI.
EMAIL = os.environ.get("FUENTES_CORREO_CONTACTO", "")
TIMEOUT = 30
