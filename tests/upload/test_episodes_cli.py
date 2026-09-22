"""Đăng cả bộ 3 tập hẹn giờ + trích đoạn. Uploader giả, không gọi API."""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from metadata.episodes import NEXT_EPISODE_PLACEHOLDER, PLAYLIST_PLACEHOLDER
from upload import episodes_cli
from upload.episodes_cli import LOCAL_TZ, default_first_air, fill_links
from upload.uploader import UploadResult


class FakeUploader:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def __call__(self, credentials, *, video_path, title, description, tags, category_id,
                 privacy_status, thumbnail_path, publish_at=None):
        if self.fail_on and Path(video_path).name == self.fail_on:
            raise RuntimeError("mạng rớt")
        self.calls.append({"video_path": Path(video_path), "title": title, "description": description,
                           "thumbnail_path": thumbnail_path, "publish_at": publish_at})
        vid = f"vid{len(self.calls)}"
        return UploadResult(video_id=vid, url=f"https://youtu.be/{vid}", title=title,
                            privacy_status=privacy_status, thumbnail_set=thumbnail_path is not None)


def _index(tmp_path: Path, with_shorts: bool = True) -> dict:
    eps = []
    for n in (1, 2, 3):
        video = tmp_path / f"truyen-tap-{n}.mp4"; video.write_bytes(b"mp4")
        thumb = tmp_path / f"t-ep-0{n}.png"; thumb.write_bytes(b"png")
        meta = tmp_path / f"t-ep-0{n}.json"
        desc = f"Hook\n\nTập {n}/3. Mô tả.\n\n{PLAYLIST_PLACEHOLDER}" + (f"\n{NEXT_EPISODE_PLACEHOLDER}" if n < 3 else "")
        meta.write_text(json.dumps({"title": f"Truyện | Tập {n}/3", "description": desc, "tags": ["a"],
                                    "pinned_comment": f"❓ Câu hỏi tập {n}"}), encoding="utf-8")
        eps.append({"number": n, "total": 3, "title": f"Truyện | Tập {n}/3", "video_path": str(video),
                    "metadata_path": str(meta), "thumbnail_path": str(thumb)})
    index = tmp_path / "t-episodes.json"
    index.write_text(json.dumps({"episodes": eps}), encoding="utf-8")
    prefix = None
    if with_shorts:
        prefix_name = "t-20260922T000000Z"
        for n in (1, 2):
            stem = f"{prefix_name}-part-{n:02d}"
            (tmp_path / f"{stem}.mp4").write_bytes(b"mp4")
            (tmp_path / f"{stem}.jpg").write_bytes(b"jpg")
            (tmp_path / f"{stem}.json").write_text(json.dumps({
                "title": f"Truyện — Trích đoạn {n}/2",
                "description": f"Truyện — Trích đoạn {n}/2.\nNghe trọn tập trên kênh — link ở phần mô tả kênh.",
                "tags": ["shorts"], "part_number": n, "total_parts": 2, "video_filename": f"{stem}.mp4"}),
                encoding="utf-8")
        prefix = tmp_path / prefix_name
    return {"index": index, "prefix": prefix}


def test_default_first_air():
    early = datetime(2026, 9, 23, 9, 0, tzinfo=LOCAL_TZ)
    assert default_first_air(early) == datetime(2026, 9, 23, 20, 0, tzinfo=LOCAL_TZ)
    late = datetime(2026, 9, 23, 19, 45, tzinfo=LOCAL_TZ)
    assert default_first_air(late) == datetime(2026, 9, 24, 20, 0, tzinfo=LOCAL_TZ)


def test_fill_links():
    d = f"x\n\n{PLAYLIST_PLACEHOLDER}\n{NEXT_EPISODE_PLACEHOLDER}\n\ny"
    assert fill_links(d, "https://youtu.be/n", None) == "x\n\n▶️ Tập tiếp theo: https://youtu.be/n\n\ny"
    assert "📚 Nghe trọn bộ theo thứ tự: https://p" in fill_links(d, None, "https://p")


def test_dang_3_tap_hen_gio_cach_nhau_1_ngay_roi_link_comment_va_short(tmp_path):
    ix = _index(tmp_path)
    up = FakeUploader()
    comments, updates = [], []

    def commenter(creds, vid, text):
        comments.append((vid, text)); return f"c-{vid}"

    def updater(creds, vid, desc):
        updates.append((vid, desc)); return True

    now = datetime(2026, 9, 23, 9, 0, tzinfo=LOCAL_TZ)
    state = episodes_cli.run(ix["index"], shorts_prefix=ix["prefix"], uploader=up, commenter=commenter,
                             description_updater=updater, credentials_loader=lambda: "creds", now=now,
                             playlist_url="https://p")

    names = [c["video_path"].name for c in up.calls]
    assert names[:3] == ["truyen-tap-1.mp4", "truyen-tap-2.mp4", "truyen-tap-3.mp4"]
    assert names[3:] == ["t-20260922T000000Z-part-01.mp4", "t-20260922T000000Z-part-02.mp4"]
    first = datetime(2026, 9, 23, 20, 0, tzinfo=LOCAL_TZ)
    assert [c["publish_at"] for c in up.calls[:3]] == [first, first + timedelta(days=1), first + timedelta(days=2)]
    # Mô tả lúc tải lên: playlist đã điền, chỗ tập sau còn giữ chỗ (chưa có id).
    assert "https://p" in up.calls[0]["description"]
    assert NEXT_EPISODE_PLACEHOLDER in up.calls[0]["description"]
    # Sau khi có id: tập 1 -> link tập 2, tập 2 -> link tập 3, tập 3 không cập nhật.
    assert [u[0] for u in updates] == ["vid1", "vid2"]
    assert "▶️ Tập tiếp theo: https://youtu.be/vid2" in updates[0][1]
    assert NEXT_EPISODE_PLACEHOLDER not in updates[0][1]
    assert [c[0] for c in comments] == ["vid1", "vid2", "vid3"]
    # Short trỏ về tập 1.
    for call in up.calls[3:]:
        assert "https://youtu.be/vid1" in call["description"]
        assert call["publish_at"] is None
    assert state["uploaded"]["1"]["next_link_set"] and state["uploaded"]["3"]["comment_posted"]
    assert (tmp_path / "t-episodes-upload-state.json").exists()


def test_loi_giua_chung_thi_chay_lai_khong_dang_trung(tmp_path):
    ix = _index(tmp_path, with_shorts=False)
    up = FakeUploader(fail_on="truyen-tap-2.mp4")
    with pytest.raises(episodes_cli.EpisodesUploadError, match="tập 2"):
        episodes_cli.run(ix["index"], uploader=up, commenter=lambda *a: "c", description_updater=lambda *a: True,
                         credentials_loader=lambda: "creds")
    assert [c["video_path"].name for c in up.calls] == ["truyen-tap-1.mp4"]

    up2 = FakeUploader()
    episodes_cli.run(ix["index"], uploader=up2, commenter=lambda *a: "c", description_updater=lambda *a: True,
                     credentials_loader=lambda: "creds")
    assert [c["video_path"].name for c in up2.calls] == ["truyen-tap-2.mp4", "truyen-tap-3.mp4"]


def test_no_schedule_khong_truyen_publish_at(tmp_path):
    ix = _index(tmp_path, with_shorts=False)
    up = FakeUploader()
    episodes_cli.run(ix["index"], uploader=up, schedule=False, commenter=lambda *a: None,
                     description_updater=lambda *a: False, credentials_loader=lambda: "creds")
    assert all(c["publish_at"] is None for c in up.calls)
