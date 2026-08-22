from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class VoiceProfile:
    voice: str
    style: str
    target_lufs: float
    sample_rate: int
    gap_seconds: float
    sentence_gap_seconds: float = 0.15
    ref_audio_path: Path | None = None


def load_voice_profile(path: Path) -> VoiceProfile:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ref_audio_path = data.get("ref_audio_path")
    if ref_audio_path:
        ref_audio_path = Path(ref_audio_path)
        if not ref_audio_path.is_absolute():
            repo_root = path.resolve().parent.parent
            ref_audio_path = repo_root / ref_audio_path

    return VoiceProfile(
        voice=data["voice"],
        style=data["style"],
        target_lufs=data["target_lufs"],
        sample_rate=data["sample_rate"],
        gap_seconds=data["gap_seconds"],
        # data.get, không phải data[...]: cấu hình cũ chưa có trường này vẫn nạp được.
        sentence_gap_seconds=data.get("sentence_gap_seconds", 0.15),
        ref_audio_path=ref_audio_path,
    )
