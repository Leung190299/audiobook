# video/props_builder.py
from pathlib import Path

from scripts.models import Script


class PropsBuildError(Exception):
    pass


def build_video_props(
    script: Script,
    tts_metadata: dict,
    images_metadata: dict,
    audio_path: Path,
    images_dir: Path,
    repo_root: Path,
) -> dict:
    for source_name, source in (("tts", tts_metadata), ("images", images_metadata)):
        if source["trope"] != script.trope or source["title"] != script.title:
            raise PropsBuildError(
                f"trope/title của {source_name}_metadata không khớp với script "
                f"(script: {script.trope!r}/{script.title!r}, "
                f"{source_name}: {source['trope']!r}/{source['title']!r})"
            )

    script_indices = {c.index for c in script.chapters}
    tts_by_index = {c["index"]: c for c in tts_metadata["chapters"]}
    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}

    missing_in_tts = script_indices - tts_by_index.keys()
    missing_in_images = script_indices - images_by_index.keys()
    if missing_in_tts or missing_in_images:
        raise PropsBuildError(
            f"Thiếu chương trong dữ liệu đầu vào — thiếu trong TTS: "
            f"{sorted(missing_in_tts)}, thiếu trong images: {sorted(missing_in_images)}"
        )

    chapters = []
    for chapter in script.chapters:
        tts_chapter = tts_by_index[chapter.index]
        image_chapter = images_by_index[chapter.index]
        chapters.append(
            {
                "index": chapter.index,
                "heading": chapter.heading,
                "text": chapter.text,
                "startSeconds": tts_chapter["start_seconds"],
                "endSeconds": tts_chapter["end_seconds"],
                "imagePath": str((images_dir / image_chapter["filename"]).relative_to(repo_root)),
            }
        )

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "sampleRate": tts_metadata["sample_rate"],
        "chapters": chapters,
    }
