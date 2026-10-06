#!/usr/bin/env python3
# ris.py — genera un .ris por lote con el MISMO mapeo que el plugin ZMI (contrato del
# prompt_03_zotero): TY/T1/AU/DA/PB/SN/SP/ET/T2/M1/KW/LA/DB/L1/ID. Importar en Zotero
# (Archivo → Importar, «enlazar a los archivos») crea los ítems con el archivo enlazado
# desde su carpeta de Calibre.
#
# Cada entrada sale de Calibre TAL COMO ESTÁ HOY (`biblioteca.ris`), no de las columnas del
# registro: hasta 2026-09-30 se copiaban del registro y fallaban dos veces. La ruta envejecía
# cuando Calibre movía la carpeta (279 enlaces muertos en los .ris del 2 al 28 de septiembre),
# y `AU` llevaba el «Nombre, Apellidos» de Calibre, que Zotero lee como «Apellido, Nombre».
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PY_COMMON") or str(Path(__file__).resolve().parents[3] / "core" / "py-common"))
import biblioteca as bib  # noqa: E402

ledger, salida = Path(sys.argv[1]), Path(sys.argv[2])
out, perdidos = [], []
for r in csv.DictReader(open(ledger, encoding="utf-8"), delimiter="\t"):
    if r.get("estado") not in ("catalogado", "archivado") or r.get("zotero_key"):
        continue   # todo lo que aún no tiene clave de Zotero
    d = bib.datos(int(r["calibre_id"])) if (r.get("calibre_id") or "").isdigit() else None
    if not d or d.get("zotero_key"):   # borrado de Calibre, o ya enlazado por ZMI o a mano
        perdidos += [] if d else [r.get("calibre_id") or r.get("titulo", "")]
        continue
    out.append(bib.ris(d))
salida.write_text("\n".join(out), encoding="utf-8")
print(f"[ris] {len(out)} ítems → {salida}" + (f" · {len(perdidos)} sin libro en Calibre: {', '.join(perdidos[:5])}" if perdidos else ""))
