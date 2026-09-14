# tests/upload/test_episode_cli.py
"""Đăng trọn một tập: video dài trước, rồi 5 trích đoạn với link video dài
trong mô tả. Dùng uploader giả -- tuyệt đối không gọi API."""
import json
from pathlib import Path

from upload import episode_cli
from upload.uploader import UploadResult


class FakeUploader:
    def __init__(self):
        self.calls = []

    def __call__(self, credentials, *, video_path, title, description, tags,
                 category_id, privacy_status, thumbnail_path):
        self.calls.append({"video_path": Path(video_path), "title": title,
                           "description": description, "thumbnail_path": thumbnail_path})
        vid = f"vid{len(self.calls)}"
        return UploadResult(video_id=vid, url=f"https://youtu.be/{vid}", title=title,
                            privacy_status=privacy_status, thumbnail_set=thumbnail_path is not None)


def _episode(tmp_path: Path) -> dict:
    video = tmp_path / "tap-dai.mp4"; video.write_bytes(b"mp4")
    thumb = tmp_path / "thumb.png"; thumb.write_bytes(b"png")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Tập Dài", "description": "Mô tả tập dài.", "tags": ["a"]}),
                    encoding="utf-8")
    prefix_name = "t-20260914T000000Z"
    for n in (1, 2):
        stem = f"{prefix_name}-part-{n:02d}"
        (tmp_path / f"{stem}.mp4").write_bytes(b"mp4")
        (tmp_path / f"{stem}.jpg").write_bytes(b"jpg")
        (tmp_path / f"{stem}.json").write_text(json.dumps({
            "title": f"Tập Dài — Trích đoạn {n}/2",
            "description": f"Tập Dài — Trích đoạn {n}/2.\nNghe trọn tập trên kênh — link ở phần mô tả kênh.\n#shorts",
            "tags": ["shorts"], "part_number": n, "total_parts": 2,
            "video_filename": f"{stem}.mp4"}), encoding="utf-8")
    return {"video": video, "meta": meta, "thumb": thumb, "prefix": tmp_path / prefix_name}


def test_dang_video_dai_truoc_roi_short_voi_link(tmp_path):
    ep = _episode(tmp_path)
    uploader = FakeUploader()

    episode_cli.run(ep["video"], ep["meta"], ep["thumb"], ep["prefix"],
                    uploader=uploader, credentials_loader=lambda: "creds")

    assert [c["video_path"].name for c in uploader.calls] == [
        "tap-dai.mp4", "t-20260914T000000Z-part-01.mp4", "t-20260914T000000Z-part-02.mp4"]
    long_url = "https://youtu.be/vid1"
    for call in uploader.calls[1:]:
        assert f"Nghe trọn tập tại: {long_url}" in call["description"]
        assert "link ở phần mô tả kênh" not in call["description"]


def test_co_san_link_video_dai_thi_khong_dang_lai_video_dai(tmp_path):
    ep = _episode(tmp_path)
    uploader = FakeUploader()

    episode_cli.run(ep["video"], ep["meta"], ep["thumb"], ep["prefix"],
                    long_video_url="https://youtu.be/DA-CO", uploader=uploader,
                    credentials_loader=lambda: "creds")

    assert [c["video_path"].name for c in uploader.calls] == [
        "t-20260914T000000Z-part-01.mp4", "t-20260914T000000Z-part-02.mp4"]
    assert all("https://youtu.be/DA-CO" in c["description"] for c in uploader.calls)


def test_in_link_video_dai_va_tung_short(tmp_path, capsys):
    ep = _episode(tmp_path)

    episode_cli.run(ep["video"], ep["meta"], ep["thumb"], ep["prefix"],
                    uploader=FakeUploader(), credentials_loader=lambda: "creds")

    out = capsys.readouterr().out
    assert "Video dài: https://youtu.be/vid1" in out
    assert "https://youtu.be/vid2" in out and "https://youtu.be/vid3" in out
