# scripts/llm.py
"""Chọn mô hình viết truyện cho stage 1: Claude API hoặc Gemini (cookie web).

    STORY_LLM=claude   # Claude API, cần ANTHROPIC_API_KEY trong .env
    STORY_LLM=gemini   # Gemini web, cần cookie SECURE_1PSID / SECURE_1PSIDTS

Không đặt STORY_LLM thì có ANTHROPIC_API_KEY là dùng Claude, không thì Gemini.
`scripts.cli --llm` ghi đè cả hai.

scripts/generator.py chỉ cần một "phiên chat" có `await send_message(text)`
trả về vật có `.text` -- đúng giao diện chat của gemini_webapi. ClaudeChat bắt
chước giao diện đó nên generator không phải biết đang nói với ai: dàn ý, từng
chương, lượt short_beats đều hỏi trong CÙNG một hội thoại để chương sau nhớ
chương trước.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import anthropic

CLAUDE = "claude"
GEMINI = "gemini"
PROVIDERS = (CLAUDE, GEMINI)

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
# Opus 5.5 mặc định effort "medium"; truyện dài 15 chương cần giữ mạch nhân vật
# và giọng kể nhất quán, nên viết ở "high". STORY_LLM_EFFORT để hạ khi muốn rẻ.
DEFAULT_CLAUDE_EFFORT = "high"
# Một chương ~1.500-2.500 chữ tiếng Việt cộng phần suy nghĩ; stream nên đặt
# trần rộng không lo timeout, chương cụt vì chạm trần còn tệ hơn tốn token.
MAX_TOKENS = 32000
# Khi Opus từ chối (bộ lọc an toàn bắt nhầm truyện gia đình có cãi vã), API tự
# chạy lại trên mô hình dự phòng trong cùng lượt gọi thay vì trả về rỗng.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Chờ (giây) trước mỗi lần thử lại khi mất kết nối / API quá tải. 12/10 09:00:
# máy vừa thức theo lịch, mạng chưa lên, SDK thử lại 2 lần trong 17 giây rồi
# bỏ -- mất nguyên lượt dựng. Tổng ~7 phút đủ cho Wi-Fi kết nối lại.
NETWORK_RETRY_DELAYS = (15, 30, 60, 120, 180)
_RETRYABLE = (anthropic.APIConnectionError, anthropic.InternalServerError, anthropic.RateLimitError)


def resolve_provider(explicit: str | None = None) -> str:
    choice = (explicit or os.getenv("STORY_LLM") or "").strip().lower()
    if not choice:
        return CLAUDE if os.getenv("ANTHROPIC_API_KEY") else GEMINI
    if choice not in PROVIDERS:
        raise ValueError(f"STORY_LLM={choice!r} không hợp lệ; chọn một trong {PROVIDERS}")
    return choice


@dataclass
class Reply:
    text: str


class ClaudeChat:
    """Một hội thoại nhiều lượt với Claude, giao diện như chat của gemini_webapi."""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str, effort: str):
        self._client = client
        self._model = model
        self._effort = effort
        self._messages: list[dict] = []

    async def send_message(self, text: str) -> Reply:
        self._messages.append({"role": "user", "content": text})
        for attempt in range(len(NETWORK_RETRY_DELAYS) + 1):
            try:
                response = await self._ask()
                break
            except _RETRYABLE as exc:
                if attempt == len(NETWORK_RETRY_DELAYS):
                    # Bỏ lượt hỏi treo để hội thoại vẫn hợp lệ nếu ai gọi tiếp.
                    self._messages.pop()
                    raise
                delay = NETWORK_RETRY_DELAYS[attempt]
                print(f"Claude lỗi kết nối ({type(exc).__name__}), thử lại sau {delay}s...", flush=True)
                await asyncio.sleep(delay)

        if response.stop_reason == "refusal":
            # Không giữ lượt bị từ chối trong lịch sử: generator sẽ hỏi lại, và
            # hỏi lại trên nền một lượt từ chối thì dễ bị từ chối tiếp.
            self._messages.pop()
            return Reply("")
        # Giữ NGUYÊN content (cả khối suy nghĩ) chứ không chỉ chữ: Opus 5.5 đọc
        # lại suy nghĩ của chính nó ở lượt sau, và lịch sử phải chỉ nối thêm.
        self._messages.append({"role": "assistant", "content": response.content})
        return Reply("".join(b.text for b in response.content if b.type == "text"))

    async def _ask(self):
        async with self._client.beta.messages.stream(
            model=self._model,
            max_tokens=MAX_TOKENS,
            messages=self._messages,
            output_config={"effort": self._effort},
            # Mỗi lượt gửi lại cả hội thoại (dàn ý + các chương đã viết): cache
            # phần đầu để chương 15 không trả tiền đọc lại 14 chương trước.
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            return await stream.get_final_message()


class ClaudeClient:
    def __init__(self, model: str | None = None, effort: str | None = None):
        self._client = anthropic.AsyncAnthropic()
        self._model = model or os.getenv("STORY_LLM_MODEL") or DEFAULT_CLAUDE_MODEL
        self._effort = effort or os.getenv("STORY_LLM_EFFORT") or DEFAULT_CLAUDE_EFFORT

    def start_chat(self) -> ClaudeChat:
        return ClaudeChat(self._client, self._model, self._effort)


async def make_client(provider: str | None = None):
    """Client có `start_chat()` theo mô hình đã chọn."""
    if resolve_provider(provider) == CLAUDE:
        return ClaudeClient()
    from gemini_webapi import GeminiClient

    client = GeminiClient(os.environ["SECURE_1PSID"], os.environ["SECURE_1PSIDTS"])
    await client.init(timeout=30, auto_close=False, close_delay=300, auto_refresh=True)
    return client
