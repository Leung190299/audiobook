"""Đường dẫn và ngày làm việc của giám đốc kênh. Mọi thứ ghi vào output/director/<ngày>/ (ngày theo giờ Việt Nam)."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTOR_DIR = ROOT / "output" / "director"
VN = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")
CHANNELS = {
    "main": {"id": "UCeTcL2zuJ1wpeZ1d35onDWA", "name": "Audio Truyện"},
    "xomque": {"id": "UCHGq5frLQ39iR5ZR_VLgf0Q", "name": "Xóm Que Kể Chuyện"},
}


def today(now: datetime | None = None) -> date:
    """Ngày theo giờ Việt Nam của thời điểm `now` (mặc định: bây giờ).
    Biến môi trường DIRECTOR_DAY (director.sh/daily_fallback.sh đặt lúc bắt đầu) thắng: phiên vắt qua nửa đêm giữ nguyên ngày."""
    env_day = os.environ.get("DIRECTOR_DAY")
    if env_day:
        return date.fromisoformat(env_day)
    now = now or datetime.now(tz=VN)
    if now.tzinfo is None:
        now = now.replace(tzinfo=VN)
    return now.astimezone(VN).date()


def day_dir(day: date, base: Path | None = None) -> Path:
    base = base or DIRECTOR_DIR
    d = base / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d
