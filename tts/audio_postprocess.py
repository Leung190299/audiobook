from dataclasses import dataclass

import numpy as np
import pyloudnorm as pyln


@dataclass
class ChapterTiming:
    index: int
    heading: str
    start_seconds: float
    end_seconds: float


def normalize_loudness(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray:
    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(audio)
    normalized = pyln.normalize.loudness(audio, loudness, target_lufs)

    peak = np.max(np.abs(normalized))
    peak_ceiling = 10 ** (-1.0 / 20)  # -1 dBFS headroom, avoids clipping on 16-bit PCM write
    if peak > peak_ceiling:
        normalized = normalized * (peak_ceiling / peak)

    return normalized


def concatenate_chapters(
    chapters: list[tuple[int, str, np.ndarray]],
    sample_rate: int,
    gap_seconds: float,
) -> tuple[np.ndarray, list[ChapterTiming]]:
    gap_samples = int(gap_seconds * sample_rate)
    gap = np.zeros(gap_samples, dtype=np.float32)

    segments = []
    timings = []
    cursor_samples = 0

    for i, (index, heading, audio) in enumerate(chapters):
        start_seconds = cursor_samples / sample_rate
        segments.append(audio)
        cursor_samples += len(audio)
        end_seconds = cursor_samples / sample_rate
        timings.append(
            ChapterTiming(
                index=index, heading=heading, start_seconds=start_seconds, end_seconds=end_seconds
            )
        )

        if i < len(chapters) - 1:
            segments.append(gap)
            cursor_samples += gap_samples

    full_audio = np.concatenate(segments) if segments else np.zeros(0, dtype=np.float32)
    return full_audio, timings
