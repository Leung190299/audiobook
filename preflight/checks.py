"""Kiểm tra điều kiện chạy trước khi bật lịch tự động.

Mục đích: bắt lỗi cấu hình trong 10 giây thay vì để lượt chạy hỏng ở phút thứ 50
(stage 7 hỏng vì token hết hạn là tốn nhất — cả tiếng render coi như phí).

Mỗi check trả về một `Check`. Check nào cần gọi mạng thì chỉ chạy khi `deep=True`.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

OK = "ok"
WARN = "warn"
FAIL = "fail"

# Một tập chiếm ~900MB video + ~300MB audio/ảnh trung gian. Dưới 20GB là sắp kẹt.
MIN_FREE_GB = 20
WARN_FREE_GB = 50


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""

    @property
    def icon(self) -> str:
        return {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}[self.status]


def check_env_file(root: Path) -> Check:
    env_path = root / ".env"
    if not env_path.exists():
        return Check(
            ".env tồn tại",
            FAIL,
            "Không tìm thấy .env",
            "cp .env.example .env rồi điền cookie Gemini",
        )
    return Check(".env tồn tại", OK, str(env_path))


def check_gemini_cookies() -> Check:
    missing = [k for k in ("SECURE_1PSID", "SECURE_1PSIDTS") if not os.getenv(k)]
    if missing:
        return Check(
            "Cookie Gemini",
            FAIL,
            f"Thiếu: {', '.join(missing)}",
            "Lấy lại cookie từ trình duyệt đã đăng nhập gemini.google.com, điền vào .env. "
            "Thiếu cái này thì stage 1 và 3 crash ngay với KeyError.",
        )
    return Check("Cookie Gemini", OK, "đã có SECURE_1PSID và SECURE_1PSIDTS")


def check_youtube_client_secret(root: Path) -> Check:
    path = root / "config" / "youtube_client_secret.json"
    if not path.exists():
        return Check(
            "OAuth client YouTube",
            FAIL,
            f"Không tìm thấy {path.name}",
            "Tạo OAuth client loại Desktop app trong Google Cloud Console, "
            "tải JSON về config/youtube_client_secret.json (xem docs/DAILY_AUTOMATION.md)",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Check("OAuth client YouTube", FAIL, f"File JSON hỏng: {exc}", "Tải lại từ Cloud Console")

    if "installed" not in data:
        return Check(
            "OAuth client YouTube",
            FAIL,
            "JSON không phải loại Desktop app (thiếu khoá 'installed')",
            "Tạo lại credential với Application type = Desktop app, không phải Web application",
        )
    return Check("OAuth client YouTube", OK, path.name)


def check_youtube_token(root: Path, deep: bool) -> Check:
    path = root / "config" / "youtube_token.json"
    if not path.exists():
        return Check(
            "Token YouTube",
            FAIL,
            "Chưa cấp quyền lần nào",
            "Chạy `uv run python -m upload.auth` một lần trên máy có trình duyệt",
        )

    if not deep:
        return Check("Token YouTube", OK, f"{path.name} tồn tại (dùng --deep để thử refresh thật)")

    try:
        from upload.auth import load_credentials

        credentials = load_credentials()
    except Exception as exc:
        return Check(
            "Token YouTube",
            FAIL,
            f"Không dùng được: {exc}",
            "Chạy lại `uv run python -m upload.auth`. Nếu app OAuth còn ở trạng thái "
            "Testing thì token hết hạn sau 7 ngày — bấm Publish app để hết cảnh này.",
        )

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        response = youtube.channels().list(part="snippet", mine=True).execute()
        items = response.get("items", [])
        if not items:
            return Check(
                "Token YouTube",
                FAIL,
                "Token hợp lệ nhưng tài khoản này chưa có kênh YouTube nào",
                "Đăng nhập đúng tài khoản sở hữu kênh rồi cấp quyền lại",
            )
        return Check("Token YouTube", OK, f"kênh: {items[0]['snippet']['title']}")
    except Exception as exc:
        return Check(
            "Token YouTube",
            FAIL,
            f"Gọi API thất bại: {exc}",
            "Kiểm tra YouTube Data API v3 đã bật trong project chưa",
        )


def check_notification(deep: bool) -> Check:
    """Kiểm tra kênh thông báo đang dùng thật sự gửi được."""
    from notify.dispatch import MACOS, NONE, TELEGRAM, resolve_channel

    channel = resolve_channel()

    if channel == NONE:
        return Check("Thông báo", WARN, "đã tắt (NOTIFY_CHANNEL=none)",
                     "Bỏ NOTIFY_CHANNEL trong .env nếu muốn được báo khi chạy xong")

    if channel == TELEGRAM:
        if not deep:
            return Check("Thông báo", OK, "Telegram (dùng --deep để gửi tin thử)")
        from notify.telegram import TelegramError, send_message

        try:
            send_message("🔧 Preflight check: bot hoạt động bình thường.")
        except TelegramError as exc:
            return Check(
                "Thông báo", FAIL, f"Telegram lỗi: {exc}",
                "Kiểm tra token, và nhớ nhắn cho bot trước ít nhất một tin",
            )
        return Check("Thông báo", OK, "Telegram — đã gửi tin thử thành công")

    # macOS
    if shutil.which("osascript") is None:
        return Check(
            "Thông báo", FAIL, "Không tìm thấy osascript",
            "Máy này không phải macOS — đặt NOTIFY_CHANNEL=telegram hoặc none trong .env",
        )
    if not deep:
        return Check("Thông báo", OK, "macOS (dùng --deep để hiện thử một thông báo)")

    from notify.macos import MacNotifyError, send_notification

    try:
        send_notification("Preflight check", "Thông báo macOS hoạt động bình thường.")
    except MacNotifyError as exc:
        return Check("Thông báo", FAIL, str(exc), "Kiểm tra quyền Thông báo cho Terminal "
                     "trong System Settings → Notifications")
    return Check("Thông báo", OK, "macOS — vừa hiện một thông báo thử")


def check_remotion(root: Path) -> Check:
    node_modules = root / "remotion" / "node_modules"
    if not node_modules.exists():
        return Check(
            "Remotion đã cài",
            FAIL,
            "Thiếu remotion/node_modules",
            "cd remotion && npm install",
        )
    return Check("Remotion đã cài", OK, "node_modules có sẵn")


def check_trend_config(root: Path, deep: bool = False) -> Check:
    import yaml

    path = root / "config" / "trend.yaml"
    if not path.exists():
        return Check("Nguồn bắt trend", FAIL, "Thiếu config/trend.yaml", "Khôi phục file từ git")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return Check("Nguồn bắt trend", FAIL, f"YAML hỏng: {exc}", "Sửa lại cú pháp YAML")

    feeds = data.get("feeds") or []
    channels = data.get("youtube_channels") or []
    if not feeds and not channels and not data.get("use_google_trends"):
        return Check(
            "Nguồn bắt trend", FAIL, "Không bật nguồn nào cả",
            "Thêm ít nhất một mục vào 'feeds' trong config/trend.yaml",
        )

    label = f"{len(feeds)} feed báo"
    if channels:
        label += f", {len(channels)} kênh YouTube"

    if not deep:
        return Check("Nguồn bắt trend", OK, f"{label} (dùng --deep để thử tải thật)")

    from trend.sources import TrendConfig, collect_signals

    signals = collect_signals(TrendConfig.load(path))
    if signals.is_empty:
        return Check(
            "Nguồn bắt trend", FAIL, "Không nguồn nào trả về dữ liệu",
            "; ".join(signals.errors[:2]) or "Kiểm tra kết nối mạng",
        )
    if signals.errors:
        return Check(
            "Nguồn bắt trend", WARN,
            f"{signals.total_items} tín hiệu, nhưng {len(signals.errors)} nguồn lỗi",
            signals.errors[0],
        )
    return Check("Nguồn bắt trend", OK, f"{label} — tải về {signals.total_items} tín hiệu")


def check_voice_config(root: Path) -> Check:
    import yaml

    path = root / "config" / "voice.yaml"
    if not path.exists():
        return Check("Cấu hình giọng đọc", FAIL, "Thiếu config/voice.yaml", "Khôi phục file từ git")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ref_audio = data.get("ref_audio_path")
    if ref_audio:
        ref_path = root / ref_audio
        if not ref_path.exists():
            return Check(
                "Cấu hình giọng đọc",
                FAIL,
                f"voice.yaml trỏ tới file không tồn tại: {ref_audio}",
                "Sửa ref_audio_path, hoặc bỏ nó đi để dùng giọng preset",
            )
        return Check("Cấu hình giọng đọc", OK, f"clone từ {ref_audio}")

    voice = data.get("voice")
    if not voice:
        return Check(
            "Cấu hình giọng đọc",
            FAIL,
            "voice.yaml không có cả 'voice' lẫn 'ref_audio_path'",
            "Đặt một trong hai",
        )
    return Check("Cấu hình giọng đọc", OK, f"giọng preset: {voice}")


def check_disk_space(root: Path) -> Check:
    free_gb = shutil.disk_usage(root).free / (1024**3)
    detail = f"còn trống {free_gb:.0f} GB"
    if free_gb < MIN_FREE_GB:
        return Check(
            "Dung lượng đĩa",
            FAIL,
            detail,
            f"Mỗi tập chiếm ~1.2GB. Dọn bớt output/video cũ — dưới {MIN_FREE_GB}GB "
            "là stage 4 sẽ hỏng giữa chừng.",
        )
    if free_gb < WARN_FREE_GB:
        return Check(
            "Dung lượng đĩa",
            WARN,
            detail,
            "Chạy hằng ngày thì mỗi tháng ngốn ~36GB — nên dọn output/video định kỳ",
        )
    return Check("Dung lượng đĩa", OK, detail)


def check_run_script(root: Path) -> Check:
    path = root / "run_daily.sh"
    if not path.exists():
        return Check("run_daily.sh", FAIL, "Không tìm thấy", "Khôi phục file từ git")
    if not os.access(path, os.X_OK):
        return Check("run_daily.sh", FAIL, "Không có quyền chạy", "chmod +x run_daily.sh")
    return Check("run_daily.sh", OK, "có quyền chạy")


def check_launchd_installed() -> Check:
    plist = Path.home() / "Library" / "LaunchAgents" / "com.lee.audiobook.daily.plist"
    if not plist.exists():
        return Check(
            "Lịch launchd",
            WARN,
            "Chưa cài — hiện chỉ chạy được bằng tay",
            "cp launchd/com.lee.audiobook.daily.plist ~/Library/LaunchAgents/ && "
            "launchctl load ~/Library/LaunchAgents/com.lee.audiobook.daily.plist",
        )
    return Check("Lịch launchd", OK, "đã cài trong ~/Library/LaunchAgents")


def run_all(root: Path, deep: bool = False, upload: bool = False) -> list[Check]:
    """upload=True mới kiểm phần YouTube — mặc định pipeline chỉ dựng video, không đăng."""
    checks = [
        check_env_file(root),
        check_gemini_cookies(),
        check_voice_config(root),
        check_trend_config(root, deep),
        check_remotion(root),
    ]
    if upload:
        checks += [
            check_youtube_client_secret(root),
            check_youtube_token(root, deep),
        ]
    checks += [
        check_notification(deep),
        check_disk_space(root),
        check_run_script(root),
        check_launchd_installed(),
    ]
    return checks


def format_report(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for check in checks:
        lines.append(f"{check.icon} {check.name.ljust(width)}  {check.detail}")
        if check.fix and check.status != OK:
            lines.append(f"   └─ {check.fix}")
    return "\n".join(lines)


def summarize(checks: list[Check]) -> tuple[int, int, int]:
    counts = {OK: 0, WARN: 0, FAIL: 0}
    for check in checks:
        counts[check.status] += 1
    return counts[OK], counts[WARN], counts[FAIL]
