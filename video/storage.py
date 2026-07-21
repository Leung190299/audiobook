# video/storage.py
import json
from datetime import datetime, timezone
from pathlib import Path


def save_video_props(video_props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    props_path = output_dir / f"{video_props['trope']}-{timestamp}.json"
    props_path.write_text(
        json.dumps(video_props, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return props_path
