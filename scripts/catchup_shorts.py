"""Đăng 3 short của truyện lên sóng TỐI NAY, công khai, tiêu đề đặt lại cho gọn.

Việc một lần cho ba tối 30/09 - 02/10/2026: năm video dài đã đăng sẵn và hẹn
giờ, nhưng short thì không đăng kèm được vì hạn mức YouTube chỉ 10.000 đơn
vị/ngày (mỗi short 1.600) và short đăng sớm sẽ trỏ vào video còn private.

Chạy bởi launchd/com.lee.audiobook.shorts-catchup.plist lúc 20:05, tức là sau
khi video dài của hôm đó đã tự công khai lúc 20:00. Ngày nào không có trong
bảng thì thoát êm, không làm gì.

Chạy lại được nhiều lần: short đã đăng rồi thì không đăng lại, chỉ bật công
khai và sửa tiêu đề cho đúng.

    uv run python -m scripts.catchup_shorts --dry-run   # xem sẽ làm gì
    uv run python -m scripts.catchup_shorts             # làm thật
"""

from __future__ import annotations

import argparse
import json
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

# Dòng episodes_cli in ra cho mỗi short vừa đăng.
DONG_SHORT = re.compile(r"^Phần (\d+): .*https://youtu\.be/([\w-]+)\s*$", re.M)


class ShortsError(Exception):
    pass


def _state_path(goc: Path) -> Path:
    return goc.with_name(f"{goc.stem}-upload-state.json")


