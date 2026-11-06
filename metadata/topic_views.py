# metadata/topic_views.py
"""Xếp hạng chủ đề theo view SHORTS (06/11/2026).

    uv run python -m metadata.topic_views
    uv run python -m metadata.topic_views --since 2026-10-01 --out output/metadata/topic-views.md

Analytics 06/11: 64 video dài chỉ 914 view (≈14 view/video) nên view theo chủ đề
của video dài không nói lên gì; Shorts ≈1.000 view/cái là số đủ lớn để so chủ
đề. Mỗi short gắn với video dài qua `<shorts_prefix>-upload-state.json`
(upload.release.shorts_of), chủ đề lấy từ dòng chỉ mục của video dài.
Dùng Analytics API (hạn mức riêng, không tốn hạn mức Data API).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median

from metadata.retention import INDEX_JSONL, RetentionError, analytics_credentials, index_rows
from upload.release import shorts_of

BATCH = 200
DEFAULT_SINCE = date(2026, 8, 1)


@dataclass
class ShortStat:
    video_id: str
    topic: str
    story_title: str
    part: int
    views: int = 0
    avg_pct: float = 0.0


HIT_VIEWS = 500  # short "nổ": YouTube đẩy tới ~1.000 người thử, short thường dừng ở 0-30


@dataclass
class TopicSummary:
    topic: str
    shorts: int        # kể cả short còn nằm kho / mới hẹn
    published: int     # đã phát (có view)
    hits: int          # >= HIT_VIEWS view
    views: int
    median_views: float  # trung vị trong số đã phát
    avg_pct: float
    best: list[ShortStat]

    @property
    def hit_rate(self) -> float:
        return self.hits / self.published if self.published else 0.0


def collect_shorts(rows: list[dict]) -> list[ShortStat]:
    return [
        ShortStat(short_id, row.get("topic") or "?", row.get("story_title") or "", part)
        for row in rows
        for part, short_id in shorts_of(row)
    ]


def fetch_views(credentials, video_ids: list[str], since: date, until: date) -> dict[str, tuple[int, float]]:
    """{video_id: (views, averageViewPercentage)} -- short không có dòng nào = 0 view."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    yt = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
    out: dict[str, tuple[int, float]] = {}
    for i in range(0, len(video_ids), BATCH):
        chunk = video_ids[i : i + BATCH]
        try:
            resp = yt.reports().query(
                ids="channel==MINE", startDate=since.isoformat(), endDate=until.isoformat(),
                metrics="views,averageViewPercentage", dimensions="video",
                filters="video==" + ",".join(chunk), sort="-views", maxResults=BATCH,
            ).execute()
        except HttpError as exc:
            raise RetentionError(f"Analytics API lỗi: {exc}") from exc
        for vid, views, pct in resp.get("rows") or []:
            out[vid] = (int(views), float(pct))
    return out


def summarize(shorts: list[ShortStat], top_n: int = 3) -> list[TopicSummary]:
    """Mỗi chủ đề một dòng, xếp theo TỶ LỆ NỔ rồi trung vị. Short chưa có view
    (còn nằm kho, mới hẹn) không tính vào tỷ lệ -- view Shorts gần như nhị phân:
    hoặc ~1.000 hoặc vài chục, nên tỷ lệ nổ nói nhiều hơn tổng view."""
    by_topic: dict[str, list[ShortStat]] = {}
    for s in shorts:
        by_topic.setdefault(s.topic, []).append(s)
    result = []
    for topic, items in by_topic.items():
        published = [s for s in items if s.views > 0]
        result.append(TopicSummary(
            topic=topic, shorts=len(items), published=len(published),
            hits=sum(1 for s in published if s.views >= HIT_VIEWS),
            views=sum(s.views for s in items),
            median_views=median(s.views for s in published) if published else 0,
            avg_pct=sum(s.avg_pct for s in published) / len(published) if published else 0.0,
            best=sorted(items, key=lambda s: -s.views)[:top_n],
        ))
    return sorted(result, key=lambda t: (-t.hit_rate, -t.median_views))


def render_markdown(summaries: list[TopicSummary], since: date, until: date) -> str:
    lines = [f"# View Shorts theo chủ đề — {since} → {until}", "",
             f"| Chủ đề | Short | Đã phát | Nổ ≥{HIT_VIEWS} | Tỷ lệ nổ | Trung vị (đã phát) | Xem TB % |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for t in summaries:
        lines.append(f"| {t.topic} | {t.shorts} | {t.published} | {t.hits} | {t.hit_rate * 100:.0f}% | "
                     f"{t.median_views:.0f} | {t.avg_pct:.0f}% |")
    lines.append("")
    for t in summaries:
        lines.append(f"**{t.topic}** — short nhiều view nhất:")
        for s in t.best:
            lines.append(f"- {s.views} view ({s.avg_pct:.0f}%) | {s.story_title} — phần {s.part} | https://youtube.com/shorts/{s.video_id}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Xếp hạng chủ đề theo view Shorts (Analytics API).")
    parser.add_argument("--since", type=date.fromisoformat, default=DEFAULT_SINCE)
    parser.add_argument("--until", type=date.fromisoformat, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    until = args.until or date.today()

    shorts = collect_shorts(index_rows())
    if not shorts:
        print("Chỉ mục không có short nào.", file=sys.stderr)
        return 1
    try:
        stats = fetch_views(analytics_credentials(), [s.video_id for s in shorts], args.since, until)
    except RetentionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for s in shorts:
        s.views, s.avg_pct = stats.get(s.video_id, (0, 0.0))
    text = render_markdown(summarize(shorts), args.since, until)
    print(text)
    out = args.out or INDEX_JSONL.parent / "topic-views.md"
    out.write_text(text, encoding="utf-8")
    print(f"Đã lưu: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
