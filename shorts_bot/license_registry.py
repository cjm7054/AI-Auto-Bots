import json
from pathlib import Path
from datetime import datetime


def init_manifest(manifest_path: str, video_title: str, topic: str, category: str):
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "video_title": video_title,
        "topic": topic,
        "category": category,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "assets": []
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


def add_asset(manifest_path: str, asset: dict):
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"manifest file not found: {manifest_path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("assets", []).append(asset)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_manifest(manifest_path: str) -> dict:
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