def _ids_tu_state(path: Path) -> list[str]:
    """Id các video đã đăng, theo thứ tự phần 1, 2, 3."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    up = data.get("uploaded", {})
    out = []
    for key in sorted(up, key=lambda k: int(k) if str(k).isdigit() else 0):
        vid = (up[key] or {}).get("video_id")
        if vid:
            out.append(vid)
    return out


def id_video_dai(index: Path) -> str | None:
    """Id video dài của chỉ mục này, đọc từ state của lượt đăng trước."""
    ids = _ids_tu_state(_state_path(index))
    return ids[0] if ids else None


def ids_short_da_dang(prefix: Path) -> list[str]:
    """Id 3 short nếu lượt trước đã đăng rồi. Rỗng nghĩa là chưa đăng."""
    return _ids_tu_state(prefix.with_name(f"{prefix.name}-upload-state.json"))


def _kiem_tra_file(index: Path, prefix: Path) -> list[Path]:
    if not index.exists():
        raise ShortsError(f"Không thấy chỉ mục metadata: {index}")
    parts = sorted(prefix.parent.glob(f"{prefix.name}-part-*.mp4"))
    if not parts:
        raise ShortsError(f"Không thấy short nào với tiền tố {prefix}")
    return parts


def _yt():
    from googleapiclient.discovery import build

    from upload.auth import load_credentials

    return build("youtube", "v3", credentials=load_credentials(), cache_discovery=False)


def trang_thai(yt, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    res = yt.videos().list(part="snippet,status", id=",".join(ids)).execute()
    return {it["id"]: it for it in res.get("items", [])}


def kiem_video_dai_cong_khai(yt, video_id: str) -> None:
    """Chặn đăng short khi video dài chưa công khai.

    Ngày 30/09 lệnh chữa cháy `--date 2026-10-02` bị chạy sớm ba ngày: 3 short
    lên kênh ở chế độ công khai và trỏ vào video còn private tới 02/10 -- người
    xem bấm vào chỉ thấy "Video unavailable", đúng mấy giờ short ăn view mạnh
    nhất. Thà dừng còn hơn đốt cú đẩy đó.
    """
    got = trang_thai(yt, [video_id]).get(video_id)
    if got is None:
        raise ShortsError(f"Không đọc được video dài {video_id} trên YouTube.")
    status = got["status"]
    if status["privacyStatus"] != "public":
        raise ShortsError(
            f"Video dài {video_id} còn {status['privacyStatus']}"
            + (f", hẹn công khai {status['publishAt']}" if status.get("publishAt") else "")
            + ". Short trỏ vào nó sẽ là link chết, nên dừng ở đây. "
            "Chạy lại sau giờ đó, hoặc thêm --force nếu bạn thực sự muốn."
        )


def chuan_hoa_short(yt, story: str, ids: list[str]) -> None:
    """Bật công khai và đặt tiêu đề "<tên truyện> — Trích đoạn N/T".

    Tiêu đề mặc định là câu đầu trích đoạn bị cắt cụt, ví dụ "Bà Sáu nhấp ngụm
    nước trà rồi vỗ đùi cái đét… #Shorts" -- không nói được truyện gì.
    """
    co = trang_thai(yt, ids)
    for n, vid in enumerate(ids, 1):
        got = co.get(vid)
        if got is None:
            print(f"CẢNH BÁO: không đọc được short {vid}, bỏ qua.")
            continue
        snip, status = got["snippet"], got["status"]
        moi = f"{story} — Trích đoạn {n}/{len(ids)}"
        viec = []
        body: dict = {"id": vid}
        parts = []
        if status["privacyStatus"] != "public":
            body["status"] = {**status, "privacyStatus": "public"}
            parts.append("status")
            viec.append("công khai")
        if snip["title"] != moi:
            # snippet.update đòi cả title lẫn categoryId; giữ nguyên mô tả và
            # tag, nhất là link sang video dài nằm trong mô tả.
            body["snippet"] = {
                "title": moi,
                "description": snip.get("description", ""),
                "tags": snip.get("tags", []),
                "categoryId": snip.get("categoryId", "24"),
            }
            parts.append("snippet")
            viec.append("đổi tiêu đề")
        if not parts:
            print(f"{vid}: đã đúng, không sửa gì")
            continue
        yt.videos().update(part=",".join(parts), body=body).execute()
        print(f"{vid}: {' + '.join(viec)} -> {moi}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="In việc sẽ làm rồi thoát, không gọi YouTube")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD, mặc định hôm nay")
    parser.add_argument("--force", action="store_true",
                        help="Đăng short kể cả khi video dài chưa công khai")
    args = parser.parse_args(argv)

    hom_nay = date.fromisoformat(args.date) if args.date else date.today()
    viec = LICH.get(hom_nay)
    if viec is None:
        print(f"{hom_nay}: không có truyện nào trong lịch, không làm gì.")
        return 0

    rel_index, rel_prefix, story = viec
    index, prefix = ROOT / rel_index, ROOT / rel_prefix
    try:
        parts = _kiem_tra_file(index, prefix)
    except ShortsError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 4

    da_co = ids_short_da_dang(prefix)
    print(f"{hom_nay}: {story} — {len(parts)} short"
          + (f" (đã đăng trước đó: {len(da_co)})" if da_co else ""))

    if args.dry_run:
        if da_co:
            print(f"  (thử) short đã có, chỉ bật công khai + sửa tiêu đề: {', '.join(da_co)}")
        else:
            print("  (thử) sẽ kiểm video dài đã công khai chưa, rồi đăng 3 short")
        print(f"  (thử) tiêu đề đích: {story} — Trích đoạn N/{len(parts)}")
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
        # Video dài đã đăng từ trước nên episodes_cli bỏ qua nó, chỉ đăng short.
        ket_qua = subprocess.run(lenh, cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(ket_qua.stdout)
        sys.stderr.write(ket_qua.stderr)
        if ket_qua.returncode != 0:
            print(f"Đăng short THẤT BẠI (mã {ket_qua.returncode}).", file=sys.stderr)
            return ket_qua.returncode
        ids = [v for _, v in sorted(DONG_SHORT.findall(ket_qua.stdout),
                                    key=lambda t: int(t[0]))]
        if not ids:
            ids = ids_short_da_dang(prefix)

    if not ids:
        print("CẢNH BÁO: không xác định được short nào để chuẩn hoá.")
        return 0

    chuan_hoa_short(yt, story, ids)
    print(f"Xong {len(ids)} short cho: {story}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
