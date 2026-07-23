# tests/thumbnail/test_prompt_generator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.models import Chapter, Script
from thumbnail.prompt_generator import ThumbnailPromptError, generate_thumbnail_prompt


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


async def test_generate_thumbnail_prompt_parses_both_labels():
    response_text = (
        "HOOK: SỐC NẶNG\n"
        "VISUAL: a young man with a shocked expression, dramatic backlighting"
    )
    fake_client = _make_fake_client(response_text)

    prompt = await generate_thumbnail_prompt(_sample_script(), client=fake_client)

    assert prompt.hook_text == "SỐC NẶNG"
    assert prompt.visual_description == (
        "a young man with a shocked expression, dramatic backlighting"
    )
    fake_client.generate_content.assert_called_once()


async def test_generate_thumbnail_prompt_raises_on_missing_label():
    fake_client = _make_fake_client("HOOK: Chỉ có hook\n")

    with pytest.raises(ThumbnailPromptError, match="VISUAL"):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_raises_on_empty_label_value():
    fake_client = _make_fake_client("HOOK: \nVISUAL: a scene")

    with pytest.raises(ThumbnailPromptError):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(ThumbnailPromptError):
        await generate_thumbnail_prompt(_sample_script(), client=fake_client)


async def test_generate_thumbnail_prompt_ignores_embedded_label_substring():
    response_text = (
        "HOOK: PHẢN ĐÒN\n"
        "VISUAL: a scene mentioning HOOK: not a real label, dramatic lighting"
    )
    fake_client = _make_fake_client(response_text)

    prompt = await generate_thumbnail_prompt(_sample_script(), client=fake_client)

    assert prompt.hook_text == "PHẢN ĐÒN"
    assert prompt.visual_description == (
        "a scene mentioning HOOK: not a real label, dramatic lighting"
    )
