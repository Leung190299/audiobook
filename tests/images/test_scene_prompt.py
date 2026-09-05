from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from images.scene_prompt import (
    ScenePromptError,
    build_scene_prompt_request,
    generate_scene_description,
)


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


async def test_generate_scene_description_returns_cleaned_text():
    fake_client = _make_fake_client('"cozy living room at dusk"')

    description = await generate_scene_description(
        1, 1, "Nội dung cảnh một.", client=fake_client
    )

    assert description == "cozy living room at dusk"
    fake_client.generate_content.assert_called_once()
    request = fake_client.generate_content.call_args.args[0]
    assert "Nội dung cảnh một." in request


async def test_generate_scene_description_raises_on_empty_response():
    fake_client = _make_fake_client("   ")

    with pytest.raises(ScenePromptError, match="chương 2 cảnh 3"):
        await generate_scene_description(2, 3, "Nội dung.", client=fake_client)


async def test_generate_scene_description_wraps_api_error():
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(side_effect=APIError("boom"))

    with pytest.raises(ScenePromptError, match="chương 3 cảnh 1"):
        await generate_scene_description(3, 1, "Nội dung.", client=fake_client)


def test_build_scene_prompt_request_ep_mot_dia_diem_va_canh_trong():
    """Mỗi quy tắc ở đây chặn một lỗi đã thấy trên ảnh thật: gộp hai địa điểm
    bằng 'transitions into', và đám đông mặt người méo vì FLUX không có negative
    prompt."""
    request = build_scene_prompt_request("Nội dung chương.")

    assert "Nội dung chương." in request
    assert "ĐÚNG MỘT địa điểm" in request
    assert "transitions" in request
    assert "không có người" in request
    assert "tối đa 30 từ" in request
