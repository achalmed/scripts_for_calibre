#!/usr/bin/env bash
# main.sh — campaña de grafías de autores (2026-09-30): Calibre y Zotero en una sola operación.
# Autorizada por el usuario el 2026-09-30. Simulacro previo sobre copia: 0 archivos perdidos, 0 enlaces rotos.
# Uso: main.sh            (aplica; Calibre y Zotero cerrados)
# Deshacer: deshacer.sh
set -euo pipefail
cd "$(dirname "$0")"
AQUI="$PWD"
source "../../../../core/env.sh"
source "$DOCS_ROOT/core/shell-lib/lock.sh"
BIB="$BIBLIOTECA_DIR"
ZOT="${ZOTERO_DB:-$HOME/Zotero/zotero.sqlite}"

if pgrep -x "calibre|calibre-parallel|calibre-server" >/dev/null; then
    echo "Calibre está abierto: ciérralo." >&2; exit 1
fi
if pgrep -x "zotero|zotero-bin" >/dev/null; then
    echo "Zotero está abierto: ciérralo." >&2; exit 1
fi
[ -e hechos.tsv ] && { echo "Ya aplicada (hay hechos.tsv); para repetir, primero deshacer.sh." >&2; exit 1; }

tomar_lock_calibre
export ECOSISTEMA_LOCK_HELD=1

RESP="$AQUI/../../backups/grafias_autores_2026-09-30"
mkdir -p "$RESP"
echo "1/4 respaldo en $RESP"
mkdir -p respaldo
sqlite3 "$BIB/metadata.db" ".backup 'respaldo/metadata.db'"
sqlite3 "$ZOT" ".backup 'respaldo/zotero.sqlite'"
[ -e "$BIB/.calnotes/notes.db" ] && sqlite3 "$BIB/.calnotes/notes.db" ".backup 'respaldo/notes.db'"
python3 - "$BIB" propuesta.tsv > respaldo/carpetas_afectadas.txt <<'E'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}/metadata.db?mode=ro", uri=True)
libros = set()
for l in open(sys.argv[2], encoding="utf-8"):
    if l.startswith(("#", "clase")):
        continue
    k, i, *_ = l.split("\t")
    libros |= {b for (b,) in c.execute("select book from books_authors_link where author = ?", (int(i),))} if k == "autor" else {int(i)}
for b in sorted(libros):
    print(c.execute("select path from books where id = ?", (b,)).fetchone()[0])
E
tar -C "$BIB" -czf "$RESP/backup_carpetas.tar.gz" -T respaldo/carpetas_afectadas.txt
tar -czf "$RESP/backup_bases.tar.gz" respaldo
rm -rf respaldo

echo "2/4 Calibre"
calibre-debug "$AQUI/aplicar_calibre.py" -- "$BIB" "$AQUI/propuesta.tsv" "$AQUI"

echo "3/4 Zotero"
python3 aplicar_zotero.py "$ZOT" "$BIB/metadata.db" "$AQUI"

echo "4/4 OPF de los libros tocados"
calibredb --with-library "$BIB" backup_metadata >/dev/null
echo "hecho; verificar con: python3 verificar.py · deshacer: deshacer.sh"
