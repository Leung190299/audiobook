import json

from keywords.story import append_auto_story, next_auto_id, slugify, to_bank_record, validate_story

PHRASE = "mẹ chồng giữ sổ đỏ"


def _ok():
    return {
        "topic": "ho_hang_viet",
        "title": "Mẹ Chồng Giữ Sổ Đỏ Tôi Mua, Tôi Mời Công Chứng Đến Bàn Ăn",
        "hook": "Mẹ chồng gõ đũa: 'Sổ đỏ để mẹ giữ cho chắc, con dâu thì biết gì.'",
        "premise": " ".join(["từ"] * 180),
        "twist": " ".join(["từ"] * 180),
        "comment_question": "Sổ đỏ nhà bạn ai giữ? 1 = Mình, 2 = Mẹ chồng",
        "thumb_keywords": ["Công Chứng"],
    }


def test_ban_ghi_dat_thi_khong_loi():
    assert validate_story(_ok(), PHRASE, ["Truyện khác"]) == []


def test_thieu_truong_bao_ngay():
    d = _ok(); del d["twist"]
    assert validate_story(d, PHRASE, []) == ["thiếu trường twist"]


def test_tieu_de_phai_mang_tu_khoa_va_khong_mo_dau_bang_toi():
    d = _ok(); d["title"] = "Tôi Mời Công Chứng Đến Bàn Ăn"; d["thumb_keywords"] = ["Công Chứng"]
    problems = validate_story(d, PHRASE, [])
    assert any("mở đầu" in p for p in problems) and any("từ khóa" in p for p in problems)


def test_bat_cac_gioi_han_do_dai_va_nhay_kep():
    d = _ok()
    d["title"] = "M" * 61
    d["hook"] = " ".join(["a"] * 21)
    d["comment_question"] = " ".join(["a"] * 26)
    d["premise"] = "ngắn"
    d["twist"] = 'có "nháy kép" ' + " ".join(["từ"] * 180)
    d["thumb_keywords"] = ["Không có"]
    problems = validate_story(d, PHRASE, [])
    for key in ("title dài", "hook dài", "comment_question dài", "premise có", "nháy kép", "thumb_keywords"):
        assert any(key in p for p in problems), (key, problems)


def test_topic_la_va_tieu_de_trung():
    d = _ok(); d["topic"] = "tinh_cam"
    problems = validate_story(d, PHRASE, [d["title"].upper()])
    assert any("topic" in p for p in problems) and any("trùng" in p for p in problems)


def test_ban_ghi_kho_co_du_truong_va_uu_tien_A(tmp_path):
    rec = to_bank_record(_ok(), 1000, PHRASE)
    assert rec["id"] == 1000 and rec["priority"] == "A" and rec["series"] == "Truyện lẻ"
    assert rec["keyword"] == PHRASE and rec["thumb_keywords"] == ["Công Chứng"]
    path = tmp_path / "story_bank.auto.json"
    assert next_auto_id(path) == 1000
    append_auto_story(rec, path)
    append_auto_story(to_bank_record(_ok(), 1001, PHRASE), path)
    assert [r["id"] for r in json.loads(path.read_text(encoding="utf-8"))["stories"]] == [1000, 1001]
    assert next_auto_id(path) == 1002


def test_slug_bo_dau():
    assert slugify("Mẹ Chồng Giữ Sổ Đỏ") == "me-chong-giu-so-do"


def test_tu_khoa_thumbnail_phai_2_den_4_chu():
    d = _ok(); d["thumb_keywords"] = ["Mẹ Chồng Giữ Sổ Đỏ Tôi Mua"]
    assert any("2-4 chữ" in p for p in validate_story(d, PHRASE, []))


def test_ten_rieng_trong_hook_phai_co_trong_truyen():
    d = _ok(); d["hook"] = "Bà Loan quát: 'Mày là con nuôi, đem sổ đỏ sang tên em trai!'"
    d["premise"] = "Mai được ông bà Tám nhận nuôi. " + " ".join(["từ"] * 170)
    problems = validate_story(d, PHRASE, [])
    assert any("'Loan'" in p for p in problems)
    d["hook"] = "Bà Tám quát: 'Mày là con nuôi, đem sổ đỏ sang tên em trai!'"
    assert not any("trong hook" in p for p in validate_story(d, PHRASE, []))
