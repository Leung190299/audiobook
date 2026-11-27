# tests/scripts/test_topics.py
from datetime import date

import pytest

from scripts.text_tools import clean_thumb_fields, pick_thumb_text
from thumbnail.sticker import STICKER_DIR
from scripts.topics import (
    DEFAULT_ROTATION,
    SATURATED_MOTIFS,
    TITLE_MAX_CHARS,
    TOPICS,
    TopicError,
    get_topic,
    parse_rotation,
    resolve_topic,
    topic_for_date,
)

TOPIC_IDS = {"ho_hang_viet", "nghe_la_hong_bien", "bo_me_trong_sinh", "hoc_duong"}


def test_registry_du_3_chu_de():
    assert set(TOPICS) == TOPIC_IDS
    for topic_id, topic in TOPICS.items():
        assert topic.id == topic_id


@pytest.mark.parametrize("topic_id", sorted(TOPIC_IDS))
def test_moi_chu_de_du_truong_bat_buoc(topic_id):
    t = TOPICS[topic_id]
    assert t.name and t.protagonist and t.tone and t.comment_question_style
    assert len(t.settings) >= 10, "cần >= 10 bối cảnh để xoay vòng 30 ngày"
    assert len(set(t.settings)) == len(t.settings)
    assert t.title_formulas
    assert len(t.thumb_palette) == 3
    assert all(c.startswith("#") and len(c) == 7 for c in t.thumb_palette)
    assert len(t.thumb_stickers) == 2 and t.thumb_stickers[0] != t.thumb_stickers[1]
    for name in t.thumb_stickers:
        assert (STICKER_DIR / f"{name}.png").exists(), name
    assert t.playlist_env.startswith("YOUTUBE_PLAYLIST_")
    assert len(t.hashtags) == 2 and all(h.startswith("#") for h in t.hashtags)
    for motif in SATURATED_MOTIFS:
        assert motif in t.banned_motifs


def test_nen_thumbnail_moi_chu_de_mot_mau():
    backgrounds = {t.thumb_palette[0] for t in TOPICS.values()}
    assert len(backgrounds) == len(TOPICS)


def test_hoc_duong_moi_tuan_mot_toi():
    from scripts.topics import DEFAULT_ROTATION

    assert DEFAULT_ROTATION.count("hoc_duong") == 1


@pytest.mark.parametrize("topic_id", sorted(TOPIC_IDS))
def test_vi_du_tieu_de_trong_cong_thuc_khong_qua_60_ky_tu(topic_id):
    for formula in TOPICS[topic_id].title_formulas:
        example = formula.split("vd '", 1)[1].rstrip("'")
        assert len(example) <= TITLE_MAX_CHARS, example


@pytest.mark.parametrize(
    "thumb,keywords",
    [
        ("Bác Cả Đòi Chia Đất Của Bố, Tôi Livestream Luôn", ["Chia Đất", "Livestream Luôn"]),
        ("Tôi Làm Chủ Trọ, Mười Phòng Mười Drama", ["mười drama"]),
        ("Trọng Sinh Năm 60 Tuổi, Tôi Không Chia Nhà Nữa", ["Không Chia Nhà", "không có trong câu"]),
    ],
)
def test_tu_khoa_thumbnail_luon_la_chuoi_con_cua_thumb_text(thumb, keywords):
    text, kws = clean_thumb_fields(thumb, keywords, "t")
    assert 1 <= len(kws) <= 3
    for kw in kws:
        assert kw in text


def test_thumb_text_bi_cat_con_12_chu():
    text, kws = clean_thumb_fields(" ".join(f"chữ{i}" for i in range(20)), ["chữ3"], "t")
    assert len(text.split()) == 12
    assert kws == ["chữ3"]


# --- chữ bìa là một câu KHÁC tiêu đề (kiểm kênh 26/11/2026) -------------------

TITLE_MC = "Mẹ Chồng Luôn Muốn Tôi Bẽ Mặt, Tôi Mở File Ghi Âm"


def test_chu_bia_khac_tieu_de_thi_giu_va_to_mau_tu_khoa_cua_no():
    text, kws = pick_thumb_text("Ăn Bám Quen Thói? Nghe Lại Đi Mẹ", ["Ăn Bám"], TITLE_MC, ["File Ghi Âm"])
    assert text == "Ăn Bám Quen Thói? Nghe Lại Đi Mẹ"
    assert kws == ["Ăn Bám"]


def test_chu_bia_boc_ngoac_kep_thi_go_ca_cap_con_ngoac_o_giua_thi_giu():
    # Mô hình hay bọc cả câu trong ngoặc kép; gỡ một đầu mà để đầu kia là hỏng chữ.
    assert pick_thumb_text('"Ăn Bám Quen Thói Rồi!"', [], TITLE_MC)[0] == "Ăn Bám Quen Thói Rồi!"
    giua = "“Ăn Bám Quen Thói?” Nghe Lại Đi Mẹ"
    assert pick_thumb_text(giua, [], TITLE_MC)[0] == giua


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        TITLE_MC,
        "Mẹ Chồng Muốn Tôi Bẽ Mặt",  # rút gọn tiêu đề: vẫn là nói lại tiêu đề
        "Một Câu Rất Dài Không Ai Đọc Kịp Khi Lướt Ngang Qua Bìa",  # quá 8 chữ
    ],
)
def test_chu_bia_trong_lap_tieu_de_hoac_qua_dai_thi_quay_ve_tieu_de(candidate):
    text, kws = pick_thumb_text(candidate, ["Bẽ Mặt"], TITLE_MC, ["File Ghi Âm"])
    assert text == TITLE_MC
    assert kws == ["File Ghi Âm"]


def test_rotation_mac_dinh_7_ngay_hop_le():
    assert len(DEFAULT_ROTATION) == 7
    assert set(DEFAULT_ROTATION) == TOPIC_IDS
    assert parse_rotation("") == DEFAULT_ROTATION


def test_auto_xoay_theo_thu_trong_tuan():
    rotation = parse_rotation(
        "ho_hang_viet,nghe_la_hong_bien,ho_hang_viet,bo_me_trong_sinh,nghe_la_hong_bien,ho_hang_viet,bo_me_trong_sinh"
    )
    # 21/09/2026 là thứ Hai.
    assert topic_for_date(date(2026, 9, 21), rotation) == "ho_hang_viet"
    assert topic_for_date(date(2026, 9, 24), rotation) == "bo_me_trong_sinh"
    assert topic_for_date(date(2026, 9, 27), rotation) == "bo_me_trong_sinh"


def test_auto_doc_rotation_tu_env(monkeypatch):
    monkeypatch.setenv("AUDIOBOOK_TOPIC_ROTATION", "nghe_la_hong_bien")
    assert resolve_topic("auto", date(2026, 9, 24)).id == "nghe_la_hong_bien"


def test_rotation_co_id_sai_thi_bao_loi():
    with pytest.raises(TopicError):
        parse_rotation("ho_hang_viet,khong_ton_tai")
    with pytest.raises(TopicError):
        get_topic("trong_sinh_bao_thu")
