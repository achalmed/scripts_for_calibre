"""biblioteca_app/servicios/pasos.py — los seis pasos de una escritura por la puerta, tal como la ventana los ve
(reingeniería B9), sin Qt.

La ventana NO abre ni cierra la puerta: eso lo hacen `lib/escribir.sh` y `lib/escribir.py` dentro de cada suite. Aquí
solo se lleva la cuenta de lo que se puede observar desde fuera:

1. la aplicación cerrada y 2. el candado libre — antes de aplicar, por `servicios/puerta.py` (lo mismo que deshabilita
   Aplicar); durante, por los «✗ … está abierto» de la puerta y el código 75;
3. el respaldo verificado — la línea «── Backup: <ruta>» que imprimen las dos puertas, o «✗ Sin respaldo verificado»;
4. aplicar — la suite corriendo tras el respaldo, hasta su código de salida;
5. la integridad — «✗ INTEGRIDAD FALLIDA» de la puerta o, al terminar, `lib/escribir.py integridad` (solo lectura)
   sobre las bases que la operación toca;
6. liberar — al terminar el proceso, que el candado haya quedado libre.

Una operación que no escribe en ninguna base no tiene pasos de puerta (`aplica()` es falso). Los pasos son los de
`LineaPasos` de gui-comun 3.1 (`gui_comun.pasos`: `linea`, `fijar`, `ESTADOS`, `NIVEL`); aquí queda lo propio de la
puerta: qué paso es cada línea de la salida de una suite.
"""
from __future__ import annotations

from gui_comun.pasos import ESTADOS, NIVEL, fijar as _fijar, linea as _linea_de_pasos  # noqa: F401  (ESTADOS: API)

PASOS = (
    ("cerrada", "La aplicación está cerrada", "Calibre (o Zotero) no puede estar abierto mientras se escribe"),
    ("candado", "Candado tomado", "una sola suite escribe a la vez (LOCK_CALIBRE, LOCK_ZOTERO)"),
    ("respaldo", "Respaldo verificado", "copia consistente de la base con quick_check = ok, antes de tocarla"),
    ("aplicar", "Aplicar los cambios", "la suite escribe por calibredb, la API de Calibre o las primitivas de Zotero"),
    ("integridad", "Integridad verificada", "PRAGMA integrity_check de cada base tocada"),
    ("liberar", "Candado liberado", "al terminar, la base queda libre para las demás suites y los timers"),
)


def nuevos(bases: tuple[str, ...] | list[str] = ()) -> list[dict]:
    """Los seis pasos en espera, para una operación que escribe en `bases`."""
    que = " y ".join({"calibre": "Calibre", "zotero": "Zotero"}.get(b, b) for b in bases) or "la base"
    cerrada = f"{que} cerrado" + ("s" if len(bases) > 1 else "")
    return _linea_de_pasos([(c, cerrada if c == "cerrada" else t, e) for c, t, e in PASOS])


def _estado(pasos: list[dict], clave: str) -> str:
    return next(p["estado"] for p in pasos if p["clave"] == clave)


def previa(pasos: list[dict], abiertas: set[str], candados_ocupados: set[str], bases) -> list[dict]:
    """Antes de aplicar: los pasos 1 y 2 como los ve `servicios/puerta.py` (no se toma nada: solo se mira)."""
    abiertas_aqui = [b for b in bases if b in abiertas]
    ocupados_aqui = [b for b in bases if b in candados_ocupados]
    if abiertas_aqui:
        _fijar(pasos, "cerrada", "fallo", ", ".join(b.capitalize() for b in abiertas_aqui) + " está abierto")
    else:
        _fijar(pasos, "cerrada", "hecho", "cerrado ahora")
    if ocupados_aqui:
        _fijar(pasos, "candado", "fallo", "lo tiene otra suite o un timer")
    else:
        _fijar(pasos, "candado", "pendiente", "libre ahora; la suite lo toma al abrir la puerta")
    return pasos


