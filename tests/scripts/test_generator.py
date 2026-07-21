# tests/scripts/test_generator.py
from unittest.mock import AsyncMock, MagicMock

from scripts.generator import ScriptGenerationError, generate_script


def _make_fake_client(response_text: str):
    fake_response = MagicMock()
    fake_response.text = response_text
    fake_client = MagicMock()
    fake_client.generate_content = AsyncMock(return_value=fake_response)
    return fake_client


async def test_generate_script_parses_json_response():
    response_text = (
        '{"title": "Ký ức không thể xoá", "chapters": ['
        + ", ".join(
            f'{{"heading": "Chương {i}", "text": "Nội dung chương {i}."}}'
            for i in range(1, 7)
        )
        + "]}"
    )
    fake_client = _make_fake_client(response_text)

    script = await generate_script(
        trope_id="trong_sinh_bao_thu",
        trope_name="Trọng sinh báo thù",
        trope_description="Mô tả test.",
        client=fake_client,
    )

    assert script.title == "Ký ức không thể xoá"
    assert script.trope == "trong_sinh_bao_thu"
    assert len(script.chapters) == 6
    assert script.chapters[0].index == 1
    assert script.chapters[0].heading == "Chương 1"
    fake_client.generate_content.assert_called_once()


async def test_generate_script_strips_markdown_json_fence():
    response_text = (
        "```json\n"
        '{"title": "T", "chapters": ['
        + ", ".join(f'{{"heading": "C{i}", "text": "Nội dung {i}"}}' for i in range(1, 7))
        + "]}\n```"
    )
    fake_client = _make_fake_client(response_text)

    script = await generate_script("id", "name", "desc", client=fake_client)

    assert script.title == "T"
    assert len(script.chapters) == 6


async def test_generate_script_raises_on_invalid_json():
    fake_client = _make_fake_client("Xin lỗi, tôi không thể giúp việc này.")

    try:
        await generate_script("id", "name", "desc", client=fake_client)
        assert False, "expected ScriptGenerationError"
    except ScriptGenerationError:
        pass


async def test_generate_script_raises_on_missing_fields():
    fake_client = _make_fake_client('{"title": "Thiếu chapters"}')

    try:
        await generate_script("id", "name", "desc", client=fake_client)
        assert False, "expected ScriptGenerationError"
    except ScriptGenerationError:
        pass
