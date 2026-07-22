import argparse
import json
from pathlib import Path

from scripts.models import Script
from tts.audio_postprocess import concatenate_chapters, normalize_loudness
from tts.storage import save_audio
from tts.synthesizer import synthesize_chapter
from tts.voice_profile import load_voice_profile

VOICE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "voice.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "audio"
CHAPTER_OUTPUT_DIR = OUTPUT_DIR / "chapters"


class ChapterNotFoundError(Exception):
    pass


def _load_model():
    import torch
    from omnivoice import OmniVoice

    return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cpu", dtype=torch.float32)


def _run(script_path: Path, model=None, chapter_index: int | None = None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

    output_dir = OUTPUT_DIR
    if chapter_index is not None:
        matching = [c for c in script.chapters if c.index == chapter_index]
        if not matching:
            valid = sorted(c.index for c in script.chapters)
            raise ChapterNotFoundError(
                f"Không tìm thấy chương {chapter_index} trong kịch bản — các chương hợp lệ: {valid}"
            )
        script.chapters = matching
        output_dir = CHAPTER_OUTPUT_DIR

    voice_profile = load_voice_profile(VOICE_CONFIG_PATH)

    if model is None:
        model = _load_model()

    normalized_chapters = []
    for chapter in script.chapters:
        audio = synthesize_chapter(chapter, model, voice_profile)
        normalized_audio = normalize_loudness(
            audio, voice_profile.sample_rate, voice_profile.target_lufs
        )
        normalized_chapters.append((chapter.index, chapter.heading, normalized_audio))

    full_audio, timings = concatenate_chapters(
        normalized_chapters,
        sample_rate=voice_profile.sample_rate,
        gap_seconds=voice_profile.gap_seconds,
    )

    audio_path, metadata_path = save_audio(
        trope=script.trope,
        title=script.title,
        audio=full_audio,
        sample_rate=voice_profile.sample_rate,
        timings=timings,
        output_dir=output_dir,
    )

    duration_seconds = len(full_audio) / voice_profile.sample_rate
    print(
        f"Đã lưu audio: {audio_path} ({duration_seconds:.1f} giây, {len(script.chapters)} chương)\n"
        f"Metadata: {metadata_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lồng tiếng kịch bản truyện audio bằng OmniVoice."
    )
    parser.add_argument("script_path", help="Đường dẫn file JSON kịch bản")
    parser.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="Chỉ lồng tiếng 1 chương (theo index) thay vì toàn bộ kịch bản",
    )
    args = parser.parse_args()
    _run(Path(args.script_path), chapter_index=args.chapter)


if __name__ == "__main__":
    main()