def empezar(pasos: list[dict]) -> list[dict]:
    """La suite arrancó con --aplicar: la puerta está comprobando la aplicación y tomando el candado."""
    for p in pasos:
        if p["estado"] != "fallo":
            p["estado"], p["nivel"] = "pendiente", NIVEL["pendiente"]
    _fijar(pasos, "cerrada", "en_curso")
    return pasos


def linea(pasos: list[dict], texto: str) -> bool:
    """Una línea de la salida de la suite; ¿cambió algún paso?"""
    t = texto.strip()
    if t.startswith("── Backup:"):
        _fijar(pasos, "cerrada", "hecho")
        _fijar(pasos, "candado", "hecho", "tomado por la suite")
        _fijar(pasos, "respaldo", "hecho", t.removeprefix("── Backup:").strip().rsplit("/", 1)[-1])
        _fijar(pasos, "aplicar", "en_curso")
        return True
    if "está abierto" in t and t.startswith("✗"):
        _fijar(pasos, "cerrada", "fallo", t.lstrip("✗ ").strip())
        return True
    if "Sin respaldo verificado" in t:
        _fijar(pasos, "cerrada", "hecho")
        _fijar(pasos, "candado", "hecho")
        _fijar(pasos, "respaldo", "fallo", "sin respaldo verificado no se escribe")
        return True
    if "INTEGRIDAD FALLIDA" in t:
        _fijar(pasos, "aplicar", "hecho")
        _fijar(pasos, "integridad", "fallo", "restaura el respaldo (vista Puerta)")
        return True
    return False


def terminar(pasos: list[dict], codigo: int, integridad_ok: bool | None, candado_libre: bool) -> list[dict]:
    """Al terminar el proceso: el código de salida, la integridad leída después y si el candado quedó libre."""
    respaldo = _estado(pasos, "respaldo")
    if codigo == 75 and respaldo != "hecho":
        if _estado(pasos, "cerrada") != "fallo":
            _fijar(pasos, "candado", "fallo", "ocupado (75): reintenta cuando termine la otra suite")
        for clave in ("respaldo", "aplicar", "integridad"):
            _fijar(pasos, clave, "omitido")
    elif respaldo == "hecho":
        _fijar(pasos, "aplicar", "hecho" if codigo == 0 else "fallo", "" if codigo == 0 else f"la suite terminó con código {codigo}")
        if _estado(pasos, "integridad") != "fallo":
            if integridad_ok is None:
                _fijar(pasos, "integridad", "omitido", "no se pudo comprobar")
            else:
                _fijar(pasos, "integridad", "hecho" if integridad_ok else "fallo", "integrity_check = ok" if integridad_ok else "restaura el respaldo (vista Puerta)")
    else:
        # la suite terminó sin abrir la puerta: no escribió (nada que aplicar, o falló antes del respaldo)
        if _estado(pasos, "cerrada") == "en_curso":
            _fijar(pasos, "cerrada", "hecho" if codigo == 0 else "fallo", "" if codigo == 0 else f"código {codigo}")
        for clave in ("candado", "respaldo", "aplicar", "integridad"):
            if _estado(pasos, clave) in ("pendiente", "en_curso"):
                _fijar(pasos, clave, "omitido", "la suite no abrió la puerta (nada que escribir)" if codigo == 0 and clave == "candado" else "")
    _fijar(pasos, "liberar", "hecho" if candado_libre else "fallo", "libre" if candado_libre else "sigue ocupado: ¿otra suite o un timer?")
    return pasos


def resumen(pasos: list[dict]) -> str:
    """«4 de 6 pasos · falló: Respaldo verificado»."""
    hechos = sum(p["estado"] == "hecho" for p in pasos)
    fallo = next((p["titulo"] for p in pasos if p["estado"] == "fallo"), "")
    return f"{hechos} de {len(pasos)} pasos" + (f" · falló: {fallo}" if fallo else "")
