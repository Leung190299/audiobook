import json
from datetime import date

import pytest

from director import report
from director.report import ReportError, credentials_for, fetch_channel


class FakeAnalytics:
    """Trả hàng theo đúng số cột của `metrics` được hỏi (như API thật); ghi lại tham số để test kiểm cửa sổ ngày."""

    def __init__(self, rows_by_metrics):
        self.rows_by_metrics = rows_by_metrics
        self.calls = []
        self._last = None

    def reports(self):
        return self

    def query(self, **kw):
        self.calls.append(kw)
        self._last = (kw.get("metrics"), kw.get("dimensions"))
        return self

    def execute(self):
        return {"rows": self.rows_by_metrics.get(self._last, [])}


def test_fetch_channel_gop_7_va_28_ngay():
    fa = FakeAnalytics({
        (report.METRICS_7D, "video"): [["abc", 10, 55.0, 130.0, 41.5, 2]],
        (report.METRICS_28D, "video"): [["abc", 31, 4]],
        ("views", "video,insightTrafficSourceType"): [["abc", "YT_SEARCH", 7], ["abc", "SUBSCRIBER", 3]],
    })
    d = fetch_channel(fa, "main", ["abc"], end=date(2026, 11, 27))
    v = d["videos"][0]
    assert v["video_id"] == "abc" and v["views_7d"] == 10 and v["avg_view_seconds_7d"] == 130.0
    assert v["views_28d"] == 31 and v["traffic_7d"] == {"YT_SEARCH": 7, "SUBSCRIBER": 3}
    assert d["totals_7d"]["views"] == 10 and d["totals_28d"]["subs"] == 4
    assert any(c["startDate"] == "2026-11-20" for c in fa.calls)
    assert any(c["startDate"] == "2026-10-30" for c in fa.calls)
    assert d["channel"] == "main" and d["loi"] == []


def test_fetch_channel_khong_video_khong_goi_api():
    fa = FakeAnalytics({})
    d = fetch_channel(fa, "xomque", [], end=date(2026, 11, 27))
    assert d["videos"] == [] and fa.calls == []


def test_credentials_for_main_thieu_quyen_analytics(monkeypatch):
    monkeypatch.setattr(report, "has_scope", lambda s: False)
    with pytest.raises(ReportError, match="upload.auth"):
        credentials_for("main")


def test_main_mot_kenh_hong_van_ghi_file(tmp_path, monkeypatch):
    def creds(ch):
        if ch == "main":
            raise ReportError("token main hỏng: chạy `uv run python -m upload.auth`")
        return object()

    monkeypatch.setattr(report, "credentials_for", creds)
    monkeypatch.setattr(report, "build_analytics", lambda c: FakeAnalytics({}))
    monkeypatch.setattr(report, "video_ids_for", lambda ch: [])
    assert report.main(["--date", "2026-11-28", "--out", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "so-lieu.json").read_text(encoding="utf-8"))
    assert data[0]["channel"] == "main" and "token main hỏng" in data[0]["loi"][0]
    assert data[1]["channel"] == "xomque" and data[1]["loi"] == []
    md = (tmp_path / "so-lieu.md").read_text(encoding="utf-8")
    assert "token main hỏng" in md and "Xóm Que" in md
