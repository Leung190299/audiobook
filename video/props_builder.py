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

    if "sentences" not in tts_metadata:
        raise PropsBuildError(
            "Metadata TTS thiếu mảng 'sentences' — tập này dựng trước khi stage 2 "
            "biết ghi mốc câu. Muốn render lại, hãy chạy lại stage 2."
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

    sentences_by_chapter: dict[int, list[dict]] = {}
    for sentence in tts_metadata["sentences"]:
        sentences_by_chapter.setdefault(sentence["chapter_index"], []).append(sentence)

    chapters = []
    for chapter in script.chapters:
        tts_chapter = tts_by_index[chapter.index]
        image_chapter = images_by_index[chapter.index]
        chapter_sentences = sentences_by_chapter.get(chapter.index)
        if not chapter_sentences:
            raise PropsBuildError(
                f"Chương {chapter.index} không có câu nào trong metadata TTS — tập này "
                "dựng trước khi stage 2 biết ghi mốc câu. Muốn render lại, hãy chạy lại stage 2."
            )
        image_scenes = image_chapter.get("scenes")
        if not image_scenes:
            raise PropsBuildError(
                f"Metadata ảnh của chương {chapter.index} không có mảng 'scenes' — tập này "
                "dựng trước khi stage 3 biết chia cảnh. Muốn render lại, hãy chạy lại stage 3."
            )
        chapters.append(
            {
                "index": chapter.index,
                "heading": chapter.heading,
                "startSeconds": tts_chapter["start_seconds"],
                "endSeconds": tts_chapter["end_seconds"],
                # Mốc cảnh giữ trục toàn tập, cùng lý do với mốc câu bên dưới.
                "scenes": [
                    {
                        "number": scene["number"],
                        "startSeconds": scene["start_seconds"],
                        "endSeconds": scene["end_seconds"],
                        "imagePath": str(
                            (images_dir / scene["filename"]).relative_to(repo_root)
                        ),
                    }
                    for scene in image_scenes
                ],
                "sentences": [
                    {
                        "text": s["text"],
                        "startSeconds": s["start_seconds"],
                        "endSeconds": s["end_seconds"],
                    }
                    for s in chapter_sentences
                ],
            }
        )

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "sampleRate": tts_metadata["sample_rate"],
        "chapters": chapters,
    }
