# gobpe/config.py — normas peruanas en la Plataforma del Estado (gob.pe): ficha y PDF de cada norma publicada por una
# institución (decretos supremos, resoluciones, y las leyes que un ministerio sube a su página).
#
# Tercera fuente del sistema documental (2026-11-15, para «Traer una norma nueva» de Inteligencia Legislativa). El
# Congreso (`fuentes/congreso`) no tiene los decretos supremos; gob.pe sí, con su sumilla, su fecha de publicación y
# la institución que la dio: lo que el paso 02 necesita para catalogar sin adivinar desde el PDF. Es la página oficial
# de la institución (el PDF lo sube ella), no un agregador.
#
# El buscador es ruidoso (trae normas parecidas): solo se acepta un resultado cuyo número (`name_with_parent`) es
# EXACTAMENTE el pedido y cuyo rótulo dice el mismo tipo de norma.

NOMBRE = "gobpe"
DESCRIPCION = "Normas peruanas en la Plataforma del Estado (gob.pe): decretos supremos, resoluciones y leyes, con su sumilla"
TIPOS = ["ley", "decreto legislativo", "decreto supremo", "decreto de urgencia", "decreto ley",
         "resolución ministerial", "resolución suprema", "resolución legislativa"]

BUSQUEDA = "https://www.gob.pe/busquedas.json?contenido[]=normas&term={term}"
BASE = "https://www.gob.pe"

# Un agente de navegador genérico, sin datos de nadie (la regla de las fuentes externas).
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
TIMEOUT = 30
PAUSA = 0.8
LIMITE_MB = 60
