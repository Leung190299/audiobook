# tests/tts/test_synthesizer.py
from pathlib import Path

import numpy as np
import pytest

from scripts.models import Chapter
from tts.synthesizer import SynthesisError, synthesize_chapter
from tts.voice_profile import VoiceProfile


def _voice_profile(ref_audio_path=None) -> VoiceProfile:
    return VoiceProfile(
        instruction="giọng nữ ấm áp",
        target_lufs=-16.0,
        sample_rate=24000,
        gap_seconds=0.5,
        ref_audio_path=ref_audio_path,
    )


class _FakeModel:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate(self, text, instruct=None, ref_audio=None):
        self.calls.append((text, instruct, ref_audio))
        return self.result


def test_synthesize_chapter_returns_audio_array():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel([fake_audio])

    audio = synthesize_chapter(chapter, model, _voice_profile())

    assert isinstance(audio, np.ndarray)
    assert audio.shape == (1000,)
    assert model.calls == [("Nội dung chương một.", "giọng nữ ấm áp", None)]


def test_synthesize_chapter_uses_ref_audio_when_voice_clone_configured():
    chapter = Chapter(index=1, heading="Chương 1", text="Nội dung chương một.")
    fake_audio = np.zeros(1000, dtype=np.float32)
    model = _FakeModel([fake_audio])
    ref_audio_path = Path("/tmp/female_ngochuyen.mp3")

    audio = synthesize_chapter(chapter, model, _voice_profile(ref_audio_path))

    assert isinstance(audio, np.ndarray)
    assert model.calls == [("Nội dung chương một.", None, str(ref_audio_path))]


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
