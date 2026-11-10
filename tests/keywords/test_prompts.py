from keywords.prompts import build_keyword_story_prompt, build_keyword_story_retry_prompt


def test_prompt_mang_tu_khoa_chu_de_luat_va_bang_chung():
    p = build_keyword_story_prompt("mẹ chồng giữ sổ đỏ", ["Kênh A: Mẹ Chồng Giữ Sổ Đỏ (x2.5)"], ["Ngôi 'tôi'."], ["Tên Cũ"])
    assert "TỪ KHÓA: mẹ chồng giữ sổ đỏ" in p
    assert "Kênh A: Mẹ Chồng Giữ Sổ Đỏ (x2.5)" in p
    assert "- ho_hang_viet:" in p and "- bo_me_trong_sinh:" in p
    assert "Ngôi 'tôi'." in p and "Tên Cũ" in p
    assert "KHÔNG mở đầu bằng 'Tôi'" in p
    assert "TUYỆT ĐỐI KHÔNG dùng dấu nháy kép" in p


def test_prompt_khong_co_bang_chung_thi_noi_ro_co_hoi_moi():
    assert "chưa kênh nào làm cụm này" in build_keyword_story_prompt("em chồng vay app đen", [], [], [])


def test_prompt_hoi_lai_liet_ke_loi():
    p = build_keyword_story_retry_prompt(["title dài 65 ký tự", "hook dài quá 20 từ"])
    assert "- title dài 65 ký tự" in p and "- hook dài quá 20 từ" in p and "DUY NHẤT một JSON" in p


def test_prompt_bien_tap_lan_hai_giu_tieu_de_va_tranh_boi_canh_cu():
    from keywords.prompts import build_keyword_story_edit_prompt

    p = build_keyword_story_edit_prompt("bố mẹ nuôi", '{"title": "X"}', ["Ở phường Ô Chợ Dừa, Hà Nội, tôi là Mai"])
    assert '"title" chỉ sửa' in p and "Ô Chợ Dừa" in p
    assert "CÚ LẬT HAI LỚP" in p and "SỐ LIỆU CỤ THỂ" in p and "NHÂN VẬT PHỤ" in p
