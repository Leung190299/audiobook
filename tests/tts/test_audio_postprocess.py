import numpy as np
import pyloudnorm as pyln

from tts.audio_postprocess import ChapterTiming, concatenate_chapters, normalize_loudness


def _sine_wave(duration_seconds: float, sample_rate: int, amplitude: float = 0.1) -> np.ndarray:
    t = np.linspace(0, duration_seconds, int(duration_seconds * sample_rate), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_normalize_loudness_moves_audio_toward_target_lufs():
    sample_rate = 24000
    audio = _sine_wave(1.0, sample_rate, amplitude=0.01)

    normalized = normalize_loudness(audio, sample_rate, target_lufs=-16.0)

    meter = pyln.Meter(sample_rate)
    result_lufs = meter.integrated_loudness(normalized)
    assert abs(result_lufs - (-16.0)) < 0.5


def test_concatenate_chapters_inserts_gap_and_computes_timestamps():
    sample_rate = 24000
    gap_seconds = 0.5
    chapter1_audio = np.ones(sample_rate, dtype=np.float32)
    chapter2_audio = np.ones(sample_rate * 2, dtype=np.float32)

    full_audio, timings = concatenate_chapters(
        [(1, "Chương 1", chapter1_audio), (2, "Chương 2", chapter2_audio)],
        sample_rate=sample_rate,
        gap_seconds=gap_seconds,
    )

    expected_length = sample_rate + int(gap_seconds * sample_rate) + sample_rate * 2
    assert len(full_audio) == expected_length

    assert timings[0] == ChapterTiming(
        index=1, heading="Chương 1", start_seconds=0.0, end_seconds=1.0
    )
    assert timings[1].index == 2
    assert timings[1].start_seconds == 1.5
    assert timings[1].end_seconds == 3.5


def test_concatenate_chapters_no_trailing_gap_after_last_chapter():
    sample_rate = 24000
    chapter_audio = np.ones(sample_rate, dtype=np.float32)

    full_audio, _ = concatenate_chapters(
        [(1, "Chương 1", chapter_audio)],
        sample_rate=sample_rate,
        gap_seconds=0.5,
    )

    assert len(full_audio) == sample_rate
