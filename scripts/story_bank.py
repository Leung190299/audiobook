"""Kho 100 truyện biên tập sẵn (`data/story_bank.json`) và cách chọn truyện mỗi ngày.

Trước 24/09 stage 1 tự chọn bối cảnh trong `scripts/topics.py` rồi để Gemini nghĩ
tiêu đề và cốt. Từ nay truyện lấy từ kho: tiêu đề, hook, câu hỏi bình luận và từ
khoá thumbnail đều do người biên tập quyết, Gemini chỉ viết chương.

Trạng thái đã dùng nằm ở file RIÊNG `output/story_bank_state.json`; `story_bank.json`
là dữ liệu biên tập, không bao giờ bị code ghi đè.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from scripts.topics import topic_for_date

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BANK_PATH = ROOT / "data" / "story_bank.json"
DEFAULT_STATE_PATH = ROOT / "output" / "story_bank_state.json"

# Cửa sổ Tết 2027 (mùng 1 rơi vào 06/02/2027): truyện gắn nhãn "Trước Tết" chỉ
# được chọn trong khoảng này, ngoài ra bỏ qua dù ưu tiên A.
TET_START = date(2027, 1, 4)
TET_END = date(2027, 2, 5)
TET_TIMING_MARK = "Trước Tết"

# Thứ tự xét ưu tiên. Hết A mới sang B, hết B mới đụng C.
PRIORITY_ORDER = ("A", "B", "C")


class StoryBankError(Exception):
    pass


@dataclass(frozen=True)
class Story:
    id: int
    topic: str
    series: str
    title: str
    premise: str
    twist: str
    hook: str
    comment_question: str
    thumb_keywords: tuple[str, ...]
    timing: str
    priority: str
    publish_date: date | None
    outline: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bank:
    writing_rules: list[str]
    series: dict
    stories: list[Story]
    publish_hour: int = 20

    def series_for(self, story: Story) -> dict | None:
        """Khối mô tả series của truyện, hoặc None nếu là truyện lẻ.

        Dùng để chèn nguyên vào prompt stage 1 cho tên và tính cách nhân vật
        nhất quán giữa các truyện cùng series.
        """
        return self.series.get(story.series)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise StoryBankError(f"publish_date không đúng dạng YYYY-MM-DD: {raw!r}") from exc


def load_bank(path: Path = DEFAULT_BANK_PATH) -> Bank:
    if not path.exists():
        raise StoryBankError(
            f"Không tìm thấy kho truyện tại {path}. Kho nằm trong repo "
            "(data/story_bank.json); kiểm tra lại nhánh đang dùng."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryBankError(f"Kho truyện {path} không phải JSON hợp lệ: {exc}") from exc

    stories = []
    for raw in data.get("stories", []):
        stories.append(
            Story(
                id=int(raw["id"]),
                topic=raw["topic"],
                series=raw.get("series", ""),
                title=raw["title"],
                premise=raw.get("premise", ""),
                twist=raw.get("twist", ""),
                hook=raw.get("hook", ""),
                comment_question=raw.get("comment_question", ""),
                thumb_keywords=tuple(raw.get("thumb_keywords", [])),
                timing=raw.get("timing", ""),
                priority=raw.get("priority", "C"),
                publish_date=_parse_date(raw.get("publish_date")),
                outline=tuple(raw.get("outline", []) or ()),
            )
        )
    if not stories:
        raise StoryBankError(f"Kho truyện {path} không có truyện nào.")

    return Bank(
        writing_rules=list(data.get("writing_rules", [])),
        series=dict(data.get("series", {})),
        stories=stories,
        publish_hour=int(data.get("publish_hour", 20)),
    )


def get_story(story_id: int, path: Path = DEFAULT_BANK_PATH) -> Story:
    bank = load_bank(path)
    for story in bank.stories:
        if story.id == story_id:
            return story
    raise StoryBankError(
        f"Kho truyện không có truyện id {story_id} (kho có {len(bank.stories)} truyện)."
    )


# --- trạng thái đã dùng ----------------------------------------------------


def load_state(state_path: Path = DEFAULT_STATE_PATH) -> dict:
    if not state_path.exists():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # State hỏng thì coi như chưa dùng truyện nào còn hơn làm vỡ cả lượt
        # chạy; tệ nhất là đăng lại một truyện, nhìn thấy ngay.
        return {}
    return data if isinstance(data, dict) else {}


def used_ids(state_path: Path = DEFAULT_STATE_PATH) -> set[int]:
    out = set()
    for key, value in load_state(state_path).items():
        if isinstance(value, dict) and value.get("status") in (None, "used", "published"):
            try:
                out.add(int(key))
            except (TypeError, ValueError):
                continue
    return out


def mark_used(
    story_id: int,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    status: str = "used",
    video_id: str | None = None,
    published_at: str | None = None,
) -> None:
    state = load_state(state_path)
    entry = dict(state.get(str(story_id), {}))
    entry["status"] = status
    if video_id is not None:
        entry["video_id"] = video_id
    if published_at is not None:
        entry["published_at"] = published_at
    state[str(story_id)] = entry
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --- chọn truyện -----------------------------------------------------------


def in_tet_window(day: date) -> bool:
    return TET_START <= day <= TET_END


def _timing_allowed(story: Story, day: date) -> bool:
    if TET_TIMING_MARK in (story.timing or ""):
        return in_tet_window(day)
    return True


def pick_story(
    day: date,
    *,
    path: Path = DEFAULT_BANK_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    rotation: tuple[str, ...] | None = None,
    exclude: set[int] | None = None,
) -> Story | None:
    """Truyện cho ngày phát sóng `day`, hoặc None nếu kho không còn gì phù hợp.

    Thứ tự: truyện hẹn đúng ngày (ưu tiên tuyệt đối, bất kể chủ đề và ưu tiên)
    -> truyện chưa dùng, đúng chủ đề của ngày theo vòng xoay, ưu tiên A rồi B
    rồi C. Trong cùng một mức ưu tiên lấy id nhỏ nhất để kết quả ổn định,
    không phụ thuộc thứ tự đọc file.
    """
    bank = load_bank(path)
    taken = used_ids(state_path) | (exclude or set())

    scheduled = [
        s for s in bank.stories if s.publish_date == day and s.id not in taken
    ]
    if scheduled:
        return min(scheduled, key=lambda s: s.id)

    topic = topic_for_date(day, rotation)
    candidates = [
        s
        for s in bank.stories
        if s.id not in taken
        and s.topic == topic
        # Truyện đã hẹn ngày khác thì để dành đúng ngày đó, không lấy sớm.
        and s.publish_date is None
        and _timing_allowed(s, day)
    ]
    for priority in PRIORITY_ORDER:
        same = [s for s in candidates if s.priority == priority]
        if same:
            return min(same, key=lambda s: s.id)
    return None


def pick_upcoming(
    start: date,
    days: int = 7,
    *,
    path: Path = DEFAULT_BANK_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    rotation: tuple[str, ...] | None = None,
) -> list[tuple[date, Story | None]]:
    """Lịch dự kiến `days` ngày liên tiếp, không lặp truyện trong cùng lần xem.

    Chỉ để xem trước (`--dry-run-pick`); không ghi gì vào state.
    """
    picked: set[int] = set()
    out: list[tuple[date, Story | None]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        story = pick_story(
            day, path=path, state_path=state_path, rotation=rotation, exclude=picked
        )
        if story is not None:
            picked.add(story.id)
        out.append((day, story))
    return out
