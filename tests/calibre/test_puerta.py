"""tests/test_puerta.py — una sola puerta de escritura en las bases de Calibre y Zotero (ola 2a, K2; RQ-PRE-06).

Objetivo: que ningún archivo de código del repo fuera de `lib/escribir.{py,sh}` y `lib/escribir_zotero.py` escriba en
  las bases: ni `calibredb` con un subcomando que escribe, ni la API de Calibre (`set_field`…), ni una
  conexión SQLite que no sea de solo lectura, ni SQL que modifique (`UPDATE … SET`, `INSERT INTO`…).
Método: búsqueda por texto en los `.py` y `.sh` rastreados y nuevos (sin `tests/`), línea a línea, sin
  comentarios ni mensajes (`echo`, `printf`, `log_*`, `print(`). Dos pruebas de la prueba: un escritor
  rebelde en un árbol de juguete la hace fallar y uno limpio no.
Límite: es una heurística de texto (como la parte D de RQ-PRE-06 en el doctor); un escritor que arme el
  comando por partes la burla. `PENDIENTES` lista lo que aún no pasa por la puerta, con el ítem que lo
  corrige: la prueba exige que sigan ahí (si se arreglan, se quitan de la lista).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PUERTA = {"lib/escribir.py", "lib/escribir.sh", "lib/escribir_zotero.py"}
FUERA = ("tests/",)   # las campañas de script_normalizacion_metadatos salieron al historial de git en K8

# archivo → ítem de la ola 2a que lo pasa por la puerta
PENDIENTES = {
}

SUB_ESCRITURA = (r"add|add_format|remove|remove_format|set_metadata|set_custom|add_custom_column|"
                 r"remove_custom_column|embed_metadata|backup_metadata|restore_database|clone|fts_index")
REGLAS = {
    "calibredb que escribe": re.compile(rf"\bcalibredb\b(?!_escribe).*?\s(?:{SUB_ESCRITURA})\b"
                                        rf"|[\"']calibredb[\"']\s*,\s*[\"'](?:{SUB_ESCRITURA})[\"']"),
    "API de Calibre que escribe": re.compile(r"\.(?:set_field|set_metadata|add_format|add_books|remove_books|"
                                             r"create_custom_column|set_custom)\s*\("),
    "SQL que modifica": re.compile(r"\b(?:UPDATE\s+\w+\s+SET|INSERT\s+(?:OR\s+\w+\s+)?INTO|DELETE\s+FROM|"
                                   r"REPLACE\s+INTO|ALTER\s+TABLE|DROP\s+TABLE)\b", re.I),
}
CONEXION_PY = re.compile(r"sqlite3\.connect\(")
SQLITE_SH = re.compile(r"(?:^|[\s;(|&`$])sqlite3\s+(?!-version)")
MENSAJE = re.compile(r"^\s*(?:#|echo\b|printf\b|log_\w+\b|print\(|\"\"\"|''')")


def _archivos(raiz: Path):
    salida = subprocess.run(["git", "-C", str(raiz), "ls-files", "-co", "--exclude-standard", "-z"],
                            capture_output=True, check=True).stdout.decode()
    for rel in sorted(filter(None, salida.split("\0"))):
        if rel.endswith((".py", ".sh")) and rel not in PUERTA and not rel.startswith(FUERA) \
                and (raiz / rel).is_file():
            yield rel


# En Bash, lo que no es código: un comentario al final de la línea y el texto de un mensaje
# (`log_*`/`echo`/`printf` con su argumento entre comillas) aunque la línea siga con código (fusión, ola 2).
_COMENTARIO_SH = re.compile(r"\s#(?![!{]).*$")
_MENSAJE_SH = re.compile(r"\b(?:log_\w+|echo|printf)\s+\"[^\"]*\"")


def _sin_mensajes(linea: str) -> str:
    return _MENSAJE_SH.sub("", _COMENTARIO_SH.sub("", linea))


def escritores(raiz: Path) -> list[tuple[str, int, str, str]]:
    """[(archivo, línea, regla, texto)] de toda escritura fuera de la puerta."""
    hallazgos = []
    for rel in _archivos(raiz):
        for n, linea in enumerate((raiz / rel).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MENSAJE.match(linea):
                continue
            codigo = _sin_mensajes(linea) if rel.endswith(".sh") else linea
            for regla, patron in REGLAS.items():
                if patron.search(codigo):
                    hallazgos.append((rel, n, regla, linea.strip()))
            if rel.endswith(".py") and CONEXION_PY.search(linea) and ("mode=ro" not in linea or " if " in linea):
                hallazgos.append((rel, n, "conexión SQLite de escritura", linea.strip()))
            if rel.endswith(".sh") and SQLITE_SH.search(linea) and not re.search(r"-readonly|mode=ro", linea) \
                    and not re.search(r"command -v sqlite3|for cmd in", linea):
                hallazgos.append((rel, n, "sqlite3 sin solo lectura", linea.strip()))
    return hallazgos


def _repo_de_juguete(tmp_path, archivos: dict) -> Path:
    for rel, texto in archivos.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_un_escritor_rebelde_hace_fallar_la_prueba(tmp_path):
    raiz = _repo_de_juguete(tmp_path, {
        "suite/main.sh": 'calibredb set_custom --with-library "$B" col 1 x\nsqlite3 "$DB" "select 1"\n',
        "suite/lib/sync.py": 'import sqlite3\nc = sqlite3.connect(db)\nc.execute("UPDATE books SET pubdate=?")\n'
                             'api.set_field("#x", {1: 2})\n',
        "lib/escribir.sh": 'calibredb "$sub" --with-library "$B" "$@"\n',
    })
    reglas = {(h[0], h[2]) for h in escritores(raiz)}
    assert reglas == {
        ("suite/main.sh", "calibredb que escribe"), ("suite/main.sh", "sqlite3 sin solo lectura"),
        ("suite/lib/sync.py", "conexión SQLite de escritura"), ("suite/lib/sync.py", "SQL que modifica"),
        ("suite/lib/sync.py", "API de Calibre que escribe"),
    }


def test_un_lector_limpio_no_la_hace_fallar(tmp_path):
    raiz = _repo_de_juguete(tmp_path, {
        "suite/main.sh": '# calibredb set_custom en un comentario\necho "calibredb add x"\n'
                         'calibredb_escribe set_custom col 1 x\nsqlite3 -readonly "$DB" "select 1"\n'
                         'command -v sqlite3 >/dev/null\n',
        "suite/lib/leer.py": 'import sqlite3\nc = sqlite3.connect(f"file:{db}?mode=ro", uri=True)\n'
                             'c.execute("select * from books where id=?")\n',
    })
    assert escritores(raiz) == []


def test_ningun_escritor_fuera_de_la_puerta():
    hallazgos = escritores(REPO)
    fuera = [h for h in hallazgos if h[0] not in PENDIENTES]
    assert fuera == [], "escrituras fuera de la puerta:\n" + "\n".join(f"{a}:{n} [{r}] {t}" for a, n, r, t in fuera)
    resueltos = set(PENDIENTES) - {h[0] for h in hallazgos}
    assert not resueltos, f"ya pasan por la puerta: quítalos de PENDIENTES: {sorted(resueltos)}"
