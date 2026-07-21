# tests/tts/test_storage.py
import json

import numpy as np

from tts.audio_postprocess import ChapterTiming
from tts.storage import save_audio


def test_save_audio_writes_wav_and_metadata_json(tmp_path):
    audio = np.zeros(24000, dtype=np.float32)
    timings = [ChapterTiming(index=1, heading="Chương 1", start_seconds=0.0, end_seconds=1.0)]

    audio_path, metadata_path = save_audio(
        trope="test_trope",
        title="Tiêu đề",
        audio=audio,
        sample_rate=24000,
        timings=timings,
        output_dir=tmp_path,
    )

    assert audio_path.exists()
    assert audio_path.suffix == ".wav"
    assert metadata_path.exists()

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["title"] == "Tiêu đề"
    assert data["trope"] == "test_trope"
    assert data["sample_rate"] == 24000
    assert data["chapters"][0]["heading"] == "Chương 1"
    assert data["chapters"][0]["end_seconds"] == 1.0


def test_save_audio_creates_output_dir_if_missing(tmp_path):
    audio = np.zeros(100, dtype=np.float32)
    missing_dir = tmp_path / "nested" / "output"

    audio_path, _ = save_audio(
        trope="t", title="T", audio=audio, sample_rate=24000, timings=[], output_dir=missing_dir
    )

    assert audio_path.exists()
