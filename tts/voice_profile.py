from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class VoiceProfile:
    instruction: str
    target_lufs: float
    sample_rate: int
    gap_seconds: float


def load_voice_profile(path: Path) -> VoiceProfile:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return VoiceProfile(
        instruction=data["instruction"],
        target_lufs=data["target_lufs"],
        sample_rate=data["sample_rate"],
        gap_seconds=data["gap_seconds"],
    )
