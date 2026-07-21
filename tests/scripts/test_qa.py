import pytest

from scripts.models import Chapter, Script
from scripts.qa import ScriptQAError, validate_script


def _make_script(word_count: int, num_chapters: int, extra_text: str = "") -> Script:
    words_per_chapter = word_count // num_chapters
    chapters = [
        Chapter(index=i + 1, heading=f"Chương {i + 1}", text=" ".join(["từ"] * words_per_chapter))
        for i in range(num_chapters)
    ]
    if extra_text:
        chapters[0].text += " " + extra_text
    return Script(trope="demo", title="Tiêu đề", chapters=chapters)


def test_validate_script_passes_for_valid_script():
    script = _make_script(word_count=6000, num_chapters=8)
    validate_script(script)  # không raise


def test_validate_script_raises_when_too_short():
    script = _make_script(word_count=1000, num_chapters=8)
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_many_chapters():
    script = _make_script(word_count=6000, num_chapters=12)
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_when_banned_term_present():
    script = _make_script(word_count=6000, num_chapters=8, extra_text="phù mỏ audio")
    with pytest.raises(ScriptQAError, match="từ khoá bị cấm"):
        validate_script(script)


def test_validate_script_passes_at_exact_minimum_boundaries():
    # 5000 // 6 = 833, 833 * 6 = 4998, so add 2 extra words to reach exactly 5000
    script = _make_script(word_count=5000, num_chapters=6, extra_text="từ từ")
    assert script.word_count == 5000
    validate_script(script)  # không raise


def test_validate_script_passes_at_exact_maximum_boundaries():
    # 8000 // 10 = 800, 800 * 10 = 8000 (perfect, no rounding loss)
    script = _make_script(word_count=8000, num_chapters=10)
    assert script.word_count == 8000
    validate_script(script)  # không raise


def test_validate_script_raises_just_below_minimum_words():
    # 4999 // 8 = 624, 624 * 8 = 4992, so add 7 extra words to reach exactly 4999
    script = _make_script(word_count=4999, num_chapters=8, extra_text="từ từ từ từ từ từ từ")
    assert script.word_count == 4999  # verify it's exactly at target boundary
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_words():
    # 8001 // 8 = 1000, 1000 * 8 = 8000, so add 1 extra word to reach 8001
    script = _make_script(word_count=8001, num_chapters=8, extra_text="từ")
    assert script.word_count == 8001
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_few_chapters():
    # 6000 // 5 = 1200, 1200 * 5 = 6000 (exact, no rounding loss)
    script = _make_script(word_count=6000, num_chapters=5)
    assert script.word_count == 6000
    assert len(script.chapters) == 5
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_chapters():
    # 6000 // 11 = 545, 545 * 11 = 5995 (below max words, but > 10 chapters)
    script = _make_script(word_count=6000, num_chapters=11)
    assert len(script.chapters) == 11
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_aggregates_multiple_failures_in_one_message():
    # 1000 // 12 = 83, 83 * 12 = 996 (< 5000 AND > 10 chapters)
    script = _make_script(word_count=1000, num_chapters=12)
    assert script.word_count == 996  # below minimum
    assert len(script.chapters) == 12  # above maximum
    with pytest.raises(ScriptQAError) as exc_info:
        validate_script(script)
    message = str(exc_info.value)
    assert "Độ dài" in message
    assert "Số chương" in message
