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
    assert any(c["startDate"] == "2026-11-21" for c in fa.calls)
    assert any(c["startDate"] == "2026-10-31" for c in fa.calls)
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


class _FakeLogin:
    """kit/login.py giả: token xomque chỉ có force-ssl."""
    ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"

    def __init__(self, tmp_path, scopes):
        self._path = tmp_path / "tok.json"
        self._path.write_text(json.dumps({"scopes": scopes}), encoding="utf-8")
        self.creds_calls = 0

    def token_path(self, key):
        return self._path

    def credentials(self, key):
        self.creds_calls += 1
        return "CREDS-" + key


def test_credentials_for_xomque_thieu_quyen_analytics(tmp_path, monkeypatch):
    fake = _FakeLogin(tmp_path, ["https://www.googleapis.com/auth/youtube.force-ssl"])
    monkeypatch.setattr(report, "_kit_module", lambda name: fake)
    with pytest.raises(ReportError, match="kit/stick login xomque --force"):
        credentials_for("xomque")
    # Data API v3 (videos.list) chỉ cần force-ssl: không đòi quyền Analytics
    assert credentials_for("xomque", need_analytics=False) == "CREDS-xomque"


def test_main_xomque_thieu_quyen_van_liet_ke_video(tmp_path, monkeypatch):
    def creds(ch, need_analytics=True):
        if ch == "xomque":
            raise ReportError("xomque chưa có quyền yt-analytics.readonly: chạy `kit/stick login xomque --force`")
        return object()

    monkeypatch.setattr(report, "credentials_for", creds)
    monkeypatch.setattr(report, "build_analytics", lambda c: FakeAnalytics({}))
    monkeypatch.setattr(report, "video_ids_for", lambda ch: [("x1", "Vong Hồn 1", "2026-11-29T20:00:00+07:00")] if ch == "xomque" else [])
    assert report.main(["--date", "2026-11-28", "--out", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "so-lieu.json").read_text(encoding="utf-8"))
    xq = data[1]
    assert "kit/stick login xomque --force" in xq["loi"][0]
    assert xq["videos"][0]["video_id"] == "x1" and xq["videos"][0]["published_at"] == "2026-11-29T20:00:00+07:00"
    assert "Vong Hồn 1" in (tmp_path / "so-lieu.md").read_text(encoding="utf-8")


def test_render_markdown_xep_video_moi_nhat_truoc():
    d = fetch_channel(FakeAnalytics({}), "main", [], end=date(2026, 11, 27))
    d["videos"] = [
        {"video_id": "cu", "title": "Cũ nhiều view", "published_at": "2026-11-01T20:00:00+07:00", "views_7d": 99, "traffic_7d": {}},
        {"video_id": "moi", "title": "Mới ít view", "published_at": "2026-11-27T20:00:00+07:00", "views_7d": 0, "traffic_7d": {}},
    ]
    md = report.render_markdown([d], date(2026, 11, 27))
    assert md.index("Mới ít view") < md.index("Cũ nhiều view")
    assert "chưa cập nhật" in md                      # ghi chú độ trễ Analytics


def test_nguon_xem_hoi_theo_lo_nho():
    ids = [f"v{i}" for i in range(25)]
    fa = FakeAnalytics({})
    fetch_channel(fa, "main", ids, end=date(2026, 11, 27))
    traffic_calls = [c for c in fa.calls if c.get("dimensions") == "video,insightTrafficSourceType"]
    assert traffic_calls and all(len(c["filters"].split("==")[1].split(",")) <= 10 for c in traffic_calls)
