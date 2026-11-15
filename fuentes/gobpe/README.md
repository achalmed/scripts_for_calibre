---
tipo: readme
estado: activo
---
# fuentes/gobpe/ — normas peruanas en la Plataforma del Estado (gob.pe)

Conector de la suite `fuentes` (2026-11-15) para las normas que publica cada institución en su página de gob.pe:
decretos supremos, resoluciones y las leyes que un ministerio sube. Además de la URL del PDF, `localizar.py` devuelve la
**sumilla**, la **fecha de publicación** y el **emisor**, que `main.py traer` usa para catalogar la norma sin adivinar
desde el PDF. Se usa con `main.py localizar gobpe "D.S. 005-2002-EF"` y `main.py descargar gobpe …`.

- El buscador de gob.pe es ruidoso: solo se acepta el resultado cuyo número es exactamente el pedido y cuyo rótulo es
  el mismo tipo de norma; con varios, el de la institución cuya sigla está en el número (EF → MEF).
- Una ley la da el Congreso aunque la suba un ministerio: su emisor es «Congreso de la República».
- La fecha es la que gob.pe da como publicación: a veces no es la de la norma; `traer` la muestra para revisarla.
- Solo lectura y una consulta por cita, con pausa y un agente de navegador genérico.
