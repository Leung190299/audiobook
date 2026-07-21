from scripts.models import Chapter, Script


def test_chapter_word_count():
    chapter = Chapter(index=1, heading="Chương 1", text="một hai ba bốn năm")
    assert chapter.word_count == 5


def test_script_word_count_sums_chapters():
    script = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="một hai ba"),
            Chapter(index=2, heading="Chương 2", text="bốn năm"),
        ],
    )
    assert script.word_count == 5


def test_script_full_text_joins_chapters_with_blank_line():
    script = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[
            Chapter(index=1, heading="Chương 1", text="Nội dung một."),
            Chapter(index=2, heading="Chương 2", text="Nội dung hai."),
        ],
    )
    assert script.full_text == "Nội dung một.\n\nNội dung hai."


def test_script_to_dict_and_from_dict_round_trip():
    original = Script(
        trope="trong_sinh_bao_thu",
        title="Tiêu đề",
        chapters=[Chapter(index=1, heading="Chương 1", text="Nội dung.")],
    )
    restored = Script.from_dict(original.to_dict())
    assert restored == original
