from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class VoiceProfile:
    instruction: str
    target_lufs: float
    sample_rate: int
    gap_seconds: float
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
        instruction=data["instruction"],
        target_lufs=data["target_lufs"],
        sample_rate=data["sample_rate"],
        gap_seconds=data["gap_seconds"],
        ref_audio_path=ref_audio_path,
    )
