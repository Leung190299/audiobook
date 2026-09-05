import json
from datetime import datetime, timezone
from pathlib import Path

from images.scene_planner import ScenePlan


def save_scene_images(
    trope: str,
    title: str,
    images: list[tuple[ScenePlan, str, bytes]],
    output_dir: Path,
) -> tuple[list[Path], Path]:
    """Ghi mỗi cảnh một PNG và một metadata JSON gom cảnh theo chương.

    Mốc start/end của cảnh đi kèm trong metadata để stage 4 biết chiếu ảnh nào
    lúc nào và stage 7 biết phần short bắt đầu ở cảnh nào -- không ai phải
    tính lại từ mốc câu.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    image_paths: list[Path] = []
    chapters: dict[int, list[dict]] = {}
    for scene, scene_description, image_bytes in images:
        image_path = (
            output_dir
            / f"{trope}-{timestamp}-chapter-{scene.chapter_index}-scene-{scene.number}.png"
        )
        image_path.write_bytes(image_bytes)
        image_paths.append(image_path)
        chapters.setdefault(scene.chapter_index, []).append(
            {
                "number": scene.number,
                "start_seconds": scene.start_seconds,
                "end_seconds": scene.end_seconds,
                "filename": image_path.name,
                "scene_description": scene_description,
            }
        )

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {
        "trope": trope,
        "title": title,
        "chapters": [
            {"index": index, "scenes": scenes} for index, scenes in chapters.items()
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return image_paths, metadata_path
