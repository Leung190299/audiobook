"""Chọn kênh gửi thông báo.

Mặc định `auto`: có cấu hình Telegram thì dùng Telegram (nhận được cả khi không ngồi
trước máy), không thì hiện thông báo macOS. Ép cứng bằng NOTIFY_CHANNEL trong .env.
"""

from __future__ import annotations

import os
import sys

AUTO = "auto"
MACOS = "macos"
TELEGRAM = "telegram"
NONE = "none"
CHANNELS = (AUTO, MACOS, TELEGRAM, NONE)


def resolve_channel(channel: str | None = None) -> str:
    channel = (channel or os.getenv("NOTIFY_CHANNEL") or AUTO).strip().lower()
    if channel not in CHANNELS:
        print(
            f"[notify] NOTIFY_CHANNEL='{channel}' không hợp lệ "
            f"(chọn một trong {', '.join(CHANNELS)}); dùng '{AUTO}'.",
            file=sys.stderr,
        )
        channel = AUTO

    if channel != AUTO:
        return channel

    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        return TELEGRAM
    return MACOS


def notify(title: str, message: str, subtitle: str = "", channel: str | None = None) -> bool:
    """Gửi thông báo, trả về True nếu gửi được.

    Không bao giờ ném lỗi ra ngoài: thông báo hỏng không được phép làm hỏng một lượt
    chạy đã dựng xong video.
    """
    resolved = resolve_channel(channel)

    if resolved == NONE:
        return False

    if resolved == TELEGRAM:
        from notify.telegram import TelegramError, send_message

        body = f"<b>{title}</b>"
        if subtitle:
            body += f"\n{subtitle}"
        body += f"\n\n{message}"
        try:
            send_message(body)
            return True
        except TelegramError as exc:
            print(f"[notify] Telegram lỗi: {exc}", file=sys.stderr)
            return False

    from notify.macos import MacNotifyError, send_notification

    try:
        send_notification(title, message, subtitle)
        return True
    except MacNotifyError as exc:
        print(f"[notify] Thông báo macOS lỗi: {exc}", file=sys.stderr)
        return False
