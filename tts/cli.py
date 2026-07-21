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


def _load_model():
    import torch
    from omnivoice import OmniVoice

    return OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cpu", dtype=torch.float32)


def _run(script_path: Path, model=None) -> None:
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    script = Script.from_dict(script_data)

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
        output_dir=OUTPUT_DIR,
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
    args = parser.parse_args()
    _run(Path(args.script_path))


if __name__ == "__main__":
    main()
