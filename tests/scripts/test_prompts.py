from scripts.prompts import build_prompt


def test_build_prompt_includes_trope_details():
    prompt = build_prompt("Trọng sinh báo thù", "Mô tả test.")

    assert "Trọng sinh báo thù" in prompt
    assert "Mô tả test." in prompt


def test_build_prompt_enforces_minimum_words_per_chapter():
    prompt = build_prompt("Trọng sinh báo thù", "Mô tả test.")

    assert "8 chương" in prompt
    assert "700 từ" in prompt
    assert "5.000–8.000 từ" in prompt
