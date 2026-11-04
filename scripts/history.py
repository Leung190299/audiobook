# scripts/history.py
"""Lịch sử premise/tiêu đề đã dùng theo chủ đề: `output/topics_history.json`.

Ba chủ đề chạy mỗi ngày nghĩa là mỗi chủ đề lặp lại 2-3 lần/tuần. Không nhớ
thì Gemini rất hay trả lại cùng một premise ("bác Cả đòi chia đất") với tiêu đề
khác chút ít -- người xem cũ bấm vào thấy truyện cũ là mất luôn. File này nhớ
bối cảnh + tiêu đề đã dùng để:

- stage 1 chọn một bối cảnh CHƯA dùng trong 30 ngày (xoay vòng qua >= 10 bối
  cảnh của mỗi chủ đề);
- chặn dàn ý trùng tiêu đề (so sau khi bỏ dấu, bỏ dấu câu) trong 30 ngày;
- đưa danh sách premise đã dùng vào prompt làm "motif cấm".

Định dạng: {"entries": [{"date", "topic", "setting", "title", "premise", "script"}]}
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

DEDUP_DAYS = 30
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "output" / "topics_history.json"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_history(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("entries", []))


def _recent(entries: list[dict], topic: str, today: date, days: int) -> list[dict]:
    cutoff = today - timedelta(days=days)
    out = []
    for e in entries:
        if e.get("topic") != topic:
            continue
        try:
            d = date.fromisoformat(e["date"])
        except (KeyError, ValueError):
            continue
        if d >= cutoff:
            out.append(e)
    return out


def pick_setting(
    settings: tuple[str, ...] | list[str],
    entries: list[dict],
    topic: str,
    today: date,
    days: int = DEDUP_DAYS,
) -> str:
    """Bối cảnh chưa dùng trong `days` ngày (theo thứ tự registry, xoay theo
    ngày để hai chủ đề không luôn bắt đầu từ bối cảnh đầu). Hết bối cảnh chưa
    dùng thì lấy cái dùng LÂU NHẤT."""
    recent = _recent(entries, topic, today, days)
    used = {e.get("setting") for e in recent}
    n = len(settings)
    offset = today.toordinal() % n
    ordered = [settings[(offset + i) % n] for i in range(n)]
    for s in ordered:
        if s not in used:
            return s
    last_used: dict[str, str] = {}
    for e in recent:
        s = e.get("setting")
        if s in settings and e["date"] > last_used.get(s, ""):
            last_used[s] = e["date"]
    return min(ordered, key=lambda s: last_used.get(s, ""))


def recent_premises(entries: list[dict], topic: str, today: date, days: int = DEDUP_DAYS) -> list[str]:
    return [
        f"{e.get('title', '')} — {e.get('premise', '')}".strip(" —")
        for e in _recent(entries, topic, today, days)
    ]


def is_duplicate(
    entries: list[dict], topic: str, title: str, premise: str, today: date, days: int = DEDUP_DAYS
) -> bool:
    """Trùng nếu tiêu đề hoặc premise (sau chuẩn hoá) đã có trong `days` ngày
    của cùng chủ đề. Premise rỗng không bao giờ tính là trùng."""
    t = normalize(title)
    p = normalize(premise)
    for e in _recent(entries, topic, today, days):
        if t and normalize(e.get("title", "")) == t:
            return True
        if p and normalize(e.get("premise", "")) == p:
            return True
    return False


def record(
    topic: str,
    setting: str,
    title: str,
    premise: str,
    script_path: str,
    today: date,
    path: Path = DEFAULT_PATH,
) -> None:
    entries = load_history(path)
    entries.append(
        {
            "date": today.isoformat(),
            "topic": topic,
            "setting": setting,
            "title": title,
            "premise": premise,
            "script": script_path,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
