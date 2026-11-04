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
    """Chuẩn hoá độ ồn TẠI CHỖ trên `audio` và trả về chính mảng đó.

    Một tập thật ~3135s @ 48kHz nặng ~600MB mỗi bản sao float32. Gọi thẳng
    pyln.normalize.loudness() rồi nhân peak-ceiling như cách cũ cấp phát thêm
    hai bản sao full-size (một cho mỗi bước) trong lúc audio gốc vẫn còn sống ở
    tay người gọi — đỉnh bộ nhớ ~3 bản. Tự tính gain rồi nhân tại chỗ (`*=`) chỉ
    còn đúng bản audio đầu vào; công thức gain giữ y hệt
    pyloudnorm.normalize.loudness (xem .venv/.../pyloudnorm/normalize.py) nên
    kết quả không đổi.
    """
    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(audio)

    delta_loudness = target_lufs - loudness
    gain = 10 ** (delta_loudness / 20.0)
    audio *= gain

    peak = np.max(np.abs(audio))
    peak_ceiling = 10 ** (-1.0 / 20)  # -1 dBFS headroom, avoids clipping on 16-bit PCM write
    if peak > peak_ceiling:
        audio *= peak_ceiling / peak

    return audio


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
