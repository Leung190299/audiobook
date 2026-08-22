# tts/synthesizer.py
import numpy as np

from scripts.models import Chapter
from tts.voice_profile import VoiceProfile


class SynthesisError(Exception):
    pass


def synthesize_chapter(chapter: Chapter, model, voice_profile: VoiceProfile) -> np.ndarray:
    # Không còn nhánh theo ref_audio_path ở đây: khi cấu hình là voice-clone,
    # tts/cli.py đã enroll ref_audio_path một lần (model.add_voice) rồi gán
    # voice_profile.voice thành tên giọng đã enroll đó trước khi vào vòng lặp
    # từng câu. Gọi ref_audio= ở đây (mỗi câu) sẽ enroll lại từ đầu mỗi lần —
    # đúng lỗi mà cách này sửa.
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
            f"Kết quả VieNeu-TTS cho chương {chapter.index} ({chapter.heading}) "
            "không đúng định dạng mong đợi"
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
