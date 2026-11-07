import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugin" / "chat_stats.py"
COVER = ROOT / "assets" / "cover.gif"
TARGET = ROOT / "plugins" / "chat_stats" / "chat_stats.plugin"
PLACEHOLDER = 'COVER_GIF = "__COVER_GIF__"'
CHUNK = 200


def main():
    encoded = base64.b64encode(COVER.read_bytes()).decode("ascii")
    rows = [f'    "{encoded[index:index + CHUNK]}"' for index in range(0, len(encoded), CHUNK)]
    literal = "COVER_GIF = (\n" + "\n".join(rows) + "\n)\n"

    source = SOURCE.read_text(encoding="utf-8")
    if PLACEHOLDER not in source:
        raise SystemExit("cover placeholder is gone")
    source = source.replace(PLACEHOLDER, literal.rstrip("\n"))

    compile(source, str(TARGET), "exec")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(source, encoding="utf-8")

    data = TARGET.read_bytes()
    print(f"{TARGET.relative_to(ROOT)}  {len(data)} bytes  sha256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
