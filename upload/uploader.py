"""Đăng video lên YouTube qua Data API v3 (resumable upload + set thumbnail)."""

from __future__ import annotations

import http.client
import random
import socket
import ssl
import time
from dataclasses import dataclass
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Giới hạn cứng của YouTube — vượt là API trả 400 và mất công render lại cả lượt.
MAX_TITLE_CHARS = 100
MAX_DESCRIPTION_CHARS = 5000
MAX_TAGS_TOTAL_CHARS = 450  # hạn thật là 500, chừa biên cho ký tự phân tách
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024

# 5MB/chunk: đủ lớn để không quá nhiều round-trip, đủ nhỏ để retry không tốn kém
# với file video ~900MB mà pipeline này thường tạo ra.
CHUNK_SIZE = 5 * 1024 * 1024
MAX_RETRIES = 8
RETRIABLE_STATUS = {500, 502, 503, 504}
RETRIABLE_EXCEPTIONS = (
    http.client.HTTPException,
    socket.error,
    socket.timeout,
    ssl.SSLError,
    ConnectionError,
)


class UploadError(Exception):
    pass


@dataclass
class UploadResult:
    video_id: str
    url: str
    title: str
    privacy_status: str
    thumbnail_set: bool


def _strip_angle_brackets(text: str) -> str:
    """YouTube từ chối '<' và '>' trong title/description."""
    return text.replace("<", "(").replace(">", ")")


def sanitize_title(title: str) -> str:
    clean = _strip_angle_brackets(title.strip().replace("\n", " "))
    return clean[:MAX_TITLE_CHARS]


def sanitize_description(description: str) -> str:
    clean = _strip_angle_brackets(description.strip())
    if len(clean) <= MAX_DESCRIPTION_CHARS:
        return clean
    # Cắt ở ranh giới dòng để không đứt giữa một mốc chương.
    truncated = clean[:MAX_DESCRIPTION_CHARS]
    cut = truncated.rfind("\n")
    return truncated[:cut] if cut > MAX_DESCRIPTION_CHARS // 2 else truncated


def sanitize_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    total = 0
    for tag in tags:
        clean = tag.strip()
        if not clean:
            continue
        if total + len(clean) > MAX_TAGS_TOTAL_CHARS:
            break
        result.append(clean)
        total += len(clean) + 1
    return result


def _execute_resumable(request, on_progress=None) -> dict:
    response = None
    attempt = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status and on_progress:
                on_progress(int(status.progress() * 100))
        except HttpError as exc:
            if exc.resp.status not in RETRIABLE_STATUS:
                raise
            attempt += 1
            _sleep_backoff(attempt, exc)
        except RETRIABLE_EXCEPTIONS as exc:
            attempt += 1
            _sleep_backoff(attempt, exc)

    if "id" not in response:
        raise UploadError(f"Upload xong nhưng phản hồi không có video id: {response}")
    return response


def _sleep_backoff(attempt: int, exc: Exception) -> None:
    if attempt > MAX_RETRIES:
        raise UploadError(f"Upload thất bại sau {MAX_RETRIES} lần thử lại: {exc}") from exc
    delay = min(2**attempt, 60) + random.random()
    print(f"[upload] Lỗi tạm thời ({exc}); thử lại sau {delay:.1f}s "
          f"(lần {attempt}/{MAX_RETRIES})")
    time.sleep(delay)


def upload_video(
    credentials,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "24",
    privacy_status: str = "private",
    thumbnail_path: Path | None = None,
    made_for_kids: bool = False,
    default_language: str = "vi",
) -> UploadResult:
    if not video_path.exists():
        raise UploadError(f"Không tìm thấy file video: {video_path}")

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)

    body = {
        "snippet": {
            "title": sanitize_title(title),
            "description": sanitize_description(description),
            "tags": sanitize_tags(tags),
            "categoryId": str(category_id),
            "defaultLanguage": default_language,
            "defaultAudioLanguage": default_language,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    media = MediaFileUpload(
        str(video_path), chunksize=CHUNK_SIZE, resumable=True, mimetype="video/mp4"
    )
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    print(f"[upload] Bắt đầu tải lên {video_path.name} "
          f"({video_path.stat().st_size / 1024 / 1024:.0f} MB)")
    response = _execute_resumable(
        request, on_progress=lambda pct: print(f"[upload] {pct}%", flush=True)
    )

    video_id = response["id"]
    thumbnail_set = False
    if thumbnail_path is not None:
        thumbnail_set = set_thumbnail(youtube, video_id, thumbnail_path)

    return UploadResult(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title=body["snippet"]["title"],
        privacy_status=response.get("status", {}).get("privacyStatus", privacy_status),
        thumbnail_set=thumbnail_set,
    )


def set_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> bool:
    """Đặt thumbnail. Trả False (không ném lỗi) nếu hỏng — video đã lên rồi,
    hỏng thumbnail thì sửa tay trong Studio, không đáng để fail cả lượt chạy."""
    if not thumbnail_path.exists():
        print(f"[upload] Bỏ qua thumbnail: không tìm thấy {thumbnail_path}")
        return False
    if thumbnail_path.stat().st_size > MAX_THUMBNAIL_BYTES:
        print(f"[upload] Bỏ qua thumbnail: file lớn hơn 2MB ({thumbnail_path})")
        return False

    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png"),
        ).execute()
        return True
    except HttpError as exc:
        # Kênh chưa xác minh số điện thoại thì không có quyền đặt thumbnail tuỳ chỉnh.
        print(f"[upload] Không đặt được thumbnail ({exc}). Đặt tay trong YouTube Studio.")
        return False
