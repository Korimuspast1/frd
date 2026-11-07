"""Сборка плагина «Тамагочи»: вшивает гифки питомцев в исходник.

Берёт plugin/pet.py (шаблон с маркером PET_GIFS), подставляет base64
гифок из assets/pets/ и кладёт готовый файл в plugins/tamagochi/.
Имена файлов: <вид>_<стадия>.gif, стадии 0..3.
"""

import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugin" / "pet.py"
PETS = ROOT / "assets" / "pets"
TARGET = ROOT / "plugins" / "tamagochi" / "tamagochi.plugin"
MARKER = "PET_GIFS = {}  # __PET_GIFS__"
CHUNK = 200


def gif_literal(path):
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    rows = ['        "%s"' % encoded[index:index + CHUNK]
            for index in range(0, len(encoded), CHUNK)]
    return "(\n" + "\n".join(rows) + "\n    )"


def main():
    gifs = sorted(PETS.glob("*.gif"))
    if not gifs:
        raise SystemExit("no pet gifs found in assets/pets/")

    entries = []
    for path in gifs:
        key = path.stem  # например "dragon_0"
        if key == "preview":
            continue
        entries.append('    "%s": %s,' % (key, gif_literal(path)))

    literal = "PET_GIFS = {\n" + "\n".join(entries) + "\n}"

    source = SOURCE.read_text(encoding="utf-8")
    if MARKER not in source:
        raise SystemExit("pet gifs placeholder is gone")
    source = source.replace(MARKER, literal)

    compile(source, str(TARGET), "exec")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(source, encoding="utf-8")

    data = TARGET.read_bytes()
    print("%s  %d bytes  sha256 %s" % (
        TARGET.relative_to(ROOT), len(data), hashlib.sha256(data).hexdigest()))
    print("gifs embedded: %d" % len(entries))


if __name__ == "__main__":
    main()
