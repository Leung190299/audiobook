# tests/scripts/test_generator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from gemini_webapi.exceptions import APIError

from scripts.generator import ScriptGenerationError, generate_script


def _outline_json(num_chapters: int) -> str:
    chapters = ", ".join(
        f'{{"heading": "Chương {i}", "summary": "Tóm tắt chương {i}."}}'
        for i in range(1, num_chapters + 1)
    )
    return f'{{"title": "Tiêu đề test", "chapters": [{chapters}]}}'


def _make_fake_client(outline_text: str, chapter_texts: list[str]):
    responses = [MagicMock(text=outline_text)] + [MagicMock(text=t) for t in chapter_texts]
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(side_effect=responses)
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat
    return fake_client, fake_chat


async def test_generate_script_builds_script_from_outline_and_chapters():
    outline_text = _outline_json(8)
    chapter_texts = [f"Nội dung đầy đủ chương {i}." for i in range(1, 9)]
    fake_client, fake_chat = _make_fake_client(outline_text, chapter_texts)

    script = await generate_script(
        trope_id="trong_sinh_bao_thu",
        trope_name="Trọng sinh báo thù",
        trope_description="Mô tả test.",
        client=fake_client,
    )

    assert script.title == "Tiêu đề test"
    assert script.trope == "trong_sinh_bao_thu"
    assert len(script.chapters) == 8
    assert script.chapters[0].index == 1
    assert script.chapters[0].heading == "Chương 1"
    assert script.chapters[0].text == "Nội dung đầy đủ chương 1."
    assert script.chapters[7].index == 8
    assert script.chapters[7].heading == "Chương 8"
    assert fake_chat.send_message.call_count == 9  # 1 outline + 8 chapters
    fake_client.start_chat.assert_called_once()


async def test_generate_script_strips_markdown_fence_from_outline():
    outline_text = "```json\n" + _outline_json(2) + "\n```"
    chapter_texts = ["Nội dung chương 1.", "Nội dung chương 2."]
    fake_client, _ = _make_fake_client(outline_text, chapter_texts)

    script = await generate_script("id", "name", "desc", client=fake_client)

    assert script.title == "Tiêu đề test"
    assert len(script.chapters) == 2


async def test_generate_script_raises_on_invalid_outline_json():
    fake_client, _ = _make_fake_client("Xin lỗi, tôi không thể giúp việc này.", [])

    with pytest.raises(ScriptGenerationError):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_raises_on_missing_outline_fields():
    fake_client, _ = _make_fake_client('{"title": "Thiếu chapters"}', [])

    with pytest.raises(ScriptGenerationError):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_error_includes_raw_response_on_structure_mismatch():
    fake_client, _ = _make_fake_client(
        '{"title": "T", "chapters": [["not", "a dict"]]}', []
    )

    with pytest.raises(ScriptGenerationError, match="Phản hồi thô"):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_wraps_api_error_from_outline():
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(side_effect=APIError("boom"))
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat

    with pytest.raises(ScriptGenerationError, match="dàn ý"):
        await generate_script("id", "name", "desc", client=fake_client)


async def test_generate_script_wraps_api_error_from_chapter():
    outline_text = _outline_json(2)
    fake_chat = MagicMock()
    fake_chat.send_message = AsyncMock(
        side_effect=[MagicMock(text=outline_text), APIError("boom mid-chapter")]
    )
    fake_client = MagicMock()
    fake_client.start_chat.return_value = fake_chat

    with pytest.raises(ScriptGenerationError, match="chương 1"):
        await generate_script("id", "name", "desc", client=fake_client)
