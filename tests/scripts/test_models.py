import json

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


def test_from_dict_chiu_duoc_kich_ban_cu_khong_co_hook():
    script = Script.from_dict(
        {"trope": "t", "title": "T", "chapters": [{"index": 1, "heading": "C1", "text": "x"}]}
    )
    assert script.hook == ""
    assert script.comment_question == ""


def test_hook_va_comment_question_round_trip():
    original = Script(
        trope="t",
        title="T",
        chapters=[Chapter(index=1, heading="C1", text="x")],
        hook="Cô bị tráo phôi",
        comment_question="Bạn sẽ tha thứ chứ?",
    )
    restored = Script.from_dict(original.to_dict())
    assert restored == original
    assert original.to_dict()["hook"] == "Cô bị tráo phôi"


def test_to_dict_giu_story_id_va_series_qua_json():
    """Stage 6 nạp kịch bản từ JSON, không dùng lại object của stage 1.

    Thiếu hai trường này thì mô tả mất dòng series và publishAt tính theo
    truyện số 0 -- hẹn giờ sai ngày, kho không đánh dấu đã dùng.
    """
    from scripts.models import Chapter, Script

    script = Script(
        trope="ho_hang_viet", title="T", topic="ho_hang_viet", format="full",
        story_id=2, series="Nhà Họ Trần",
        chapters=[Chapter(index=1, heading="C1", text="x")],
    )

    data = script.to_dict()
    assert data["story_id"] == 2
    assert data["series"] == "Nhà Họ Trần"

    lai = Script.from_dict(json.loads(json.dumps(data)))
    assert lai.story_id == 2
    assert lai.series == "Nhà Họ Trần"


def test_from_dict_kich_ban_cu_khong_co_hai_truong_thi_ve_mac_dinh():
    """Kịch bản dựng trước 25/09 vẫn nạp được, không vỡ."""
    from scripts.models import Script

    lai = Script.from_dict({"trope": "x", "title": "T", "chapters": []})
    assert lai.story_id == 0 and lai.series == ""
