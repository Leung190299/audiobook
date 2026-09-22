# episodes/storage.py
"""Đường dẫn và manifest của stage 4 (episodes).

Một lượt chạy sinh một stem `<trope>-<ts>` dùng chung cho mọi tập (như
shorts/storage.py), tập N thành `<stem>-ep-0N.{wav,mp4,-props.json}`. Manifest
`<stem>-episodes.json` là hợp đồng giữa stage 4 và stage 5/6/8: ai cần biết có
mấy tập, file nào, mốc chương ra sao thì đọc nó, không tự đoán từ tên file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def make_stem(trope: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{trope}-{timestamp}"


def episode_stem(stem: str, number: int) -> str:
    if not 1 <= number <= 99:
        raise ValueError(f"Số tập phải nằm trong khoảng 1-99, nhận được {number}")
    return f"{stem}-ep-{number:02d}"


def episode_audio_path(ep_stem: str, output_dir: Path) -> Path:
    return output_dir / f"{ep_stem}.wav"


def episode_video_path(ep_stem: str, output_dir: Path) -> Path:
    return output_dir / f"{ep_stem}.mp4"


def save_episode_props(ep_stem: str, props: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{ep_stem}-props.json"
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def manifest_path(stem: str, output_dir: Path) -> Path:
    return output_dir / f"{stem}-episodes.json"


def save_manifest(stem: str, manifest: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(stem, output_dir)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "episodes" not in data or not data["episodes"]:
        raise ValueError(f"Manifest {path} không có mảng 'episodes'.")
    return data
