from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from metadata.seo_generator import SeoGenerationError, generate_seo_copy
from scripts.models import Chapter, Script


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


def _sample_script() -> Script:
    return Script(
        trope="phe_vat_nghich_tap",
        title="Kẻ Phế Vật Mang Linh Hồn Thần Cổ",
        chapters=[
            Chapter(index=1, heading="Chương 1: Phế Vật Họ Lâm", text="..."),
            Chapter(index=2, heading="Chương 2: Biến Cố", text="..."),
        ],
    )


async def test_generate_seo_copy_parses_all_labels():
    response_text = (
        "TITLE: Kẻ Phế Vật Trở Lại Báo Thù | Truyện Audio Hay Nhất 2026\n"
        "DESCRIPTION: Một câu chuyện về sự trở lại đầy bất ngờ...\n"
        "TAGS: truyện audio, phế vật nghịch tập, trọng sinh, audio truyện đêm khuya\n"
        "HASHTAGS: #truyenaudio #phevatnghichtap"
    )
    fake_client = _make_fake_client(response_text)

    seo_copy = await generate_seo_copy(_sample_script(), client=fake_client)

    assert seo_copy.title == "Kẻ Phế Vật Trở Lại Báo Thù | Truyện Audio Hay Nhất 2026"
    assert seo_copy.description_draft == "Một câu chuyện về sự trở lại đầy bất ngờ..."
    assert seo_copy.tags == [
        "truyện audio", "phế vật nghịch tập", "trọng sinh", "audio truyện đêm khuya"
    ]
    assert seo_copy.hashtags == ["#truyenaudio", "#phevatnghichtap"]
    fake_client.generate_content.assert_called_once()


async def test_generate_seo_copy_raises_on_missing_label():
    fake_client = _make_fake_client("TITLE: Chỉ có tiêu đề\nDESCRIPTION: Có mô tả\n")

    with pytest.raises(SeoGenerationError, match="TAGS"):
        await generate_seo_copy(_sample_script(), client=fake_client)


async def test_generate_seo_copy_raises_on_empty_label_value():
    fake_client = _make_fake_client(
        "TITLE: \nDESCRIPTION: mô tả\nTAGS: a, b\nHASHTAGS: #a #b"
    )

    with pytest.raises(SeoGenerationError):
        await generate_seo_copy(_sample_script(), client=fake_client)


async def test_generate_seo_copy_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(SeoGenerationError):
        await generate_seo_copy(_sample_script(), client=fake_client)


async def test_generate_seo_copy_ignores_embedded_label_substring_in_description():
    response_text = (
        "TITLE: Video hay\n"
        "DESCRIPTION: Xem thêm TAGS: linh tinh không phải nhãn thật\n"
        "TAGS: truyen, audio\n"
        "HASHTAGS: #a #b"
    )
    fake_client = _make_fake_client(response_text)

    seo_copy = await generate_seo_copy(_sample_script(), client=fake_client)

    assert seo_copy.tags == ["truyen", "audio"]
    assert (
        seo_copy.description_draft
        == "Xem thêm TAGS: linh tinh không phải nhãn thật"
    )
