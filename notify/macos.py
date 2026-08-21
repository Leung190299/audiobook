"""Thông báo trên màn hình macOS qua osascript — không cần cài gì thêm.

launchd chạy job này trong phiên đăng nhập của người dùng nên osascript hiển thị
được thông báo bình thường. Nếu chạy qua ssh hoặc trong ngữ cảnh không có giao
diện thì osascript sẽ lỗi — bắt lỗi và coi như không gửi được, chứ không làm
hỏng lượt chạy đã thành công.
"""

from __future__ import annotations

import subprocess


class MacNotifyError(Exception):
    pass


def _escape(text: str) -> str:
    """Chuỗi AppleScript: chỉ cần thoát dấu ngoặc kép và dấu chéo ngược."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_notification(title: str, message: str, subtitle: str = "", sound: str = "Glass") -> None:
    script = (
        f'display notification "{_escape(message)}" '
        f'with title "{_escape(title)}"'
    )
    if subtitle:
        script += f' subtitle "{_escape(subtitle)}"'
    if sound:
        script += f' sound name "{_escape(sound)}"'

    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=15
        )
    except FileNotFoundError as exc:
        raise MacNotifyError("Không tìm thấy osascript — máy này không phải macOS?") from exc
    except subprocess.TimeoutExpired as exc:
        raise MacNotifyError("osascript treo quá 15 giây") from exc

    if result.returncode != 0:
        raise MacNotifyError(f"osascript lỗi: {result.stderr.strip() or result.returncode}")
