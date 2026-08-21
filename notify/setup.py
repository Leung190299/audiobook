"""Cài đặt bot Telegram: xác thực token, tự dò chat id, ghi vào .env.

    uv run python -m notify.setup

Tự dò chat id để khỏi phải mở getUpdates trong trình duyệt rồi đọc JSON bằng mắt —
đó là bước hay sai nhất trong cả khâu cài đặt.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
API = "https://api.telegram.org/bot{token}/{method}"


class SetupError(Exception):
    pass


def set_env_value(content: str, key: str, value: str) -> str:
    """Đặt KEY=value trong nội dung .env, giữ nguyên mọi dòng khác.

    Sửa tại chỗ nếu key đã có (kể cả đang để trống), thêm vào cuối nếu chưa có.
    Không dùng thư viện ngoài để tránh làm xáo trộn thứ tự dòng và comment.
    """
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(f"{key}={value}", content, count=1)

    separator = "" if content.endswith("\n") or not content else "\n"
    return f"{content}{separator}{key}={value}\n"


def _call(token: str, method: str, params: dict | None = None) -> dict:
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code == 401:
            raise SetupError("Token sai — kiểm tra lại chuỗi @BotFather đưa cho bạn.") from exc
        raise SetupError(f"Telegram trả lỗi HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SetupError(f"Không gọi được Telegram API: {exc}") from exc


def verify_token(token: str) -> str:
    """Trả về username của bot nếu token hợp lệ."""
    body = _call(token, "getMe")
    if not body.get("ok"):
        raise SetupError(f"Token không hợp lệ: {body}")
    return body["result"]["username"]


def detect_chat_id(token: str) -> tuple[str, str]:
    """Dò chat id từ tin nhắn gần nhất người dùng gửi cho bot.

    Trả về (chat_id, tên người gửi). Ném SetupError nếu chưa có tin nào —
    bot Telegram không được phép nhắn trước cho người chưa từng nhắn nó.
    """
    body = _call(token, "getUpdates")
    if not body.get("ok"):
        raise SetupError(f"getUpdates thất bại: {body}")

    updates = body.get("result", [])
    chats = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post")
        if not message:
            continue
        chat = message.get("chat", {})
        if "id" in chat:
            name = chat.get("username") or chat.get("first_name") or chat.get("title") or "?"
            chats[str(chat["id"])] = name

    if not chats:
        raise SetupError(
            "Chưa thấy tin nhắn nào gửi tới bot. Mở Telegram, tìm bot vừa tạo, "
            "bấm Start rồi nhắn một tin bất kỳ, sau đó chạy lại lệnh này."
        )

    if len(chats) > 1:
        listing = "\n".join(f"  {cid}  ({name})" for cid, name in chats.items())
        raise SetupError(
            f"Có nhiều hơn một cuộc trò chuyện với bot:\n{listing}\n"
            "Điền thủ công TELEGRAM_CHAT_ID vào .env bằng id bạn muốn nhận thông báo."
        )

    chat_id, name = next(iter(chats.items()))
    return chat_id, name


def main() -> None:
    print("=== Cài đặt thông báo Telegram ===\n")
    print("1. Mở Telegram, nhắn cho @BotFather:  /newbot")
    print("2. Đặt tên và username cho bot, BotFather sẽ đưa lại một token")
    print("3. Tìm bot vừa tạo, bấm Start và nhắn cho nó một tin bất kỳ\n")

    token = input("Dán token vào đây: ").strip()
    if not token:
        print("Không có token, dừng lại.", file=sys.stderr)
        raise SystemExit(1)

    try:
        username = verify_token(token)
        print(f"✅ Token hợp lệ — bot @{username}")

        chat_id, name = detect_chat_id(token)
        print(f"✅ Tìm thấy chat id: {chat_id} ({name})")

        _call(token, "sendMessage", {"chat_id": chat_id, "text": "🔧 Cài đặt xong. Từ giờ tôi sẽ báo cho bạn mỗi khi tập truyện lên sóng."})
        print("✅ Đã gửi tin thử — kiểm tra Telegram xem nhận được chưa")
    except SetupError as exc:
        print(f"\n❌ {exc}", file=sys.stderr)
        raise SystemExit(1)

    content = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    content = set_env_value(content, "TELEGRAM_BOT_TOKEN", token)
    content = set_env_value(content, "TELEGRAM_CHAT_ID", chat_id)
    ENV_PATH.write_text(content, encoding="utf-8")
    ENV_PATH.chmod(0o600)

    print(f"\n✅ Đã ghi vào {ENV_PATH.name} (quyền 600 — chỉ bạn đọc được)")


if __name__ == "__main__":
    main()
