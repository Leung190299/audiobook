import argparse
import json
from pathlib import Path

import soundfile as sf

from scripts.models import Script
from tts.audio_postprocess import concatenate_chapters
from tts.storage import save_audio
from tts.voice_profile import load_voice_profile

VOICE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "voice.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "audio"


class MergeError(Exception):
    pass


def _load_chapter_audio(metadata_path: Path):
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    chapters = data["chapters"]
    if len(chapters) != 1:
        raise MergeError(
            f"{metadata_path} không phải audio 1 chương (có {len(chapters)} chương)"
        )
    chapter = chapters[0]

    audio_path = metadata_path.with_suffix(".wav")
    if not audio_path.exists():
        raise MergeError(f"Không tìm thấy file audio tương ứng: {audio_path}")
    audio, sample_rate = sf.read(audio_path, dtype="float32")

    return chapter["index"], chapter["heading"], audio, sample_rate


def _run(script_path: Path, chapter_audio_dir: Path) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    by_index = {}
    sample_rates = set()
    for metadata_path in sorted(chapter_audio_dir.glob("*.json")):
        index, heading, audio, sample_rate = _load_chapter_audio(metadata_path)
        by_index[index] = (heading, audio)
        sample_rates.add(sample_rate)

    expected_indices = [c.index for c in script.chapters]
    missing = [i for i in expected_indices if i not in by_index]
    if missing:
        raise MergeError(
            f"Thiếu audio cho các chương: {missing} trong thư mục {chapter_audio_dir}"
        )

    if len(sample_rates) > 1:
        raise MergeError(f"Các chương có sample_rate khác nhau: {sorted(sample_rates)}")
    sample_rate = sample_rates.pop()

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)

    ordered_chapters = [
        (index, by_index[index][0], by_index[index][1]) for index in expected_indices
    ]

    full_audio, timings = concatenate_chapters(
        ordered_chapters, sample_rate=sample_rate, gap_seconds=voice_profile.gap_seconds
    )

    audio_path, metadata_path = save_audio(
        trope=script.trope,
        title=script.title,
        audio=full_audio,
        sample_rate=sample_rate,
        timings=timings,
        output_dir=OUTPUT_DIR,
    )

    duration_seconds = len(full_audio) / sample_rate
    print(
        f"Đã ghép {len(ordered_chapters)} chương thành audio: {audio_path} "
        f"({duration_seconds:.1f} giây)\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ghép các file audio lồng tiếng theo từng chương "
            "(do 'tts.cli --chapter' tạo ra) thành 1 audio hoàn chỉnh."
        )
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản gốc (đủ tất cả chương)")
    parser.add_argument(
        "chapter_audio_dir", help="Thư mục chứa các file audio+metadata theo chương"
    )
    args = parser.parse_args()
    _run(Path(args.script_path), Path(args.chapter_audio_dir))


if __name__ == "__main__":
    main()
