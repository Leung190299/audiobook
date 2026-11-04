# metadata/retention.py
"""Đọc CSV "Tỷ lệ giữ chân khán giả" xuất từ YouTube Studio, chỉ ra người nghe bỏ ở ĐÂU.

    uv run python -m metadata.retention <file.csv> --video <video_id>
    uv run python -m metadata.retention <file.csv> --duration 2460   # video không có trong index

Lấy file: Studio -> video -> Số liệu phân tích -> Mức độ tương tác -> biểu đồ
tỷ lệ giữ chân -> nút tải xuống. (Data API/report.py không có số này.)

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


def find_props(video_id: str, index_jsonl: Path = INDEX_JSONL, episodes_dir: Path = EPISODES_DIR) -> Path | None:
    if not index_jsonl.exists():
        return None
    for line in index_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id") == video_id and row.get("index"):
            props = episodes_dir / f"{Path(row['index']).stem}-props.json"
            return props if props.exists() else None
    return None


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Phân tích CSV tỷ lệ giữ chân từ YouTube Studio.")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--video", help="video_id trên YouTube -- để in câu đang đọc ở mỗi vực")
    parser.add_argument("--duration", type=float, help="độ dài video (giây), khi không dùng --video")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    props, title = None, ""
    if args.video:
        props_path = find_props(args.video)
        if props_path is None:
            raise SystemExit(f"Không tìm thấy props của video {args.video} qua {INDEX_JSONL}.")
        props = json.loads(props_path.read_text(encoding="utf-8"))
        title = props.get("title", "")
    duration = args.duration or (video_duration(props) if props else None)
    if not duration:
        raise SystemExit("Cần --video (video của kênh) hoặc --duration <giây>.")

    try:
        report = analyze(load_retention_csv(args.csv), duration)
    except RetentionError as exc:
        raise SystemExit(str(exc)) from exc
    text = render_markdown(report, title, props)
    print(text)
    if args.out or args.video:
        out = args.out or INDEX_JSONL.parent / f"retention-{args.video}.md"
        out.write_text(text, encoding="utf-8")
        print(f"Đã lưu: {out}")


if __name__ == "__main__":
    main()
