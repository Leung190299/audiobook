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
    scenes = image_chapter.get("scenes")
    if not scenes:
        raise ShortPropsBuildError(
            f"Metadata ảnh của chương {part.chapter_index} không có mảng 'scenes' -- "
            "tập này dựng trước khi stage 3 biết chia cảnh. Hãy chạy lại stage 3."
        )

    # Lấy mọi cảnh giao với khoảng thời gian của phần. Planner không bao giờ cắt
    # phần qua ranh giới chương và các cảnh phủ kín chương, nên luôn có ít nhất
    # một cảnh. So "end > start phần" và "start < end phần" để cảnh vừa kết thúc
    # đúng lúc phần bắt đầu không bị lấy thừa.
    part_start = part.source_start_seconds
    part_end = part.source_end_seconds
    overlapping = [
        s for s in scenes
        if s["end_seconds"] > part_start and s["start_seconds"] < part_end
    ]
    if not overlapping:
        raise ShortPropsBuildError(
            f"Không có cảnh nào của chương {part.chapter_index} phủ khoảng "
            f"{part_start:.2f}-{part_end:.2f}s của phần {part.number}"
        )

    def _relative(filename: str) -> str:
        image_path = images_dir / filename
        if not image_path.exists():
            raise ShortPropsBuildError(f"Không tìm thấy file ảnh: {image_path}")
        try:
            return str(image_path.relative_to(repo_root))
        except ValueError as exc:
            raise ShortPropsBuildError(
                f"File ảnh {image_path} nằm ngoài repo ({repo_root}) -- "
                "images_dir phải là thư mục con của repo_root"
            ) from exc

    # Mốc QUY VỀ GỐC PHẦN, khác video dài (giữ trục toàn tập): audio của short
    # đã bị cắt nên ShortVideo.tsx so với thời gian của composition, bắt đầu từ 0.
    scene_props = [
        {
            "number": s["number"],
            "startSeconds": max(0.0, s["start_seconds"] - part_start),
            "endSeconds": min(part.duration_seconds, s["end_seconds"] - part_start),
            "imagePath": _relative(s["filename"]),
        }
        for s in overlapping
    ]
    # Ảnh bìa (ShortThumbnail) vẫn là cảnh đang chiếu lúc phần bắt đầu.
    image_path_relative = scene_props[0]["imagePath"]

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
        "scenes": scene_props,
        "hookText": part.heading,
        "partLabel": f"PHẦN {part.number}/{total_parts}",
        "captions": captions,
        "audioDurationSeconds": part.duration_seconds,
        "ctaSeconds": cta_seconds,
        "ctaText": cta_text,
    }
