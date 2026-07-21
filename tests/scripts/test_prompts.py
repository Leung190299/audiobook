from scripts.prompts import build_chapter_prompt, build_outline_prompt


def test_build_outline_prompt_includes_trope_details():
    prompt = build_outline_prompt("Trọng sinh báo thù", "Mô tả test.")

    assert "Trọng sinh báo thù" in prompt
    assert "Mô tả test." in prompt
    assert "8 chương" in prompt


def test_build_chapter_prompt_enforces_minimum_words():
    prompt = build_chapter_prompt(3, 8, "Chương 3: Bí mật", "Tóm tắt chương 3.")

    assert "Chương 3/8" in prompt
    assert "Bí mật" in prompt
    assert "Tóm tắt chương 3." in prompt
    assert "650" in prompt
    assert "800" in prompt
