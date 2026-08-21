"""Lưu ý tưởng hằng ngày + lịch sử để tránh làm trùng motif."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trend.idea_generator import StoryIdea

HISTORY_LIMIT = 30


def history_path(output_dir: Path) -> Path:
    return output_dir / "history.json"


def load_recent_titles(output_dir: Path, limit: int = 15) -> list[str]:
    path = history_path(output_dir)
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(entries, list):
        return []
    return [
        f"{e.get('title_hint', '')} ({e.get('slug', '')})"
        for e in entries[-limit:]
        if isinstance(e, dict)
    ]


def append_history(output_dir: Path, idea: StoryIdea) -> None:
    path = history_path(output_dir)
    entries: list = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                entries = loaded
        except json.JSONDecodeError:
            entries = []

    entries.append(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            **idea.to_dict(),
        }
    )
    path.write_text(
        json.dumps(entries[-HISTORY_LIMIT:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_idea(idea: StoryIdea, output_dir: Path) -> tuple[Path, Path]:
    """Ghi file .txt (đầu vào cho scripts.cli --idea-file) và .json (lưu vết)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{idea.slug}-{timestamp}"

    txt_path = output_dir / f"{stem}.txt"
    # scripts.cli đọc nguyên file này làm mô tả motif, nên chỉ ghi nội dung ý tưởng,
    # không kèm nhãn hay ghi chú — mọi thứ trong file đều đi thẳng vào prompt Gemini.
    txt_path.write_text(f"{idea.title_hint}\n\n{idea.idea}\n", encoding="utf-8")

    json_path = output_dir / f"{stem}.json"
    json_path.write_text(
        json.dumps(idea.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return txt_path, json_path
