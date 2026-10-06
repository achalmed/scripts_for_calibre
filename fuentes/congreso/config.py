# congreso/config.py — normas peruanas: del NÚMERO DE NORMA a su PDF oficial.
#
# Primera fuente del sistema documental. Una norma es un DOCUMENTO (se lee, se
# cita, va a Calibre y a Zotero), no una base de datos: por eso vive aquí y no en
# los conectores de datafw, que adquieren series y microdatos.
#
# La capacidad venía del CIL (scripts_for_fuentes/manifiestos/marco_legal/localizar_normas.py) y al
# migrar gana lo que allí no tenía: validación por bytes mágicos, hash y una fila
# de procedencia. Ver ecosistema/ARQUITECTURA.md §2.

NOMBRE = "congreso"
DESCRIPCION = "Normas peruanas (leyes, decretos legislativos, decretos de urgencia)"
TIPOS = ["ley", "decreto legislativo", "decreto ley", "decreto de urgencia"]

BASE = "https://www.leyes.congreso.gob.pe/Documentos/"

# Periodos parlamentarios del Archivo Digital de la Legislación (ADLP), del más
# reciente al más antiguo: la misma ley puede estar bajo cualquiera de ellos.
PERIODOS = ["2021_2026", "2016_2021", "2011_2016", "2006_2011", "2001_2006", "1995_2000"]

# Patrones de URL por tipo de norma, en orden de preferencia. `{n}` es el número
# normalizado; `{p}` el periodo; `{n5}` el número a cinco dígitos.
PATRONES = {
    "ley": [("{p}/ADLP/Normas_Legales/{n}-LEY.pdf", "Congreso-ADLP"),
            ("Leyes/{n}.pdf", "Congreso-Leyes")],
    "decreto legislativo": [("DecretosLegislativos/{n5}.pdf", "Congreso-DLeg"),
                            ("{p}/ADLP/Normas_Legales/{n}-DL.pdf", "Congreso-ADLP")],
    "decreto ley": [("Leyes/{n}.pdf", "Congreso-Leyes"),
                    ("DecretosLey/{n}.pdf", "Congreso-DLey")],
    "decreto de urgencia": [("DecretosUrgencia/{n}.pdf", "Congreso-DU")],
}

# Búsqueda en la Plataforma del Estado como último recurso. Es RUIDOSA: solo se
# acepta un resultado si el título contiene el número exacto de la norma.
GOBPE_BUSQUEDA = "https://www.gob.pe/busquedas.json?contenido[]=normas&term={term}"
GOBPE_CDN = r"https://cdn\.www\.gob\.pe/uploads/document/file/[^\"]+\.pdf"

# Muchos PDF del ADLP son escaneos sin capa de texto: pasar por
# pipeline/documentos (OCR) antes de citar un artículo literal.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 30
PAUSA = 0.8
LIMITE_MB = 60
