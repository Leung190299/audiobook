# shorts/cli.py
"""Stage 7: cắt tập đã đọc theo câu thành series short đánh số liên tục.

    uv run python -m shorts.cli <tts_metadata_json> [<images_metadata_json>]

Không truyền metadata ảnh = dựng short bằng video nền (assets/backgrounds/,
ưu tiên video dọc) -- stage 3 đã bị bỏ.
    # Đã render short: output/shorts/<trope>-<ts>-part-01.mp4
    # Metadata short: output/shorts/<trope>-<ts>-part-01.txt
    # ...
    # Đã render <N> short vào output/shorts

Chỉ cắt file wav đã có sẵn từ stage 2 (đã narrate theo câu và ghi mốc thời
gian), không TTS lại lần nào -- xem
docs/superpowers/specs/2026-08-22-shorts-series-design.md. Vì vậy stage này
chạy được cả khi cookie Gemini hết hạn: không còn phụ thuộc Gemini nữa.
"""

import argparse
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from shorts.audio_cut import cut_wav
from scripts.models import Script
from scripts.topics import TOPICS
from shorts.planner import plan_beat_shorts, plan_teasers, short_title_from_line
from episodes import backgrounds
from shorts.props_builder import build_short_props
from shorts.storage import (
    make_stem,
    part_stem,
    save_short_metadata,
    save_short_props,
    short_audio_path,
    short_thumbnail_path,
    short_video_path,
)

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "shorts"


# Chất lượng JPEG cho ảnh bìa. 85 cho ra ~400-600KB ở 1080x1920, thừa sức dưới
# trần 2MB của YouTube mà mắt thường không phân biệt được với PNG.
THUMBNAIL_JPEG_QUALITY = 85


class ShortRenderError(Exception):
    pass


FULL_CTA_TEXT = "Nghe trọn truyện trên kênh"


