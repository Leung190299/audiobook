"""Kho 100 truyện biên tập sẵn (`data/story_bank.json`) và cách chọn truyện mỗi ngày.

Trước 24/09 stage 1 tự chọn bối cảnh trong `scripts/topics.py` rồi để Gemini nghĩ
tiêu đề và cốt. Từ nay truyện lấy từ kho: tiêu đề, hook, câu hỏi bình luận và từ
khoá thumbnail đều do người biên tập quyết, Gemini chỉ viết chương.

Trạng thái đã dùng nằm ở file RIÊNG `output/story_bank_state.json`; `story_bank.json`
là dữ liệu biên tập, không bao giờ bị code ghi đè.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.topics import parse_rotation, topic_for_date

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BANK_PATH = ROOT / "data" / "story_bank.json"
DEFAULT_STATE_PATH = ROOT / "output" / "story_bank_state.json"
# Kho phụ do stage 0 (keywords/) tự viết từ từ khóa xu hướng; gitignore, id từ
# AUTO_ID_START để không đụng kho biên tập. load_bank gộp cả hai.
DEFAULT_AUTO_BANK_PATH = ROOT / "data" / "story_bank.auto.json"
AUTO_ID_START = 1000

# Cửa sổ Tết 2027 (mùng 1 rơi vào 06/02/2027): truyện gắn nhãn "Trước Tết" chỉ
# được chọn trong khoảng này, ngoài ra bỏ qua dù ưu tiên A.
TET_START = date(2027, 1, 4)
TET_END = date(2027, 2, 5)
TET_TIMING_MARK = "Trước Tết"

# Thứ tự xét ưu tiên. Hết A mới sang B, hết B mới đụng C.
PRIORITY_ORDER = ("A", "B", "C")

# Giờ lên sóng cố định của kênh; "ngày phát sóng kế tiếp" tính theo múi giờ này.
CHANNEL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PUBLISH_HOUR = 20


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
    for raw in list(data.get("stories", [])) + _auto_stories(path):
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


def _auto_stories(bank_path: Path) -> list[dict]:
    """Truyện trong kho phụ cạnh kho chính (data/story_bank.auto.json). Kho chính
    ở chỗ khác (test) thì tìm file .auto.json cạnh nó."""
    auto_path = bank_path.with_name(bank_path.stem + ".auto.json")
    if not auto_path.exists():
        return []
    try:
        data = json.loads(auto_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = data.get("stories", []) if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict)]


def get_story(story_id: int, path: Path = DEFAULT_BANK_PATH) -> Story:
    bank = load_bank(path)
    for story in bank.stories:
        if story.id == story_id:
            return story
    raise StoryBankError(
        f"Kho truyện không có truyện id {story_id} (kho có {len(bank.stories)} truyện)."
    )


# --- trạng thái đã dùng ----------------------------------------------------


def load_state(state_path: Path | None = None) -> dict:
    state_path = state_path or DEFAULT_STATE_PATH
    if not state_path.exists():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # State hỏng thì coi như chưa dùng truyện nào còn hơn làm vỡ cả lượt
        # chạy; tệ nhất là đăng lại một truyện, nhìn thấy ngay.
        return {}
    return data if isinstance(data, dict) else {}


def used_ids(state_path: Path | None = None) -> set[int]:
    state_path = state_path or DEFAULT_STATE_PATH
    out = set()
    for key, value in load_state(state_path).items():
        if isinstance(value, dict) and value.get("status") in (
            None, "used", "built", "published"
        ):
            try:
                out.add(int(key))
            except (TypeError, ValueError):
                continue
    return out


def mark_used(
    story_id: int,
    *,
    state_path: Path | None = None,
    status: str = "used",
    video_id: str | None = None,
    published_at: str | None = None,
) -> None:
    state_path = state_path or DEFAULT_STATE_PATH
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


def set_air_time(
    story_id: int, published_at: str | None, *, state_path: Path | None = None
) -> None:
    """Đặt hoặc XOÁ (None) giờ chiếu của truyện đã đăng -- upload/release.py gọi
    khi hẹn một video trong kho lên sóng hoặc bỏ hẹn video đã hẹn quá xa.
    mark_used không xoá được published_at (None nghĩa là "không đổi" ở đó)."""
    state_path = state_path or DEFAULT_STATE_PATH
    state = load_state(state_path)
    entry = dict(state.get(str(story_id), {}))
    entry["status"] = "published"
    if published_at is None:
        entry.pop("published_at", None)
    else:
        entry["published_at"] = published_at
    state[str(story_id)] = entry
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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
    state_path: Path | None = None,
    rotation: tuple[str, ...] | None = None,
    exclude: set[int] | None = None,
) -> Story | None:
    """Truyện cho ngày phát sóng `day`, hoặc None nếu kho không còn gì phù hợp.

    Thứ tự: truyện hẹn đúng ngày (ưu tiên tuyệt đối, bất kể chủ đề và ưu tiên)
    -> truyện chưa dùng, đúng chủ đề của ngày theo vòng xoay, ưu tiên A rồi B
    rồi C. Trong cùng một mức ưu tiên lấy id nhỏ nhất để kết quả ổn định,
    không phụ thuộc thứ tự đọc file.
    """
    state_path = state_path or DEFAULT_STATE_PATH
    bank = load_bank(path)
    taken = used_ids(state_path) | (exclude or set())

    scheduled = [
        s for s in bank.stories if s.publish_date == day and s.id not in taken
    ]
    if scheduled:
        return min(scheduled, key=lambda s: s.id)

    topic = topic_for_date(day, rotation)
    pool = [
        s
        for s in bank.stories
        if s.id not in taken
        # Truyện đã hẹn ngày khác thì để dành đúng ngày đó, không lấy sớm.
        and s.publish_date is None
        and _timing_allowed(s, day)
    ]
    # Hết truyện đúng chủ đề của ngày thì lấy chủ đề khác chứ không bỏ trống tối
    # đó (10/11: kho thay 50 truyện từ doc "50 ý tưởng", hoc_duong chỉ còn 2).
    for candidates in ([s for s in pool if s.topic == topic], pool):
        for priority in PRIORITY_ORDER:
            same = [s for s in candidates if s.priority == priority]
            if same:
                return min(same, key=lambda s: s.id)
    return None


def occupied_days(*, path: Path | None = None, state_path: Path | None = None) -> set[date]:
    """Những tối đã có video: đã đăng vào tối đó, hoặc truyện hẹn tối đó đã dựng.

    Truyện đã đăng tính theo published_at (có thể đã bị dời khỏi ngày hẹn vì
    đăng muộn). Truyện dựng xong chưa đăng thì tính theo ngày hẹn của nó.
    """
    # Giải mặc định lúc gọi: gắn lúc import thì monkeypatch trong test không ăn.
    path = path or DEFAULT_BANK_PATH
    state_path = state_path or DEFAULT_STATE_PATH
    state = load_state(state_path)
    days: set[date] = set()
    for value in state.values():
        if not isinstance(value, dict) or value.get("status") != "published":
            continue
        raw = value.get("published_at")
        if not raw:
            continue
        try:
            days.add(datetime.fromisoformat(raw).astimezone(CHANNEL_TZ).date())
        except ValueError:
            continue
    for story in load_bank(path).stories:
        ban_ghi = state.get(str(story.id))
        if (
            story.publish_date
            and isinstance(ban_ghi, dict)
            and ban_ghi.get("status") in (None, "used", "built")
        ):
            days.add(story.publish_date)
    return days


def pick_next_unfilled(
    start: date,
    *,
    horizon: int = 60,
    path: Path | None = None,
    state_path: Path | None = None,
    rotation: tuple[str, ...] | None = None,
) -> tuple[date, Story] | None:
    """Tối gần nhất từ `start` chưa có video, cùng truyện nên dựng cho tối đó.

    Thay cho pick_story(ngày phát sóng kế tiếp) trong `--story auto`. Lịch biên
    tập kín mọi tối tới 25/10; cách cũ thấy 06/10 đã có #42 thì vớ một truyện
    KHÔNG hẹn (#46), dựng mất một tiếng mà không có tối nào để chiếu. Nay đi
    tiếp tới tối chưa có video và dựng đúng truyện đã hẹn cho tối đó (hoặc
    theo vòng xoay nếu tối đó không ai hẹn) -- kênh luôn có video sẵn trước.
    """
    path = path or DEFAULT_BANK_PATH
    state_path = state_path or DEFAULT_STATE_PATH
    occupied = occupied_days(path=path, state_path=state_path)
    for offset in range(horizon):
        day = start + timedelta(days=offset)
        if day in occupied:
            continue
        story = pick_story(day, path=path, state_path=state_path, rotation=rotation)
        if story is not None:
            return day, story
    return None


def first_free_evening(
    start: date,
    *,
    horizon: int = 365,
    path: Path | None = None,
    state_path: Path | None = None,
) -> date:
    """Tối đầu tiên từ `start` chưa có video VÀ chưa được biên tập hẹn cho ai.

    Dùng khi đăng truyện không có ngày hẹn. Trước đây code mặc định "tối mai"
    bất kể tối mai đã có video, phải tự chỉ ngày bằng tay cho #6/#75 (28/09)
    và #9 (05/10).
    """
    path = path or DEFAULT_BANK_PATH
    state_path = state_path or DEFAULT_STATE_PATH
    occupied = occupied_days(path=path, state_path=state_path)
    reserved = {s.publish_date for s in load_bank(path).stories if s.publish_date}
    for offset in range(horizon):
        day = start + timedelta(days=offset)
        if day not in occupied and day not in reserved:
            return day
    return start + timedelta(days=horizon)


def pick_upcoming(
    start: date,
    days: int = 7,
    *,
    path: Path = DEFAULT_BANK_PATH,
    state_path: Path | None = None,
    rotation: tuple[str, ...] | None = None,
) -> list[tuple[date, Story | None]]:
    """Lịch dự kiến `days` ngày liên tiếp, không lặp truyện trong cùng lần xem.

    Chỉ để xem trước (`--dry-run-pick`); không ghi gì vào state.
    """
    state_path = state_path or DEFAULT_STATE_PATH
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


def next_air_date(now: datetime | None = None) -> date:
    """Ngày phát sóng kế tiếp: hôm nay nếu chưa tới 20h, không thì ngày mai.

    `--story auto` chọn truyện cho NGÀY LÊN SÓNG chứ không phải ngày dựng, vì
    lượt chạy 09:00 hôm nay tạo video phát 20h cùng ngày, còn lượt chạy lúc 22h
    thì video phát tối mai.
    """
    now = now.astimezone(CHANNEL_TZ) if now else datetime.now(CHANNEL_TZ)
    today = now.date()
    return today if now.hour < PUBLISH_HOUR else today + timedelta(days=1)


def _format_row(day: date, story: "Story | None") -> str:
    if story is None:
        return f"{day}  (kho không còn truyện phù hợp)"
    mark = "hẹn" if story.publish_date == day else "   "
    return (
        f"{day}  {mark}  #{story.id:<3} {story.priority}  "
        f"{story.topic:<18} {story.title}"
    )


def main(argv: "list[str] | None" = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Xem trước hoặc chọn truyện từ kho, không dựng gì."
    )
    parser.add_argument("--upcoming", type=int, default=None, metavar="N",
                        help="In lịch N ngày tới rồi thoát")
    parser.add_argument("--pick", action="store_true",
                        help="In đúng id truyện cho --date (rỗng + mã thoát 3 nếu hết)")
    parser.add_argument("--mark-used", type=int, default=None, metavar="ID",
                        help="Đánh dấu truyện đã dựng xong (chưa đăng) rồi thoát")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; mặc định ngày phát sóng kế tiếp")
    parser.add_argument("--from", dest="start", default=None, help="YYYY-MM-DD cho --upcoming")
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--rotation", default=None,
                        help="Danh sách chủ đề cách nhau dấu phẩy; mặc định lấy .env")
    args = parser.parse_args(argv)

    rotation = parse_rotation(args.rotation) if args.rotation else None

    try:
        if args.mark_used is not None:
            # Dựng xong mà chưa đăng thì kho vẫn coi là chưa dùng, nên hôm sau
            # `--story auto` chọn lại đúng truyện đó và dựng lại từ đầu (lượt
            # 28/09 mất gần 2 tiếng như thế). Đánh dấu "built" ngay sau khi
            # dựng; lúc đăng, upload sẽ nâng lên "published" kèm video_id.
            hien = load_state(args.state).get(str(args.mark_used), {})
            if hien.get("status") == "published":
                print(f"Truyện #{args.mark_used} đã đăng rồi, giữ nguyên trạng thái.")
                return 0
            mark_used(args.mark_used, state_path=args.state, status="built")
            print(f"Đã đánh dấu truyện #{args.mark_used} là đã dựng.")
            return 0

        if args.upcoming:
            start = date.fromisoformat(args.start) if args.start else next_air_date()
            for day, story in pick_upcoming(
                start, args.upcoming, path=args.bank, state_path=args.state, rotation=rotation
            ):
                print(_format_row(day, story))
            return 0

        day = date.fromisoformat(args.date) if args.date else next_air_date()
        ket_qua = pick_next_unfilled(
            day, path=args.bank, state_path=args.state, rotation=rotation
        )
        if ket_qua is None:
            # Mã thoát riêng để run_daily.sh phân biệt "hết truyện" (rơi về
            # --topic auto) với lỗi thật (kho hỏng, thiếu file).
            return 3
        ngay, story = ket_qua
        # stdout chỉ có id (run_daily.sh đọc nguyên dòng); ngày chiếu ra stderr
        # để vào log mà không làm vỡ chỗ parse.
        print(f"Dựng sẵn cho tối {ngay:%d/%m}: #{story.id} {story.title}", file=sys.stderr)
        print(story.id)
        return 0
    except StoryBankError as exc:
        print(f"Lỗi kho truyện: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
