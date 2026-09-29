"""Đăng 3 short của truyện lên sóng TỐI NAY, công khai, tiêu đề đặt lại cho gọn.

Việc một lần cho ba tối 30/09 - 02/10/2026: năm video dài đã đăng sẵn và hẹn
giờ, nhưng short thì không đăng kèm được vì hạn mức YouTube chỉ 10.000 đơn
vị/ngày (mỗi short 1.600) và short đăng sớm sẽ trỏ vào video còn private.

Chạy bởi launchd/com.lee.audiobook.shorts-catchup.plist lúc 20:05, tức là sau
khi video dài của hôm đó đã tự công khai lúc 20:00. Ngày nào không có trong
bảng thì thoát êm, không làm gì.

    uv run python -m scripts.catchup_shorts --dry-run   # xem sẽ làm gì
    uv run python -m scripts.catchup_shorts             # làm thật
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ngày lên sóng -> (chỉ mục metadata, tiền tố short, tên truyện cho tiêu đề).
# Bảng cố định chứ không dò tự động: chỉ mục và tiền tố short mang hai dấu thời
# gian KHÁC nhau (stage 6 và stage 7 chạy cách nhau vài phút), dò theo giờ là
# tự rước rủi ro đăng nhầm short của truyện khác lên kênh.
LICH: dict[date, tuple[str, str, str]] = {
    date(2026, 9, 30): (
        "output/metadata/ho_hang_viet-20260925T031642Z-full.json",
        "output/shorts/ho_hang_viet-20260925T034102Z",
        "Chị Dâu Mỏ Hỗn Nhất Xóm, Cả Nhà Chồng Phải Nể",
    ),
    date(2026, 10, 1): (
        "output/metadata/bo_me_trong_sinh-20260927T023707Z-full.json",
        "output/shorts/bo_me_trong_sinh-20260927T025336Z",
        "Kiếp Trước Trông Cháu Không Công, Kiếp Này Tôi Tính Lương",
    ),
    date(2026, 10, 2): (
        "output/metadata/ho_hang_viet-20260926T023336Z-full.json",
        "output/shorts/ho_hang_viet-20260926T024901Z",
        "Bà Nội 80 Tuổi Mở Nhóm Zalo Bóc Phốt Cả Họ",
    ),
}

# Dòng episodes_cli in ra cho mỗi short đã đăng.
DONG_SHORT = re.compile(r"^Phần (\d+): .*https://youtu\.be/([\w-]+)\s*$", re.M)


def _kiem_tra(index: Path, prefix: Path) -> list[Path]:
    if not index.exists():
        raise SystemExit(f"Không thấy chỉ mục metadata: {index}")
    parts = sorted(prefix.parent.glob(f"{prefix.name}-part-*.mp4"))
    if not parts:
        raise SystemExit(f"Không thấy short nào với tiền tố {prefix}")
    return parts


def dat_lai_tieu_de(story: str, ids: list[str]) -> None:
    """Tiêu đề mặc định là câu đầu trích đoạn bị cắt cụt, ví dụ
    "Bà Sáu nhấp ngụm nước trà rồi vỗ đùi cái đét… #Shorts" -- không nói được
    truyện gì. Đổi sang "<tên truyện> — Trích đoạn N/T"."""
    from googleapiclient.discovery import build

    from upload.auth import load_credentials

    yt = build("youtube", "v3", credentials=load_credentials(), cache_discovery=False)
    res = yt.videos().list(part="snippet", id=",".join(ids)).execute()
    co = {it["id"]: it["snippet"] for it in res.get("items", [])}

    for n, vid in enumerate(ids, 1):
        snip = co.get(vid)
        if snip is None:
            print(f"CẢNH BÁO: không đọc được short {vid}, giữ nguyên tiêu đề.")
            continue
        moi = f"{story} — Trích đoạn {n}/{len(ids)}"
        if snip["title"] == moi:
            continue
        # snippet.update đòi cả title lẫn categoryId; giữ nguyên mô tả và tag,
        # nhất là link sang video dài nằm trong mô tả.
        yt.videos().update(
            part="snippet",
            body={
                "id": vid,
                "snippet": {
                    "title": moi,
                    "description": snip.get("description", ""),
                    "tags": snip.get("tags", []),
                    "categoryId": snip.get("categoryId", "24"),
                },
            },
        ).execute()
        print(f"Đặt lại tiêu đề {vid}: {moi}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="In việc sẽ làm rồi thoát, không gọi YouTube")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, mặc định hôm nay")
    args = parser.parse_args(argv)

    hom_nay = date.fromisoformat(args.date) if args.date else date.today()
    viec = LICH.get(hom_nay)
    if viec is None:
        print(f"{hom_nay}: không có truyện nào trong lịch, không làm gì.")
        return 0

    rel_index, rel_prefix, story = viec
    index, prefix = ROOT / rel_index, ROOT / rel_prefix
    parts = _kiem_tra(index, prefix)

    print(f"{hom_nay}: {story} — {len(parts)} short")
    lenh = [
        "uv", "run", "python", "-m", "upload.episodes_cli", str(index),
        "--shorts-prefix", str(prefix), "--privacy", "public",
    ]
    if args.dry_run:
        print("  (thử) sẽ chạy:", " ".join(lenh))
        print("  (thử) rồi đặt lại tiêu đề 3 short theo mẫu "
              f"{story} — Trích đoạn N/{len(parts)}")
        return 0

    # Video dài đã đăng từ trước nên episodes_cli bỏ qua nó, chỉ đăng short.
    ket_qua = subprocess.run(lenh, cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(ket_qua.stdout)
    sys.stderr.write(ket_qua.stderr)
    if ket_qua.returncode != 0:
        print(f"Đăng short THẤT BẠI (mã {ket_qua.returncode}).", file=sys.stderr)
        return ket_qua.returncode

    ids = [vid for _, vid in sorted(DONG_SHORT.findall(ket_qua.stdout), key=lambda t: int(t[0]))]
    if not ids:
        print("CẢNH BÁO: đăng xong nhưng không đọc được id short nào để đổi tiêu đề.")
        return 0

    dat_lai_tieu_de(story, ids)
    print(f"Xong {len(ids)} short cho: {story}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
