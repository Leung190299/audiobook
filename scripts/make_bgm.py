# scripts/make_bgm.py
"""Sinh nhạc nền pad nhẹ, lặp liền mạch, cho episodes/music.py (09/11/2026).

    uv run python -m scripts.make_bgm            # -> assets/music/pad-am-soft.mp3

Vì sao tự sinh thay vì tải nhạc: kênh từng bị claim bản quyền (31/10), và nhạc
thư viện YouTube phải tải tay. Pad sine nhiều lớp, hợp âm La thứ chậm, lọc
thông thấp -- đủ "có nhạc" dưới giọng đọc mà không tranh chú ý. Vòng 8 hợp âm
x 20 giây = 160 giây, hợp âm cuối hòa vào hợp âm đầu nên lặp không nghe mối nối.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "music"
SR = 44100
CHORD_SECONDS = 20.0
XFADE_SECONDS = 6.0
# La thứ: Am - F - C - G - Am - F - Em - Am (Hz, 4 bè thấp để nằm dưới giọng nữ).
CHORDS = [
    [110.00, 164.81, 220.00, 261.63],
    [87.31, 130.81, 174.61, 220.00],
    [130.81, 196.00, 261.63, 329.63],
    [98.00, 146.83, 196.00, 246.94],
    [110.00, 164.81, 220.00, 261.63],
    [87.31, 130.81, 174.61, 220.00],
    [82.41, 123.47, 164.81, 196.00],
    [110.00, 164.81, 220.00, 261.63],
]
TARGET_RMS_DB = -18.0
PEAK_DB = -3.0


def _voice(freq: float, n: int, phase_seed: int) -> np.ndarray:
    """Một nốt pad: hai dao động lệch ±4 cent + bội âm 2, 3 nhỏ dần, rung chậm."""
    t = np.arange(n) / SR
    rng = np.random.default_rng(phase_seed)
    out = np.zeros(n)
    for cents, gain in ((-4, 0.5), (4, 0.5)):
        f = freq * 2 ** (cents / 1200)
        vib = 1 + 0.003 * np.sin(2 * np.pi * 0.11 * t + rng.uniform(0, 2 * np.pi))
        ph = rng.uniform(0, 2 * np.pi)
        out += gain * np.sin(2 * np.pi * f * vib * t + ph)
        out += gain * 0.25 * np.sin(2 * np.pi * 2 * f * vib * t + ph)
        out += gain * 0.10 * np.sin(2 * np.pi * 3 * f * vib * t + ph)
    return out


def _envelope(n: int, fade: int) -> np.ndarray:
    env = np.ones(n)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, fade))
    env[:fade] = ramp
    env[-fade:] = ramp[::-1]
    return env


def render(chords=CHORDS, chord_seconds=CHORD_SECONDS, xfade_seconds=XFADE_SECONDS) -> np.ndarray:
    total = int(len(chords) * chord_seconds * SR)
    seg = int((chord_seconds + xfade_seconds) * SR)
    fade = int(xfade_seconds * SR)
    env = _envelope(seg, fade)
    left = np.zeros(total)
    right = np.zeros(total)
    for i, chord in enumerate(chords):
        start = int(i * chord_seconds * SR - fade / 2) % total
        idx = (np.arange(seg) + start) % total  # vòng tròn -> hợp âm cuối hòa vào đầu
        for k, f in enumerate(chord):
            tone = _voice(f, seg, phase_seed=i * 10 + k) * env / len(chord)
            left[idx] += tone
            right[idx] += np.roll(tone, int(0.011 * SR))  # lệch 11 ms cho rộng stereo
    stereo = np.stack([left, right])
    # Lọc thông thấp 1,6 kHz: pad nằm dưới dải giọng nói (chủ yếu 1-4 kHz).
    sos = butter(2, 1600, btype="low", fs=SR, output="sos")
    stereo = sosfilt(sos, stereo, axis=1)
    # Hơi thở chậm ±12% để không đều như máy.
    t = np.arange(total) / SR
    stereo *= 1 + 0.12 * np.sin(2 * np.pi * t / 37.0)
    rms = np.sqrt(np.mean(stereo**2))
    stereo *= 10 ** (TARGET_RMS_DB / 20) / rms
    peak = np.max(np.abs(stereo))
    limit = 10 ** (PEAK_DB / 20)
    if peak > limit:
        stereo *= limit / peak
    return stereo.astype(np.float32)


def write(stereo: np.ndarray, out_mp3: Path) -> Path:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    wav = out_mp3.with_suffix(".wav")
    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype("<i2")
    import wave

    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "160k", str(out_mp3)],
        check=True,
    )
    wav.unlink()
    return out_mp3


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else OUT_DIR / "pad-am-soft.mp3"
    path = write(render(), out)
    print(f"Đã sinh nhạc nền: {path} ({len(CHORDS) * CHORD_SECONDS:.0f} giây, lặp liền mạch)")


if __name__ == "__main__":
    main()
