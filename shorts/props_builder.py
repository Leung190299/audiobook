# shorts/props_builder.py
from pathlib import Path

from scripts.models import Script
from shorts.excerpt import ShortExcerpt
from tts.audio_postprocess import ChapterTiming


class ShortPropsBuildError(Exception):
    pass


CTA_SECONDS = 4.0


def build_short_props(
    script: Script,
    excerpt: ShortExcerpt,
    sentences: list[str],
    timings: list[ChapterTiming],
    images_metadata: dict,
    audio_path: Path,
    images_dir: Path,
    repo_root: Path,
    cta_seconds: float = CTA_SECONDS,
) -> dict:
    if not sentences or not timings:
        raise ShortPropsBuildError("Không có câu nào để dựng short")

    if len(sentences) != len(timings):
        raise ShortPropsBuildError(
            f"Số câu ({len(sentences)}) không khớp số mốc thời gian ({len(timings)})"
        )

    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}
    image_chapter = images_by_index.get(excerpt.chapter_index)
    if image_chapter is None:
        raise ShortPropsBuildError(
            f"Metadata ảnh không có chương {excerpt.chapter_index}"
        )

    image_path = images_dir / image_chapter["filename"]
    if not image_path.exists():
        raise ShortPropsBuildError(f"Không tìm thấy file ảnh: {image_path}")

    captions = [
        {
            "text": sentence,
            "startSeconds": timing.start_seconds,
            "endSeconds": timing.end_seconds,
        }
        for sentence, timing in zip(sentences, timings)
    ]

    return {
        "trope": script.trope,
        "title": script.title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "imagePath": str(image_path.relative_to(repo_root)),
        "hookText": excerpt.hook_text,
        "captions": captions,
        "audioDurationSeconds": timings[-1].end_seconds,
        "ctaSeconds": cta_seconds,
    }
