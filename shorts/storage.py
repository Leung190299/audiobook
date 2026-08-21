# shorts/storage.py
"""Lưu output của stage short.

Khác `tts/storage.py` và `video/storage.py` ở chỗ: timestamp được sinh MỘT LẦN qua
`make_stem()` rồi truyền vào từng hàm lưu, để cả .wav/.mp4/-props.json/.txt của cùng
một lượt chạy dùng chung một tên gốc. Nếu mỗi hàm tự sinh timestamp thì bốn file sẽ
lệch nhau vài giây và rất khó ghép lại khi cần lần vết.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from shorts.excerpt import ShortExcerpt


def make_stem(trope: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{trope}-{timestamp}"


def save_short_audio(
    stem: str, audio: np.ndarray, sample_rate: int, output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.wav"
    sf.write(path, audio, sample_rate)
    return path


def save_short_props(stem: str, props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}-props.json"
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def short_video_path(stem: str, output_dir: Path) -> Path:
    return output_dir / f"{stem}.mp4"


def save_short_metadata(
    stem: str,
    excerpt: ShortExcerpt,
    episode_title: str,
    video_filename: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{stem}.txt"
    path.write_text(
        f"TIÊU ĐỀ:\n{excerpt.short_title}\n\n"
        f"MÔ TẢ:\n{excerpt.short_description}\n\n"
        f"TẬP ĐẦY ĐỦ:\n{episode_title}\n\n"
        f"TÊN FILE VIDEO:\n{video_filename}\n",
        encoding="utf-8",
    )
    return path
