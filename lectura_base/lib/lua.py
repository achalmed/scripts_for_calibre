"""lectura_base/lib/lua.py — leer y escribir las tablas que serializa KOReader (`metadata.<ext>.lua`).

El lector es el de Yachay (`yachay/lector.py`, `_Lua`, 2026-11-17), con un cambio: el archivo se lee como bytes
(latin-1, uno a uno) y cada cadena se decodifica en UTF-8 al final, así un `\\ddd` por byte y un carácter escrito tal cual
dan lo mismo. El escritor imita `dump.lua` de KOReader (claves ordenadas, `["clave"] = valor,`, cuatro espacios, cadenas
con el `%q` de Lua), de modo que lo que se lee y se vuelve a escribir sin cambios queda igual para KOReader.
"""
from __future__ import annotations

import re

NAN, INF = float("nan"), float("inf")      # KOReader escribe `nan` (un percent_finished de 0/0) e `inf` tal cual
_NUMERO = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_NOMBRE = re.compile(r"[A-Za-z_]\w*\s*=")


class _Lua:
    def __init__(self, t: str):
        self.t, self.i = t, 0

    def _esp(self):
        t = self.t
        while self.i < len(t):
            if t[self.i].isspace():
                self.i += 1
            elif t.startswith("--", self.i):
                fin = t.find("\n", self.i)
                self.i = len(t) if fin < 0 else fin + 1
            else:
                break

    def valor(self):
        self._esp()
        t = self.t
        if t.startswith("return", self.i):
            self.i += 6
            return self.valor()
        c = t[self.i]
        if c == "{":
            return self._tabla()
        if c in "\"'":
            return self._cadena()
        for palabra, v in (("true", True), ("false", False), ("nil", None), ("-nan", NAN), ("nan", NAN), ("-inf", -INF),
                           ("inf", INF)):
            if t.startswith(palabra, self.i):
                self.i += len(palabra)
                return v
        m = _NUMERO.match(t, self.i)
        if not m:
            raise ValueError(f"Lua: no se entiende en {self.i}")
        self.i = m.end()
        n = m.group(0)
        return float(n) if any(x in n for x in ".eE") else int(n)

    def _cadena(self) -> str:
        t, q = self.t, self.t[self.i]
        self.i += 1
        partes = []
        escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "\n": "\n", "a": "\a", "b": "\b",
                   "f": "\f", "v": "\v"}
        while t[self.i] != q:
            c = t[self.i]
            if c == "\\":
                s = t[self.i + 1]
                if s.isdigit():
                    m = re.compile(r"\d{1,3}").match(t, self.i + 1)
                    partes.append(chr(int(m.group(0))))
                    self.i = m.end()
                    continue
                partes.append(escapes.get(s, s))
                self.i += 2
                continue
            partes.append(c)
            self.i += 1
        self.i += 1
        return "".join(partes).encode("latin-1", "replace").decode("utf-8", "replace")

    def _tabla(self):
        self.i += 1
        dic: dict = {}
        lista: list = []
        while True:
            self._esp()
            if self.t[self.i] == "}":
                self.i += 1
                break
            if self.t[self.i] == "[":
                self.i += 1
                clave = self.valor()
                self._esp()
                self.i += 1                                  # ]
                self._esp()
                self.i += 1                                  # =
                dic[clave] = self.valor()
            else:
                m = _NOMBRE.match(self.t, self.i)
                if m:
                    clave = m.group(0)[:-1].strip()
                    self.i = m.end()
                    dic[clave] = self.valor()
                else:
                    lista.append(self.valor())
            self._esp()
            if self.t[self.i] in ",;":
                self.i += 1
        if lista and not dic:
            return lista
        for k, v in enumerate(lista, 1):
            dic[k] = v
        return dic


def leer(datos: bytes | str):
    """El valor que devuelve un archivo de KOReader (`return {…}`), con las cadenas en UTF-8."""
    if isinstance(datos, bytes):
        datos = datos.decode("latin-1")
    else:
        datos = datos.encode("utf-8").decode("latin-1")
    return _Lua(datos).valor()


def _cadena(s: str) -> str:
    """El `%q` de Lua 5.1: barra, comillas y controles escapados; el salto de línea como «\\» y un salto real."""
    salida = []
    for c in s:
        if c == "\\":
            salida.append("\\\\")
        elif c == '"':
            salida.append('\\"')
        elif c == "\n":
            salida.append("\\\n")
        elif c == "\r":
            salida.append("\\r")
        elif c == "\0":
            salida.append("\\0")
        elif ord(c) < 32 or ord(c) == 127:
            salida.append(f"\\{ord(c)}")
        else:
            salida.append(c)
    return '"' + "".join(salida) + '"'


def _numero(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if v != v:
        return "nan"
    if v in (INF, -INF):
        return "inf" if v > 0 else "-inf"
    if float(v).is_integer() and abs(v) < 1e15:
        return str(int(v)) if "e" not in format(v, ".14g") else format(v, ".14g")
    return format(v, ".14g")


def _orden(k):
    return (0, k, "") if isinstance(k, (int, float)) and not isinstance(k, bool) else (1, 0, str(k))


def _valor(v, nivel: int) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return _numero(v)
    if isinstance(v, str):
        return _cadena(v)
    if isinstance(v, (list, tuple)):
        v = {i: x for i, x in enumerate(v, 1)}
    if isinstance(v, dict):
        if not v:
            return "{}"
        sangria = "    " * (nivel + 1)
        lineas = ["{"]
        for k in sorted(v, key=_orden):
            clave = f"[{_numero(k)}]" if isinstance(k, (int, float)) and not isinstance(k, bool) else f"[{_cadena(str(k))}]"
            lineas.append(f"{sangria}{clave} = {_valor(v[k], nivel + 1)},")
        lineas.append("    " * nivel + "}")
        return "\n".join(lineas)
    raise TypeError(f"Lua: no se escribe {type(v).__name__}")


def escribir(valor, ruta_original: str = "") -> bytes:
    """El archivo completo, en bytes UTF-8, como lo deja KOReader (`-- <ruta>` y `return {…}`)."""
    cabeza = f"-- {ruta_original}\n" if ruta_original else "-- we can read Lua syntax here!\n"
    return (cabeza + "return " + _valor(valor, 0) + "\n").encode("utf-8")