def _run(
    tts_metadata_path: Path, images_metadata_path: Path | None, script_path: Path | None = None
) -> None:
    # Resolve trước khi lấy .parent/.with_suffix: build_short_props tính đường
    # dẫn bằng .relative_to(REPO_ROOT), cần cả hai vế đều là đường dẫn tuyệt đối.
    tts_metadata_path = tts_metadata_path.resolve()
    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    images_metadata = None
    if images_metadata_path is not None:
        images_metadata_path = images_metadata_path.resolve()
        images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    if images_metadata is not None and (
        tts_metadata["trope"] != images_metadata["trope"]
        or tts_metadata["title"] != images_metadata["title"]
    ):
        raise ShortRenderError(
            f"trope/title của tts_metadata không khớp với images_metadata "
            f"(tts: {tts_metadata['trope']!r}/{tts_metadata['title']!r}, "
            f"images: {images_metadata['trope']!r}/{images_metadata['title']!r})"
        )

    trope = tts_metadata["trope"]
    episode_title = tts_metadata["title"]
    source_wav = tts_metadata_path.with_suffix(".wav")
    if not source_wav.exists():
        raise ShortRenderError(
            f"Không tìm thấy file wav nguồn tại {source_wav} (suy ra từ đường dẫn "
            f"metadata TTS {tts_metadata_path} bằng .with_suffix('.wav'))."
        )
    images_dir = images_metadata_path.parent if images_metadata_path is not None else None

    script = (
        Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
        if script_path is not None
        else None
    )
    # Kịch bản chủ đề (24/09/2026): 3 Shorts từ 3 đoạn hài/sảng nhất, mở bằng
    # câu thoại. Không có short_beats: trích đoạn mời nghe rải đều như trước.
    if script is not None and script.short_beats:
        parts = plan_beat_shorts(tts_metadata, script.short_beats)
    else:
        parts = plan_teasers(tts_metadata)
    is_full = script is not None and script.format == "full"
    cta_text = FULL_CTA_TEXT if is_full else None
    topic = TOPICS.get(script.topic) if script is not None else None
    short_tags = (
        ["truyện audio", "truyện hài", "nghe truyện", "shorts", topic.name.split(",")[0].lower()]
        if topic
        else None
    )
    total_parts = len(parts)
    if not 1 <= total_parts <= 99:
        raise ShortRenderError(
            f"Tập này chia được {total_parts} phần, ngoài khoảng 1-99 mà "
            "part_stem() hỗ trợ đánh số. Dừng trước khi render phần nào để "
            "không tốn công render rồi mới vỡ ở part_stem — kiểm tra lại "
            "MAX_PART_SECONDS trong shorts/planner.py hoặc dữ liệu mốc câu."
        )
    stem = make_stem(trope)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    completed_parts = 0

    for part in parts:
        this_part_stem = part_stem(stem, part.number)
        audio_path = short_audio_path(this_part_stem, OUTPUT_DIR)
        props_path = None
        output_path = short_video_path(this_part_stem, OUTPUT_DIR)
        thumbnail_path = short_thumbnail_path(this_part_stem, OUTPUT_DIR)

        try:
            cut_wav(source_wav, part.source_start_seconds, part.source_end_seconds, audio_path)

            # Không có ảnh: mỗi short bốc một video nền (ưu tiên dọc) theo stem
            # của chính phần đó, nên 3 short của một truyện thường khác nền.
            nen = (
                backgrounds.choose_for_short(seed=this_part_stem)
                if images_metadata is None
                else None
            )
            props = build_short_props(
                part=part,
                total_parts=total_parts,
                episode_title=episode_title,
                trope=trope,
                images_metadata=images_metadata,
                audio_path=audio_path,
                images_dir=images_dir,
                repo_root=REPO_ROOT,
                cta_text=cta_text,
                background=nen,
            )
            props_path = save_short_props(this_part_stem, props, OUTPUT_DIR)

            cmd = [
                "npx",
                "remotion",
                "render",
                "src/index.ts",
                "ShortVideo",
                str(output_path),
                f"--props={props_path}",
                f"--public-dir={REPO_ROOT}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=REMOTION_DIR)

            if result.returncode != 0:
                raise ShortRenderError(
                    f"Lỗi khi render short phần {part.number}/{total_parts} bằng "
                    f"Remotion: {result.stderr or result.stdout} "
                    f"({completed_parts} phần trước đó đã render xong, vẫn giữ nguyên trên đĩa)"
                )
            if not output_path.exists():
                raise ShortRenderError(
                    f"Remotion trả về mã thành công nhưng không có file short phần "
                    f"{part.number}/{total_parts} tại {output_path} "
                    f"({completed_parts} phần trước đó đã render xong, vẫn giữ nguyên trên đĩa)"
                )

            # YouTube Shorts tự lấy khung hình trong video làm ảnh bìa, không nhận
            # ảnh tải lên -- ảnh tĩnh này chỉ phục vụ việc chọn khung thủ công,
            # đăng chéo sang nền tảng khác, và trường hợp một phần bị xếp thành
            # video thường. Render sau khi .mp4 đã xong để dùng chung props.json.
            cmd_thumbnail = [
                "npx",
                "remotion",
                "still",
                "src/index.ts",
                "ShortThumbnail",
                str(thumbnail_path),
                f"--props={props_path}",
                f"--public-dir={REPO_ROOT}",
                "--image-format=jpeg",
                f"--jpeg-quality={THUMBNAIL_JPEG_QUALITY}",
            ]
            result = subprocess.run(
                cmd_thumbnail, capture_output=True, text=True, cwd=REMOTION_DIR
            )

            if result.returncode != 0:
                raise ShortRenderError(
                    f"Lỗi khi render ảnh bìa short phần {part.number}/{total_parts} bằng "
                    f"Remotion: {result.stderr or result.stdout} "
                    f"({completed_parts} phần trước đó đã render xong, vẫn giữ nguyên trên đĩa)"
                )
            if not thumbnail_path.exists():
                raise ShortRenderError(
                    f"Remotion trả về mã thành công nhưng không có ảnh bìa short phần "
                    f"{part.number}/{total_parts} tại {thumbnail_path} "
                    f"({completed_parts} phần trước đó đã render xong, vẫn giữ nguyên trên đĩa)"
                )
        except Exception:
            # Phần đang làm dở lỗi giữa chừng: dọn sạch file rời của riêng phần
            # này (wav cắt sẵn, props.json, mp4 dở và png dở nếu Remotion kịp
            # tạo) rồi mới bắn lỗi lên, để một lượt chạy hỏng không để lại rác
            # chờ lượt sau (đánh timestamp mới) ghi đè lẫn. KHÔNG đụng các phần
            # đã xong trước đó -- chúng vẫn dùng được và cố tình được giữ lại để
            # nhận diện một lượt chạy dở dang.
            for leftover in (audio_path, props_path, output_path, thumbnail_path):
                if leftover is not None and leftover.exists():
                    leftover.unlink()
            raise

        metadata_path, metadata_json_path = save_short_metadata(
            this_part_stem,
            trope,
            episode_title,
            part.number,
            total_parts,
            OUTPUT_DIR,
            title_override=short_title_from_line(part.hook_line) if part.hook_line else None,
            tags=short_tags,
        )

        # In ngay sau khi mỗi phần xong, không dồn đến cuối -- một tập ra ~30
        # phần mất khá lâu, người vận hành cần thấy tiến độ trong log. Hai chuỗi
        # đầu là hợp đồng với run_daily.sh và n8n, không đổi chữ; các dòng thêm
        # sau (metadata JSON, ảnh bìa) không nằm trong hợp đồng đó.
        print(f"Đã render short: {output_path}")
        print(f"Metadata short: {metadata_path}")
        print(f"Metadata JSON short: {metadata_json_path}")
        print(f"Ảnh bìa short: {thumbnail_path}")
        completed_parts += 1

    print(f"Đã render {total_parts} short vào {OUTPUT_DIR.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cắt tập đã đọc theo câu thành series short đánh số."
    )
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument(
        "images_metadata_path",
        nargs="?",
        default=None,
        help="Metadata ảnh của stage 3. Bỏ trống = nền short là video (assets/backgrounds/)",
    )
    parser.add_argument(
        "--script",
        type=Path,
        default=None,
        help="JSON kịch bản: có short_beats thì dựng 3 Shorts từ 3 đoạn hài/sảng nhất.",
    )
    args = parser.parse_args()
    _run(
        Path(args.tts_metadata_path),
        Path(args.images_metadata_path) if args.images_metadata_path else None,
        args.script,
    )


if __name__ == "__main__":
    main()
