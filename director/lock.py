"""Khóa "một video mới mỗi ngày": tệp output/director/<ngày>/da-goi-nha-may.

    python -m director.lock [--date YYYY-MM-DD] [--by X]   tạo khóa (mã 0; đã có thì vẫn 0 nhưng in "đã khóa từ trước")
    python -m director.lock --check [--date YYYY-MM-DD]    mã 0 nếu đang khóa, 3 nếu chưa
Phiên sáng và lượt dự phòng 10:30 cùng dùng khóa này nên không bao giờ có hai lượt dựng trong một ngày.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from director import paths
from director.paths import DIRECTOR_DIR  # noqa: F401  (test monkeypatch lock.DIRECTOR_DIR)

LOCK_NAME = "da-goi-nha-may"


def lock_path(day: date, base: Path | None = None) -> Path:
    base = base or sys.modules[__name__].DIRECTOR_DIR
    return paths.day_dir(day, base) / LOCK_NAME


def is_locked(day: date, base: Path | None = None) -> bool:
    return lock_path(day, base).exists()


def acquire(day: date, base: Path | None = None, by: str | None = None) -> bool:
    """Ghi khóa (nguyên tử: mở với "x"); trả False nếu hôm đó đã có khóa. `by` ghi ai khóa (giam-doc, du-phong)."""
    p = lock_path(day, base)
    try:
        with p.open("x", encoding="utf-8") as f:
            f.write(datetime.now(tz=paths.VN).isoformat(timespec="seconds") + (f" {by}" if by else "") + "\n")
    except FileExistsError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Khóa một video mới mỗi ngày của giám đốc kênh.")
    ap.add_argument("--check", action="store_true", help="chỉ kiểm: mã 0 đang khóa, 3 chưa khóa")
    ap.add_argument("--date", type=date.fromisoformat, default=None)
    ap.add_argument("--by", default=None, help="ai khóa: giam-doc | du-phong")
    a = ap.parse_args(argv)
    day = a.date or paths.today()
    if a.check:
        locked = is_locked(day)
        print(f"{'Đã khóa' if locked else 'Chưa khóa'} ngày {day}: {lock_path(day)}")
        return 0 if locked else 3
    if acquire(day, by=a.by):
        print(f"Đã khóa ngày {day}: {lock_path(day)}")
    else:
        print(f"Đã khóa từ trước ngày {day}: {lock_path(day)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
