# upload/series_cli.py
"""Stage 7 (theo lô): đăng cả series short lên YouTube, đúng thứ tự phần, có
nhớ trạng thái để chạy nhiều lần qua nhiều ngày mà không đăng trùng.

    uv run python -m upload.series_cli <series_prefix> [--from N] [--limit N] \\
        [--privacy private] [--dry-run]
    # series_prefix vd: output/shorts/vo_doi_tra_trung-20260822T182521Z
    # Phần 1: <tiêu đề> — https://youtu.be/xxx
    # ...
    # Đã đăng N phần trong lượt này. Còn M phần chưa đăng, chạy lại lệnh này
    # vào ngày mai để đăng tiếp.

Lý do có lệnh riêng này thay vì lặp upload/cli.py 32 lần: hạn mức mặc định của
YouTube Data API v3 là 10.000 đơn vị/ngày, mỗi videos.insert tốn 1.600 đơn vị
-- khoảng 6 video mỗi ngày. Một series ~32 phần vì thế phải rải qua nhiều
ngày, và công cụ bắt buộc phải nhớ đã đăng tới đâu trong
`<series_prefix>-upload-state.json`, ghi ngay sau MỖI lần đăng thành công (không
dồn đến cuối lượt) -- mất điện/kill giữa chừng thì lần sau vẫn biết chính xác
đã đăng tới phần nào, không đăng trùng lên kênh thật.

Đây là lệnh chạy tay, KHÔNG nối vào run_daily.sh hay n8n -- một lượt dựng ra
~32 phần nhưng chỉ đăng được ~6, gắn vào job hằng ngày là vô nghĩa.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.errors import HttpError

from shorts.storage import short_thumbnail_path
from upload.auth import YouTubeAuthError, load_credentials
from upload.uploader import upload_video

load_dotenv()

# Hạn mức mặc định YouTube Data API v3: 10.000 đơn vị/ngày, mỗi videos.insert
# tốn 1.600 đơn vị -> tối đa khoảng 6 lượt đăng an toàn trong một ngày trước
# khi có nguy cơ chạm quotaExceeded.
DEFAULT_LIMIT = 6

_PART_NUMBER_RE = re.compile(r"-part-(\d{2})\.(mp4|json)$")


class SeriesUploadError(Exception):
    pass


@dataclass
class SeriesPart:
    number: int
    video_path: Path
    metadata_path: Path
    thumbnail_path: Path


def _state_path(series_prefix: Path) -> Path:
    return series_prefix.parent / f"{series_prefix.name}-upload-state.json"


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"uploaded": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def _save_state(state_path: Path, state: dict) -> None:
    # Ghi trực tiếp, không qua file tạm rồi rename -- state này chỉ đọc/ghi từ
    # một lượt chạy tay duy nhất tại một thời điểm, không có concurrent writer
    # nào cần bảo vệ khỏi việc đọc phải file dở dang.
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_parts(series_prefix: Path) -> list[SeriesPart]:
    """Tìm mọi số phần có `<series_prefix>-part-NN.mp4` VÀ/HOẶC `.json`, sắp
    theo số phần tăng dần -- filesystem/glob không đảm bảo trả về đúng thứ tự
    này. Gộp cả hai đuôi (không chỉ .mp4) để một phần thiếu mất .mp4 (hay
    thiếu .json) vẫn được nhận diện là "phần dở dang" và bị _validate_files()
    báo lỗi, thay vì âm thầm biến mất khỏi danh sách vì không có .mp4 để
    glob() thấy."""
    directory = series_prefix.parent
    prefix_name = series_prefix.name
    numbers: set[int] = set()
    for pattern in (f"{prefix_name}-part-*.mp4", f"{prefix_name}-part-*.json"):
        for path in directory.glob(pattern):
            match = _PART_NUMBER_RE.search(path.name)
            if match:
                numbers.add(int(match.group(1)))

    parts = []
    for number in sorted(numbers):
        stem = f"{prefix_name}-part-{number:02d}"
        parts.append(
            SeriesPart(
                number=number,
                video_path=directory / f"{stem}.mp4",
                metadata_path=directory / f"{stem}.json",
                # Lấy đường dẫn từ chính hàm mà stage 7 dùng để GHI ảnh bìa,
                # chứ không ghi cứng đuôi file ở đây. Ghi cứng ".png" đã hỏng
                # một lần: stage 7 đổi sang JPEG cho lọt trần 2MB của YouTube,
                # chỗ này không đổi theo, và vì thiếu file thì bị bỏ qua trong
                # im lặng nên mọi short đăng lên đều không có ảnh bìa mà không
                # ai báo gì.
                thumbnail_path=short_thumbnail_path(stem, directory),
            )
        )
    return parts


def _select_candidates(
    parts: list[SeriesPart], state: dict, from_n: int, limit: int
) -> list[SeriesPart]:
    uploaded_numbers = {int(n) for n in state.get("uploaded", {})}
    remaining = [p for p in parts if p.number >= from_n and p.number not in uploaded_numbers]
    remaining.sort(key=lambda p: p.number)
    return remaining[:limit]


def _validate_files(candidates: list[SeriesPart]) -> None:
    missing = []
    for part in candidates:
        if not part.video_path.exists():
            missing.append(str(part.video_path))
        if not part.metadata_path.exists():
            missing.append(str(part.metadata_path))
    if missing:
        raise SeriesUploadError(
            "Thiếu file cho các phần sắp đăng, dừng trước khi đăng bất cứ gì: "
            + ", ".join(missing)
        )


def _is_quota_exceeded(exc: HttpError) -> bool:
    if getattr(exc.resp, "status", None) != 403:
        return False
    details = exc.error_details
    if isinstance(details, list):
        return any(isinstance(d, dict) and d.get("reason") == "quotaExceeded" for d in details)
    return False


def run(
    series_prefix: Path,
    *,
    from_n: int = 1,
    limit: int = DEFAULT_LIMIT,
    privacy_status: str = "private",
    dry_run: bool = False,
    category_id: str = "24",
    uploader=upload_video,
    credentials_loader=load_credentials,
) -> None:
    series_prefix = Path(series_prefix)
    state_path = _state_path(series_prefix)
    state = _load_state(state_path)

    all_parts = discover_parts(series_prefix)
    if not all_parts:
        raise SeriesUploadError(
            f"Không tìm thấy phần nào khớp {series_prefix}-part-NN.mp4"
        )

    candidates = _select_candidates(all_parts, state, from_n, limit)

    already_uploaded = len(state.get("uploaded", {}))
    if not candidates:
        print(
            f"Không còn phần nào để đăng trong khoảng đã chọn "
            f"(đã đăng {already_uploaded}/{len(all_parts)} phần của cả series)."
        )
        return

    _validate_files(candidates)

    if dry_run:
        print(f"[dry-run] Sẽ đăng {len(candidates)} phần theo đúng thứ tự này, không gọi API:")
        for part in candidates:
            print(f"[dry-run] Phần {part.number}: {part.video_path.name}")
        return

    credentials = credentials_loader()

    uploaded_this_run = 0
    for part in candidates:
        metadata = json.loads(part.metadata_path.read_text(encoding="utf-8"))
        thumbnail_path = part.thumbnail_path
        if not thumbnail_path.exists():
            # Vẫn đăng, nhưng phải nói ra. Thiếu ảnh bìa trong im lặng là cách
            # lỗi trên tự giấu mình suốt nhiều lượt đăng.
            print(
                f"CẢNH BÁO: phần {part.number} không có ảnh bìa "
                f"{thumbnail_path.name}, đăng không kèm ảnh."
            )
            thumbnail_path = None

        try:
            result = uploader(
                credentials,
                video_path=part.video_path,
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata.get("tags", []),
                category_id=category_id,
                privacy_status=privacy_status,
                thumbnail_path=thumbnail_path,
            )
        except HttpError as exc:
            if _is_quota_exceeded(exc):
                print(
                    f"[series] Hết hạn mức YouTube Data API sau khi đăng "
                    f"{uploaded_this_run} phần trong lượt này (tổng "
                    f"{already_uploaded + uploaded_this_run}/{len(all_parts)} phần). "
                    "Hạn mức không tự hồi trong ngày -- chạy lại lệnh này vào ngày mai "
                    "khi hạn mức reset, không thử lại ngay bây giờ."
                )
                return
            raise SeriesUploadError(
                f"Lỗi khi đăng phần {part.number} ({part.video_path.name}): {exc}. "
                f"Đã đăng {uploaded_this_run} phần trước đó trong lượt này, trạng thái "
                "giữ nguyên trên đĩa, dừng lượt để không đăng lộn thứ tự."
            ) from exc
        except Exception as exc:
            raise SeriesUploadError(
                f"Lỗi khi đăng phần {part.number} ({part.video_path.name}): {exc}. "
                f"Đã đăng {uploaded_this_run} phần trước đó trong lượt này, trạng thái "
                "giữ nguyên trên đĩa, dừng lượt để không đăng lộn thứ tự."
            ) from exc

        # Ghi state ngay sau khi phần này đăng xong -- KHÔNG dồn đến cuối
        # lượt. Chết giữa chừng (mất điện, bị kill) sau dòng này thì phần vừa
        # đăng đã nằm bền trên đĩa, lần chạy sau sẽ tự bỏ qua nó.
        state.setdefault("uploaded", {})[str(part.number)] = {
            "video_id": result.video_id,
            "url": result.url,
            "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        _save_state(state_path, state)
        uploaded_this_run += 1

        print(f"Phần {part.number}: {metadata['title']} — {result.url}")

    total_uploaded = len(state.get("uploaded", {}))
    remaining = len(all_parts) - total_uploaded
    print(f"Đã đăng {uploaded_this_run} phần trong lượt này.")
    if remaining > 0:
        print(
            f"Còn {remaining} phần chưa đăng. Chạy lại lệnh này vào ngày mai để đăng tiếp."
        )
    else:
        print("Đã đăng xong toàn bộ series.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Đăng series short lên YouTube theo lô, đúng thứ tự phần tăng dần, "
            "nhớ trạng thái để chạy lại nhiều ngày mà không đăng trùng."
        )
    )
    parser.add_argument(
        "series_prefix",
        type=Path,
        help=(
            "Phần chung của series, vd output/shorts/vo_doi_tra_trung-20260822T182521Z "
            "-- khớp mọi <prefix>-part-NN.mp4 cùng .json/.jpg đi kèm"
        ),
    )
    parser.add_argument(
        "--from",
        dest="from_n",
        type=int,
        default=1,
        help="Chỉ xét các phần có số >= N (mặc định 1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            f"Đăng tối đa N phần trong lượt này (mặc định {DEFAULT_LIMIT}: hạn mức mặc "
            "định của YouTube Data API v3 là 10.000 đơn vị/ngày, mỗi videos.insert tốn "
            "1.600 đơn vị -- khoảng 6 lượt đăng an toàn mỗi ngày)"
        ),
    )
    parser.add_argument(
        "--privacy",
        default=os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
        choices=["private", "unlisted", "public"],
        help="Mặc định private cho an toàn, giống upload/cli.py -- đăng công khai phải cố ý",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ in ra các phần sẽ được đăng theo thứ tự nào rồi thoát, không gọi API",
    )
    parser.add_argument(
        "--category-id",
        default=os.getenv("YOUTUBE_CATEGORY_ID", "24"),
        help="24 = Entertainment, 22 = People & Blogs, 1 = Film & Animation",
    )
    args = parser.parse_args()

    try:
        run(
            args.series_prefix,
            from_n=args.from_n,
            limit=args.limit,
            privacy_status=args.privacy,
            dry_run=args.dry_run,
            category_id=args.category_id,
        )
    except (SeriesUploadError, YouTubeAuthError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
