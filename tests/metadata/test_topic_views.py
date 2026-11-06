# tests/metadata/test_topic_views.py
"""Xếp hạng chủ đề theo view Shorts (06/11/2026). Không gọi API."""
import json
from datetime import date

from metadata import topic_views
from metadata.topic_views import ShortStat, collect_shorts, render_markdown, summarize


def _s(vid, topic, views, pct=50.0, part=1):
    return ShortStat(vid, topic, f"Truyện {vid}", part, views, pct)


def test_summarize_xep_theo_ty_le_no_roi_trung_vi():
    shorts = [_s("a1", "A", 5000), _s("a2", "A", 10), _s("a3", "A", 12),
              _s("b1", "B", 900), _s("b2", "B", 1100, 70.0), _s("b3", "B", 1000, 60.0)]
    out = summarize(shorts, top_n=2)
    assert [t.topic for t in out] == ["B", "A"]
    b = out[0]
    assert (b.shorts, b.published, b.hits, b.views, b.median_views) == (3, 3, 3, 3000, 1000)
    assert b.hit_rate == 1.0 and round(b.avg_pct) == 60
    assert [s.video_id for s in b.best] == ["b2", "b3"]
    assert out[1].hits == 1 and round(out[1].hit_rate, 2) == 0.33


def test_summarize_short_chua_phat_khong_tinh_vao_ty_le_va_phan_tram():
    out = summarize([_s("a1", "A", 600, 80.0), _s("a2", "A", 0, 0.0)])
    assert (out[0].shorts, out[0].published, out[0].hits) == (2, 1, 1)
    assert out[0].hit_rate == 1.0 and out[0].avg_pct == 80.0 and out[0].median_views == 600


def test_collect_shorts_gan_chu_de_cua_video_dai(tmp_path):
    prefix = tmp_path / "shorts" / "p"
    prefix.parent.mkdir()
    (prefix.parent / "p-upload-state.json").write_text(json.dumps(
        {"uploaded": {"1": {"video_id": "s1"}, "2": {"video_id": "s2"}}}))
    index = tmp_path / "x-full.json"
    index.write_text(json.dumps({"shorts_prefix": str(prefix)}))
    rows = [{"video_id": "v", "topic": "ho_hang_viet", "story_title": "T", "index": str(index)},
            {"video_id": "khong-index"}]
    got = collect_shorts(rows)
    assert [(s.video_id, s.topic, s.part) for s in got] == [("s1", "ho_hang_viet", 1), ("s2", "ho_hang_viet", 2)]


def test_render_markdown_co_bang_va_link_short():
    text = render_markdown(summarize([_s("a1", "A", 100, 55.0)]), date(2026, 8, 1), date(2026, 11, 6))
    assert "| A | 1 | 1 | 0 | 0% | 100 | 55% |" in text
    assert "https://youtube.com/shorts/a1" in text


def test_main_bao_loi_khi_khong_co_short(monkeypatch, capsys):
    monkeypatch.setattr(topic_views, "index_rows", lambda: [])
    assert topic_views.main([]) == 1
    assert "không có short" in capsys.readouterr().err.lower()
