from unittest.mock import MagicMock

import pytest

from scripts.generator import ScriptGenerationError, generate_script


def _stream_client_returning(fake_response):
    fake_client = MagicMock()
    fake_stream_cm = MagicMock()
    fake_stream_cm.__enter__.return_value.get_final_message.return_value = fake_response
    fake_client.messages.stream.return_value = fake_stream_cm
    return fake_client


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
    fake_response.stop_reason = "tool_use"

    fake_client = _stream_client_returning(fake_response)

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
    fake_client.messages.stream.assert_called_once()


def test_generate_script_raises_when_no_tool_use_block():
    fake_response = MagicMock()
    fake_response.content = []
    fake_response.stop_reason = "end_turn"
    fake_client = _stream_client_returning(fake_response)

    with pytest.raises(ScriptGenerationError):
        generate_script("id", "name", "desc", client=fake_client)


def test_generate_script_raises_when_truncated_by_max_tokens():
    fake_response = MagicMock()
    fake_response.content = []
    fake_response.stop_reason = "max_tokens"
    fake_client = _stream_client_returning(fake_response)

    with pytest.raises(ScriptGenerationError, match="max_tokens"):
        generate_script("id", "name", "desc", client=fake_client)


def test_generate_script_raises_on_malformed_tool_input():
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.input = {"title": "Thiếu chapters"}
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "tool_use"
    fake_client = _stream_client_returning(fake_response)

    with pytest.raises(ScriptGenerationError):
        generate_script("id", "name", "desc", client=fake_client)
