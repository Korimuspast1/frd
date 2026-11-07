import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
INDEX = ROOT / "extera-plugins.json"

REPOSITORY = {
    "schema": 1,
    "name": "ox4gg plugins",
    "description": "Плагины для exteraGram",
    "author": "@ox4gg",
    "homepage": "https://github.com/Korimuspast1/frd",
}

FIELDS = (
    "id",
    "name",
    "description",
    "author",
    "version",
    "icon",
    "app_version",
    "sdk_version",
    "requirements",
    "category",
)


def metadata(path):
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id.startswith("__") and target.id.endswith("__"):
            key = target.id[2:-2]
            if key in FIELDS:
                values[key] = ast.literal_eval(node.value)
    return values


def main():
    previous = {}
    if INDEX.exists():
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        previous = {item["id"]: item for item in payload.get("plugins", [])}

    plugins = []
    for path in sorted(PLUGINS.rglob("*.plugin")):
        meta = metadata(path)
        missing = [key for key in ("id", "name", "version") if not meta.get(key)]
        if missing:
            raise SystemExit(f"{path}: missing {', '.join(missing)}")
        if isinstance(meta.get("requirements"), list):
            meta["requirements"] = ", ".join(meta["requirements"])

        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        entry = {
            **meta,
            "file": path.relative_to(ROOT).as_posix(),
            "sha256": digest,
            "size": len(data),
        }
        old = previous.get(meta["id"], {})
        if old.get("sha256") == digest and old.get("updated_at"):
            entry["updated_at"] = old["updated_at"]
        else:
            entry["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plugins.append(entry)

    INDEX.write_text(
        json.dumps({**REPOSITORY, "plugins": plugins}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{INDEX.name}: {len(plugins)} plugin(s)")


if __name__ == "__main__":
    main()
