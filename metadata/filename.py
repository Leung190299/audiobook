import re
import unicodedata
from pathlib import Path


def slugify(title: str, max_length: int = 100) -> str:
    normalized = unicodedata.normalize("NFD", title)
    without_accents = "".join(
        c for c in normalized if unicodedata.category(c) != "Mn"
    )
    without_accents = without_accents.replace("Đ", "D").replace("đ", "d")
    lowered = without_accents.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")

    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def rename_video_file(video_path: Path, title: str) -> Path:
    slug = slugify(title)
    new_path = video_path.with_name(f"{slug}{video_path.suffix}")
    video_path.rename(new_path)
    return new_path
