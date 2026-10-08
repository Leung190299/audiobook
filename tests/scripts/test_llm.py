# tests/scripts/test_llm.py
from types import SimpleNamespace

import pytest

from scripts import llm
from scripts.generator import _parse_json_response


class _Stream:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self._response


def _fake_client(responses):
    calls = []

    def stream(**kwargs):
        calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return _Stream(responses.pop(0))

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    return client, calls


def _resp(text, stop="end_turn"):
    content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(stop_reason=stop, content=content)


async def test_chat_giu_ca_hoi_thoai_va_khoi_suy_nghi():
    client, calls = _fake_client([_resp("dàn ý"), _resp("chương 1")])
    chat = llm.ClaudeChat(client, "claude-opus-5-5", "high")

    assert (await chat.send_message("viết dàn ý")).text == "dàn ý"
    assert (await chat.send_message("viết chương 1")).text == "chương 1"

    second = calls[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert any(b.type == "thinking" for b in second[1]["content"]), "giữ nguyên content, cả khối suy nghĩ"
    assert calls[0]["model"] == "claude-opus-5-5"
    assert calls[0]["output_config"] == {"effort": "high"}
    assert calls[0]["fallbacks"] == "default" and llm.FALLBACK_BETA in calls[0]["betas"]
    assert calls[0]["cache_control"] == {"type": "ephemeral"}


async def test_bi_tu_choi_thi_tra_rong_va_khong_giu_luot_do():
    client, calls = _fake_client([_resp("", stop="refusal"), _resp("chương 1")])
    chat = llm.ClaudeChat(client, "m", "high")

    assert (await chat.send_message("viết chương 1")).text == ""
    await chat.send_message("viết chương 1")
    assert [m["role"] for m in calls[1]["messages"]] == ["user"]


@pytest.mark.parametrize(
    ("env", "explicit", "expected"),
    [
        ({"ANTHROPIC_API_KEY": "k"}, None, "claude"),
        ({}, None, "gemini"),
        ({"ANTHROPIC_API_KEY": "k", "STORY_LLM": "gemini"}, None, "gemini"),
        ({"STORY_LLM": "gemini"}, "claude", "claude"),
    ],
)
def test_chon_mo_hinh(monkeypatch, env, explicit, expected):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("STORY_LLM", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert llm.resolve_provider(explicit) == expected


def test_ten_mo_hinh_sai_thi_bao_loi(monkeypatch):
    monkeypatch.setenv("STORY_LLM", "gpt")
    with pytest.raises(ValueError, match="STORY_LLM"):
        llm.resolve_provider()


def test_json_co_cau_dan_phia_truoc():
    raw = 'Đây là dàn ý:\n```json\n{"title": "A", "chapters": []}\n```'
    assert _parse_json_response(raw) == {"title": "A", "chapters": []}


def test_claude_doc_cham_hon_nen_it_tu_hon(monkeypatch):
    from scripts.prompts import full_chapter_words_range, full_words_range

    gemini = full_words_range()
    monkeypatch.setenv("STORY_LLM", "claude")
    claude = full_words_range()
    assert claude[0] < gemini[0] and claude[1] < gemini[1]
    assert full_chapter_words_range() == (530, 670)
