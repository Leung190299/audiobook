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
    # 11200 // 16 = 700, 700 * 16 = 11200 (divides evenly, no rounding loss)
    script = _make_script(word_count=11200, num_chapters=16)
    assert script.word_count == 11200
    validate_script(script)  # không raise


def test_validate_script_raises_when_too_short():
    # 1600 // 16 = 100, 100 * 16 = 1600 (well below MIN_WORDS, chapter count valid)
    script = _make_script(word_count=1600, num_chapters=16)
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_many_chapters():
    # 11000 // 20 = 550, 550 * 20 = 11000 (words valid, but 20 > MAX_CHAPTERS)
    script = _make_script(word_count=11000, num_chapters=20)
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_when_banned_term_present():
    # Valid words and chapters; the 3 extra words keep it inside MAX_WORDS.
    script = _make_script(word_count=11200, num_chapters=16, extra_text="phù mỏ audio")
    with pytest.raises(ScriptQAError, match="từ khoá bị cấm"):
        validate_script(script)


def test_validate_script_passes_at_exact_minimum_boundaries():
    # 9000 // 14 = 642, 642 * 14 = 8988, so add 12 extra words to reach exactly 9000
    script = _make_script(
        word_count=9000,
        num_chapters=14,
        extra_text="từ từ từ từ từ từ từ từ từ từ từ từ",
    )
    assert script.word_count == 9000  # exactly MIN_WORDS
    assert len(script.chapters) == 14  # exactly MIN_CHAPTERS
    validate_script(script)  # không raise


def test_validate_script_passes_at_exact_maximum_boundaries():
    # 14000 // 18 = 777, 777 * 18 = 13986, so add 14 extra words to reach exactly 14000
    script = _make_script(
        word_count=14000,
        num_chapters=18,
        extra_text="từ từ từ từ từ từ từ từ từ từ từ từ từ từ",
    )
    assert script.word_count == 14000  # exactly MAX_WORDS
    assert len(script.chapters) == 18  # exactly MAX_CHAPTERS
    validate_script(script)  # không raise


def test_validate_script_raises_just_below_minimum_words():
    # 8999 // 16 = 562, 562 * 16 = 8992, so add 7 extra words to reach exactly 8999
    script = _make_script(word_count=8999, num_chapters=16, extra_text="từ từ từ từ từ từ từ")
    assert script.word_count == 8999  # one word below MIN_WORDS
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_words():
    # 14001 // 16 = 875, 875 * 16 = 14000, so add 1 extra word to reach exactly 14001
    script = _make_script(word_count=14001, num_chapters=16, extra_text="từ")
    assert script.word_count == 14001  # one word above MAX_WORDS
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_when_too_few_chapters():
    # 13000 // 13 = 1000, 1000 * 13 = 13000 (words valid, but 13 < MIN_CHAPTERS)
    script = _make_script(word_count=13000, num_chapters=13)
    assert script.word_count == 13000
    assert len(script.chapters) == 13
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_chapters():
    # 11400 // 19 = 600, 600 * 19 = 11400 (words valid, but 19 > MAX_CHAPTERS)
    script = _make_script(word_count=11400, num_chapters=19)
    assert script.word_count == 11400
    assert len(script.chapters) == 19
    with pytest.raises(ScriptQAError, match="Số chương"):
        validate_script(script)


def test_validate_script_aggregates_multiple_failures_in_one_message():
    # 1000 // 20 = 50, 50 * 20 = 1000 (< MIN_WORDS AND > MAX_CHAPTERS)
    script = _make_script(word_count=1000, num_chapters=20)
    assert script.word_count == 1000  # below minimum
    assert len(script.chapters) == 20  # above maximum
    with pytest.raises(ScriptQAError) as exc_info:
        validate_script(script)
    message = str(exc_info.value)
    assert "Độ dài" in message
    assert "Số chương" in message
