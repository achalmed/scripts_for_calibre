#!/usr/bin/env python3
"""lib/enlazar_notas.py — enlaza en la columna «apuntes» de Calibre las notas de lectura que ya existen y no lo están.

Objetivo: que la nota de un libro (`notas/<clave>.md`, la que crean el complemento de KOReader y Zotero Integration)
quede enlazada en su libro aunque se haya creado con Calibre abierto.
Método: lee el índice (`lib/indice.py`) y, por cada libro sin «apuntes» cuya nota existe, llama a la orden que ya
escribe por la puerta: `koreader/main.sh --apuntes ID RUTA TÍTULO`. Este archivo no escribe en ninguna base.
Uso:
    python3 lib/enlazar_notas.py             # simula: qué notas enlazaría
    python3 lib/enlazar_notas.py --aplicar   # las enlaza (con Calibre cerrado; si está abierto, sale 75)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "lib"))
from indice import ruta_indice  # noqa: E402


def pendientes(indice: dict) -> list[tuple[str, str, str]]:
    """[(calibre_id, ruta de la nota, título)] de los libros sin «apuntes» cuya nota ya existe."""
    return [(b, d["nota"], d["titulo"]) for b, d in indice["libros"].items()
            if not d.get("apuntes") and d.get("nota") and Path(d["nota"]).is_file()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Enlaza las notas de lectura en la columna «apuntes» de Calibre.")
    ap.add_argument("--aplicar", action="store_true", help="enlaza (sin esto, simula)")
    a = ap.parse_args(argv)
    ruta = ruta_indice()
    if not ruta.is_file():
        print(f"No hay índice en {ruta}: python3 lib/indice.py --aplicar")
        return 1
    lista = pendientes(json.loads(ruta.read_text(encoding="utf-8")))
    if not lista:
        print("Ninguna nota de lectura por enlazar.")
        return 0
    for b, nota, titulo in lista:
        print(f"{'enlazar' if a.aplicar else '[simulación] enlazaría'} {b} · {titulo} → {nota}")
    if not a.aplicar:
        print(f"[simulación] {len(lista)} nota(s); --aplicar las enlaza por la puerta (Calibre cerrado)")
        return 0
    for b, nota, _titulo in lista:
        r = subprocess.run(["bash", str(RAIZ / "koreader" / "main.sh"), "--apuntes", b, nota, "Apuntes de lectura"])
        if r.returncode != 0:
            print(f"✗ {b}: la puerta devolvió {r.returncode} (75: Calibre abierto u otra suite con el candado)")
            return r.returncode
    subprocess.run([sys.executable, str(RAIZ / "lib" / "indice.py"), "--aplicar"], check=False)
    print(f"✓ {len(lista)} nota(s) enlazada(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
