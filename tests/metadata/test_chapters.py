import pytest

from metadata.chapters import build_chapter_lines


def test_build_chapter_lines_formats_mm_ss():
    tts_metadata = {
        "chapters": [
            {"index": 1, "heading": "Chương 1: Mở đầu", "start_seconds": 0.0, "end_seconds": 190.5},
            {"index": 2, "heading": "Chương 2: Biến cố", "start_seconds": 190.5, "end_seconds": 380.0},
        ]
    }

    lines = build_chapter_lines(tts_metadata)

    assert lines == ["0:00 Chương 1: Mở đầu", "3:10 Chương 2: Biến cố"]


def test_build_chapter_lines_sorts_by_index():
    tts_metadata = {
        "chapters": [
            {"index": 2, "heading": "Chương 2", "start_seconds": 100.0, "end_seconds": 200.0},
            {"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 100.0},
        ]
    }

    lines = build_chapter_lines(tts_metadata)

    assert lines[0].endswith("Chương 1")
    assert lines[1].endswith("Chương 2")


def test_build_chapter_lines_uses_h_mm_ss_after_one_hour():
    tts_metadata = {
        "chapters": [
            {"index": 1, "heading": "Chương 1", "start_seconds": 0.0, "end_seconds": 3600.0},
            {"index": 2, "heading": "Chương 2", "start_seconds": 3725.0, "end_seconds": 3800.0},
        ]
    }

    lines = build_chapter_lines(tts_metadata)

    assert lines[1] == "1:02:05 Chương 2"


def test_build_chapter_lines_warns_if_first_chapter_not_zero():
    tts_metadata = {
        "chapters": [
            {"index": 1, "heading": "Chương 1", "start_seconds": 5.0, "end_seconds": 100.0},
        ]
    }

    with pytest.warns(UserWarning, match="0:00"):
        build_chapter_lines(tts_metadata)
