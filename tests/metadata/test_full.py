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
    # Mô tả đầy đủ (quay lại từ 05/11): hook -> cảnh báo AI -> tóm tắt 2 câu ->
    # câu hỏi -> playlist -> CTA -> chương -> hashtag. Không "Keywords:".
    from metadata.full import AI_NOTICE_SHORT

    khoi = desc.split("\n\n")
    assert khoi[0] == "Bác Cả đòi đất, tôi bật live."
    assert khoi[1] == AI_NOTICE_SHORT
    assert khoi[2] == "Câu một giới thiệu. Câu hai hấp dẫn!"
    assert khoi[3] == f"❓ {QUESTION}"
    assert TOPIC_PLAYLIST_PLACEHOLDER in desc
    assert "Chương:\n0:00 Mở đầu\n0:25 Chương 1" in desc
    assert desc.rstrip().endswith("#truyenaudio #hohangcucpham #truyenhai")
    assert "Keywords:" not in desc
    assert meta["pinned_comment"].startswith(f"❓ {QUESTION}")
    assert "1 = cho, 2 = không" in meta["pinned_comment"]


# --- dòng series cho truyện thuộc series (spec kho 24/09 §5) ---


def test_mo_ta_co_dong_series_khi_truyen_thuoc_series():
    from metadata.full import SERIES_LINE, build_full_description

    desc = build_full_description(
        SeoCopy(title="T", description_draft="Câu một. Câu hai.", tags=[], hashtags=[]),
        hook="hook",
        comment_question="q?",
        chapter_lines=["0:00 Chương 1"],
        hashtags=["#truyenaudio"],
        series="Nhà Họ Trần",
    )

    assert SERIES_LINE.format(series="Nhà Họ Trần") in desc
    # Đứng trước link playlist để người đọc thấy ngay truyện này nằm trong series.
    assert desc.index("Nhà Họ Trần") < desc.index("playlist)")


def test_mo_ta_truyen_le_khong_co_dong_series():
    from metadata.full import build_full_description

    desc = build_full_description(
        SeoCopy(title="T", description_draft="Câu một. Câu hai.", tags=[], hashtags=[]),
        hook="hook",
        comment_question="q?",
        chapter_lines=[],
        hashtags=[],
        series="Truyện lẻ",
    )

    assert "Series" not in desc


def test_mo_ta_khong_truyen_series_van_chay_nhu_cu():
    from metadata.full import build_full_description

    desc = build_full_description(
        SeoCopy(title="T", description_draft="Câu một. Câu hai.", tags=[], hashtags=[]),
        hook="hook", comment_question="q?", chapter_lines=[], hashtags=[],
    )

    assert "Series" not in desc


# --- cảnh báo nội dung AI (30/09/2026) ---------------------------------------


def test_mo_ta_co_canh_bao_ai_o_dong_hai_va_ban_day_du_o_cuoi():
    """Truyện kể ngôi 'tôi' về chuyện nhà rất đời thường, người nghe dễ tưởng
    có thật. YouTube chỉ hiện ~2 dòng đầu trước khi phải bấm 'thêm', nên dòng
    ngắn phải nằm ngay sau hook thì mới thấy được mà không đè mất hook."""
    from metadata.full import AI_NOTICE_FULL, AI_NOTICE_SHORT, build_full_description

    desc = build_full_description(
        SEO, hook="Hook mở đầu.", comment_question=QUESTION,
        chapter_lines=["0:00 Mở đầu", "1:00 Chương 1"], hashtags=["#truyenaudio"],
    )
    khoi = desc.split("\n\n")

    assert khoi[0] == "Hook mở đầu."
    assert khoi[1] == AI_NOTICE_SHORT
    assert AI_NOTICE_FULL in desc
    # Bản đầy đủ ở cuối, hashtag vẫn là khối chốt.
    assert khoi.index(AI_NOTICE_FULL) == len(khoi) - 2
    assert khoi[-1] == "#truyenaudio"


def test_canh_bao_noi_ca_hu_cau_lan_ai():
    """Chỉ nói 'do AI tạo' thì người nghe vẫn có thể nghĩ AI kể lại vụ có thật."""
    from metadata.full import AI_NOTICE_FULL, AI_NOTICE_SHORT

    for text in (AI_NOTICE_SHORT, AI_NOTICE_FULL):
        assert "hư cấu" in text.lower()
        assert "AI" in text


def test_khong_co_hook_thi_canh_bao_van_len_dau():
    from metadata.full import AI_NOTICE_SHORT, build_full_description

    desc = build_full_description(SEO, hook="", comment_question=QUESTION,
                                  chapter_lines=[], hashtags=[])

    assert desc.split("\n\n")[0] == AI_NOTICE_SHORT


# --- mô tả tối giản theo format tham khảo (05/10/2026) -----------------------


def test_mo_ta_toi_gian_gom_tieu_de_canh_bao_hashtag_tu_khoa():
    """Format tham khảo (2,38 triệu view) chỉ có ba dòng: tiêu đề, hashtag, từ
    khoá. Giữ thêm cảnh báo AI -- yêu cầu riêng của kênh từ 30/09."""
    from metadata.full import AI_NOTICE_SHORT, build_minimal_description

    desc = build_minimal_description(
        "[Truyện Audio] Bác Cả Đòi Chia Đất | Audio Truyện",
        hashtags=["#truyenaudio", "#hohangcucpham"],
        keywords=["truyện audio", "truyện gia đình"],
    )
    khoi = desc.split("\n\n")

    assert khoi[0] == "[Truyện Audio] Bác Cả Đòi Chia Đất | Audio Truyện"
    assert khoi[1] == AI_NOTICE_SHORT
    assert khoi[2] == "Hashtags: #truyenaudio #hohangcucpham"
    assert khoi[3] == "Keywords: truyện audio, truyện gia đình"
    assert len(khoi) == 4


def test_mo_ta_toi_gian_khong_con_chuong_hay_cau_hoi():
    from metadata.full import build_minimal_description

    desc = build_minimal_description("T", hashtags=["#a"], keywords=["k"])

    assert "Chương:" not in desc and "❓" not in desc and "(link playlist)" not in desc


def test_hashtag_khong_qua_15_cai_ke_ca_khi_seo_tra_nhieu():
    """Quá 15 hashtag là YouTube bỏ qua TẤT CẢ hashtag trong mô tả."""
    from metadata.full import build_minimal_description

    desc = build_minimal_description("T", hashtags=[f"#h{i}" for i in range(30)], keywords=[])

    dong = [l for l in desc.splitlines() if l.startswith("Hashtags:")][0]
    assert len(dong.split()) - 1 <= 15


def test_thieu_tu_khoa_thi_bo_dong_keywords():
    from metadata.full import build_minimal_description

    assert "Keywords:" not in build_minimal_description("T", hashtags=["#a"], keywords=[])


def test_hashtag_trung_khac_hoa_thuong_chi_giu_mot():
    """YouTube coi #truyenaudio và #TruyenAudio là một. Bản #9 ngày 05/10 đã
    ra cả hai vì hashtag chủ đề và hashtag Gemini gợi ý viết hoa khác nhau."""
    from metadata.full import build_minimal_description

    desc = build_minimal_description(
        "T", hashtags=["#truyenaudio", "#hohang", "#TruyenAudio", "#HoHang", "#moi"], keywords=[]
    )

    dong = [l for l in desc.splitlines() if l.startswith("Hashtags:")][0]
    assert dong == "Hashtags: #truyenaudio #hohang #moi"
