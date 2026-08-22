# tests/shorts/test_excerpt.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.models import Chapter, Script
from shorts.excerpt import (
    MAX_CHAPTER_WORDS,
    RESERVED_ENDING_CHAPTERS,
    ShortExcerptError,
    build_excerpt_prompt,
    eligible_chapters,
    pick_short_chapter,
    split_sentences,
)


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


def _chapter(index: int, word_count: int, heading: str | None = None) -> Chapter:
    return Chapter(
        index=index,
        heading=heading or f"Chương {index}",
        text=" ".join(["từ"] * word_count),
    )


def _sample_script() -> Script:
    # 4 chương, đều đủ ngắn (<= MAX_CHAPTER_WORDS); chương 4 là chương kết bị loại
    # bởi RESERVED_ENDING_CHAPTERS=2 -> hợp lệ còn 1, 2.
    return Script(
        trope="trong_sinh_bao_thu",
        title="Trọng Sinh Báo Thù",
        chapters=[
            _chapter(1, 50, "Chương 1: Mở đầu"),
            _chapter(2, 60, "Chương 2: Cao trào"),
            _chapter(3, 40, "Chương 3: Áp chót"),
            _chapter(4, 30, "Chương 4: Kết"),
        ],
    )


def _response(chapter: str = "2") -> str:
    return (
        f"CHAPTER: {chapter}\n"
        "HOOK: CÔ ẤY BIẾT HẾT RỒI\n"
        "TITLE: Trọng sinh báo thù - đoạn gay cấn nhất\n"
        "DESCRIPTION: Nghe full trên kênh nhé. #shorts"
    )


async def test_parse_day_du_bon_nhan():
    client = _make_fake_client(_response())

    pick = await pick_short_chapter(_sample_script(), client=client)

    assert pick.chapter_index == 2
    assert pick.hook_text == "CÔ ẤY BIẾT HẾT RỒI"
    assert pick.short_title == "Trọng sinh báo thù - đoạn gay cấn nhất"
    assert pick.short_description == "Nghe full trên kênh nhé. #shorts"


async def test_chapter_text_lay_nguyen_van_tu_kich_ban_khong_phai_tu_gemini():
    # Nội dung đọc phải đến từ text thật của chương trong kịch bản — chứng minh
    # bằng cách khẳng định nó khớp hệt Chapter.text, dù Gemini không hề trả về nó.
    script = _sample_script()
    client = _make_fake_client(_response(chapter="2"))

    pick = await pick_short_chapter(script, client=client)

    expected = next(c for c in script.chapters if c.index == 2).text
    assert pick.chapter_text == expected


async def test_thieu_nhan_thi_bao_loi():
    client = _make_fake_client("HOOK: CHỈ CÓ HOOK THÔI")

    with pytest.raises(ShortExcerptError, match="CHAPTER"):
        await pick_short_chapter(_sample_script(), client=client)


async def test_chapter_ngoai_danh_sach_hop_le_thi_bao_loi():
    client = _make_fake_client(_response(chapter="4"))

    with pytest.raises(ShortExcerptError, match="chương 4"):
        await pick_short_chapter(_sample_script(), client=client)


async def test_chapter_ton_tai_trong_kich_ban_nhung_khong_hop_le_van_bao_loi():
    # Chương 4 tồn tại trong kịch bản (kể cả nằm trong khoảng 1..4) nhưng bị loại
    # vì là chương kết -> vẫn phải báo lỗi, không được chỉ kiểm tra "có trong kịch bản".
    script = _sample_script()
    assert 4 in {c.index for c in script.chapters}
    client = _make_fake_client(_response(chapter="4"))

    with pytest.raises(ShortExcerptError):
        await pick_short_chapter(script, client=client)


async def test_chapter_khong_phai_so_thi_bao_loi():
    client = _make_fake_client(_response(chapter="chương hai"))

    with pytest.raises(ShortExcerptError, match="số chương"):
        await pick_short_chapter(_sample_script(), client=client)


async def test_khong_thu_lai_khi_loi_phan_tich_nhan():
    client = _make_fake_client("HOOK: CHỈ CÓ HOOK THÔI")

    with pytest.raises(ShortExcerptError, match="CHAPTER"):
        await pick_short_chapter(_sample_script(), client=client)

    assert client.generate_content.await_count == 1


async def test_gemini_loi_thi_boc_thanh_loi_cua_module():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("hỏng"))

    with pytest.raises(ShortExcerptError, match="Gemini"):
        await pick_short_chapter(_sample_script(), client=fake_client)

    assert fake_client.generate_content.await_count == 1


def test_prompt_chua_noi_dung_tung_chuong_hop_le():
    prompt = build_excerpt_prompt(_sample_script())

    assert "[Chương 1]" in prompt
    assert "Chương 1: Mở đầu" in prompt
    assert "[Chương 2]" in prompt
    assert "Chương 2: Cao trào" in prompt


def test_prompt_khong_liet_ke_chuong_ket():
    prompt = build_excerpt_prompt(_sample_script())

    assert "[Chương 4]" not in prompt


def test_prompt_bat_buoc_chon_trong_danh_sach_hop_le():
    prompt = build_excerpt_prompt(_sample_script())

    assert "1, 2" in prompt


def test_eligible_chapters_loc_theo_so_tu_va_bo_chuong_ket():
    script = _sample_script()

    eligible = eligible_chapters(script)

    assert [c.index for c in eligible] == [1, 2]


def test_eligible_chapters_loai_chuong_qua_dai():
    script = Script(
        trope="t",
        title="T",
        chapters=[
            _chapter(1, MAX_CHAPTER_WORDS + 1),
            _chapter(2, MAX_CHAPTER_WORDS),
            _chapter(3, 10),
            _chapter(4, 10),
        ],
    )

    eligible = eligible_chapters(script)

    assert [c.index for c in eligible] == [2]


def test_eligible_chapters_rong_thi_bao_loi_neu_khong_chuong_nao_du_ngan():
    script = Script(
        trope="t",
        title="T",
        chapters=[
            _chapter(1, MAX_CHAPTER_WORDS + 100),
            _chapter(2, MAX_CHAPTER_WORDS + 1),
            _chapter(3, 10),
            _chapter(4, 10),
        ],
    )

    with pytest.raises(ShortExcerptError, match=str(MAX_CHAPTER_WORDS + 1)):
        eligible_chapters(script)


def test_eligible_chapters_rong_khi_kich_ban_qua_it_chuong():
    # Chỉ 2 chương -> cả hai đều là chương kết theo RESERVED_ENDING_CHAPTERS=2,
    # không còn chương nào để xét -> phải báo lỗi, không được âm thầm quay lại
    # dùng chương kết.
    script = Script(
        trope="t",
        title="T",
        chapters=[_chapter(1, 10), _chapter(2, 10)],
    )

    with pytest.raises(ShortExcerptError, match="không đủ"):
        eligible_chapters(script)


def test_reserved_ending_chapters_la_hai():
    assert RESERVED_ENDING_CHAPTERS == 2


def test_tach_cau_theo_dau_ket_cau():
    assert split_sentences("Cô ấy đến. Trời mưa! Anh biết chứ?") == [
        "Cô ấy đến.",
        "Trời mưa!",
        "Anh biết chứ?",
    ]


def test_cau_ngan_giu_tach_biet():
    assert split_sentences("Không. Dừng lại. Sao?") == [
        "Không.",
        "Dừng lại.",
        "Sao?",
    ]


def test_tach_cau_chuoi_rong():
    assert split_sentences("   ") == []
