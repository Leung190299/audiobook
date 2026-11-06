# metadata/retention.py
"""Đọc CSV "Tỷ lệ giữ chân khán giả" xuất từ YouTube Studio, chỉ ra người nghe bỏ ở ĐÂU.

    uv run python -m metadata.retention --days 14            # mọi video 14 ngày qua, qua Analytics API
    uv run python -m metadata.retention --video <video_id>   # một video, qua Analytics API
    uv run python -m metadata.retention <file.csv> --video <video_id>   # CSV tải tay từ Studio
    uv run python -m metadata.retention <file.csv> --duration 2460      # video không có trong index

Analytics API cần quyền yt-analytics.readonly (upload.auth xin ở lần đồng ý)
và API "YouTube Analytics API" bật trong Google Cloud Console. Data API
(report.py) không có số này. Không có API thì tải CSV: Studio -> video -> Số
liệu phân tích -> Mức độ tương tác -> biểu đồ tỷ lệ giữ chân -> nút tải xuống.

Ba vấn đề khác nhau, ba cách sửa khác nhau (ý từ yt-retention trong
github.com/Jakeschincariol/chatgpt-youtube-agent-skill, viết lại cho kênh mình):
  RƠI ĐẦU    mất bao nhiêu trong 30 giây đầu -- lỗi cold open/"Mở đầu" và tiêu đề
             không khớp nội dung, không phải lỗi truyện.
  VỰC        một đoạn tụt dốc hẳn so với nhịp chung -- một khoảnh khắc cụ thể.
             Có --video thì in luôn chương và câu đang đọc ở đó, đọc là biết sửa gì.
  TRƯỢT      mất đều bao nhiêu điểm mỗi phút ở thân truyện -- nhịp truyện, sửa
             bằng cắt chứ không bằng viết lại.

Mốc câu lấy từ output/episodes/<stem>-props.json (trục thời gian VIDEO, đã cộng
cold open), nối qua output/metadata/index.jsonl theo video_id.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_JSONL = REPO_ROOT / "output" / "metadata" / "index.jsonl"
EPISODES_DIR = REPO_ROOT / "output" / "episodes"

HOOK_SECONDS = 30.0
HEALTHY_HOOK_LEAK = 25.0
SEVERE_HOOK_LEAK = 40.0
# Đoạn cuối luôn tụt (card kết, người nghe biết truyện hết): không tính là vực.
TAIL_FRACTION = 0.05
MAX_CLIFFS = 5
# Vực = tụt ít nhất chừng này điểm VÀ gấp CLIFF_FACTOR lần mức tụt trung vị.
MIN_CLIFF_POINTS = 0.8
CLIFF_FACTOR = 2.5

_POSITION_HEADER = re.compile(r"position|vị trí", re.I)
_ABSOLUTE_HEADER = re.compile(r"absolute|tuyệt đối", re.I)
_RETENTION_HEADER = re.compile(r"retention|giữ chân", re.I)
_RELATIVE_HEADER = re.compile(r"relative|tương đối", re.I)


class RetentionError(Exception):
    pass


@dataclass(frozen=True)
class Cliff:
    start_seconds: float
    end_seconds: float
    lost: float  # điểm phần trăm người xem mất trong đoạn


@dataclass
class RetentionReport:
    duration: float
    start: float
    end: float
    hook_leak: float
    cliffs: list[Cliff] = field(default_factory=list)
    slide_per_minute: float = 0.0

    @property
    def hook_verdict(self) -> str:
        if self.hook_leak < HEALTHY_HOOK_LEAK:
            return "ổn"
        return "rò" if self.hook_leak < SEVERE_HOOK_LEAK else "nặng"


def _number(cell: str) -> float | None:
    text = cell.strip().replace("%", "").replace(" ", "")
    # Studio tiếng Việt có thể xuất "45,3": một dấu phẩy, không dấu chấm = thập phân.
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def load_retention_csv(path: Path) -> list[tuple[float, float]]:
    """-> [(vị trí % 0-100, tỷ lệ giữ chân %)] theo thứ tự vị trí.

    Chọn cột theo tiêu đề (Anh hoặc Việt), ưu tiên giữ chân TUYỆT ĐỐI -- cột
    "tương đối" so với video khác cùng độ dài, không phải số người còn nghe.
    Thiếu tiêu đề thì lấy hai cột số đầu tiên. Số dạng tỉ lệ (0-1) được đổi ra %.
    """
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        rows = [r for r in csv.reader(fh) if any(c.strip() for c in r)]
    if not rows:
        raise RetentionError(f"{path} rỗng.")

    header = rows[0] if all(_number(c) is None for c in rows[0] if c.strip()) else []
    body = rows[1:] if header else rows

    def pick(pattern: re.Pattern, exclude: re.Pattern | None = None) -> int | None:
        for i, name in enumerate(header):
            if pattern.search(name) and not (exclude and exclude.search(name)):
                return i
        return None

    pos_col = pick(_POSITION_HEADER)
    ret_col = pick(_ABSOLUTE_HEADER)
    if ret_col is None:
        ret_col = pick(_RETENTION_HEADER, exclude=_RELATIVE_HEADER)
    if pos_col is None or ret_col is None:
        numeric = [i for i, c in enumerate(body[0]) if _number(c) is not None] if body else []
        if len(numeric) < 2:
            raise RetentionError(f"Không nhận ra cột vị trí/tỷ lệ giữ chân trong {path}.")
        pos_col = numeric[0] if pos_col is None else pos_col
        ret_col = next(i for i in numeric if i != pos_col) if ret_col is None else ret_col

    points = []
    for r in body:
        if max(pos_col, ret_col) >= len(r):
            continue
        x, y = _number(r[pos_col]), _number(r[ret_col])
        if x is not None and y is not None:
            points.append((x, y))
    if len(points) < 8:
        raise RetentionError(f"Chỉ đọc được {len(points)} điểm từ {path} -- cần ít nhất 8.")
    points.sort()
    if max(x for x, _ in points) <= 1.0:
        points = [(x * 100, y) for x, y in points]
    if max(y for _, y in points) <= 1.5:
        points = [(x, y * 100) for x, y in points]
    return points


def _interpolate(points: list[tuple[float, float]], x: float) -> float:
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def analyze(points: list[tuple[float, float]], duration: float) -> RetentionReport:
    """`points` là [(vị trí %, giữ chân %)], `duration` là độ dài video (giây)."""
    timeline = [(x / 100 * duration, y) for x, y in points]
    start = timeline[0][1]
    hook_leak = start - _interpolate(timeline, HOOK_SECONDS)

    body_end = duration * (1 - TAIL_FRACTION)
    drops = [
        (t0, t1, y0 - y1)
        for (t0, y0), (t1, y1) in zip(timeline, timeline[1:])
        if t0 >= HOOK_SECONDS and t1 <= body_end
    ]
    cliffs: list[Cliff] = []
    slide = 0.0
    if drops:
        typical = statistics.median(max(d, 0.0) for _, _, d in drops)
        threshold = max(MIN_CLIFF_POINTS, typical * CLIFF_FACTOR)
        cliffs = sorted(
            (Cliff(t0, t1, d) for t0, t1, d in drops if d >= threshold),
            key=lambda c: -c.lost,
        )[:MAX_CLIFFS]
        # Trượt tính trên các đoạn KHÔNG phải vực: vực đã báo riêng.
        cliff_spans = {(c.start_seconds, c.end_seconds) for c in cliffs}
        calm = [(t0, t1, d) for t0, t1, d in drops if (t0, t1) not in cliff_spans]
        minutes = sum(t1 - t0 for t0, t1, _ in calm) / 60
        slide = sum(d for _, _, d in calm) / minutes if minutes else 0.0

    return RetentionReport(
        duration=duration,
        start=start,
        end=timeline[-1][1],
        hook_leak=hook_leak,
        cliffs=cliffs,
        slide_per_minute=slide,
    )


# --- nối video_id -> mốc câu trên trục video --------------------------------


def index_rows(index_jsonl: Path = INDEX_JSONL) -> list[dict]:
    if not index_jsonl.exists():
        return []
    rows = []
    for line in index_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id"):
            rows.append(row)
    return rows


def find_row(video_id: str, index_jsonl: Path = INDEX_JSONL) -> dict | None:
    return next((r for r in index_rows(index_jsonl) if r["video_id"] == video_id), None)


def props_for(row: dict, episodes_dir: Path = EPISODES_DIR) -> Path | None:
    if not row.get("index"):
        return None
    props = episodes_dir / f"{Path(row['index']).stem}-props.json"
    return props if props.exists() else None


def find_props(video_id: str, index_jsonl: Path = INDEX_JSONL, episodes_dir: Path = EPISODES_DIR) -> Path | None:
    row = find_row(video_id, index_jsonl)
    return props_for(row, episodes_dir) if row else None


def video_duration(props: dict) -> float:
    chapters = props.get("chapters") or []
    if not chapters:
        raise RetentionError("Props không có chương nào.")
    return float(chapters[-1]["endSeconds"]) + float(props.get("outroSeconds") or 0)


def spoken_between(props: dict, start: float, end: float) -> tuple[str, list[str]]:
    """-> (tên chương, các câu đọc trong [start, end)) theo trục thời gian video."""
    heading, lines = "", []
    for chapter in props.get("chapters") or []:
        for s in chapter.get("sentences") or []:
            if s["endSeconds"] > start and s["startSeconds"] < end:
                heading = heading or chapter.get("heading", "")
                lines.append(s["text"])
    return heading, lines


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def render_markdown(report: RetentionReport, title: str = "", props: dict | None = None) -> str:
    lines = [f"# Tỷ lệ giữ chân{' — ' + title if title else ''}", ""]
    lines.append(
        f"Video {_clock(report.duration)}: {report.start:.1f}% lúc đầu -> {report.end:.1f}% lúc cuối."
    )
    lines += [
        "",
        f"**RƠI ĐẦU** {report.hook_leak:.1f} điểm trong {HOOK_SECONDS:.0f}s đầu [{report.hook_verdict}] "
        f"— dưới {HEALTHY_HOOK_LEAK:.0f} là ổn. Cao thì sửa cold open/\"Mở đầu\" "
        "hoặc tiêu đề hứa một đằng truyện một nẻo, đừng sửa thân truyện.",
        "",
        "**VỰC** — khoảnh khắc người nghe bỏ hàng loạt:",
    ]
    if not report.cliffs:
        lines.append("- Không có: mất người đều đều, không có khoảnh khắc nào tệ hẳn.")
    for c in report.cliffs:
        lines.append(f"- -{c.lost:.1f} điểm, {_clock(c.start_seconds)}–{_clock(c.end_seconds)}")
        if props:
            heading, said = spoken_between(props, c.start_seconds, c.end_seconds)
            if said:
                quote = " ".join(said)
                quote = quote if len(quote) <= 220 else quote[:217] + "…"
                lines.append(f"  - Chương *{heading}*: “{quote}”")
    lines += [
        "",
        f"**TRƯỢT** {report.slide_per_minute:.2f} điểm/phút ở thân truyện (ngoài các vực). "
        "Trượt đều là nhịp truyện: cắt bớt đoạn kể lể, không cần viết lại.",
        "",
    ]
    if report.hook_leak >= HEALTHY_HOOK_LEAK:
        verdict = "Sửa RƠI ĐẦU trước — mọi thứ phía sau chỉ áp dụng cho người còn ở lại."
    elif report.cliffs:
        verdict = f"Sửa vực lớn nhất ở {_clock(report.cliffs[0].start_seconds)} trước."
    else:
        verdict = "Video giữ chân ổn. View thấp thì vấn đề là tiêu đề/thumbnail (CTR), không phải truyện."
    lines.append(f"**Việc nên làm:** {verdict}")
    return "\n".join(lines) + "\n"


# --- lấy số qua YouTube Analytics API ----------------------------------------


def analytics_credentials():
    from upload.auth import ANALYTICS_SCOPE, CONSENT_SCOPES, has_scope, load_credentials

    if not has_scope(ANALYTICS_SCOPE):
        raise RetentionError(
            "Token YouTube chưa có quyền đọc Analytics. Chạy `uv run python -m upload.auth --force` "
            "và bấm đồng ý cả quyền xem báo cáo YouTube Analytics."
        )
    return load_credentials(scopes=CONSENT_SCOPES)


def fetch_retention(credentials, video_id: str, start: date, end: date) -> list[tuple[float, float]]:
    """-> [(vị trí % 0-100, giữ chân %)] từ YouTube Analytics, cùng dạng load_retention_csv.

    audienceWatchRatio là tỉ lệ (1.0 = 100%, có thể >1 khi người xem tua lại);
    elapsedVideoTimeRatio là vị trí 0.01-1.0. Số liệu trễ 1-2 ngày.
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    yta = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
    try:
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=f"video=={video_id}",
            sort="elapsedVideoTimeRatio",
        ).execute()
    except HttpError as exc:
        # str(HttpError) chỉ có "403 Forbidden"; lý do thật nằm trong thân phản hồi.
        detail = (exc.content or b"").decode("utf-8", errors="ignore")
        if "accessNotConfigured" in detail or "SERVICE_DISABLED" in detail or "has not been used" in detail:
            raise RetentionError(
                "YouTube Analytics API chưa bật cho project OAuth: vào Google Cloud Console -> "
                "APIs & Services -> Library -> \"YouTube Analytics API\" -> Enable."
            ) from exc
        raise RetentionError(f"Analytics API lỗi với video {video_id}: {exc}") from exc
    points = [(float(r[0]) * 100, float(r[1]) * 100) for r in resp.get("rows") or []]
    if len(points) < 8:
        raise RetentionError(f"Video {video_id} chưa đủ số liệu giữ chân ({len(points)} điểm) -- chờ thêm vài ngày.")
    return points


