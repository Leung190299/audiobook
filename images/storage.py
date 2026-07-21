import json
from datetime import datetime, timezone
from pathlib import Path


def save_chapter_images(
    trope: str,
    title: str,
    images: list[tuple[int, str, bytes]],
    output_dir: Path,
) -> tuple[list[Path], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    image_paths = []
    metadata_chapters = []
    for chapter_index, scene_description, image_bytes in images:
        image_path = output_dir / f"{trope}-{timestamp}-chapter-{chapter_index}.png"
        image_path.write_bytes(image_bytes)
        image_paths.append(image_path)
        metadata_chapters.append(
            {
                "index": chapter_index,
                "filename": image_path.name,
                "scene_description": scene_description,
            }
        )

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {"trope": trope, "title": title, "chapters": metadata_chapters}
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return image_paths, metadata_path
