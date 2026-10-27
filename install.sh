#!/usr/bin/env bash
# Установка frdfetch в Termux: кладёт скрипт в $PREFIX/bin/frdfetch.
set -e

SRC="$(cd "$(dirname "$0")" && pwd)/frdfetch.py"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
DEST="$PREFIX/bin/frdfetch"

if [ ! -f "$SRC" ]; then
    echo "Не найден frdfetch.py рядом со скриптом установки" >&2
    exit 1
fi

command -v python3 >/dev/null 2>&1 || { echo "Нужен Python: pkg install python" >&2; exit 1; }

cp "$SRC" "$DEST"
chmod 755 "$DEST"

# В Termux /usr/bin/env может отсутствовать — переписываем shebang на реальный путь
if command -v termux-fix-shebang >/dev/null 2>&1; then
    termux-fix-shebang "$DEST"
fi

echo "Готово: теперь можно запускать командой  frdfetch"
echo "Автозапуск при старте Termux:  echo 'frdfetch' >> ~/.bashrc"
