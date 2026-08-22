# shorts/props_builder.py
"""Dựng props Remotion cho một phần short từ một `ShortPart` đã lên kế hoạch.

Không còn nhận `Script`/`ShortPick` như bản đọc trọn chương: dữ liệu về tập
(trope, tiêu đề) và về phần (chương, mốc câu) tới từ hai chỗ tách biệt --
`shorts.cli` đọc metadata TTS/ảnh, `shorts.planner` cắt thành các `ShortPart`.
"""

from pathlib import Path

from shorts.planner import ShortPart

CTA_SECONDS = 4.0


class ShortPropsBuildError(Exception):
    pass


def build_short_props(
    part: ShortPart,
    total_parts: int,
    episode_title: str,
    trope: str,
    images_metadata: dict,
    audio_path: Path,
    images_dir: Path,
    repo_root: Path,
    cta_seconds: float = CTA_SECONDS,
) -> dict:
    images_by_index = {c["index"]: c for c in images_metadata["chapters"]}
    image_chapter = images_by_index.get(part.chapter_index)
    if image_chapter is None:
        raise ShortPropsBuildError(
            f"Metadata ảnh không có chương {part.chapter_index}"
        )

    image_path = images_dir / image_chapter["filename"]
    if not image_path.exists():
        raise ShortPropsBuildError(f"Không tìm thấy file ảnh: {image_path}")

    try:
        image_path_relative = image_path.relative_to(repo_root)
    except ValueError as exc:
        raise ShortPropsBuildError(
            f"File ảnh {image_path} nằm ngoài repo ({repo_root}) -- "
            "images_dir phải là thư mục con của repo_root"
        ) from exc

    # Phần cuối cùng của tập không có "phần kế tiếp" để mời xem -- mời nghe trọn
    # tập trên kênh thay vào đó.
    if part.number >= total_parts:
        cta_text = "Nghe full trên kênh"
    else:
        cta_text = f"Xem phần {part.number + 1}"

    captions = [
        {
            "text": caption.text,
            "startSeconds": caption.start_seconds,
            "endSeconds": caption.end_seconds,
        }
        for caption in part.captions
    ]

    return {
        "trope": trope,
        "title": episode_title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "imagePath": str(image_path_relative),
        "hookText": part.heading,
        "captions": captions,
        "audioDurationSeconds": part.duration_seconds,
        "ctaSeconds": cta_seconds,
        "ctaText": cta_text,
    }
