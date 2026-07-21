# tests/tts/test_synthesizer.py
import numpy as np
import pytest

from scripts.models import Chapter
from tts.synthesizer import SynthesisError, synthesize_chapter
from tts.voice_profile import VoiceProfile


def _voice_profile() -> VoiceProfile:
    return VoiceProfile(
        instruction="giọng nữ ấm áp", target_lufs=-16.0, sample_rate=24000, gap_seconds=0.5
    )


class _FakeModel:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate(self, text, instruct):
        self.calls.append((text, instruct))
        return self.result


def test_synthesize_chapter_returns_audio_array():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel([fake_audio])

    audio = synthesize_chapter(chapter, model, _voice_profile())

    assert isinstance(audio, np.ndarray)
    assert audio.shape == (1000,)
    assert model.calls == [("Nội dung chương một.", "giọng nữ ấm áp")]


def test_synthesize_chapter_raises_synthesis_error_on_model_failure():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")

    class _FailingModel:
        def generate(self, text, instruct):
            raise RuntimeError("model crashed")

    with pytest.raises(SynthesisError, match="chương 1"):
        synthesize_chapter(chapter, _FailingModel(), _voice_profile())


def test_synthesize_chapter_raises_synthesis_error_on_unexpected_result_shape():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung.")
    model = _FakeModel(None)

    with pytest.raises(SynthesisError):
        synthesize_chapter(chapter, model, _voice_profile())
