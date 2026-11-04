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
    images_metadata: dict | None,
    audio_path: Path,
    images_dir: Path | None,
    repo_root: Path,
    cta_seconds: float = CTA_SECONDS,
    cta_text: str | None = None,
    background: dict | None = None,
) -> dict:
    """`images_metadata` None = đã bỏ stage 3, nền short là video (`background`,
    từ episodes/backgrounds.choose_for_short). Khi đó scenes rỗng và imagePath
    rỗng; ShortVideo/ShortThumbnail vẽ video thay ảnh."""
    if images_metadata is None:
        if not background:
            raise ShortPropsBuildError(
                "Short không có ảnh (đã bỏ stage 3) mà cũng không có video nền -- "
                "thêm video .mp4 vào assets/backgrounds/ hoặc chạy stage 3."
            )
        scene_props: list[dict] = []
        image_path_relative = ""
    else:
        scene_props, image_path_relative = _scenes_from_images(
            part, images_metadata, images_dir, repo_root
        )
    return _assemble(
        part, total_parts, episode_title, trope, audio_path, repo_root,
        scene_props, image_path_relative, cta_seconds, cta_text, background,
    )


def _scenes_from_images(
    part: ShortPart, images_metadata: dict, images_dir: Path, repo_root: Path
) -> tuple[list[dict], str]:
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
    return scene_props, scene_props[0]["imagePath"]


def _assemble(
    part: ShortPart,
    total_parts: int,
    episode_title: str,
    trope: str,
    audio_path: Path,
    repo_root: Path,
    scene_props: list[dict],
    image_path_relative: str,
    cta_seconds: float,
    cta_text: str | None,
    background: dict | None,
) -> dict:
    # Mọi trích đoạn đều mời về video dài. Trước đây card cuối ghi "Xem phần N+1"
    # vì short là một series nối tiếp; nay short chỉ là mồi, nên chỉ có một đích
    # duy nhất đáng dẫn tới là tập đầy đủ trên kênh.
    cta_text = cta_text or "Nghe trọn tập 1 trên kênh"

    captions = [
        {
            "text": caption.text,
            "startSeconds": caption.start_seconds,
            "endSeconds": caption.end_seconds,
        }
        for caption in part.captions
    ]

    props = {
        "trope": trope,
        "title": episode_title,
        "audioPath": str(audio_path.relative_to(repo_root)),
        "imagePath": image_path_relative,
        "scenes": scene_props,
        "hookText": part.hook_line or part.heading,
        "partLabel": f"TRÍCH ĐOẠN {part.number}/{total_parts}",
        "captions": captions,
        "audioDurationSeconds": part.duration_seconds,
        "ctaSeconds": cta_seconds,
        "ctaText": cta_text,
    }
    if background:
        props.update(background)
    return props
