# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    try:
        result = model.generate(text=chapter.text, instruct=voice_profile.instruction)
    except Exception as exc:
        raise SynthesisError(
            f"Lỗi khi lồng tiếng chương {chapter.index} ({chapter.heading}): {exc}"
        ) from exc

    try:
        audio = result[0]
    except (TypeError, IndexError, KeyError) as exc:
        raise SynthesisError(
            f"Kết quả OmniVoice cho chương {chapter.index} không đúng định dạng mong đợi: {exc}"
        ) from exc

    return np.asarray(audio, dtype=np.float32)
