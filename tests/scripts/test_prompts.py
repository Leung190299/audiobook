from scripts.prompts import build_chapter_prompt, build_outline_prompt


def test_build_outline_prompt_includes_trope_details():
    prompt = build_outline_prompt("Trọng sinh báo thù", "Mô tả test.")

    assert "Trọng sinh báo thù" in prompt
    assert "Mô tả test." in prompt
    assert "16 chương" in prompt
    assert "10.000–13.000" in prompt


def test_build_chapter_prompt_enforces_minimum_words():
    prompt = build_chapter_prompt(3, 8, "Chương 3: Bí mật", "Tóm tắt chương 3.")

    assert "Chương 3/8" in prompt
    assert "Bí mật" in prompt
    assert "Tóm tắt chương 3." in prompt
    assert "650" in prompt
    assert "800" in prompt


def test_outline_prompt_yeu_cau_cliffhanger_dung_chuong_cuoi_tap():
    prompt = build_outline_prompt("Trọng sinh", "Mô tả.")

    assert "3 TẬP" in prompt
    assert "Tập 1/3: chương 1–5" in prompt
    assert "Tập 2/3: chương 6–11" in prompt
    assert "chương 5, 11 PHẢI nói rõ cliffhanger" in prompt
    assert '"hook"' in prompt
    assert '"comment_question"' in prompt


def test_chapter_prompt_chuong_1_mo_thang_vao_xung_dot():
    prompt = build_chapter_prompt(1, 16, "Mở đầu", "Tóm tắt.")
    assert "CHƯƠNG MỞ ĐẦU" in prompt
    assert "cliffhanger" not in prompt.lower()


def test_chapter_prompt_chuong_cuoi_tap_phai_cliffhanger():
    for n in (5, 11):
        prompt = build_chapter_prompt(n, 16, "Cuối tập", "Tóm tắt.")
        assert "CHƯƠNG CUỐI TẬP" in prompt
        assert "cliffhanger" in prompt


def test_chapter_prompt_chuong_thuong_va_chuong_ket():
    assert "CHƯƠNG" not in build_chapter_prompt(7, 16, "Giữa", "Tóm tắt.").split("YÊU CẦU BẮT BUỘC")[1][:40]
    assert "CHƯƠNG KẾT" in build_chapter_prompt(16, 16, "Kết", "Tóm tắt.")
