"""Sổ thay đổi cấu hình của giám đốc kênh: output/director/thay-doi.log, mỗi dòng một thay đổi (TSV).

    python -m director.changelog --file config/keywords.yaml --reason "thêm hạt giống" --old "" --new "mẹ kế"
Cột: thời điểm ISO (+07:00) \t tệp \t lý do \t giá trị cũ \t giá trị mới (xuống dòng trong giá trị ghi thành \\n).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from director import paths

LOG_NAME = "thay-doi.log"


def _cell(s: str) -> str:
    return str(s).replace("\t", " ").replace("\r", "").replace("\n", "\\n")


def record(file: str, reason: str, old: str, new: str, *, now: datetime | None = None, log: Path | None = None) -> str:
    """Nối một dòng vào sổ và trả về dòng đó (không có ký tự xuống dòng cuối)."""
    now = now or datetime.now(tz=paths.VN)
    log = log or paths.DIRECTOR_DIR / LOG_NAME
    line = "\t".join([now.isoformat(timespec="seconds"), _cell(file), _cell(reason), _cell(old), _cell(new)])
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ghi một thay đổi cấu hình vào sổ của giám đốc kênh.")
    ap.add_argument("--file", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--old", default="")
    ap.add_argument("--new", default="")
    a = ap.parse_args(argv)
    print(record(a.file, a.reason, a.old, a.new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
