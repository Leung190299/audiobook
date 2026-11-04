"""Đăng trọn một tập: video dài trước, rồi 5 trích đoạn có link video dài.

    uv run python -m upload.episode_cli <video_mp4> <metadata_json> <thumbnail_png> <series_prefix>
    # Video dài: https://youtu.be/<id>
    # Phần 1: <tiêu đề> — https://youtu.be/<id>
    # ...

Lý do có lệnh riêng: 5 trích đoạn chỉ có ý nghĩa khi mô tả trỏ được về tập
đầy đủ, mà link đó chỉ tồn tại sau khi video dài đăng xong. Hai lệnh rời
(upload.cli rồi series_cli) bắt người vận hành chép link bằng tay mỗi ngày.

--long-video-url <url>: video dài đã đăng rồi (chạy lại sau lỗi giữa chừng)
thì truyền link vào, lệnh bỏ qua bước đăng video dài.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from upload import series_cli
from upload.auth import YouTubeAuthError, load_credentials
from upload.series_cli import SeriesUploadError
from upload.uploader import upload_video

load_dotenv()


def run(
    video_path: Path,
    metadata_path: Path,
    thumbnail_path: Path | None,
    series_prefix: Path,
    *,
    privacy_status: str = "private",
    category_id: str = "24",
    long_video_url: str | None = None,
    uploader=upload_video,
    credentials_loader=load_credentials,
) -> str:
    credentials = credentials_loader()

    if long_video_url is None:
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        result = uploader(
            credentials,
            video_path=Path(video_path),
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata.get("tags", []),
            category_id=category_id,
            privacy_status=privacy_status,
            thumbnail_path=Path(thumbnail_path) if thumbnail_path else None,
        )
        long_video_url = result.url
        print(f"Video dài: {result.url}")
        print(f"Thumbnail: {'đã đặt' if result.thumbnail_set else 'chưa đặt'}")
    else:
        print(f"Video dài (đã có): {long_video_url}")

    # Short nào cũng chỉ là mồi cho một tập, nên đăng hết trong một lượt;
    # limit lớn để không vấp mặc định 6 của series_cli.
    series_cli.run(
        Path(series_prefix),
        limit=99,
        privacy_status=privacy_status,
        category_id=category_id,
        long_video_url=long_video_url,
        uploader=uploader,
        credentials_loader=lambda: credentials,
    )
    return long_video_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Đăng video dài rồi các trích đoạn kèm link về tập dài.")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("metadata_path", type=Path)
    parser.add_argument("thumbnail_path", type=Path)
    parser.add_argument("series_prefix", type=Path, help="vd output/shorts/<slug>-<ts>")
    parser.add_argument("--privacy", default=os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
                        choices=["private", "unlisted", "public"])
    parser.add_argument("--category-id", default=os.getenv("YOUTUBE_CATEGORY_ID", "24"))
    parser.add_argument("--long-video-url", default=None,
                        help="Video dài đã đăng rồi thì đưa link vào để bỏ qua bước đăng nó")
    args = parser.parse_args()
    try:
        run(
            args.video_path, args.metadata_path, args.thumbnail_path, args.series_prefix,
            privacy_status=args.privacy, category_id=args.category_id,
            long_video_url=args.long_video_url,
        )
    except (SeriesUploadError, YouTubeAuthError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
