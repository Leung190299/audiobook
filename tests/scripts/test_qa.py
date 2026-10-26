import pytest

from scripts.models import Chapter, Script
from scripts.qa import (
    MAX_WORDS,
    MIN_CHAPTER_WORDS,
    ScriptQAError,
    looks_like_refusal,
    validate_script,
)


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
    # Bám theo MAX_WORDS thay vì đóng cứng con số: trần đã phải nới một lần vì
    # kịch bản thật chạm nóc, và hai test biên khi đó lệch theo.
    chapters = 18
    script = _make_script(
        word_count=MAX_WORDS,
        num_chapters=chapters,
        extra_text=" ".join(["từ"] * (MAX_WORDS - (MAX_WORDS // chapters) * chapters)),
    )
    assert script.word_count == MAX_WORDS
    assert len(script.chapters) == 18  # exactly MAX_CHAPTERS
    validate_script(script)  # không raise


def test_validate_script_raises_just_below_minimum_words():
    # 8999 // 16 = 562, 562 * 16 = 8992, so add 7 extra words to reach exactly 8999
    script = _make_script(word_count=8999, num_chapters=16, extra_text="từ từ từ từ từ từ từ")
    assert script.word_count == 8999  # one word below MIN_WORDS
    with pytest.raises(ScriptQAError, match="Độ dài"):
        validate_script(script)


def test_validate_script_raises_just_above_maximum_words():
    chapters = 16
    over = MAX_WORDS + 1
    script = _make_script(
        word_count=over,
        num_chapters=chapters,
        extra_text=" ".join(["từ"] * (over - (over // chapters) * chapters)),
    )
    assert script.word_count == over  # đúng một từ trên MAX_WORDS
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


def test_validate_script_bat_chuong_qua_ngan_du_tong_tu_du():
    # Tổng 11.200 từ vẫn đạt, nhưng chương 4 chỉ còn 29 từ: đúng dạng lỗi
    # tập 05/09 lọt qua QA cũ.
    script = _make_script(word_count=11200, num_chapters=16)
    script.chapters[3].text = " ".join(["từ"] * 29)

    with pytest.raises(ScriptQAError, match="Chương 4"):
        validate_script(script)


def test_validate_script_bat_chuong_la_loi_tu_choi():
    script = _make_script(word_count=11200, num_chapters=16)
    script.chapters[3].text = (
        "Tôi không thể giúp bạn việc đó, vì tôi chỉ là một mô hình ngôn ngữ "
        + " ".join(["từ"] * MIN_CHAPTER_WORDS)
    )

    with pytest.raises(ScriptQAError, match="Chương 4.*từ chối"):
        validate_script(script)


def test_looks_like_refusal():
    assert looks_like_refusal("Tôi không thể giúp bạn việc đó, vì tôi chỉ là một mô hình ngôn ngữ.")
    assert looks_like_refusal("Xin lỗi, tôi không thể tạo nội dung này.")
    assert looks_like_refusal("I can't help with that request.")
    assert not looks_like_refusal("Tôi không thể tin nổi, cô ta dám cầm sổ đỏ đi thế chấp.")


# --- tiêu đề không được tục / miệt thị ---


def test_title_problem_bat_tu_mieng_thi_trong_tieu_de():
    from scripts.qa import title_problem

    # Tập 20/09 thật: Gemini đặt "Bà Chó Sủa Mỏ Hỗn Hóa Ra Lại Là Đồng Minh".
    assert title_problem("Bà Chó Sủa Mỏ Hỗn Hóa Ra Lại Là Đồng Minh") is not None
    assert title_problem("Con Đĩ Trà Xanh Bị Vả Mặt") is not None


def test_title_problem_khong_bat_nham_tu_lanh():
    from scripts.qa import title_problem

    assert title_problem("Mẹ Chồng Mỏ Hỗn Hóa Ra Là Đồng Minh") is None
    assert title_problem("Chống Lại Cả Hào Môn, Tôi Thắng") is None  # "chống" ≠ "chó"
    assert title_problem("Thiên Kim Thật Trở Về") is None


def test_validate_script_chan_tieu_de_tuc():
    script = _make_script(word_count=11200, num_chapters=16)
    script.title = "Bà Chó Sủa Mỏ Hỗn Hóa Ra Lại Là Đồng Minh"

    with pytest.raises(ScriptQAError, match="Tiêu đề"):
        validate_script(script)


def test_chuong_mo_dau_ngan_hon_san_van_qua():
    from scripts.models import PROLOGUE_HEADING
    from scripts.qa import MIN_CHAPTER_WORDS, validate_script

    body = " ".join(["chữ"] * 700)
    chapters = [Chapter(index=1, heading=PROLOGUE_HEADING, text=" ".join(["mở"] * 140))]
    chapters += [Chapter(index=i, heading=f"C{i}", text=body) for i in range(2, 17)]
    script = Script(trope="t", title="Tiêu đề", chapters=chapters)
    assert chapters[0].word_count < MIN_CHAPTER_WORDS
    validate_script(script)  # không ném lỗi
