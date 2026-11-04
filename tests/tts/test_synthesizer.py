# tests/tts/test_synthesizer.py
from pathlib import Path

import numpy as np
import pytest

from scripts.models import Chapter
from tts.synthesizer import SynthesisError, synthesize_chapter
from tts.voice_profile import VoiceProfile


def _voice_profile(ref_audio_path=None) -> VoiceProfile:
    return VoiceProfile(
        voice="Ngọc Linh",
        style="doc_truyen",
        target_lufs=-16.0,
        sample_rate=48000,
        gap_seconds=0.5,
        ref_audio_path=ref_audio_path,
    )


class _FakeModel:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def infer(self, text, voice=None, style=None):
        self.calls.append((text, voice, style))
        return self.result


def test_synthesize_chapter_returns_audio_array():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel(fake_audio)

    audio = synthesize_chapter(chapter, model, _voice_profile())

    assert isinstance(audio, np.ndarray)
    assert audio.shape == (1000,)
    assert model.calls == [("Nội dung chương một.", "Ngọc Linh", "doc_truyen")]


def test_synthesize_chapter_khong_dung_ref_audio_du_ref_audio_path_duoc_cau_hinh():
    # synthesize_chapter không còn biết gì về ref_audio_path -- việc enroll
    # giọng nhân bản và gán voice_profile.voice thành tên đã enroll là việc
    # của tts/cli.py, làm một lần trước vòng lặp từng câu (xem finding #1: enroll
    # lại mỗi câu qua ref_audio= từng khiến stage 2 chậm gấp đôi). Ở đây chỉ cần
    # xác nhận hàm luôn gọi infer bằng voice_profile.voice, không có tham số
    # ref_audio/denoise nào được truyền, dù ref_audio_path vẫn còn trên profile.
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel(fake_audio)
    profile = _voice_profile(ref_audio_path=Path("/tmp/female_ngochuyen.mp3"))
    profile.voice = "__cloned_reference__"  # mô phỏng cli.py đã gán sau khi enroll

    audio = synthesize_chapter(chapter, model, profile)

    assert isinstance(audio, np.ndarray)
    assert model.calls == [
        ("Nội dung chương một.", "__cloned_reference__", "doc_truyen")
    ]


def test_synthesize_chapter_raises_synthesis_error_on_model_failure():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")

    class _FailingModel:
        def infer(self, text, voice=None, style=None):
            raise RuntimeError("model crashed")

    with pytest.raises(SynthesisError, match="chương 1"):
        synthesize_chapter(chapter, _FailingModel(), _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_none_result():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel(None)

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_empty_audio():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel(np.array([], dtype=np.float32))

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_non_numeric_result():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel("not audio")

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())
