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
