# tests/metadata/test_full.py
"""Metadata video FULL của truyện chủ đề (spec 24/09/2026 §6)."""

import json

from metadata import cli
from metadata.full import (
    TOPIC_PLAYLIST_PLACEHOLDER,
    full_title,
    youtube_chapter_lines,
)
from metadata.seo_generator import SeoCopy
from scripts.models import Chapter, Script

SEO = SeoCopy(
    title="Tiêu Đề SEO Khác",
    description_draft="Câu một giới thiệu. Câu hai hấp dẫn! Câu ba thừa. Câu bốn thừa.",
    tags=["truyện audio", "họ hàng"],
    hashtags=["#TruyenAudio", "#HoHang", "#Khac"],
)
STORY = "Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn"
QUESTION = "Nếu là bạn, bạn có cho bác Cả mượn sổ đỏ không? 1 = cho, 2 = không"


def test_tieu_de_full_dung_khuon_va_gioi_han():
    t = full_title(STORY, "Audio Truyện")
    assert t == f"[Truyện Audio] {STORY} | Audio Truyện"
    assert len(t) <= 100
    long = full_title("Chữ " * 40, "Kênh")
    assert len(long) <= 100
    core = long.removeprefix("[Truyện Audio] ").removesuffix(" | Kênh")
    assert len(core) <= 60
    assert len(full_title(STORY, "K" * 60)) <= 100


def test_chuong_theo_luat_youtube():
    chapters = [
        {"heading": "Mở đầu", "start_seconds": 0.0},
        {"heading": "C1", "start_seconds": 25.0},
        {"heading": "C2", "start_seconds": 30.0},  # cách C1 < 10s -> bỏ
        {"heading": "C3", "start_seconds": 200.0},
    ]
    assert youtube_chapter_lines(chapters) == ["0:00 Mở đầu", "0:25 C1", "3:20 C3"]
    assert youtube_chapter_lines(chapters[:2]) == []  # < 3 mốc


async def test_run_full_ghi_metadata_index_va_doi_ten(tmp_path, monkeypatch, capsys):
    script = Script(
        trope="ho_hang_viet", title=STORY, topic="ho_hang_viet", format="full",
        hook="Bác Cả đòi đất, tôi bật live.", comment_question=QUESTION,
        chapters=[Chapter(index=i, heading=f"Chương {i}", text="x") for i in range(1, 4)],
    )
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script.to_dict(), ensure_ascii=False), encoding="utf-8")
    ep_dir = tmp_path / "output" / "episodes"
    ep_dir.mkdir(parents=True)
    video = ep_dir / "ho_hang_viet-20260924T000000Z-full.mp4"
    video.write_bytes(b"mp4")
    manifest = {
        "trope": "ho_hang_viet", "topic": "ho_hang_viet", "format": "full", "title": STORY,
        "hook": script.hook, "comment_question": QUESTION,
        "episodes": [{
            "number": 1, "total": 1, "video_path": str(video),
            "chapters": [{"heading": "Mở đầu", "start_seconds": 0.0}]
            + [{"heading": f"Chương {i}", "start_seconds": 25.0 + 600 * (i - 1)} for i in range(1, 4)],
        }],
    }
    manifest_path = ep_dir / "ho_hang_viet-20260924T000000Z-full.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    thumbs = tmp_path / "thumbs"
    thumbs.mkdir()
    (thumbs / "ho_hang_viet-20260924T000100Z-thumbnail-a.png").write_bytes(b"a")
    (thumbs / "ho_hang_viet-20260924T000100Z-thumbnail-b.png").write_bytes(b"b")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output" / "metadata")
    monkeypatch.setenv("CHANNEL_NAME", "Audio Truyện")

    async def fake_seo(script, client):
        return SEO

    monkeypatch.setattr(cli, "generate_seo_copy", fake_seo)
    index_path = await cli._run_episodes(script_path, manifest_path, gemini_client=object(), thumbnails_dir=thumbs)

    out = capsys.readouterr().out
    assert "Video full đã đổi tên:" in out and f"Danh sách: {index_path}" in out
    assert index_path.name == "ho_hang_viet-20260924T000000Z-full.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["topic"] == "ho_hang_viet" and index["format"] == "full"
    (ep,) = index["episodes"]
    assert ep["title"] == f"[Truyện Audio] {STORY} | Audio Truyện"
    assert ep["video_path"].endswith("bac-ca-doi-chia-dat-cua-bo-toi-livestream-luon.mp4")
    assert ep["thumbnail_path"].endswith("-thumbnail-a.png")
    assert ep["thumbnail_b_path"].endswith("-thumbnail-b.png")

    meta = json.loads(open(ep["metadata_path"], encoding="utf-8").read())
    desc = meta["description"]
    order = [
        desc.index("Bác Cả đòi đất, tôi bật live."),
        desc.index("Câu một giới thiệu. Câu hai hấp dẫn!"),
        desc.index(f"❓ {QUESTION}"),
        desc.index(TOPIC_PLAYLIST_PLACEHOLDER),
        desc.index("Đăng ký kênh"),
        desc.index("0:00 Mở đầu"),
        desc.index("#truyenaudio"),
    ]
    assert order == sorted(order)
    assert "Câu ba thừa" not in desc
    assert desc.splitlines()[-1] == "#truyenaudio #hohangcucpham #truyenhai"
    assert meta["pinned_comment"].startswith(f"❓ {QUESTION}")
    assert "1 = cho, 2 = không" in meta["pinned_comment"]
