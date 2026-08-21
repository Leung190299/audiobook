"""Stage 7: đăng video lên YouTube.

    uv run python -m upload.cli <video_path> <metadata_json> --thumbnail <png>
    # Đã upload: https://youtu.be/<id>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from upload.auth import load_credentials
from upload.uploader import upload_video

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


def _run(
    video_path: Path,
    metadata_path: Path,
    thumbnail_path: Path | None,
    privacy_status: str,
    category_id: str,
) -> None:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    credentials = load_credentials()
    result = upload_video(
        credentials,
        video_path=video_path,
        title=metadata["title"],
        description=metadata["description"],
        tags=metadata.get("tags", []),
        category_id=category_id,
        privacy_status=privacy_status,
        thumbnail_path=thumbnail_path,
    )

    print(f"Đã upload: {result.url}")
    print(f"Video ID: {result.video_id}")
    print(f"Trạng thái: {result.privacy_status}")
    print(f"Thumbnail: {'đã đặt' if result.thumbnail_set else 'chưa đặt (làm tay)'}")

    if result.privacy_status == "private" and privacy_status != "private":
        print(
            "[upload] YouTube đã ép video về private. Đây là hành vi mặc định với "
            "OAuth project chưa qua audit — vào YouTube Studio đổi sang public bằng "
            "tay, hoặc nộp đơn audit API cho project trên Google Cloud Console."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Đăng video truyện audio lên YouTube.")
    parser.add_argument("video_path", type=Path, help="File .mp4 đã render (sau stage 6)")
    parser.add_argument("metadata_path", type=Path, help="File .json từ metadata.cli")
    parser.add_argument("--thumbnail", type=Path, default=None, help="File .png thumbnail")
    parser.add_argument(
        "--privacy",
        default=os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
        choices=["private", "unlisted", "public"],
        help="Mặc định private cho an toàn; đổi trong .env qua YOUTUBE_PRIVACY_STATUS",
    )
    parser.add_argument(
        "--category-id",
        default=os.getenv("YOUTUBE_CATEGORY_ID", "24"),
        help="24 = Entertainment, 22 = People & Blogs, 1 = Film & Animation",
    )
    args = parser.parse_args()
    _run(
        args.video_path,
        args.metadata_path,
        args.thumbnail,
        args.privacy,
        args.category_id,
    )


if __name__ == "__main__":
    main()
