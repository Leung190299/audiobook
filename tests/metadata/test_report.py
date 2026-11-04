# tests/metadata/test_report.py
import json
from datetime import datetime, timedelta, timezone

from metadata.report import load_rows, render_markdown, summarize

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def test_nhom_kpi_theo_chu_de(tmp_path):
    path = tmp_path / "index.jsonl"
    rows = [
        {"topic": "ho_hang_viet", "video_id": "a", "publishAt": (NOW - timedelta(hours=24)).isoformat()},
        {"topic": "ho_hang_viet", "video_id": "b", "publishAt": (NOW - timedelta(hours=96)).isoformat()},
        {"topic": "bo_me_trong_sinh", "video_id": "c", "publishAt": (NOW - timedelta(hours=48)).isoformat()},
        {"topic": "bo_me_trong_sinh", "video_id": "old", "publishAt": (NOW - timedelta(days=30)).isoformat()},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\nhỏng\n", encoding="utf-8")
    loaded = load_rows(path, since=NOW - timedelta(days=14))
    assert {r["video_id"] for r in loaded} == {"a", "b", "c"}
    stats = {"a": {"viewCount": "100"}, "b": {"viewCount": "400"}, "c": {"viewCount": "50", "commentCount": "4"}}
    s = summarize(loaded, stats, NOW)
    assert s["ho_hang_viet"]["videos"] == 2
    assert s["ho_hang_viet"]["avg_views"] == 250
    assert s["ho_hang_viet"]["avg_views_48h_est"] == (100 + 200) / 2  # b: 400/96h*48
    md = render_markdown(s, 14, NOW)
    assert "Họ hàng cực phẩm" in md and "thấp nhất: **bo_me_trong_sinh**" in md
