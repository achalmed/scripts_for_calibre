# articulo/localizar.py — localiza el PDF de acceso abierto de un DOI o de una URL de artículo.
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
RE_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.I)
RE_PDF_META = re.compile(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']', re.I)
RE_PDF_META2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']', re.I)
RE_TITLE_META = re.compile(r'<meta[^>]+name=["\']citation_title["\'][^>]+content=["\']([^"\']+)["\']', re.I)
RE_OJS_PDF = re.compile(r'href=["\']([^"\']*/article/(?:download|view)/\d+/\d+[^"\']*)["\']', re.I)


def _get(url, cfg, binario=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=cfg.TIMEOUT) as r:
        datos = r.read(2_000_000 if not binario else 8)
        return (datos if binario else datos.decode("utf-8", "replace")), r.geturl(), r.headers.get("Content-Type", "")


def _es_pdf(url, cfg):
    try:
        cab, _, ct = _get(url, cfg, binario=True)
        return cab.startswith(b"%PDF") or "pdf" in ct.lower()
    except Exception:
        return False


def _unpaywall(doi, cfg):
    if not cfg.EMAIL:          # sin correo de contacto (FUENTES_CORREO_CONTACTO) Unpaywall no responde: se omite
        return None, ""
    try:
        t, _, _ = _get(cfg.UNPAYWALL.format(doi=urllib.parse.quote(doi, safe="/()"), email=cfg.EMAIL), cfg)
        j = json.loads(t)
    except Exception:
        return None, ""
    locs = [j.get("best_oa_location") or {}] + (j.get("oa_locations") or [])
    for l in locs:
        if l.get("url_for_pdf"):
            return l["url_for_pdf"], j.get("title", "")
    return None, j.get("title", "")


def _crossref(doi, cfg):
    try:
        t, _, _ = _get(cfg.CROSSREF.format(doi=urllib.parse.quote(doi, safe="/()")), cfg)
        m = json.loads(t)["message"]
    except Exception:
        return None, ""
    tit = (m.get("title") or [""])[0]
    for l in m.get("link") or []:
        if "pdf" in (l.get("content-type") or "").lower():
            return l["URL"], tit
    return None, tit


def _pagina(url, cfg):
    """PDF anunciado por la página de destino (citation_pdf_url o enlace OJS de descarga)."""
    try:
        t, final, ct = _get(url, cfg)
    except Exception as e:
        return None, "", f"{type(e).__name__}"
    if "pdf" in ct.lower():
        return final, "", ""
    tit = ""
    mt = RE_TITLE_META.search(t)
    if mt:
        tit = html.unescape(mt.group(1))
    for rx in (RE_PDF_META, RE_PDF_META2, RE_OJS_PDF):
        m = rx.search(t)
        if m:
            return urllib.parse.urljoin(final, html.unescape(m.group(1))), tit, ""
    return None, tit, "la página no anuncia un PDF (citation_pdf_url)"


def localizar(referencia, cfg):
    ref = referencia.strip()
    m = RE_DOI.search(ref)
    doi = m.group(1).rstrip(".,;)") if m and not ref.lower().startswith("http") else (m.group(1).rstrip(".,;)") if m and "doi.org" in ref.lower() else None)
    intentos = []
    if doi:
        url, tit = _unpaywall(doi, cfg)
        if url and _es_pdf(url, cfg):
            return {"url": url, "fuente": "Unpaywall", "tipo": "articulo", "numero": re.sub(r"[^A-Za-z0-9.-]+", "_", doi), "titulo": tit or doi}
        intentos.append("Unpaywall" if cfg.EMAIL else "Unpaywall omitido (falta FUENTES_CORREO_CONTACTO)")
        url, tit2 = _crossref(doi, cfg)
        if url and _es_pdf(url, cfg):
            return {"url": url, "fuente": "Crossref", "tipo": "articulo", "numero": re.sub(r"[^A-Za-z0-9.-]+", "_", doi), "titulo": tit2 or tit or doi}
        intentos.append("Crossref")
        url, tit3, err = _pagina(cfg.DOI_ORG.format(doi=doi), cfg)
        if url and _es_pdf(url, cfg):
            return {"url": url, "fuente": "citation_pdf_url", "tipo": "articulo", "numero": re.sub(r"[^A-Za-z0-9.-]+", "_", doi), "titulo": tit3 or tit or tit2 or doi}
        intentos.append("página del DOI" + (f" ({err})" if err else ""))
        return {"error": "sin PDF de acceso abierto: " + ", ".join(intentos)}
    if ref.lower().startswith("http"):
        url, tit, err = _pagina(ref, cfg)
        if url and _es_pdf(url, cfg):
            return {"url": url, "fuente": "citation_pdf_url", "tipo": "documento", "numero": re.sub(r"[^A-Za-z0-9.-]+", "_", urllib.parse.urlparse(ref).path.strip("/"))[-60:], "titulo": tit or ref}
        return {"error": err or "la URL no lleva a un PDF"}
    return {"error": "referencia no reconocida: se espera un DOI (10.xxxx/…) o una URL"}
