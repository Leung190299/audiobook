# episodes/music.py
"""Nhạc nền nhẹ dưới giọng đọc (thử nghiệm 09/11/2026).

Gợi ý tìm kiếm YouTube xếp "audio truyện buồn có nhạc" ở vị trí 2 khi gõ
"audio truyện": người nghe muốn có nhạc nền. Kênh chưa từng có nhạc, nên thử
MỘT tập rồi so giữ chân với các tập cùng tuần trước khi bật hẳn.

Bật bằng biến môi trường, mặc định TẮT để lượt chạy hằng ngày không đổi:
    AUDIOBOOK_BGM=1            bốc một file trong assets/music/ (seed = stem tập)
    AUDIOBOOK_BGM=assets/music/pad-am-soft.mp3   dùng đúng file đó
    AUDIOBOOK_BGM_VOLUME=0.15  hệ số âm lượng Remotion (0-1), mặc định 0.15

Remotion phát file này lặp (<Audio loop />) suốt tập, trộn với giọng đọc lúc
render -- không đụng vào wav của stage 2 nên mốc câu/chương cho Shorts giữ
nguyên. Nhạc tự sinh bằng scripts/make_bgm.py (không có Content ID); file nhạc
nằm trong assets/music/ và được gitignore như video nền.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSIC_DIR = ROOT / "assets" / "music"
ENV_FLAG = "AUDIOBOOK_BGM"
ENV_VOLUME = "AUDIOBOOK_BGM_VOLUME"
DEFAULT_VOLUME = 0.15
EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg"}
_OFF = {"", "0", "off", "no", "false"}
_AUTO = {"1", "on", "yes", "true", "auto"}


def list_sources(directory: Path | None = None) -> list[Path]:
    directory = directory or MUSIC_DIR
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in EXTENSIONS and not p.name.startswith("."))


def volume() -> float:
    raw = os.getenv(ENV_VOLUME, "").strip()
    if not raw:
        return DEFAULT_VOLUME
    try:
        v = float(raw)
    except ValueError:
        print(f"CẢNH BÁO: {ENV_VOLUME}={raw!r} không phải số, dùng {DEFAULT_VOLUME}")
        return DEFAULT_VOLUME
    return min(1.0, max(0.01, v))


def choose(seed: str = "", directory: Path | None = None, repo_root: Path | None = None) -> dict | None:
    """Props nhạc nền cho MainVideo, hoặc None khi tắt / không có file dùng được.

    Giống backgrounds.choose: một file nhạc hỏng không đáng làm mất lượt dựng,
    nên mọi lỗi chỉ in cảnh báo và trả None (dựng không nhạc như cũ)."""
    repo_root = repo_root or ROOT
    flag = os.getenv(ENV_FLAG, "").strip()
    if flag.lower() in _OFF:
        return None
    if flag.lower() in _AUTO:
        sources = list_sources(directory)
        if not sources:
            print(f"CẢNH BÁO: {ENV_FLAG} bật nhưng {directory or MUSIC_DIR} không có file nhạc; dựng không nhạc.")
            return None
        src = random.Random(seed).choice(sources)
    else:
        src = Path(flag)
        if not src.is_absolute():
            src = repo_root / src
        if not src.is_file():
            print(f"CẢNH BÁO: {ENV_FLAG}={flag!r} không phải file có thật; dựng không nhạc.")
            return None
    try:
        rel = src.resolve().relative_to(repo_root.resolve())
    except ValueError:
        print(f"CẢNH BÁO: file nhạc {src} nằm ngoài repo, Remotion không đọc được; dựng không nhạc.")
        return None
    vol = volume()
    print(f"Nhạc nền: {src.name} (âm lượng {vol:g})")
    return {"backgroundMusic": str(rel), "backgroundMusicVolume": vol}
