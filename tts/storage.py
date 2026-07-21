import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from tts.audio_postprocess import ChapterTiming


def save_audio(
    trope: str,
    title: str,
    audio: np.ndarray,
    sample_rate: int,
    timings: list[ChapterTiming],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    audio_path = output_dir / f"{trope}-{timestamp}.wav"
    sf.write(audio_path, audio, sample_rate)

    metadata_path = output_dir / f"{trope}-{timestamp}.json"
    metadata = {
        "trope": trope,
        "title": title,
        "chapters": [
            {
                "index": t.index,
                "heading": t.heading,
                "start_seconds": t.start_seconds,
                "end_seconds": t.end_seconds,
            }
            for t in timings
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return audio_path, metadata_path
