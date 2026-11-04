"""Kiểm tra cấu hình trước khi bật lịch chạy tự động.

    uv run python -m preflight.cli           # kiểm tra nhanh, không gọi mạng
    uv run python -m preflight.cli --deep    # gọi thật YouTube API + gửi tin Telegram thử
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from preflight.checks import FAIL, format_report, run_all, summarize

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kiểm tra pipeline đã đủ điều kiện chạy tự động chưa."
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Gọi thật YouTube API và gửi một tin Telegram thử (chậm hơn, chính xác hơn)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Kiểm cả phần đăng YouTube (mặc định bỏ qua vì pipeline chỉ dựng video)",
    )
    args = parser.parse_args()

    # Nạp .env trước khi check, vì phần lớn check đọc biến môi trường.
    load_dotenv(ROOT / ".env")

    checks = run_all(ROOT, deep=args.deep, upload=args.upload)
    print(format_report(checks))

    ok, warn, fail = summarize(checks)
    print(f"\n{ok} đạt, {warn} cảnh báo, {fail} lỗi.")

    if fail:
        print("\nCòn lỗi ở trên — sửa xong hãy bật lịch, đừng để lượt chạy 1 tiếng hỏng giữa chừng.")
        raise SystemExit(1)

    if not args.deep:
        print("\nMẹo: chạy lại với --deep để thử thật token YouTube và bot Telegram.")

    print("\nSẵn sàng. Chạy thử trọn lượt: ./run_daily.sh")


if __name__ == "__main__":
    main()
