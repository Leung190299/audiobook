"""Đăng 3 short của truyện vừa lên sóng tối nay. Chạy hằng đêm lúc 20:05.

Khác scripts/catchup_shorts.py (bảng ba ngày cố định, việc một lần): module này
tự tìm truyện nào lên sóng hôm nay từ output/story_bank_state.json, nên dùng
được mãi về sau mà không phải sửa bảng.

Dây nối truyện -> bộ short: stage 7 đặt tên short theo một dấu thời gian RIÊNG,
khác dấu thời gian của chỉ mục metadata (stage 6) vài phút. Dò theo giờ là tự
rước rủi ro đăng nhầm short của truyện khác, nên run_daily.sh ghi thẳng tiền tố
vào chỉ mục ngay sau stage 7 (`--record`), còn ở đây chỉ việc đọc ra.

    uv run python -m scripts.post_shorts --dry-run
    uv run python -m scripts.post_shorts
    uv run python -m scripts.post_shorts --record <chỉ mục> <tiền tố>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from scripts.catchup_shorts import (
    DONG_SHORT,
    ShortsError,
    _yt,
    chuan_hoa_short,
    id_video_dai,
    ids_short_da_dang,
    kiem_video_dai_cong_khai,
)
from scripts.story_bank import CHANNEL_TZ, DEFAULT_STATE_PATH, get_story

ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = ROOT / "output" / "metadata"


def ghi_shorts_prefix(index: Path, prefix: str) -> None:
    """Ghi tiền tố short vào chỉ mục metadata (gọi từ run_daily.sh sau stage 7)."""
    data = json.loads(index.read_text(encoding="utf-8"))
    data["shorts_prefix"] = prefix
    index.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def truyen_len_song(ngay: date, state_path: Path | None = None) -> int | None:
    """id truyện có published_at rơi đúng ngày đó, theo giờ kênh.

    Không có hoặc có nhiều thì trả None/cái sớm nhất -- thà không làm gì còn hơn
    đăng nhầm short lên kênh.
    """
    # Giải ở đây chứ không gắn làm tham số mặc định: mặc định gắn lúc import thì
    # monkeypatch trong test không ăn, và ngày 01/10 test đã vì thế mà đi quét
    # thư mục thật rồi gọi YouTube thật.
    state_path = state_path or DEFAULT_STATE_PATH
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    hop: list[tuple[str, int]] = []
    for key, value in (state or {}).items():
        raw = (value or {}).get("published_at")
        if not raw:
            continue
        try:
            khi = datetime.fromisoformat(raw).astimezone(CHANNEL_TZ)
        except ValueError:
            continue
        if khi.date() == ngay:
            try:
                hop.append((raw, int(key)))
            except (TypeError, ValueError):
                continue
    if not hop:
        return None
    return min(hop)[1]


def chi_muc_cua_truyen(story_id: int, metadata_dir: Path | None = None) -> Path | None:
    """Chỉ mục *-full.json có story_id khớp; nhiều bản thì lấy bản mới nhất."""
    metadata_dir = metadata_dir or METADATA_DIR
    hop = []
    for p in metadata_dir.glob("*-full.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if int(data.get("story_id") or 0) == story_id:
            hop.append(p)
    if not hop:
        return None
    return max(hop, key=lambda p: p.stat().st_mtime)


def prefix_cua_chi_muc(index: Path) -> Path | None:
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    raw = data.get("shorts_prefix")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, mặc định hôm nay")
    parser.add_argument("--force", action="store_true",
                        help="Đăng kể cả khi video dài chưa công khai")
    parser.add_argument("--record", nargs=2, metavar=("CHI_MUC", "TIEN_TO"),
                        help="Ghi tiền tố short vào chỉ mục rồi thoát")
    args = parser.parse_args(argv)

    if args.record:
        chi_muc, tien_to = args.record
        ghi_shorts_prefix(Path(chi_muc), tien_to)
        print(f"Đã ghi shorts_prefix vào {chi_muc}: {tien_to}")
        return 0

    hom_nay = date.fromisoformat(args.date) if args.date else \
        datetime.now(CHANNEL_TZ).date()

    sid = truyen_len_song(hom_nay)
    if sid is None:
        print(f"{hom_nay}: không có truyện nào lên sóng hôm nay, không làm gì.")
        return 0

    index = chi_muc_cua_truyen(sid)
    if index is None:
        print(f"{hom_nay}: truyện #{sid} lên sóng nhưng không thấy chỉ mục metadata.",
              file=sys.stderr)
        return 4

    prefix = prefix_cua_chi_muc(index)
    if prefix is None:
        print(f"{hom_nay}: chỉ mục {index.name} chưa ghi shorts_prefix "
              "(dựng trước 01/10). Đăng tay bằng --shorts-prefix.", file=sys.stderr)
        return 4

    parts = sorted(prefix.parent.glob(f"{prefix.name}-part-*.mp4"))
    if not parts:
        print(f"{hom_nay}: không thấy short nào với tiền tố {prefix}.", file=sys.stderr)
        return 4

    try:
        story = get_story(sid)
        ten = story.title
    except Exception:
        ten = json.loads(index.read_text(encoding="utf-8")).get("story_title") or f"Truyện #{sid}"

    da_co = ids_short_da_dang(prefix)
    print(f"{hom_nay}: #{sid} {ten} — {len(parts)} short"
          + (f" (đã đăng trước đó: {len(da_co)})" if da_co else ""))

    if args.dry_run:
        print(f"  (thử) chỉ mục: {index}")
        print(f"  (thử) tiền tố: {prefix}")
        print("  (thử) " + ("chỉ bật công khai + sửa tiêu đề"
                            if da_co else "kiểm video dài rồi đăng short"))
        return 0

    try:
        yt = _yt()
        vid_dai = id_video_dai(index)
        if vid_dai and not args.force:
            kiem_video_dai_cong_khai(yt, vid_dai)
        elif vid_dai:
            print(f"--force: bỏ qua kiểm tra video dài {vid_dai}.")
    except ShortsError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 4

    ids = da_co
    if not ids:
        lenh = [
            "uv", "run", "python", "-m", "upload.episodes_cli", str(index),
            "--shorts-prefix", str(prefix), "--privacy", "public",
        ]
        ket_qua = subprocess.run(lenh, cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(ket_qua.stdout)
        sys.stderr.write(ket_qua.stderr)
        if ket_qua.returncode != 0:
            print(f"Đăng short THẤT BẠI (mã {ket_qua.returncode}).", file=sys.stderr)
            return ket_qua.returncode
        ids = [v for _, v in sorted(DONG_SHORT.findall(ket_qua.stdout),
                                    key=lambda t: int(t[0]))] or ids_short_da_dang(prefix)

    if not ids:
        print("CẢNH BÁO: không xác định được short nào để chuẩn hoá.")
        return 0

    chuan_hoa_short(yt, ten, ids)
    print(f"Xong {len(ids)} short cho: {ten}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
