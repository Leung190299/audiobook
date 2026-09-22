# thumbnail/storage.py
from datetime import datetime, timezone
from pathlib import Path


def make_stem(trope: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{trope}-{timestamp}"


def save_thumbnail(trope: str, image_bytes: bytes, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{make_stem(trope)}.png"
    output_path.write_bytes(image_bytes)
    return output_path


def save_episode_thumbnail(stem: str, number: int, image_bytes: bytes, output_dir: Path) -> Path:
    """Ảnh của tập N: `<stem>-ep-0N.png`, cùng gốc tên với ảnh truyện `<stem>.png`
    để nhìn thư mục là biết bộ nào đi với nhau."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{stem}-ep-{number:02d}.png"
    output_path.write_bytes(image_bytes)
    return output_path
