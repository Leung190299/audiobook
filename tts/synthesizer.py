# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    try:
        audio = model.infer(
            text=chapter.text, voice=voice_profile.voice, style=voice_profile.style
        )
    except Exception as exc:
        raise SynthesisError(
            f"Lỗi khi lồng tiếng chương {chapter.index} ({chapter.heading}): {exc}"
        ) from exc

    if audio is None or not hasattr(audio, "__len__"):
        raise SynthesisError(
            f"Kết quả VieNeu-TTS cho chương {chapter.index} không đúng định dạng mong đợi"
        )

    return np.asarray(audio, dtype=np.float32)
