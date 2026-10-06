"""migraciones/leer_campos.py — lee, por la API de Calibre y en solo lectura, los campos de una lista de libros (ola 2b).

Uso (dentro de calibre-debug): calibre-debug -e leer_campos.py BIBLIOTECA PEDIDO.json SALIDA.json
PEDIDO = {campo: [libros]}; SALIDA = {campo: {libro: valor}} (listas y tuplas como listas; fechas en ISO).
"""
import json
import sys
from pathlib import Path

from calibre.library import db as calibre_db

biblioteca, pedido, salida = sys.argv[1:4]
api = calibre_db(biblioteca, read_only=True).new_api
out = {}
for campo, libros in json.loads(Path(pedido).read_text(encoding="utf-8")).items():
    vals = {}
    for b in libros:
        v = api.field_for(campo, int(b))
        if isinstance(v, (tuple, set, frozenset)):
            v = sorted(v) if campo == "tags" else list(v)
        elif hasattr(v, "isoformat"):
            v = v.isoformat()
        vals[str(b)] = v
    out[campo] = vals
Path(salida).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
