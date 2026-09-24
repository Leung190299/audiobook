# metadata/report.py
"""Báo cáo KPI theo CHỦ ĐỀ từ output/metadata/index.jsonl (spec 24/09/2026 §9).

    uv run python -m metadata.report [--days 14] [--out output/metadata/report-<ngày>.md]

Mỗi video dài stage 8 đăng được ghi một dòng (topic, format, video_id, publishAt).
Báo cáo đọc số liệu hiện tại qua YouTube Data API (videos.list statistics --
dùng token sẵn có, không cần cấp quyền thêm) rồi nhóm theo chủ đề.

Giới hạn: Data API chỉ có tổng view/like/bình luận hiện tại. "View 48h" được
xấp xỉ bằng view/giờ tuổi video x 48 (đúng hướng để so giữa các chủ đề, không
phải số tuyệt đối). CTR, thời lượng xem TB và sub thu được KHÔNG có trong Data
API (CTR không có cả trong Analytics API) -- báo cáo để cột trống cho bạn điền
từ YouTube Studio. Quy tắc chốt sau 14 ngày: chủ đề có view 48h TB thấp nhất VÀ
CTR < 3% -> giảm tần suất trong AUDIOBOOK_TOPIC_ROTATION.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from scripts.topics import TOPICS

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_JSONL = REPO_ROOT / "output" / "metadata" / "index.jsonl"


def load_rows(path: Path, since: datetime | None = None) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not row.get("video_id"):
            continue
        if since and row.get("publishAt"):
            if datetime.fromisoformat(row["publishAt"]) < since:
                continue
        rows.append(row)
    return rows


def fetch_stats(credentials, video_ids: list[str]) -> dict[str, dict]:
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        resp = youtube.videos().list(part="statistics", id=",".join(video_ids[i : i + 50])).execute()
        for item in resp.get("items", []):
            out[item["id"]] = item.get("statistics", {})
    return out


def summarize(rows: list[dict], stats: dict[str, dict], now: datetime) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row.get("topic") or "(không chủ đề)"].append(row)
    summary = {}
    for topic, items in groups.items():
        views, est48, likes, comments = [], [], [], []
        for row in items:
            st = stats.get(row["video_id"], {})
            v = int(st.get("viewCount", 0))
            views.append(v)
            likes.append(int(st.get("likeCount", 0)))
            comments.append(int(st.get("commentCount", 0)))
            if row.get("publishAt"):
                age_h = (now - datetime.fromisoformat(row["publishAt"])).total_seconds() / 3600
                if age_h > 0:
                    est48.append(v if age_h <= 48 else v / age_h * 48)
        n = len(items)
        summary[topic] = {
            "videos": n,
            "avg_views": sum(views) / n if n else 0,
            "avg_views_48h_est": sum(est48) / len(est48) if est48 else 0,
            "avg_likes": sum(likes) / n if n else 0,
            "avg_comments": sum(comments) / n if n else 0,
        }
    return summary


def render_markdown(summary: dict[str, dict], days: int, now: datetime) -> str:
    lines = [
        f"# Báo cáo KPI theo chủ đề — {now.date().isoformat()} ({days} ngày gần nhất)",
        "",
        "| Chủ đề | Video | View TB | View 48h (ước) | Like TB | Bình luận TB | CTR (Studio) | Xem TB (Studio) | Sub (Studio) |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for topic, s in sorted(summary.items(), key=lambda kv: -kv[1]["avg_views_48h_est"]):
        name = TOPICS[topic].name if topic in TOPICS else topic
        lines.append(
            f"| {name} | {s['videos']} | {s['avg_views']:.0f} | {s['avg_views_48h_est']:.0f} | "
            f"{s['avg_likes']:.1f} | {s['avg_comments']:.1f} |  |  |  |"
        )
    if summary:
        worst = min(summary, key=lambda t: summary[t]["avg_views_48h_est"])
        lines += [
            "",
            f"Chủ đề view 48h thấp nhất: **{worst}**. Nếu CTR của nó (xem Studio) < 3% sau đủ 14 ngày, "
            "giảm số lần của nó trong AUDIOBOOK_TOPIC_ROTATION.",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Báo cáo KPI video dài theo chủ đề.")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    rows = load_rows(INDEX_JSONL, since=now - timedelta(days=args.days))
    if not rows:
        raise SystemExit(f"Chưa có video nào trong {INDEX_JSONL} ({args.days} ngày gần nhất).")
    from upload.auth import load_credentials

    stats = fetch_stats(load_credentials(), [r["video_id"] for r in rows])
    text = render_markdown(summarize(rows, stats, now), args.days, now)
    out = args.out or INDEX_JSONL.parent / f"report-{now.date().isoformat()}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"Đã lưu báo cáo: {out}")


if __name__ == "__main__":
    main()
