# shorts/cli.py
"""Stage 7: dựng video ngắn (Shorts) từ chương gay cấn nhất của tập.

    uv run python -m shorts.cli <script_json> <images_metadata_json>
    # Đã render short: output/shorts/<trope>-<ts>.mp4
    # Metadata short: output/shorts/<trope>-<ts>.txt

Chỉ đọc output của stage 1 và stage 3, nên chạy được cho cả tập đã dựng xong từ trước.
"""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from scripts.models import Chapter, Script
from shorts import excerpt as excerpt_module
from shorts.props_builder import build_short_props
from shorts.storage import (
    make_stem,
    save_short_audio,
    save_short_metadata,
    save_short_props,
    short_video_path,
)
from tts.audio_postprocess import concatenate_chapters, normalize_loudness
from tts.synthesizer import synthesize_chapter
from tts.voice_profile import load_voice_profile

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = REPO_ROOT / "remotion"
OUTPUT_DIR = REPO_ROOT / "output" / "shorts"
VOICE_CONFIG_PATH = REPO_ROOT / "config" / "voice.yaml"

# Khoảng nghỉ giữa hai câu. KHÔNG dùng gap_seconds trong voice.yaml — giá trị đó
# (~0.5s) dành cho khoảng nghỉ giữa các chương, áp vào giữa câu nghe rời rạc.
SENTENCE_GAP_SECONDS = 0.15


class ShortRenderError(Exception):
    pass


def _load_model():
    from vieneu import Vieneu

    return Vieneu(backend="onnx")


async def _run(
    script_path: Path,
    images_metadata_path: Path,
    gemini_client=None,
    model=None,
) -> None:
    # Resolve trước khi lấy .parent: build_short_props tính đường dẫn bằng
    # .relative_to(REPO_ROOT), cần cả hai vế đều là đường dẫn tuyệt đối.
    images_metadata_path = images_metadata_path.resolve()

    script = Script.from_dict(json.loads(script_path.read_text(encoding="utf-8")))
    images_metadata = json.loads(images_metadata_path.read_text(encoding="utf-8"))

    pick = await excerpt_module.pick_short_chapter(script, gemini_client)
    sentences = excerpt_module.split_sentences(pick.chapter_text)

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)
    if model is None:
        model = _load_model()

    # Đọc từng câu một để lấy mốc thời gian thật cho phụ đề. Chapter ở đây chỉ là
    # vỏ bọc cho synthesize_chapter — index/heading chỉ dùng trong thông báo lỗi.
    #
    # KHÔNG chuẩn hoá độ ồn từng câu riêng lẻ: một câu thoại một từ ("Sao?", "Không!")
    # ngắn hơn 0.4s làm pyloudnorm bắn ValueError (block size), và kể cả khi không
    # crash thì LUFS đo trên vài trăm ms cũng vô nghĩa, khiến âm lượng nhảy giữa các
    # câu. Ghép âm thanh thô trước, chuẩn hoá một lần trên cả đoạn — giống cách
    # tts/cli.py chuẩn hoá theo cả chương chứ không theo câu.
    pieces = []
    for i, sentence in enumerate(sentences, start=1):
        audio = synthesize_chapter(
            Chapter(index=i, heading=f"Câu {i}", text=sentence), model, voice_profile
        )
        pieces.append((i, sentence, audio))

    raw_audio, timings = concatenate_chapters(
        pieces,
        sample_rate=voice_profile.sample_rate,
        gap_seconds=SENTENCE_GAP_SECONDS,
    )
    # concatenate_chapters chỉ nối mảng, không đổi số sample -> mốc thời gian trong
    # timings vẫn đúng sau khi chuẩn hoá độ ồn trên full_audio bên dưới.
    full_audio = normalize_loudness(
        raw_audio, voice_profile.sample_rate, voice_profile.target_lufs
    )

    stem = make_stem(script.trope)
    audio_path = save_short_audio(stem, full_audio, voice_profile.sample_rate, OUTPUT_DIR)

    props = build_short_props(
        script=script,
        pick=pick,
        sentences=sentences,
        timings=timings,
        images_metadata=images_metadata,
        audio_path=audio_path,
        images_dir=images_metadata_path.parent,
        repo_root=REPO_ROOT,
    )
    props_path = save_short_props(stem, props, OUTPUT_DIR)

    output_path = short_video_path(stem, OUTPUT_DIR)
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
            f"Lỗi khi render short bằng Remotion: {result.stderr or result.stdout}"
        )
    if not output_path.exists():
        raise ShortRenderError(
            f"Remotion trả về mã thành công nhưng không có file short tại {output_path}"
        )

    metadata_path = save_short_metadata(
        stem, pick, script.title, output_path.name, OUTPUT_DIR
    )

    print(f"Đã render short: {output_path}")
    print(f"Metadata short: {metadata_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dựng video ngắn (Shorts) từ chương gay cấn nhất của tập."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument("images_metadata_path", help="Đường dẫn file JSON metadata ảnh")
    args = parser.parse_args()
    asyncio.run(_run(Path(args.script_path), Path(args.images_metadata_path)))


if __name__ == "__main__":
    main()
