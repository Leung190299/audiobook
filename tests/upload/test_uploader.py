"""upload/uploader.py — thân request gửi lên YouTube."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from upload import uploader


@pytest.fixture
def _bat_request(monkeypatch, tmp_path):
    """Chặn ở tầng discovery: giữ lại body rồi trả về phản hồi giả."""
    ghi = {}

    def fake_build(*a, **kw):
        yt = MagicMock()

        def _insert(part, body, media_body):
            ghi["part"] = part
            ghi["body"] = body
            req = MagicMock()
            req.next_chunk.return_value = (None, {"id": "vid1", "status": {"privacyStatus": "private"}})
            return req

        yt.videos.return_value.insert.side_effect = _insert
        return yt

    monkeypatch.setattr(uploader, "build", fake_build)
    monkeypatch.setattr(uploader, "MediaFileUpload", lambda *a, **kw: MagicMock())
    video = tmp_path / "v.mp4"
    video.write_bytes(b"mp4")
    ghi["video"] = video
    return ghi


def test_khai_bao_noi_dung_ai_cho_youtube(_bat_request):
    """Kịch bản, giọng đọc và ảnh đều do AI sinh -- YouTube bắt khai báo mục
    "nội dung tổng hợp hoặc đã chỉnh sửa". Bật sẵn trong body chứ không để
    người dùng nhớ tick tay trong Studio sau mỗi lượt đăng."""
    uploader.upload_video(
        credentials="cred", video_path=_bat_request["video"],
        title="T", description="D", tags=["a"],
    )

    assert _bat_request["body"]["status"]["containsSyntheticMedia"] is True


def test_tat_duoc_khi_khong_phai_noi_dung_ai(_bat_request):
    uploader.upload_video(
        credentials="cred", video_path=_bat_request["video"],
        title="T", description="D", tags=["a"], synthetic_media=False,
    )

    assert _bat_request["body"]["status"]["containsSyntheticMedia"] is False


# --- đổi lịch video đã đăng (upload/release.py) ---------------------------------


def _yt_status(monkeypatch, status: dict | None):
    ghi = {}
    yt = MagicMock()
    yt.videos.return_value.list.return_value.execute.return_value = (
        {"items": [{"id": "v1", "status": status}]} if status is not None else {"items": []}
    )

    def _update(part, body):
        ghi["part"], ghi["body"] = part, body
        return MagicMock()

    yt.videos.return_value.update.side_effect = _update
    monkeypatch.setattr(uploader, "build", lambda *a, **kw: yt)
    return ghi


def test_update_status_hen_gio_giu_nguyen_truong_khac(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ghi = _yt_status(monkeypatch, {"privacyStatus": "private", "license": "youtube", "embeddable": True})
    at = datetime(2026, 11, 12, 20, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    assert uploader.update_status(None, "v1", at)
    assert ghi["part"] == "status"
    assert ghi["body"]["status"] == {
        "privacyStatus": "private", "license": "youtube", "embeddable": True,
        "publishAt": "2026-11-12T20:00:00+07:00",
    }


def test_update_status_bo_hen_thi_xoa_publish_at_va_giu_private(monkeypatch):
    ghi = _yt_status(monkeypatch, {"privacyStatus": "private", "publishAt": "2026-12-01T13:00:00Z"})
    assert uploader.update_status(None, "v1", None)
    assert ghi["body"]["status"] == {"privacyStatus": "private"}


def test_update_status_video_mat_thi_tra_false(monkeypatch, capsys):
    _yt_status(monkeypatch, None)
    assert not uploader.update_status(None, "v1", None)
    assert "Không tìm thấy" in capsys.readouterr().out


def test_update_status_doi_gio_co_mui_gio():
    from datetime import datetime

    with pytest.raises(uploader.UploadError):
        uploader.update_status(None, "v1", datetime(2026, 11, 12, 20))


def test_list_status_chia_lo_50_id(monkeypatch):
    calls = []
    yt = MagicMock()

    def _list(part, id):
        calls.append(id.split(","))
        m = MagicMock()
        m.execute.return_value = {"items": [{"id": i, "status": {"privacyStatus": "private"}} for i in id.split(",")]}
        return m

    yt.videos.return_value.list.side_effect = _list
    monkeypatch.setattr(uploader, "build", lambda *a, **kw: yt)
    out = uploader.list_status(None, [f"v{i}" for i in range(120)])
    assert [len(c) for c in calls] == [50, 50, 20]
    assert len(out) == 120 and out["v7"] == {"privacyStatus": "private"}


def test_update_description_mo_ta_da_dung_thi_khong_goi_update(monkeypatch):
    yt = MagicMock()
    yt.videos.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "T", "description": "Mô tả cũ"}}]}
    monkeypatch.setattr(uploader, "build", lambda *a, **kw: yt)
    assert uploader.update_description(None, "v1", "Mô tả cũ") is True
    yt.videos.return_value.update.assert_not_called()
    assert uploader.update_description(None, "v1", "Mô tả mới") is True
    yt.videos.return_value.update.assert_called_once()
