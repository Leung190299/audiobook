"""Kho video riêng tư và lịch nhả 7 ngày (đánh giá kênh 05/11/2026).

    uv run python -m upload.release              # hằng sáng, trước khi dựng gì
    uv run python -m upload.release --dry-run    # chỉ in kế hoạch
    uv run python -m upload.release --unschedule-only

Đánh giá 05/11: phân phối về ≈0 sau khi tải lên 9+ video một lúc (27/10) và hẹn
sẵn 30 ngày × 4 video/ngày. Kế hoạch 30 ngày: chỉ giữ 7 ngày tới trên lịch,
1 truyện + 2 Shorts mỗi ngày. Nên:

- Mọi video đăng lên đều vào KHO: riêng tư, không hẹn giờ (episodes_cli
  --no-schedule). Kho là trạng thái thật trên YouTube (videos.list), không phải
  file local -- biên tập sửa tay trong Studio thì đây vẫn đúng.
- Mỗi sáng: bỏ hẹn video nào hẹn QUÁ cửa sổ 7 ngày (về kho), rồi hẹn ĐÚNG MỘT
  video trong kho cho tối trống gần nhất trong cửa sổ, 20h, kèm 2 short đầu lúc
  20h05. Short thứ 3 (của truyện dựng trước 05/11) nằm im trong kho.
- Chọn video: ưu tiên hai chủ đề đang thắng (mẹ chồng/bố mẹ trọng sinh, họ hàng
  cực phẩm) xen kẽ nhau, rồi học đường, cuối cùng nghề lạ; cùng chủ đề thì
  video vào kho trước đi trước.

Mã thoát: 0 = đã hẹn, hoặc lịch 7 ngày đã kín; 3 = kho trống mà còn tối trống
-> run_daily.sh dựng truyện mới (xong lại gọi lệnh này để hẹn). Khác = lỗi.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from scripts import story_bank
from upload.auth import YouTubeAuthError, load_credentials
from upload.episodes_cli import (
    DEFAULT_PUBLISH_HOUR,
    INDEX_JSONL,
    LOCAL_TZ,
    SHORT_DELAY,
    default_first_air,
)
from upload.uploader import list_status, update_status

load_dotenv()

WINDOW_DAYS = 7
# Chỉ hẹn giờ short 1 và 2; từ cái thứ 3 trở đi giữ riêng tư.
RELEASE_SHORT_PARTS = 2
# Thứ tự ưu tiên chủ đề khi lấy từ kho. Hai cái đầu là "đang thắng" (05/11) và
# được xen kẽ nhau; các chủ đề không có trong danh sách xếp cuối.
WINNING_TOPICS = ("bo_me_trong_sinh", "ho_hang_viet")
TOPIC_PRIORITY = WINNING_TOPICS + ("hoc_duong", "nghe_la_hong_bien")
# uploadStatus mà video coi như không dùng được.
DEAD_UPLOAD_STATUS = {"failed", "rejected", "deleted"}


class ReleaseError(Exception):
    pass


@dataclass
class Video:
    row: dict
    privacy: str
    publish_at: datetime | None  # giờ kênh
    upload_status: str = "processed"

    @property
    def video_id(self) -> str:
        return self.row["video_id"]

    @property
    def topic(self) -> str:
        return self.row.get("topic") or ""

    @property
    def title(self) -> str:
        return self.row.get("story_title") or self.row.get("title") or self.video_id

    @property
    def url(self) -> str:
        return self.row.get("url") or f"https://youtu.be/{self.video_id}"

    @property
    def story_id(self) -> int:
        return int(self.row.get("story_id") or 0)

    @property
    def air_date(self) -> date | None:
        return self.publish_at.date() if self.publish_at else None

    @property
    def is_stock(self) -> bool:
        return (
            self.privacy == "private"
            and self.publish_at is None
            and self.upload_status not in DEAD_UPLOAD_STATUS
        )


@dataclass
class Plan:
    unschedule: list[Video] = field(default_factory=list)
    hole: date | None = None
    chosen: Video | None = None
    stock_left: int = 0

    @property
    def stock_empty(self) -> bool:
        return self.hole is not None and self.chosen is None


# --- index.jsonl ---------------------------------------------------------------


def load_index(index_jsonl: Path = INDEX_JSONL) -> list[dict]:
    """Mỗi video dài một dòng, theo thứ tự đăng; video_id trùng thì giữ dòng sau."""
    if not index_jsonl.exists():
        return []
    by_id: dict[str, dict] = {}
    for line in index_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id") and row.get("format", "full") == "full":
            by_id.pop(row["video_id"], None)
            by_id[row["video_id"]] = row
    return list(by_id.values())


def rewrite_publish_at(index_jsonl: Path, video_id: str, publish_at: datetime | None) -> None:
    """Sửa publishAt của đúng dòng có video_id (report.py và retention.py đọc cột này)."""
    if not index_jsonl.exists():
        return
    out = []
    for line in index_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if row.get("video_id") == video_id:
            row["publishAt"] = publish_at.isoformat() if publish_at else None
            line = json.dumps(row, ensure_ascii=False)
        out.append(line)
    index_jsonl.write_text("\n".join(out) + "\n", encoding="utf-8")


def shorts_of(row: dict) -> list[tuple[int, str]]:
    """[(số phần, video_id)] các short đã đăng của video dài này, theo
    `<shorts_prefix>-upload-state.json` mà chỉ mục metadata trỏ tới."""
    if not row.get("index"):
        return []
    index_path = Path(row["index"])
    if not index_path.is_file():
        return []
    try:
        prefix = json.loads(index_path.read_text(encoding="utf-8")).get("shorts_prefix")
    except json.JSONDecodeError:
        return []
    if not prefix:
        return []
    prefix = Path(prefix)
    state_path = prefix.parent / f"{prefix.name}-upload-state.json"
    if not state_path.exists():
        return []
    try:
        uploaded = json.loads(state_path.read_text(encoding="utf-8")).get("uploaded") or {}
    except json.JSONDecodeError:
        return []
    out = []
    for key, entry in uploaded.items():
        try:
            out.append((int(key), entry["video_id"]))
        except (TypeError, ValueError, KeyError):
            continue
    return sorted(out)


# --- trạng thái từ YouTube -------------------------------------------------------


def _parse_publish_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def attach_status(rows: list[dict], statuses: dict[str, dict]) -> list[Video]:
    """Ghép dòng index với status đọc từ API; video API không trả (đã xoá) thì bỏ."""
    videos = []
    for row in rows:
        st = statuses.get(row["video_id"])
        if st is None:
            continue
        videos.append(
            Video(
                row=row,
                privacy=st.get("privacyStatus") or "private",
                publish_at=_parse_publish_at(st.get("publishAt")),
                upload_status=st.get("uploadStatus") or "processed",
            )
        )
    return videos


# --- lập kế hoạch ------------------------------------------------------------------


def pick_stock(videos: list[Video]) -> Video | None:
    """Video kế tiếp lấy từ kho.

    Chủ đề theo TOPIC_PRIORITY; trong hai chủ đề thắng thì xen kẽ: lấy chủ đề
    có lần lên sóng (đã hẹn hoặc đã chiếu) xa nhất. Cùng chủ đề: vào kho trước
    đi trước (thứ tự index.jsonl).
    """
    stock = [v for v in videos if v.is_stock]
    if not stock:
        return None
    last_air: dict[str, date] = {}
    for v in videos:
        if v.air_date and (v.topic not in last_air or v.air_date > last_air[v.topic]):
            last_air[v.topic] = v.air_date

    def rank(topic: str) -> int:
        return TOPIC_PRIORITY.index(topic) if topic in TOPIC_PRIORITY else len(TOPIC_PRIORITY)

    winners = [v for v in stock if v.topic in WINNING_TOPICS]
    if winners:
        topic = min(
            {v.topic for v in winners},
            key=lambda t: (last_air.get(t, date.min), WINNING_TOPICS.index(t)),
        )
        return next(v for v in winners if v.topic == topic)
    return min(stock, key=lambda v: rank(v.topic))  # min ổn định: giữ thứ tự kho


def plan(videos: list[Video], now: datetime, window_days: int = WINDOW_DAYS) -> Plan:
    now = now.astimezone(LOCAL_TZ)
    today = now.date()
    end = today + timedelta(days=window_days)
    out = Plan()
    out.unschedule = [
        v for v in videos if v.privacy == "private" and v.air_date and v.air_date > end
    ]
    freed = {v.video_id for v in out.unschedule}
    taken = {v.air_date for v in videos if v.air_date and v.video_id not in freed}
    start = default_first_air(now).date()
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        if day not in taken:
            out.hole = day
            break
    stock = [v for v in videos if v.is_stock] + out.unschedule
    out.stock_left = len(stock)
    if out.hole is not None:
        # Video vừa bỏ hẹn cũng là hàng trong kho, đứng sau hàng có sẵn.
        pool = [v for v in videos if v.is_stock] + [
            Video(row=v.row, privacy="private", publish_at=None, upload_status=v.upload_status)
            for v in out.unschedule
        ]
        others = [v for v in videos if not v.is_stock and v.video_id not in freed]
        out.chosen = pick_stock(others + pool)
        if out.chosen is not None:
            out.stock_left -= 1
    return out


# --- thực hiện ---------------------------------------------------------------------


def _set_local(video: Video, publish_at: datetime | None, index_jsonl: Path, state_path: Path | None) -> None:
    rewrite_publish_at(index_jsonl, video.video_id, publish_at)
    if video.story_id:
        story_bank.set_air_time(
            video.story_id, publish_at.isoformat() if publish_at else None, state_path=state_path
        )


def apply(
    credentials,
    plan_: Plan,
    *,
    updater=None,
    index_jsonl: Path = INDEX_JSONL,
    state_path: Path | None = None,
    publish_hour: int = DEFAULT_PUBLISH_HOUR,
) -> None:
    # Giải lúc gọi chứ không gắn mặc định: monkeypatch trong test mới ăn.
    updater = updater or update_status
    for v in plan_.unschedule:
        if not updater(credentials, v.video_id, None):
            raise ReleaseError(f"Không bỏ hẹn được {v.title} ({v.video_id}).")
        for _, short_id in shorts_of(v.row):
            updater(credentials, short_id, None)
        _set_local(v, None, index_jsonl, state_path)
        print(f"Bỏ hẹn (về kho): {v.title} — {v.url} (từng hẹn {v.air_date})")

    if plan_.hole is None:
        print(f"Lịch {WINDOW_DAYS} ngày đã kín, kho còn {plan_.stock_left} video.")
        return
    if plan_.chosen is None:
        print(f"Kho trống: tối {plan_.hole} chưa có video.")
        return

    v = plan_.chosen
    at = datetime.combine(plan_.hole, dtime(hour=publish_hour, minute=0), tzinfo=LOCAL_TZ)
    if not updater(credentials, v.video_id, at):
        raise ReleaseError(f"Không hẹn được {v.title} ({v.video_id}) cho {at:%d/%m %H:%M}.")
    held = 0
    for n, short_id in shorts_of(v.row):
        if n <= RELEASE_SHORT_PARTS:
            updater(credentials, short_id, at + SHORT_DELAY)
        else:
            held += 1
    _set_local(v, at, index_jsonl, state_path)
    print(
        f"Đã hẹn: {v.title} — {v.url} (lên sóng {at:%Y-%m-%d %H:%M}"
        + (f", giữ lại {held} short" if held else "")
        + f"); kho còn {plan_.stock_left} video."
    )


def describe(plan_: Plan) -> str:
    lines = [f"Bỏ hẹn {len(plan_.unschedule)} video hẹn quá {WINDOW_DAYS} ngày:"]
    lines += [f"  - {v.air_date}  {v.title}" for v in plan_.unschedule] or ["  (không có)"]
    if plan_.hole is None:
        lines.append(f"Lịch {WINDOW_DAYS} ngày đã kín.")
    elif plan_.chosen is None:
        lines.append(f"Tối trống gần nhất {plan_.hole}: KHO TRỐNG.")
    else:
        lines.append(f"Tối trống gần nhất {plan_.hole}: hẹn [{plan_.chosen.topic}] {plan_.chosen.title}")
    lines.append(f"Kho sau lượt này: {plan_.stock_left} video.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bỏ hẹn video quá 7 ngày, hẹn 1 video trong kho cho tối trống gần nhất.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--unschedule-only", action="store_true", help="Chỉ bỏ hẹn, không hẹn thêm")
    parser.add_argument("--window", type=int, default=WINDOW_DAYS)
    parser.add_argument("--publish-hour", type=int, default=int(os.getenv("YOUTUBE_PUBLISH_HOUR", DEFAULT_PUBLISH_HOUR)))
    args = parser.parse_args(argv)

    rows = load_index()
    if not rows:
        print(f"Chưa có video nào trong {INDEX_JSONL}.")
        return 3
    try:
        credentials = load_credentials()
    except YouTubeAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    videos = attach_status(rows, list_status(credentials, [r["video_id"] for r in rows]))
    plan_ = plan(videos, datetime.now(LOCAL_TZ), args.window)
    if args.unschedule_only:
        plan_.hole, plan_.chosen = None, None
    if args.dry_run:
        print(describe(plan_))
        return 3 if plan_.stock_empty else 0
    try:
        apply(credentials, plan_, publish_hour=args.publish_hour)
    except ReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 3 if plan_.stock_empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
