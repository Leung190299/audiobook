# thumbnail/storage.py
from datetime import datetime, timezone
from pathlib import Path


def save_thumbnail(trope: str, image_bytes: bytes, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    output_path = output_dir / f"{trope}-{timestamp}.png"
    output_path.write_bytes(image_bytes)

    return output_path