def _publish_date(row: dict) -> date | None:
    """Ngày lên sóng theo chỉ mục; None nếu video đang nằm kho (publishAt null) hoặc thiếu."""
    try:
        return datetime.fromisoformat(row["publishAt"]).date()
    except (KeyError, TypeError, ValueError):
        return None


def report_for_video(credentials, row: dict, today: date) -> tuple[RetentionReport, str, dict | None]:
    props_path = props_for(row)
    props = json.loads(props_path.read_text(encoding="utf-8")) if props_path else None
    if props is None:
        raise RetentionError(f"Không tìm thấy props của video {row['video_id']} -- không biết độ dài video.")
    points = fetch_retention(credentials, row["video_id"], _publish_date(row) or today - timedelta(days=30), today)
    title = props.get("title") or row.get("story_title", "")
    return analyze(points, video_duration(props)), title, props


def render_summary(results: list[tuple[dict, RetentionReport | None, str]], today: date) -> str:
    lines = [
        f"# Tỷ lệ giữ chân — {today.isoformat()}",
        "",
        "| Lên sóng | Truyện | Rơi 30s đầu | Vực lớn nhất | Trượt/phút | Cuối video |",
        "|---|---|---:|---|---:|---:|",
    ]
    for row, report, note in results:
        aired = (row.get("publishAt") or "")[:10]
        title = row.get("story_title") or row.get("title", "")
        if report is None:
            lines.append(f"| {aired} | {title} | {note} | | | |")
            continue
        cliff = (f"-{report.cliffs[0].lost:.1f} @ {_clock(report.cliffs[0].start_seconds)}"
                 if report.cliffs else "không")
        lines.append(
            f"| {aired} | {title} | {report.hook_leak:.1f} [{report.hook_verdict}] | {cliff} | "
            f"{report.slide_per_minute:.2f} | {report.end:.1f}% |"
        )
    lines += ["", "Chi tiết từng video (chương và câu ở mỗi vực): `retention-<video_id>.md` cùng thư mục."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phân tích tỷ lệ giữ chân: CSV từ Studio hoặc tự lấy qua Analytics API.")
    parser.add_argument("csv", type=Path, nargs="?", help="CSV tải từ Studio; bỏ trống thì lấy qua Analytics API")
    parser.add_argument("--video", help="video_id trên YouTube")
    parser.add_argument("--days", type=int, help="mọi video lên sóng trong N ngày qua (qua Analytics API)")
    parser.add_argument("--duration", type=float, help="độ dài video (giây), khi CSV không thuộc video nào trong index")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    today = date.today()

    try:
        if args.days:
            _run_recent(args.days, today, args.out)
            return
        if args.csv is None and not args.video:
            raise RetentionError("Cần CSV, --video <id> hoặc --days <N>.")

        row = find_row(args.video) if args.video else None
        if args.video and row is None:
            raise RetentionError(f"Không có video {args.video} trong {INDEX_JSONL}.")
        if args.csv is None:
            report, title, props = report_for_video(analytics_credentials(), row, today)
        else:
            props_path = props_for(row) if row else None
            props = json.loads(props_path.read_text(encoding="utf-8")) if props_path else None
            title = props.get("title", "") if props else ""
            duration = args.duration or (video_duration(props) if props else None)
            if not duration:
                raise RetentionError("Cần --video (video của kênh) hoặc --duration <giây>.")
            report = analyze(load_retention_csv(args.csv), duration)
    except RetentionError as exc:
        raise SystemExit(str(exc)) from exc

    text = render_markdown(report, title, props)
    print(text)
    if args.out or args.video:
        out = args.out or INDEX_JSONL.parent / f"retention-{args.video}.md"
        out.write_text(text, encoding="utf-8")
        print(f"Đã lưu: {out}")


def _run_recent(days: int, today: date, out: Path | None) -> None:
    # Analytics trễ 1-2 ngày: video lên sóng chưa tới 2 ngày chưa có số.
    newest = today - timedelta(days=2)
    oldest = today - timedelta(days=days)
    rows = [r for r in index_rows() if (aired := _publish_date(r)) and oldest <= aired <= newest]
    if not rows:
        raise RetentionError(f"Không có video nào lên sóng từ {oldest} tới {newest}.")
    credentials = analytics_credentials()
    results = []
    for row in sorted(rows, key=lambda r: r.get("publishAt") or ""):
        try:
            report, title, props = report_for_video(credentials, row, today)
        except RetentionError as exc:
            results.append((row, None, str(exc).split(" -- ")[0][:60]))
            continue
        (INDEX_JSONL.parent / f"retention-{row['video_id']}.md").write_text(
            render_markdown(report, title, props), encoding="utf-8"
        )
        results.append((row, report, ""))
    text = render_summary(results, today)
    print(text)
    out = out or INDEX_JSONL.parent / f"retention-{today.isoformat()}.md"
    out.write_text(text, encoding="utf-8")
    print(f"Đã lưu: {out}")


if __name__ == "__main__":
    main()
