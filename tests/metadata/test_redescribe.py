# tests/metadata/test_redescribe.py
"""Viết lại mô tả video đã đăng theo mẫu đầy đủ (05/11/2026). Không gọi API."""
import json
from pathlib import Path

import pytest

from metadata import redescribe
from metadata.full import AI_NOTICE_SHORT, TOPIC_PLAYLIST_PLACEHOLDER

QUESTION = "Ông bà trông cháu có nên được trả tiền? 1 = nên, 2 = không"


def _files(tmp_path: Path, vid: str = "v1", shorts: list[str] | None = None) -> dict:
    meta_dir, ep_dir = tmp_path / "metadata", tmp_path / "episodes"
    meta_dir.mkdir(exist_ok=True)
    ep_dir.mkdir(exist_ok=True)
    stem = f"bo_me_trong_sinh-20261101T000000Z-full"
    video_meta = meta_dir / f"{stem}-video.json"
    video_meta.write_text(json.dumps({
        "title": "[Truyện Audio] Bà Nội Trọng Sinh | Audio Truyện",
        "description": "[Truyện Audio] Bà Nội Trọng Sinh | Audio Truyện\n\nKeywords: a, b",
        "hashtags": ["#truyenaudio", "#trongsinh"],
    }, ensure_ascii=False))
    prefix = tmp_path / "shorts" / "p"
    prefix.parent.mkdir(exist_ok=True)
    (prefix.parent / "p-upload-state.json").write_text(json.dumps(
        {"uploaded": {str(n): {"video_id": s} for n, s in enumerate(shorts or [], 1)}}))
    index = meta_dir / f"{stem}.json"
    index.write_text(json.dumps({
        "topic": "bo_me_trong_sinh", "series": "Truyện lẻ",
        "episodes": [{"metadata_path": str(video_meta)}],
        "shorts_prefix": str(prefix),
    }))
    (ep_dir / f"{stem}.json").write_text(json.dumps({
        "hook": "'Mẹ trông cháu giúp con nhé.' — 'Được. Ký đây.'",
        "comment_question": QUESTION,
        "episodes": [{"chapters": [
            {"heading": "Mở đầu", "start_seconds": 0.0},
            {"heading": "Ký hợp đồng", "start_seconds": 24.0},
            {"heading": "Lương tháng đầu", "start_seconds": 190.0},
        ]}],
    }, ensure_ascii=False))
    return {"video_id": vid, "index": str(index), "story_title": "Bà Nội Trọng Sinh",
            "url": f"https://youtu.be/{vid}"}


def test_mo_ta_day_du_tu_file_tren_may(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PLAYLIST_BO_ME", "https://www.youtube.com/playlist?list=PLabc")
    row = _files(tmp_path)
    desc, meta_path = redescribe.full_description_for(row, tmp_path / "episodes")
    khoi = desc.split("\n\n")
    assert khoi[0] == "'Mẹ trông cháu giúp con nhé.' — 'Được. Ký đây.'"
    assert khoi[1] == AI_NOTICE_SHORT
    assert khoi[2] == f"❓ {QUESTION}"
    assert "📚 Nghe thêm truyện cùng chủ đề: https://www.youtube.com/playlist?list=PLabc" in desc
    assert TOPIC_PLAYLIST_PLACEHOLDER not in desc
    assert "Chương:\n0:00 Mở đầu\n0:24 Ký hợp đồng\n3:10 Lương tháng đầu" in desc
    assert desc.rstrip().endswith("#truyenaudio #trongsinh")
    assert "Keywords:" not in desc
    assert meta_path.name.endswith("-full-video.json")


def test_mo_ta_short_dung_cau_hoi_cua_truyen(tmp_path):
    row = _files(tmp_path)
    assert redescribe.short_description_for(row, tmp_path / "episodes") == (
        f"Bà Nội Trọng Sinh.\nNghe trọn tập tại: https://youtu.be/v1\n❓ {QUESTION}"
    )


def test_run_sua_video_dai_va_short_roi_ghi_lai_file_local(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_PLAYLIST_BO_ME", raising=False)
    row = _files(tmp_path, shorts=["s1", "s2", "s3"])
    calls = []
    counts = redescribe.run(None, [row], include_shorts=True, episodes_dir=tmp_path / "episodes",
                            updater=lambda c, vid, d: calls.append((vid, d)) or True)
    assert [c[0] for c in calls] == ["v1", "s1", "s2", "s3"]
    assert counts == {"long": 1, "short": 3, "failed": 0, "skipped": 0}
    saved = json.loads(Path(json.loads(Path(row["index"]).read_text())["episodes"][0]["metadata_path"]).read_text())
    assert saved["description"] == calls[0][1]
    assert "Keywords:" not in saved["description"]


def test_run_hong_3_lan_lien_tiep_thi_dung(tmp_path, capsys):
    rows = [_files(tmp_path, vid=f"v{i}") for i in range(5)]
    counts = redescribe.run(None, rows, episodes_dir=tmp_path / "episodes", updater=lambda *a: False)
    assert counts["failed"] == 3
    assert "Dừng" in capsys.readouterr().out


def test_thieu_chi_muc_thi_bo_qua_video_do(tmp_path, capsys):
    row = {"video_id": "mat", "index": str(tmp_path / "khong-co.json")}
    counts = redescribe.run(None, [row], episodes_dir=tmp_path, updater=lambda *a: True)
    assert counts["skipped"] == 1 and "BỎ QUA mat" in capsys.readouterr().out


def test_dry_run_khong_goi_update(tmp_path):
    row = _files(tmp_path)
    counts = redescribe.run(None, [row], dry_run=True, episodes_dir=tmp_path / "episodes",
                            updater=lambda *a: pytest.fail("không được gọi"))
    assert counts["long"] == 1
