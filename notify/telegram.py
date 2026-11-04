"""Thông báo Telegram — dùng urllib để không thêm dependency mới."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_CHARS = 4096


class TelegramError(Exception):
    pass


def send_message(text: str, token: str | None = None, chat_id: str | None = None) -> None:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise TelegramError(
            "Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env — "
            "xem docs/DAILY_AUTOMATION.md để lấy hai giá trị này."
        )

    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text[:MAX_MESSAGE_CHARS],
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        }
    ).encode("utf-8")

    request = urllib.request.Request(API_URL.format(token=token), data=payload)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise TelegramError(
            f"Telegram trả lỗi HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}"
        ) from exc
    except urllib.error.URLError as exc:
        raise TelegramError(f"Không gọi được Telegram API: {exc}") from exc

    if not body.get("ok"):
        raise TelegramError(f"Telegram từ chối tin nhắn: {body}")
