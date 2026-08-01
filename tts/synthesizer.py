# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    try:
        if voice_profile.ref_audio_path is not None:
            audio = model.infer(
                text=chapter.text,
                ref_audio=str(voice_profile.ref_audio_path),
                denoise=True,
                style=voice_profile.style,
            )
        else:
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

    if len(audio) == 0:
        raise SynthesisError(
            f"Kết quả VieNeu-TTS cho chương {chapter.index} ({chapter.heading}) rỗng (0 mẫu âm thanh)"
        )

    try:
        return np.asarray(audio, dtype=np.float32)
    except Exception as exc:
        raise SynthesisError(
            f"Kết quả VieNeu-TTS cho chương {chapter.index} không đúng định dạng mong đợi: {exc}"
        ) from exc
