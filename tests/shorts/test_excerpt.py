# tests/shorts/test_excerpt.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.models import Chapter, Script
from shorts.excerpt import (
    ShortExcerptError,
    build_excerpt_prompt,
    generate_short_excerpt,
    split_sentences,
)


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


def _sample_script() -> Script:
    return Script(
        trope="trong_sinh_bao_thu",
        title="Trọng Sinh Báo Thù",
        chapters=[
            Chapter(index=1, heading="Chương 1: Mở đầu", text="Câu chuyện bắt đầu."),
            Chapter(index=2, heading="Chương 2: Cao trào", text="Mọi thứ vỡ vụn."),
        ],
    )


def _excerpt_of(word_count: int) -> str:
    return " ".join(["từ"] * word_count)


def _response(chapter: str = "2", excerpt_words: int = 150) -> str:
    return (
        f"CHAPTER: {chapter}\n"
        "HOOK: CÔ ẤY BIẾT HẾT RỒI\n"
        f"EXCERPT: {_excerpt_of(excerpt_words)}\n"
        "TITLE: Trọng sinh báo thù - đoạn gay cấn nhất\n"
        "DESCRIPTION: Nghe full trên kênh nhé. #shorts"
    )


async def test_parse_day_du_nam_nhan():
    client = _make_fake_client(_response())

    excerpt = await generate_short_excerpt(_sample_script(), client=client)

    assert excerpt.chapter_index == 2
    assert excerpt.hook_text == "CÔ ẤY BIẾT HẾT RỒI"
    assert len(excerpt.excerpt_text.split()) == 150
    assert excerpt.short_title == "Trọng sinh báo thù - đoạn gay cấn nhất"
    assert excerpt.short_description == "Nghe full trên kênh nhé. #shorts"


async def test_thieu_nhan_thi_bao_loi():
    client = _make_fake_client("HOOK: CHỈ CÓ HOOK THÔI")

    with pytest.raises(ShortExcerptError, match="CHAPTER"):
        await generate_short_excerpt(_sample_script(), client=client)


async def test_chapter_ngoai_pham_vi_thi_bao_loi():
    client = _make_fake_client(_response(chapter="9"))

    with pytest.raises(ShortExcerptError, match="chương 9"):
        await generate_short_excerpt(_sample_script(), client=client)


async def test_chapter_khong_phai_so_thi_bao_loi():
    client = _make_fake_client(_response(chapter="chương hai"))

    with pytest.raises(ShortExcerptError, match="số chương"):
        await generate_short_excerpt(_sample_script(), client=client)


@pytest.mark.parametrize("word_count", [119, 321])
async def test_doan_trich_sai_do_dai_thi_bao_loi(word_count):
    client = _make_fake_client(_response(excerpt_words=word_count))

    with pytest.raises(ShortExcerptError, match="120-320"):
        await generate_short_excerpt(_sample_script(), client=client)

    assert client.generate_content.await_count == 2


async def test_doan_trich_sai_do_dai_lan_dau_thu_lai_thanh_cong():
    lan_dau = MagicMock()
    lan_dau.text = _response(excerpt_words=400)
    lan_hai = MagicMock()
    lan_hai.text = _response(excerpt_words=150)

    client = MagicMock()
    client.generate_content = AsyncMock(side_effect=[lan_dau, lan_hai])

    excerpt = await generate_short_excerpt(_sample_script(), client=client)

    assert len(excerpt.excerpt_text.split()) == 150
    assert client.generate_content.await_count == 2


async def test_thieu_nhan_thi_khong_thu_lai():
    client = _make_fake_client("HOOK: CHỈ CÓ HOOK THÔI")

    with pytest.raises(ShortExcerptError, match="CHAPTER"):
        await generate_short_excerpt(_sample_script(), client=client)

    assert client.generate_content.await_count == 1


async def test_gemini_loi_thi_boc_thanh_loi_cua_module():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("hỏng"))

    with pytest.raises(ShortExcerptError, match="Gemini"):
        await generate_short_excerpt(_sample_script(), client=fake_client)


def test_prompt_chua_noi_dung_tung_chuong():
    prompt = build_excerpt_prompt(_sample_script())

    assert "Câu chuyện bắt đầu." in prompt
    assert "Mọi thứ vỡ vụn." in prompt
    assert "[Chương 2]" in prompt


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
