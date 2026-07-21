from unittest.mock import MagicMock

import pytest

from scripts.generator import ScriptGenerationError, generate_script


def test_generate_script_parses_tool_use_response():
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.input = {
        "title": "Ký ức không thể xoá",
        "chapters": [
            {"heading": f"Chương {i}", "text": "Nội dung." * 50} for i in range(1, 7)
        ],
    }
    fake_response = MagicMock()
    fake_response.content = [fake_block]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    script = generate_script(
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
    fake_client.messages.create.assert_called_once()


def test_generate_script_raises_when_no_tool_use_block():
    fake_response = MagicMock()
    fake_response.content = []
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with pytest.raises(ScriptGenerationError):
        generate_script("id", "name", "desc", client=fake_client)
