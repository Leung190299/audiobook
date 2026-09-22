import json

from metadata import cli
from metadata.episodes import (
    DEFAULT_COMMENT_QUESTION,
    NEXT_EPISODE_PLACEHOLDER,
    PLAYLIST_PLACEHOLDER,
    build_episode_description,
    episode_chapter_lines,
    episode_title,
    pinned_comment,
)
from metadata.seo_generator import SeoCopy, clip_title
from scripts.models import Chapter, Script

SEO = SeoCopy(
    title="Mẹ Chồng Quỳ Xin Con Dâu Trả Nợ",
    description_draft="Mô tả truyện.",
    tags=["truyện audio", "trọng sinh"],
    hashtags=["#TruyenAudio", "#TrongSinh"],
)


def test_episode_title_va_clip_title():
    assert episode_title("Tiêu đề", 2, 3) == "Tiêu đề | Tập 2/3"
    long = "Một Tiêu Đề Rất Dài " * 5
    clipped = clip_title(long)
    assert len(clipped) <= 60 and not clipped.endswith(" ")
    assert clip_title("Ngắn") == "Ngắn"


def test_mo_ta_tap_giua_co_hook_cau_hoi_link_va_chuong():
    lines = episode_chapter_lines([{"heading": "Mở đầu", "start_seconds": 0.0}, {"heading": "Chương 6", "start_seconds": 31.2}])
    assert lines == ["0:00 Mở đầu", "0:31 Chương 6"]
    desc = build_episode_description(SEO, "Bị tráo phôi", "Bạn tha thứ chứ?", 2, 3, lines)
    assert desc.startswith("Bị tráo phôi\n\nTập 2/3. Mô tả truyện.")
    assert "❓ Bạn tha thứ chứ?" in desc
    assert PLAYLIST_PLACEHOLDER in desc and NEXT_EPISODE_PLACEHOLDER in desc
    assert "0:00 Mở đầu\n0:31 Chương 6" in desc
    assert desc.splitlines()[-1] == "#TruyenAudio #TrongSinh"


def test_mo_ta_tap_cuoi_khong_co_link_tap_sau_va_cau_hoi_mac_dinh():
    desc = build_episode_description(SEO, "", "", 3, 3, ["0:00 Chương 12"])
    assert NEXT_EPISODE_PLACEHOLDER not in desc
    assert DEFAULT_COMMENT_QUESTION in desc
    assert not desc.startswith("\n")


def test_binh_luan_ghim():
    p = pinned_comment("Bạn ký đơn hay tha?", 1, 3)
    assert p.startswith("❓ Bạn ký đơn hay tha?")
    assert "Tập 2 lên sóng" in p
    assert "Hết truyện" in pinned_comment("", 3, 3)


async def test_run_episodes_ghi_metadata_tung_tap_va_doi_ten_video(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="demo", title="T", hook="Bị tráo phôi", comment_question="Bạn tha thứ chứ?",
        chapters=[Chapter(index=i, heading=f"Chương {i}", text="x") for i in range(1, 7)],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")

    ep_dir = tmp_path / "output" / "episodes"
    ep_dir.mkdir(parents=True)
    episodes = []
    for n, (a, b) in enumerate([(1, 2), (3, 4), (5, 6)], start=1):
        video = ep_dir / f"demo-20260922T000000Z-ep-0{n}.mp4"
        video.write_bytes(b"mp4")
        episodes.append(
            {
                "number": n, "total": 3, "first_chapter": a, "last_chapter": b,
                "video_path": str(video), "duration_seconds": 900.0,
                "chapters": [{"heading": "Mở đầu", "start_seconds": 0.0}, {"heading": f"Chương {a}", "start_seconds": 25.0}, {"heading": f"Chương {b}", "start_seconds": 400.0}],
            }
        )
    manifest_path = ep_dir / "demo-20260922T000000Z-episodes.json"
    manifest_path.write_text(json.dumps({"trope": "demo", "title": "T", "hook": "Bị tráo phôi", "comment_question": "Bạn tha thứ chứ?", "episodes": episodes}, ensure_ascii=False), encoding="utf-8")

    thumbs = tmp_path / "output" / "thumbnails"
    thumbs.mkdir()
    (thumbs / "demo-20260922T000100Z-ep-02.png").write_bytes(b"png")

    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output" / "metadata")

    async def fake_seo(script, client):
        return SEO

    monkeypatch.setattr(cli, "generate_seo_copy", fake_seo)

    index_path = await cli._run_episodes(script_path, manifest_path, gemini_client=object(), thumbnails_dir=thumbs)

    out = capsys.readouterr().out
    assert "Đã lưu metadata tập 1/3:" in out and "Đã lưu metadata tập 3/3:" in out
    assert f"Danh sách: {index_path}" in out

    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["story_title"] == SEO.title
    eps = index["episodes"]
    assert [e["title"] for e in eps] == [f"{SEO.title} | Tập {n}/3" for n in (1, 2, 3)]
    assert eps[0]["video_path"].endswith("me-chong-quy-xin-con-dau-tra-no-tap-1.mp4")
    assert (ep_dir / "me-chong-quy-xin-con-dau-tra-no-tap-3.mp4").exists()
    assert eps[1]["thumbnail_path"].endswith("-ep-02.png")
    assert eps[0]["thumbnail_path"] is None

    meta2 = json.loads(open(eps[1]["metadata_path"], encoding="utf-8").read())
    assert meta2["episode_number"] == 2
    assert meta2["pinned_comment"].startswith("❓ Bạn tha thứ chứ?")
    assert "0:25 Chương 3" in meta2["description"]
    assert meta2["description"].startswith("Bị tráo phôi")
    txt = (tmp_path / "output" / "metadata" / "demo-20260922T000000Z-ep-02.txt").read_text(encoding="utf-8")
    assert "BÌNH LUẬN GHIM:" in txt and "THUMBNAIL:" in txt


def test_main_episodes_mode(monkeypatch):
    calls = []

    async def fake(script_path, manifest_path):
        calls.append((script_path, manifest_path))

    monkeypatch.setattr(cli, "_run_episodes", fake)
    monkeypatch.setattr("sys.argv", ["cli.py", "s.json", "--episodes", "m.json"])
    cli.main()
    assert calls and str(calls[0][1]) == "m.json"
