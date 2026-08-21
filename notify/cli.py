"""Gửi thông báo từ shell script.

    uv run python -m notify.cli success --title "..." --video "..." --slug "..." --duration "42m"
    uv run python -m notify.cli failure --stage "Stage 3" --log "..." --detail-file "..."
    uv run python -m notify.cli text --text "..."

Kênh gửi do NOTIFY_CHANNEL quyết định (auto | macos | telegram | none), mặc định auto:
có cấu hình Telegram thì dùng Telegram, không thì hiện thông báo macOS.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from notify.dispatch import notify

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gửi thông báo khi pipeline xong hoặc lỗi.")
    parser.add_argument(
        "--channel", default=None, help="auto | macos | telegram | none (mặc định lấy từ .env)"
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    ok = sub.add_parser("success")
    ok.add_argument("--title", required=True, help="Tiêu đề truyện")
    ok.add_argument("--video", default="", help="Đường dẫn file video đã dựng xong")
    ok.add_argument("--slug", default="")
    ok.add_argument("--duration", default="")
    ok.add_argument("--url", default="", help="Link YouTube nếu có upload")

    fail = sub.add_parser("failure")
    fail.add_argument("--stage", required=True)
    fail.add_argument("--log", default="")
    fail.add_argument("--detail-file", type=Path, default=None)

    raw = sub.add_parser("text")
    raw.add_argument("--text", required=True)

    args = parser.parse_args()

    if args.mode == "success":
        title = "✅ Tập truyện hôm nay đã xong"
        subtitle = args.title
        parts = []
        if args.url:
            parts.append(args.url)
        elif args.video:
            # Chỉ hiện tên file: thông báo macOS rất hẹp, đường dẫn đầy đủ bị cắt mất đuôi.
            parts.append(Path(args.video).name)
        if args.duration:
            parts.append(f"dựng trong {args.duration}")
        message = " · ".join(parts) or "Xem log để biết chi tiết"

    elif args.mode == "failure":
        title = "❌ Pipeline truyện hôm nay lỗi"
        subtitle = f"Hỏng ở {args.stage}"
        detail = ""
        if args.detail_file and args.detail_file.exists():
            detail = args.detail_file.read_text(encoding="utf-8", errors="replace").strip()
            detail = detail.splitlines()[-1] if detail else ""
        message = detail[:200] or f"Xem log: {args.log}"

    else:
        title = "Pipeline truyện audio"
        subtitle = ""
        message = args.text

    if not notify(title, message, subtitle, channel=args.channel):
        # Không thoát khác 0: lượt chạy có thể đã thành công, chỉ mỗi khâu báo hỏng.
        print("[notify] Không gửi được thông báo (xem stderr ở trên).")
        return

    print("Đã gửi thông báo.")


if __name__ == "__main__":
    main()
