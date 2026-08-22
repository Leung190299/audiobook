import numpy as np
import pyloudnorm as pyln
import pytest

from tts.audio_postprocess import (
    ChapterTiming,
    SentenceTiming,
    concatenate_chapters,
    concatenate_sentences,
    normalize_loudness,
)


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


def test_normalize_loudness_caps_peak_to_avoid_clipping():
    sample_rate = 24000
    audio = _sine_wave(1.0, sample_rate, amplitude=0.9)

    normalized = normalize_loudness(audio, sample_rate, target_lufs=-1.0)

    peak = np.max(np.abs(normalized))
    peak_ceiling = 10 ** (-1.0 / 20)
    assert peak <= peak_ceiling + 1e-6


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


def _chapters_for_sentence_concat(sample_rate: int):
    # Chương 1 có 2 câu (1s, 0.5s), chương 2 có 1 câu (2s).
    return [
        (
            1,
            "Chương 1",
            [
                ("Câu 1a.", np.ones(sample_rate, dtype=np.float32)),
                ("Câu 1b.", np.ones(int(sample_rate * 0.5), dtype=np.float32)),
            ],
        ),
        (
            2,
            "Chương 2",
            [("Câu 2a.", np.ones(sample_rate * 2, dtype=np.float32))],
        ),
    ]


def test_concatenate_sentences_moc_cau_lien_tiep_khong_chong_lan():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, _, sentence_timings = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    for prev, nxt in zip(sentence_timings, sentence_timings[1:]):
        assert prev.end_seconds <= nxt.start_seconds


def test_concatenate_sentences_khoang_nghi_giua_cau_dung_bang_sentence_gap():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, _, sentence_timings = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    # Câu 1a và 1b cùng chương 1 -> khoảng nghỉ giữa chúng là sentence_gap_seconds.
    gap = sentence_timings[1].start_seconds - sentence_timings[0].end_seconds
    assert gap == pytest.approx(0.15)


def test_concatenate_sentences_khoang_nghi_giua_chuong_dung_bang_chapter_gap():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, chapter_timings, _ = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    gap = chapter_timings[1].start_seconds - chapter_timings[0].end_seconds
    assert gap == pytest.approx(0.5)


def test_concatenate_sentences_moc_chuong_bao_tron_cac_cau_cua_no():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, chapter_timings, sentence_timings = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    chapter1_sentences = [s for s in sentence_timings if s.chapter_index == 1]
    assert chapter_timings[0].start_seconds == chapter1_sentences[0].start_seconds
    assert chapter_timings[0].end_seconds == chapter1_sentences[-1].end_seconds


def test_concatenate_sentences_index_cau_danh_lai_tu_1_moi_chuong():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, _, sentence_timings = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    chapter1_indices = [s.index for s in sentence_timings if s.chapter_index == 1]
    chapter2_indices = [s.index for s in sentence_timings if s.chapter_index == 2]
    assert chapter1_indices == [1, 2]
    assert chapter2_indices == [1]


def test_concatenate_sentences_tong_so_mau_khop_voi_audio_tra_ve():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)
    sentence_gap_seconds = 0.15
    chapter_gap_seconds = 0.5

    full_audio, _, _ = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=sentence_gap_seconds,
        chapter_gap_seconds=chapter_gap_seconds,
    )

    total_sentence_samples = sample_rate + int(sample_rate * 0.5) + sample_rate * 2
    sentence_gap_samples = int(sentence_gap_seconds * sample_rate)  # 1 khoảng nghỉ trong chương 1
    chapter_gap_samples = int(chapter_gap_seconds * sample_rate)  # 1 khoảng nghỉ giữa 2 chương
    expected_length = total_sentence_samples + sentence_gap_samples + chapter_gap_samples
    assert len(full_audio) == expected_length


def test_concatenate_sentences_text_va_chapter_index_duoc_giu_dung():
    sample_rate = 24000
    chapters = _chapters_for_sentence_concat(sample_rate)

    _, _, sentence_timings = concatenate_sentences(
        chapters,
        sample_rate=sample_rate,
        sentence_gap_seconds=0.15,
        chapter_gap_seconds=0.5,
    )

    assert sentence_timings[0] == SentenceTiming(
        chapter_index=1,
        index=1,
        text="Câu 1a.",
        start_seconds=0.0,
        end_seconds=1.0,
    )
