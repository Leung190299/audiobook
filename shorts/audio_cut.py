# shorts/audio_cut.py
"""Cắt một đoạn từ file wav gốc của cả tập ra file wav riêng cho một phần short.

Đọc thẳng đúng đoạn cần bằng `soundfile.read(..., start=, stop=)` chứ không nạp
cả file gốc (~50 phút) vào bộ nhớ mỗi lần cắt -- một tập cắt ra ~30 phần, nạp cả
file 30 lần sẽ rất tốn bộ nhớ và chậm.

`sample_rate` đọc từ chính file nguồn qua `soundfile.info`, không nhận qua tham
số -- như vậy không có chỗ để truyền sai sample rate giữa nguồn và đích.

Không chuẩn hoá lại độ ồn ở đây: audio nguồn đã được stage 2 chuẩn hoá một lần
trên toàn tập, xem docs/superpowers/specs/2026-08-22-shorts-series-design.md.
"""

from pathlib import Path

import soundfile as sf


class AudioCutError(Exception):
    pass


def cut_wav(source: Path, start_seconds: float, end_seconds: float, dest: Path) -> int:
    if end_seconds <= start_seconds:
        raise AudioCutError(
            f"Khoảng cắt rỗng: start_seconds ({start_seconds}) phải nhỏ hơn "
            f"end_seconds ({end_seconds})"
        )

    info = sf.info(source)
    sample_rate = info.samplerate

    start_frame = round(start_seconds * sample_rate)
    stop_frame = round(end_seconds * sample_rate)

    if start_frame < 0 or stop_frame > info.frames:
        raise AudioCutError(
            f"Khoảng cắt [{start_seconds}s, {end_seconds}s) nằm ngoài độ dài file "
            f"nguồn {source} (dài {info.frames / sample_rate:.2f}s)"
        )

    data, _ = sf.read(source, start=start_frame, stop=stop_frame, dtype="float32")

    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dest, data, sample_rate)

    return len(data)
