# episodes/audio_build.py
"""Ghép wav của một tập: cold open + khoảng lặng + thân tập + khoảng lặng outro.

Đọc đúng hai khúc cần từ wav gốc bằng `soundfile.read(start=, stop=)` như
shorts/audio_cut.py, không nạp cả file ~50 phút vào bộ nhớ. Không chuẩn hoá
lại độ ồn: stage 2 đã chuẩn hoá một lần trên toàn tập, cắt ra rồi ghép lại
không đổi mức.

Trả về thời lượng thật (giây) của file ghi ra, tính từ số mẫu -- stage 4 dùng
số này để đặt mốc outro chứ không tin vào mốc câu của stage 2 (mốc câu làm tròn
tới ms, cộng dồn qua ba khúc có thể lệch vài chục ms so với file thật, đủ để
card CTA hiện lệch một khung hình).
"""

from pathlib import Path

import numpy as np
import soundfile as sf

from episodes.cutter import EpisodeCut


class EpisodeAudioError(Exception):
    pass


def _read_segment(source: Path, start_seconds: float, end_seconds: float, info) -> np.ndarray:
    sample_rate = info.samplerate
    start_frame = round(start_seconds * sample_rate)
    stop_frame = round(end_seconds * sample_rate)
    if start_frame < 0 or stop_frame > info.frames or stop_frame <= start_frame:
        raise EpisodeAudioError(
            f"Khoảng cắt [{start_seconds}s, {end_seconds}s) nằm ngoài độ dài file "
            f"nguồn {source} (dài {info.frames / sample_rate:.2f}s)"
        )
    data, _ = sf.read(source, start=start_frame, stop=stop_frame, dtype="float32")
    return data


def build_episode_wav(source: Path, cut: EpisodeCut, dest: Path) -> float:
    info = sf.info(source)
    sample_rate = info.samplerate

    def silence(seconds: float) -> np.ndarray:
        frames = round(seconds * sample_rate)
        if info.channels > 1:
            return np.zeros((frames, info.channels), dtype="float32")
        return np.zeros(frames, dtype="float32")

    parts: list[np.ndarray] = []
    if cut.cold_open is not None:
        parts.append(
            _read_segment(
                source, cut.cold_open.source_start_seconds, cut.cold_open.source_end_seconds, info
            )
        )
        parts.append(silence(cut.gap_seconds))
    parts.append(
        _read_segment(source, cut.body_source_start_seconds, cut.body_source_end_seconds, info)
    )
    parts.append(silence(cut.outro_seconds))

    data = np.concatenate(parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dest, data, sample_rate)
    return len(data) / sample_rate
