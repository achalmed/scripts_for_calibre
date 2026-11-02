"""biblioteca_app/servicios/puerta.py — el estado de la puerta de escritura y de las tareas automáticas, sin Qt.

Solo lee: si Calibre y Zotero corren (`/proc`, el mismo criterio que `core/shell-lib/detectar_apps.sh`), si los
candados `LOCK_CALIBRE` y `LOCK_ZOTERO` están ocupados (flock compartido sin esperar), los respaldos que la puerta
dejó (`$RESPALDOS_DIR/biblioteca/puerta/<suite>/` con el SSD montado; si no, el estado de usuario: la regla de
`lib/escribir.raiz_respaldos`) y los timers de usuario (`systemctl --user`, en JSON).
"""
from __future__ import annotations

import fcntl
import getpass
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

NOMBRE_BASE = {"calibre": "Calibre", "zotero": "Zotero"}
UNIDADES = ("ecosistema-lectura", "ecosistema-metadatos", "koreader-calibre-sync")


def abiertas() -> set[str]:
    """«calibre» y «zotero» si su proceso corre."""
    vistas = set()
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            nombre = comm.read_text().strip().lower()
        except OSError:
            continue
        for app in NOMBRE_BASE:
            if nombre.startswith(app):
                vistas.add(app)
    return vistas


def candado_ocupado(ruta: str | os.PathLike) -> bool:
    """¿Alguna suite tiene el candado? Se prueba sin quedárselo (flock compartido, sin esperar)."""
    p = Path(ruta) if ruta else None
    if not p or not p.exists():
        return False
    try:
        with open(p) as f:
            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        return False
    except OSError:
        return True


def raiz_respaldos() -> Path:
    """La misma regla que `lib/escribir.raiz_respaldos`, sin avisos: PUERTA_RESPALDOS; el SSD si está montado; si no,
    el estado de usuario."""
    if os.environ.get("PUERTA_RESPALDOS"):
        return Path(os.environ["PUERTA_RESPALDOS"])
    ssd = Path(os.environ.get("ARCHDISK_DIR") or Path("/run/media") / (os.environ.get("USER") or getpass.getuser()) / "ARCHDISK")
    if os.path.ismount(ssd):
        return Path(os.environ.get("RESPALDOS_DIR") or ssd / "respaldos") / "biblioteca" / "puerta"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "biblioteca" / "respaldos"


def respaldos(raiz: Path | None = None) -> list[dict]:
    """Una fila por suite con respaldos: cuántos archivos hay y cuándo se escribió el último."""
    raiz = Path(raiz) if raiz else raiz_respaldos()
    salida = []
    if not raiz.is_dir():
        return salida
    for d in sorted(p for p in raiz.iterdir() if p.is_dir()):
        archivos = [p for p in d.rglob("*") if p.is_file()]
        ultimo = max((p.stat().st_mtime for p in archivos), default=0.0)
        salida.append({"suite": d.name, "n": len(archivos), "ultimo_ts": ultimo, "carpeta": str(d),
                       "ultimo": datetime.fromtimestamp(ultimo).strftime("%Y-%m-%d %H:%M") if ultimo else "—"})
    return salida


def _hora(microsegundos) -> str:
    try:
        return datetime.fromtimestamp(int(microsegundos) / 1_000_000).strftime("%Y-%m-%d %H:%M") if microsegundos else "—"
    except (ValueError, OSError, OverflowError):
        return "—"


def timers(unidades: tuple[str, ...] = UNIDADES) -> list[dict]:
    """Las tareas automáticas de la biblioteca: próxima y última corrida (list-timers) y el resultado del servicio (show)."""
    try:
        r = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--no-pager", "--output=json"],
                           capture_output=True, text=True, timeout=5)
        lista = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return [{"unidad": u + ".timer", "activo": "?", "proxima": "—", "ultima": "—", "resultado": "systemd no responde",
                 "nivel": "inactivo"} for u in unidades]
    por_unidad = {t.get("unit", ""): t for t in lista}
    salida = []
    for u in unidades:
        t = por_unidad.get(u + ".timer")
        fila = {"unidad": u + ".timer", "activo": "instalado" if t else "no instalado", "proxima": _hora(t.get("next")) if t else "—",
                "ultima": _hora(t.get("last")) if t else "—", "resultado": "—", "nivel": "neutro" if t else "inactivo"}
        if t:
            try:
                s = subprocess.run(["systemctl", "--user", "show", u + ".service", "-p", "Result,ExecMainStatus,ActiveState", "--no-pager"],
                                   capture_output=True, text=True, timeout=5).stdout
                campos = dict(l.split("=", 1) for l in s.splitlines() if "=" in l)
                codigo = campos.get("ExecMainStatus", "")
                estado = campos.get("ActiveState", "")
                if estado == "active":
                    fila["resultado"], fila["nivel"] = "corriendo", "activo"
                elif codigo in ("0", ""):
                    fila["resultado"], fila["nivel"] = "bien", "positivo"
                elif codigo == "75":
                    fila["resultado"], fila["nivel"] = "aplazada (75: aplicación abierta o candado ocupado)", "neutro"
                else:
                    fila["resultado"], fila["nivel"] = f"falló (código {codigo})", "negativo"
            except (OSError, subprocess.SubprocessError):
                pass
        salida.append(fila)
    return salida
