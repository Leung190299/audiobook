from dataclasses import dataclass

import numpy as np
import pyloudnorm as pyln


@dataclass
class ChapterTiming:
    index: int
    heading: str
    start_seconds: float
    end_seconds: float


@dataclass
class SentenceTiming:
    chapter_index: int
    index: int
    text: str
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


def concatenate_sentences(
    chapters: list[tuple[int, str, list[tuple[str, np.ndarray]]]],
    sample_rate: int,
    sentence_gap_seconds: float,
    chapter_gap_seconds: float,
) -> tuple[np.ndarray, list[ChapterTiming], list[SentenceTiming]]:
    """Ghép audio đã đọc theo câu thành một tập, ghi mốc cả hai mức.

    Ghép hai tầng vì khoảng nghỉ giữa câu (ngắn, tự nhiên trong lời nói) khác
    khoảng nghỉ giữa chương (dài hơn, đánh dấu chuyển cảnh). Mốc chương chạy từ
    đầu câu đầu tiên tới cuối câu cuối cùng của chương đó, không tính khoảng
    nghỉ hai bên.
    """
    sentence_gap_samples = int(sentence_gap_seconds * sample_rate)
    chapter_gap_samples = int(chapter_gap_seconds * sample_rate)
    sentence_gap = np.zeros(sentence_gap_samples, dtype=np.float32)
    chapter_gap = np.zeros(chapter_gap_samples, dtype=np.float32)

    segments = []
    chapter_timings = []
    sentence_timings = []
    cursor_samples = 0

    for chapter_i, (chapter_index, heading, sentences) in enumerate(chapters):
        chapter_start_samples = cursor_samples

        for sentence_i, (text, audio) in enumerate(sentences):
            start_seconds = cursor_samples / sample_rate
            segments.append(audio)
            cursor_samples += len(audio)
            end_seconds = cursor_samples / sample_rate

            sentence_timings.append(
                SentenceTiming(
                    chapter_index=chapter_index,
                    index=sentence_i + 1,
                    text=text,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                )
            )

            if sentence_i < len(sentences) - 1:
                segments.append(sentence_gap)
                cursor_samples += sentence_gap_samples

        chapter_timings.append(
            ChapterTiming(
                index=chapter_index,
                heading=heading,
                start_seconds=chapter_start_samples / sample_rate,
                end_seconds=cursor_samples / sample_rate,
            )
        )

        if chapter_i < len(chapters) - 1:
            segments.append(chapter_gap)
            cursor_samples += chapter_gap_samples

    full_audio = np.concatenate(segments) if segments else np.zeros(0, dtype=np.float32)
    return full_audio, chapter_timings, sentence_timings
