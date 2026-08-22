# shorts/cli.py
"""Stage 7: cắt tập đã đọc theo câu thành series short đánh số liên tục.

    uv run python -m shorts.cli <tts_metadata_json> <images_metadata_json>
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
from shorts.planner import plan_parts
from shorts.props_builder import build_short_props
from shorts.storage import (
    make_stem,
    part_stem,
    save_short_metadata,
    save_short_props,
    short_audio_path,
    short_video_path,
)

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "shorts"


class ShortRenderError(Exception):
    pass


def _run(tts_metadata_path: Path, images_metadata_path: Path) -> None:
    # Resolve trước khi lấy .parent/.with_suffix: build_short_props tính đường
    # dẫn bằng .relative_to(REPO_ROOT), cần cả hai vế đều là đường dẫn tuyệt đối.
    tts_metadata_path = tts_metadata_path.resolve()
    images_metadata_path = images_metadata_path.resolve()

    tts_metadata = json.loads(tts_metadata_path.read_text(encoding="utf-8"))
    images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    if (
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
    images_dir = images_metadata_path.parent

    parts = plan_parts(tts_metadata)
    total_parts = len(parts)
    stem = make_stem(trope)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for part in parts:
        this_part_stem = part_stem(stem, part.number)

        audio_path = short_audio_path(this_part_stem, OUTPUT_DIR)
        cut_wav(source_wav, part.source_start_seconds, part.source_end_seconds, audio_path)

        props = build_short_props(
            part=part,
            total_parts=total_parts,
            episode_title=episode_title,
            trope=trope,
            images_metadata=images_metadata,
            audio_path=audio_path,
            images_dir=images_dir,
            repo_root=REPO_ROOT,
        )
        props_path = save_short_props(this_part_stem, props, OUTPUT_DIR)

        output_path = short_video_path(this_part_stem, OUTPUT_DIR)
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
                f"Remotion: {result.stderr or result.stdout}"
            )
        if not output_path.exists():
            raise ShortRenderError(
                f"Remotion trả về mã thành công nhưng không có file short phần "
                f"{part.number}/{total_parts} tại {output_path}"
            )

        metadata_path = save_short_metadata(
            this_part_stem, episode_title, part.number, total_parts, OUTPUT_DIR
        )

        # In ngay sau khi mỗi phần xong, không dồn đến cuối -- một tập ra ~30
        # phần mất khá lâu, người vận hành cần thấy tiến độ trong log. Hai chuỗi
        # dưới đây là hợp đồng với run_daily.sh và n8n, không đổi chữ.
        print(f"Đã render short: {output_path}")
        print(f"Metadata short: {metadata_path}")

    print(f"Đã render {total_parts} short vào {OUTPUT_DIR.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cắt tập đã đọc theo câu thành series short đánh số."
    )
    parser.add_argument("tts_metadata_path", help="Đường dẫn file JSON metadata TTS")
    parser.add_argument(
        "images_metadata_path", help="Đường dẫn file JSON metadata ảnh"
    )
    args = parser.parse_args()
    _run(Path(args.tts_metadata_path), Path(args.images_metadata_path))


if __name__ == "__main__":
    main()
